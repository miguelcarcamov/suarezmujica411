#!/usr/bin/env python3
"""Arma padron/padron.csv desde los Excel de datos_info/ (solo en tu computador).

Una fila por unidad. El correo es el del Dueño (si hay varios dueños con correo,
se usa el primero del listado y se deja aviso). No se pone el correo del
arrendatario automáticamente: hace falta poder del propietario.

Correos repetidos entre unidades distintas NO son error: un mismo dueño de
varios deptos recibe una credencial Belenios por unidad (cada una con su peso).

Uso:
  python padron_desde_excel.py
  python padron_desde_excel.py --y-validar --ponderado --tipo reforzada

Por defecto lee:
  datos_info/Listado de Residentes.xlsx
  datos_info/Unidades Morosas.xlsx
y escribe:
  padron/padron.csv
  padron/avisos_desde_excel.txt
  padron/pendientes_correo.csv   (habilitadas sin correo de dueño)
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("Falta openpyxl. Instala con: pip install openpyxl")

ROOT = Path(__file__).resolve().parent
EMAIL_OK = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


def _unidad(valor) -> str | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    if isinstance(valor, int):
        return str(valor)
    texto = str(valor).strip()
    if not texto or texto.lower() == "total":
        return None
    if texto.isdigit():
        return str(int(texto))
    return texto


def _prorrateo_str(valor) -> str:
    if valor is None or valor == "":
        return ""
    n = float(valor)
    return f"{n:.10f}".rstrip("0").rstrip(".")


def leer_residentes(ruta: Path) -> dict[str, list[dict]]:
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        filas = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    hdr = None
    for i, fila in enumerate(filas):
        celdas = [str(c).strip() if c is not None else "" for c in (fila or ())]
        if "Unidad" in celdas and "Prorrateo" in celdas:
            hdr = i
            idx = {nombre: celdas.index(nombre) for nombre in ("Unidad", "Prorrateo", "Nombre y apellido", "Rol", "Correo")}
            break
    if hdr is None:
        sys.exit(f"No encontré la fila de encabezados en {ruta}")

    por_unidad: dict[str, list[dict]] = defaultdict(list)
    for fila in filas[hdr + 1 :]:
        if not fila:
            continue
        unidad = _unidad(fila[idx["Unidad"]] if idx["Unidad"] < len(fila) else None)
        if not unidad:
            continue
        nombre = (fila[idx["Nombre y apellido"]] or "").strip() if idx["Nombre y apellido"] < len(fila) else ""
        rol = (fila[idx["Rol"]] or "").strip() if idx["Rol"] < len(fila) else ""
        correo_raw = fila[idx["Correo"]] if idx["Correo"] < len(fila) else ""
        correo = (correo_raw or "").strip().lower()
        prorrateo = fila[idx["Prorrateo"]] if idx["Prorrateo"] < len(fila) else None
        por_unidad[unidad].append(
            {"nombre": nombre, "rol": rol, "email": correo, "prorrateo": prorrateo}
        )
    return dict(por_unidad)


def leer_morosas(ruta: Path) -> set[str]:
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        started = False
        morosas: set[str] = set()
        for fila in ws.iter_rows(values_only=True):
            if not fila:
                continue
            if fila[1] == "Unidad":
                started = True
                continue
            if not started:
                continue
            unidad = _unidad(fila[1])
            if unidad:
                morosas.add(unidad)
    finally:
        wb.close()
    return morosas


def elegir_votante(personas: list[dict]) -> tuple[dict, str, list[str]]:
    """Devuelve (persona_elegida, origen, avisos_de_esta_unidad)."""
    avisos: list[str] = []
    dueños = [p for p in personas if p["rol"] == "Dueño"]
    dueños_con_mail = [p for p in dueños if p["email"] and EMAIL_OK.match(p["email"])]

    if len(dueños) > 1:
        avisos.append(
            f"{len(dueños)} dueños en el listado"
            + (
                f"; se usa el correo de {dueños_con_mail[0]['nombre']}"
                if dueños_con_mail
                else "; ninguno con correo válido"
            )
        )

    if dueños_con_mail:
        return dueños_con_mail[0], "dueño", avisos

    if dueños:
        elegido = dict(dueños[0])
        elegido["email"] = ""
        arr = [p for p in personas if p["rol"] == "Arrendatario" and p["email"]]
        if arr:
            avisos.append(
                "dueño sin correo; hay arrendatario con mail "
                f"({arr[0]['email']}) — completar dueño o poder antes de Belenios"
            )
        else:
            avisos.append("dueño sin correo y sin arrendatario con mail")
        return elegido, "dueño_sin_correo", avisos

    con_mail = [p for p in personas if p["email"] and EMAIL_OK.match(p["email"])]
    prorrateo = next((p["prorrateo"] for p in personas if p["prorrateo"] is not None), None)
    if con_mail:
        # No autoasignar: el voto es del propietario.
        base = {
            "nombre": "(sin dueño en listado)",
            "rol": "",
            "email": "",
            "prorrateo": prorrateo,
        }
        avisos.append(
            f"sin fila Dueño; hay {con_mail[0]['rol']} con mail "
            f"({con_mail[0]['email']}) — el comité debe fijar el correo del propietario"
        )
        return base, "sin_dueño", avisos

    vacío = {
        "nombre": "(sin dueño en listado)",
        "rol": "",
        "email": "",
        "prorrateo": prorrateo,
    }
    avisos.append("sin dueño ni correo utilizable")
    return vacío, "sin_correo", avisos


def orden_unidad(u: str) -> tuple:
    return (0, int(u)) if u.isdigit() else (1, u)


def construir(
    residentes: dict[str, list[dict]], morosas: set[str]
) -> tuple[list[dict], list[str]]:
    filas: list[dict] = []
    avisos: list[str] = []
    email_a_deptos: dict[str, list[str]] = defaultdict(list)

    for unidad in sorted(residentes.keys(), key=orden_unidad):
        personas = residentes[unidad]
        prorrateos = {
            round(float(p["prorrateo"]), 10)
            for p in personas
            if p["prorrateo"] is not None and p["prorrateo"] != ""
        }
        if len(prorrateos) > 1:
            avisos.append(f"depto {unidad}: prorrateos distintos en el Excel {sorted(prorrateos)}")
        prorrateo = next((p["prorrateo"] for p in personas if p["prorrateo"] is not None), None)

        persona, origen, avisos_u = elegir_votante(personas)
        for a in avisos_u:
            avisos.append(f"depto {unidad}: {a}")

        email = (persona.get("email") or "").strip().lower()
        if email:
            email_a_deptos[email].append(unidad)

        filas.append(
            {
                "depto": unidad,
                "nombre": persona.get("nombre") or "",
                "rut": "",
                "email": email,
                "prorrateo": _prorrateo_str(prorrateo),
                "habilitado": "no" if unidad in morosas else "si",
                "origen_correo": origen,
            }
        )

    for email, deptos in sorted(email_a_deptos.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(deptos) > 1:
            avisos.append(
                f"correo {email} en {len(deptos)} unidades ({', '.join(deptos)}): "
                "es normal si es el mismo dueño; Belenios envía una credencial por unidad"
            )

    huérfanas = sorted(morosas - set(residentes), key=orden_unidad)
    for u in huérfanas:
        avisos.append(f"morosa {u}: aparece en morosos pero no en residentes (omitida)")

    return filas, avisos


def escribir_csv(ruta: Path, filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    campos = ["depto", "nombre", "rut", "email", "prorrateo", "habilitado"]
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for f in filas:
            w.writerow({k: f.get(k, "") for k in campos})


def escribir_pendientes(
    ruta: Path, filas: list[dict], residentes: dict[str, list[dict]]
) -> int:
    """Unidades habilitadas sin correo de dueño, con sugerencia del Excel."""
    pendientes = []
    for f in filas:
        if f["email"] or f["habilitado"] != "si":
            continue
        personas = residentes.get(f["depto"], [])
        arr = [
            p
            for p in personas
            if p["rol"] == "Arrendatario" and p["email"] and EMAIL_OK.match(p["email"])
        ]
        sugerencia = "; ".join(f"{p['nombre']} <{p['email']}>" for p in arr[:3])
        pendientes.append(
            {
                "depto": f["depto"],
                "nombre_dueño": f["nombre"],
                "motivo": f.get("origen_correo", ""),
                "sugerencia_arrendatario": sugerencia,
            }
        )
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["depto", "nombre_dueño", "motivo", "sugerencia_arrendatario"],
        )
        w.writeheader()
        w.writerows(pendientes)
    return len(pendientes)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--residentes",
        type=Path,
        default=ROOT / "datos_info" / "Listado de Residentes.xlsx",
        help="Excel de residentes / copropietarios",
    )
    p.add_argument(
        "--morosas",
        type=Path,
        default=ROOT / "datos_info" / "Unidades Morosas.xlsx",
        help="Excel de unidades morosas",
    )
    p.add_argument(
        "--salida",
        type=Path,
        default=ROOT / "padron" / "padron.csv",
        help="CSV de padrón (local, no se sube a Git)",
    )
    p.add_argument(
        "--y-validar",
        action="store_true",
        help="Después de escribir el CSV, corre padron.py",
    )
    p.add_argument("--ponderado", action="store_true", help="Pasa --ponderado a padron.py")
    p.add_argument("--tipo", default="", help="Pasa --tipo a padron.py (ej. reforzada)")
    args = p.parse_args()

    if not args.residentes.is_file():
        sys.exit(f"No está el Excel de residentes: {args.residentes}")
    if not args.morosas.is_file():
        sys.exit(f"No está el Excel de morosas: {args.morosas}")

    residentes = leer_residentes(args.residentes)
    morosas = leer_morosas(args.morosas)
    filas, avisos = construir(residentes, morosas)
    escribir_csv(args.salida, filas)

    reporte_avisos = args.salida.parent / "avisos_desde_excel.txt"
    pendientes_path = args.salida.parent / "pendientes_correo.csv"
    n_pend = escribir_pendientes(pendientes_path, filas, residentes)
    resumen = [
        f"Unidades: {len(filas)}",
        f"Habilitadas: {sum(1 for f in filas if f['habilitado'] == 'si')}",
        f"Morosas (habilitado=no): {sum(1 for f in filas if f['habilitado'] == 'no')}",
        f"Sin correo (todas): {sum(1 for f in filas if not f['email'])}",
        f"Habilitadas sin correo (bloquean Belenios): {n_pend}",
        f"Suma prorrateo: {sum(float(f['prorrateo']) for f in filas if f['prorrateo']):.6f}",
        "",
        "Avisos:",
        *([f"- {a}" for a in avisos] if avisos else ["- (ninguno)"]),
    ]
    reporte_avisos.write_text("\n".join(resumen) + "\n", encoding="utf-8")

    print(f"OK -> {args.salida}", flush=True)
    print(f"Avisos -> {reporte_avisos} ({len(avisos)})", flush=True)
    if n_pend:
        print(
            f"Pendiente -> {pendientes_path} ({n_pend} habilitadas sin correo de dueño)",
            flush=True,
        )
    else:
        print(f"Pendientes de correo: ninguna ({pendientes_path} vacío de filas)", flush=True)

    if args.y_validar:
        cmd = [sys.executable, str(ROOT / "padron.py"), str(args.salida)]
        if args.ponderado:
            cmd.append("--ponderado")
        if args.tipo:
            cmd.extend(["--tipo", args.tipo])
        print("\n→", " ".join(cmd), flush=True)
        raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
