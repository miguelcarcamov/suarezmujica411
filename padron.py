#!/usr/bin/env python3
"""Valida el padrón y genera la lista de votantes para Belenios.

Corre SOLO en tu computador. El padrón con RUT nunca se sube a GitHub
(padron/ está en .gitignore) y el RUT nunca se envía a Belenios.

Uso:
  python padron.py padron/padron.csv               # un voto por depto (por defecto)
  python padron.py padron/padron.csv --ponderado   # ponderado por prorrateo
  Agrega --tipo ordinaria|absoluta|reforzada para calcular los quórums en el reporte.

CSV de entrada (encabezados obligatorios, separador , o ;):
  depto,nombre,email
  - columna "rut" opcional (si viene, se valida; no se envía a Belenios).
  - columna "prorrateo" solo con --ponderado: % (suma ≈ 100) o fracción/alícuota (suma ≈ 1).
  - columna opcional "habilitado" (si/no): "no" excluye la unidad (p. ej. morosos,
    solo si el reglamento lo permite).

Salida:
  padron/belenios_votantes.txt  -> pegar en Belenios (correo,login,peso)
  padron/reporte.txt            -> resumen para el acta
"""
import csv
import re
import sys

import quorum
from collections import Counter
from pathlib import Path

ESCALA = 10_000          # prorrateo 0,8523 % -> peso entero 8523
EMAIL = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


def rut_valido(rut):
    limpio = re.sub(r"[.\-\s]", "", rut).upper()
    if not re.fullmatch(r"\d{7,8}[\dK]", limpio):
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma, factor = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    esperado = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(esperado, str(esperado))
    return dv == esperado


