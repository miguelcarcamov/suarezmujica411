#!/usr/bin/env python3
"""Genera versiones públicas de los convenios VUELTA (sin RUT/CI/teléfonos).

Lee los PDF originales en datos_info/ (gitignored) y escribe static/docs/.

Uso (desde la raíz del repo):
  .venv/bin/python scripts/generar_pdfs_publicos.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer
except ImportError:
    sys.exit("Falta reportlab. Crea el venv: python3 -m venv .venv && .venv/bin/pip install reportlab")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "docs"

RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b")
CI_FRASE = re.compile(
    r",?\s*cédula nacional de identidad número\s+\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]",
    re.I,
)
RUT_FRASE = re.compile(
    r",?\s*rol único tributario número\s+\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]",
    re.I,
)
TEL_LINE = re.compile(r"(?im)^(\s*Teléfono:\s*).+$")

AVISO = (
    "Versión pública para la consulta a copropietarios. "
    "Se omitieron RUT, cédulas de identidad y teléfonos de personas naturales. "
    "El texto operativo y los términos económicos se mantienen para transparencia del voto. "
    "El original queda en poder del comité."
)


def scrub(texto: str) -> str:
    t = CI_FRASE.sub("", texto)
    t = RUT_FRASE.sub(" (RUT omitido en versión pública)", t)
    t = RUT.sub("[RUT omitido]", t)
    t = TEL_LINE.sub(r"\1[omitido en versión pública]", t)
    t = re.sub(r"(?m)^\s*\[RUT omitido\]\s*$", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


def pdf_desde_txt(src_pdf: Path, dest: Path, titulo: str) -> None:
    raw = subprocess.check_output(["pdftotext", "-layout", str(src_pdf), "-"], text=True)
    cuerpo = scrub(raw.replace("\x0c", "\n\n"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest),
        pagesize=letter,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=titulo,
        author="Comunidad Suárez Mújica 411",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="Aviso", parent=styles["Normal"], fontSize=9, leading=12, textColor="#444")
    )
    styles.add(
        ParagraphStyle(
            name="TituloDoc",
            parent=styles["Heading1"],
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(name="Cuerpo", parent=styles["Code"], fontName="Courier", fontSize=7.5, leading=9.2)
    )
    doc.build(
        [
            Paragraph(titulo, styles["TituloDoc"]),
            Paragraph(AVISO, styles["Aviso"]),
            Spacer(1, 0.4 * cm),
            Preformatted(cuerpo, styles["Cuerpo"]),
        ]
    )
    print(f"OK -> {dest}")


def main() -> None:
    pares = [
        (
            ROOT / "datos_info/Convenio_VUELTA_CAFE_-_Jardines_de_Suarez_Mujica.pdf",
            OUT / "convenio-vuelta-cafe.pdf",
            "Convenio máquina de café Nescafé (VUELTA CAFÉ / Rosetta SpA), versión pública",
        ),
        (
            ROOT / "datos_info/Convenio_VUELTA_Bebidas_-_Jardines_de_Suarez_Mujica.pdf",
            OUT / "convenio-vuelta-bebidas.pdf",
            "Convenio VUELTA / Amawa: agua y bebidas (Rosetta SpA), versión pública",
        ),
    ]
    for src, dest, titulo in pares:
        if not src.is_file():
            sys.exit(f"No está el original: {src}")
        pdf_desde_txt(src, dest, titulo)


if __name__ == "__main__":
    main()
