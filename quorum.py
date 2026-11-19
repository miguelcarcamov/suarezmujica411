#!/usr/bin/env python3
"""Quórums de la Ley 21.442 (art. 15) y evaluación de resultados.

Tipos de sesión:
  ordinaria  constitución >= 33 % de los derechos; aprueba la mayoría absoluta de los asistentes
  absoluta   constitución y aprobación > 50 % de los derechos del condominio
  reforzada  constitución y aprobación >= 66 % de los derechos del condominio
Las consultas por escrito exigen los mismos quórums que la sesión equivalente.

"Total" son los derechos del condominio: con un voto por depto, el número total
de unidades; con ponderación, la suma de los pesos.

Evaluar un resultado (después de descifrar en Belenios):
  python quorum.py --tipo absoluta --total 40 --participan 31 --a-favor 24
  (con ponderación, usa pesos en vez de unidades)
"""
import argparse
import math

TIPOS = {
    "ordinaria": "Ordinaria",
    "absoluta": "Extraordinaria de mayoría absoluta",
    "reforzada": "Extraordinaria de mayoría reforzada",
}


def _mayoria(n):
    """Mínimo estrictamente mayor que la mitad."""
    return n // 2 + 1


def _al_menos(pct, n):
    """Mínimo entero que alcanza pct de n (se redondea hacia arriba)."""
    return math.ceil(round(pct * n, 9))


def umbrales(tipo, total):
    """Devuelve (mínimo para constituir, mínimo para aprobar o None si depende de asistentes)."""
    if tipo == "ordinaria":
        return _al_menos(0.33, total), None
    if tipo == "absoluta":
        m = _mayoria(total)
        return m, m
    if tipo == "reforzada":
        m = _al_menos(0.66, total)
        return m, m
    raise ValueError(f"tipo_sesion desconocido: {tipo!r} (usa: {', '.join(TIPOS)})")


def describir(tipo):
    return {
        "ordinaria": ("Participación de al menos el 33 % de los derechos",
                      "Mayoría absoluta de quienes participan"),
        "absoluta": ("Participación de más del 50 % de los derechos",
                     "Más del 50 % de los derechos del condominio"),
        "reforzada": ("Participación de al menos el 66 % de los derechos",
                      "Al menos el 66 % de los derechos del condominio"),
    }[tipo]


def evaluar(tipo, total, participan, a_favor):
    constituir, aprobar = umbrales(tipo, total)
    if aprobar is None:
        aprobar = _mayoria(participan)
    hay_quorum = participan >= constituir
    aprobado = hay_quorum and a_favor >= aprobar
    return {
        "constituir": constituir, "aprobar": aprobar,
        "hay_quorum": hay_quorum, "aprobado": aprobado,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tipo", required=True, choices=TIPOS)
    ap.add_argument("--total", type=int, required=True, help="derechos totales (unidades o suma de pesos)")
    ap.add_argument("--participan", type=int, required=True, help="unidades (o pesos) que votaron")
    ap.add_argument("--a-favor", type=int, required=True, help="votos (o pesos) de la opción evaluada")
    a = ap.parse_args()
    if not 0 <= a.a_favor <= a.participan <= a.total:
        ap.error("debe cumplirse 0 <= a-favor <= participan <= total")
    r = evaluar(a.tipo, a.total, a.participan, a.a_favor)
    print(f"Tipo: {TIPOS[a.tipo]}")
    print(f"Quórum de constitución: {r['constituir']} de {a.total} -> participaron {a.participan}: "
          f"{'CUMPLE' if r['hay_quorum'] else 'NO CUMPLE'}")
    print(f"Quórum de aprobación: {r['aprobar']} -> a favor {a.a_favor}: "
          f"{'CUMPLE' if a.a_favor >= r['aprobar'] else 'NO CUMPLE'}")
    print(f"\nResultado: {'APROBADO' if r['aprobado'] else 'NO APROBADO'}")


if __name__ == "__main__":
    main()
