#!/usr/bin/env python3
"""Valida el padrón y genera la lista de votantes para Belenios.

Corre SOLO en tu computador. El padrón con RUT nunca se sube a GitHub
(padron/ está en .gitignore) y el RUT nunca se envía a Belenios.

Uso:
  python padron.py padron/padron.csv               # un voto por depto (por defecto)
  python padron.py padron/padron.csv --ponderado   # ponderado por prorrateo
  Agrega --tipo ordinaria|absoluta|reforzada para calcular los quórums en el reporte.

CSV de entrada (encabezados obligatorios, separador , o ;):
  depto,nombre,rut,email
  - columna "prorrateo" (porcentaje, ej. 0,8523) solo se necesita con --ponderado.
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
    requeridas = {"depto", "nombre", "rut", "email"} | ({"prorrateo"} if ponderado else set())
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
    correos = Counter(f["email"].lower() for f in filas)

    for n, f in enumerate(filas, start=2):
        ref = f"línea {n} (depto {f['depto'] or '?'})"
        if not f["depto"]:
            errores.append(f"{ref}: falta depto")
        elif deptos[f["depto"]] > 1:
            errores.append(f"{ref}: depto repetido; debe haber un solo votante por unidad")
        if not rut_valido(f["rut"]):
            errores.append(f"{ref}: RUT inválido ({f['rut']!r})")
        if not EMAIL.match(f["email"]):
            errores.append(f"{ref}: correo inválido ({f['email']!r})")
        elif correos[f["email"].lower()] > 1:
            avisos.append(f"{ref}: el correo {f['email']} se repite (una persona con varias unidades recibirá varias credenciales)")
        peso = 1
        if ponderado:
            try:
                pct = float(f["prorrateo"].replace(",", "."))
                peso = round(pct * ESCALA)
                if peso <= 0:
                    raise ValueError
            except ValueError:
                errores.append(f"{ref}: prorrateo inválido ({f['prorrateo']!r})")
        if f.get("habilitado", "si").lower() in ("no", "n", "0", "false"):
            excluidos.append(f["depto"])
            continue
        votantes.append((f["email"].lower(), re.sub(r"[^\w\-]", "", f["depto"]), peso))

    if ponderado:
        total_pct = sum(float(f["prorrateo"].replace(",", ".") or 0) for f in filas
                        if re.fullmatch(r"[\d.,]+", f["prorrateo"] or ""))
        if abs(total_pct - 100) > 0.05:
            avisos.append(f"la suma de prorrateos es {total_pct:.4f} % (se esperaba ~100 %)")

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

    peso_total = sum(p for _, _, p in votantes)
    reporte = [
        f"Padrón: {ruta.name}",
        f"Unidades en padrón: {len(filas)}",
        f"Unidades habilitadas: {len(votantes)}",
        f"Excluidas: {len(excluidos)} {('(' + ', '.join(excluidos) + ')') if excluidos else ''}",
        f"Modo: {'ponderado por prorrateo (peso = % x ' + str(ESCALA) + ')' if ponderado else 'un voto por unidad'}",
        f"Peso total habilitado: {peso_total}",
    ]
    total = len(filas) if not ponderado else ESCALA * 100
    unidad = "unidades" if not ponderado else "de peso"
    reporte.append(f"Derechos totales del condominio: {total} {unidad}")
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