def leer(ruta, ponderado):
    texto = Path(ruta).read_text(encoding="utf-8-sig")
    dialecto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=",;")
    filas = list(csv.DictReader(texto.splitlines(), dialect=dialecto))
    filas = [{(k or "").strip().lower(): (v or "").strip() for k, v in f.items()} for f in filas]
    requeridas = {"depto", "nombre", "email"} | ({"prorrateo"} if ponderado else set())
    faltan = requeridas - set(filas[0] if filas else {})
    if faltan:
        sys.exit(f"Faltan columnas en el CSV: {', '.join(sorted(faltan))}")
    return filas


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ruta = Path(sys.argv[1])
    ponderado = "--ponderado" in sys.argv
    filas = leer(ruta, ponderado)

    errores, avisos, votantes, excluidos = [], [], [], []
    deptos = Counter(f["depto"] for f in filas)
    email_a_deptos = {}
    for f in filas:
        if f.get("habilitado", "si").lower() in ("no", "n", "0", "false"):
            continue
        em = f["email"].lower().strip()
        if em:
            email_a_deptos.setdefault(em, []).append(f["depto"])

    sin_rut = 0
    for n, f in enumerate(filas, start=2):
        ref = f"línea {n} (depto {f['depto'] or '?'})"
        excluido = f.get("habilitado", "si").lower() in ("no", "n", "0", "false")
        if not f["depto"]:
            errores.append(f"{ref}: falta depto")
        elif deptos[f["depto"]] > 1:
            errores.append(f"{ref}: depto repetido; debe haber un solo votante por unidad")
        rut = f.get("rut", "").strip()
        if rut and not rut_valido(rut):
            errores.append(f"{ref}: RUT inválido ({rut!r})")
        elif not rut:
            sin_rut += 1
        if ponderado:
            try:
                pct = float(f["prorrateo"].replace(",", "."))
            except ValueError:
                errores.append(f"{ref}: prorrateo inválido ({f['prorrateo']!r})")
                pct = None
            else:
                f["_pct"] = pct
        if excluido:
            excluidos.append(f["depto"])
            continue
        if not EMAIL.match(f["email"]):
            errores.append(f"{ref}: correo inválido ({f['email']!r})")
            continue
        votantes.append((f["email"].lower(), re.sub(r"[^\w\-]", "", f["depto"]), f if ponderado else 1))
    if sin_rut:
        avisos.append(f"{sin_rut} fila(s) sin RUT (ok para Belenios; útil solo para control interno)")
    repetidos = {e: ds for e, ds in email_a_deptos.items() if len(ds) > 1}
    if repetidos:
        avisos.append(
            f"{len(repetidos)} correo(s) en varias unidades (normal si es el mismo dueño; "
            "Belenios envía una credencial por unidad):"
        )
        for email, ds in sorted(repetidos.items(), key=lambda x: (-len(x[1]), x[0])):
            avisos.append(f"  {email} → {', '.join(ds)}")

    if ponderado:
        # Acepta prorrateo como % (suma ~100) o como fracción/alícuota (suma ~1).
        pcts = [f["_pct"] for f in filas if "_pct" in f]
        total_pct = sum(pcts)
        if abs(total_pct - 1) <= 0.05:
            escala = ESCALA * 100  # 0,004554 -> 4554
            avisos.append(f"prorrateo detectado como fracción (suma {total_pct:.6f}); se convierte a peso × {escala}")
        elif abs(total_pct - 100) <= 0.05:
            escala = ESCALA  # 0,4554 % -> 4554
        else:
            avisos.append(f"la suma de prorrateos es {total_pct:.4f} (se esperaba ~1 o ~100)")
            escala = ESCALA if total_pct > 2 else ESCALA * 100
        convertidos = []
        for email, login, f in votantes:
            if "_pct" not in f:
                continue
            peso = round(f["_pct"] * escala)
            if peso <= 0:
                errores.append(f"depto {f['depto']}: prorrateo {f['prorrateo']!r} da peso 0")
                continue
            convertidos.append((email, login, peso))
        votantes = convertidos

    for a in avisos:
        print("AVISO:", a)
    if errores:
        print(f"\n{len(errores)} error(es). Corrígelos y vuelve a correr:")
        for e in errores:
            print("  -", e)
        sys.exit(1)

    salida = ruta.parent / "belenios_votantes.txt"
    with salida.open("w", encoding="utf-8") as fh:
        for email, login, peso in votantes:
            fh.write(f"{email},{login},{peso}\n" if ponderado else f"{email},{login}\n")

    peso_habilitado = sum(p for _, _, p in votantes)
    if ponderado:
        # Derechos del condominio = suma de pesos de todas las unidades del padrón
        # (incluidas las no habilitadas), no solo de quienes pueden votar.
        pesos_todas = []
        for f in filas:
            if "_pct" not in f:
                continue
            pesos_todas.append(round(f["_pct"] * escala))
        total = sum(pesos_todas)
        unidad = "de peso"
        modo = f"ponderado por prorrateo (× {escala})"
    else:
        total = len(filas)
        unidad = "unidades"
        modo = "un voto por unidad"
    reporte = [
        f"Padrón: {ruta.name}",
        f"Unidades en padrón: {len(filas)}",
        f"Unidades habilitadas: {len(votantes)}",
        f"Excluidas: {len(excluidos)} {('(' + ', '.join(excluidos) + ')') if excluidos else ''}",
        f"Modo: {modo}",
        f"Peso total habilitado: {peso_habilitado}" if ponderado else f"Unidades habilitadas (conteo): {len(votantes)}",
        f"Derechos totales del condominio: {total} {unidad}",
    ]
    tipos = [sys.argv[sys.argv.index("--tipo") + 1]] if "--tipo" in sys.argv else list(quorum.TIPOS)
    for tipo in tipos:
        constituir, aprobar = quorum.umbrales(tipo, total)
        aprob = f"{aprobar} {unidad}" if aprobar else "mayoría absoluta de quienes participan"
        reporte.append(f"[{quorum.TIPOS[tipo]}] constituir: {constituir} {unidad} | aprobar: {aprob}")
    (ruta.parent / "reporte.txt").write_text("\n".join(reporte) + "\n", encoding="utf-8")
    print("\n".join(reporte))
    print(f"\nListo -> {salida}  (pégalo en Belenios: 'Votantes')")


if __name__ == "__main__":
    main()
