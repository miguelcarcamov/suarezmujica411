#!/usr/bin/env python3
"""Genera el sitio estático de votaciones en _site/.

Uso:  python build.py            (genera _site/)
      python build.py --check    (solo valida los YAML)
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import yaml

import quorum
from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "_site"
FMT = "%Y-%m-%d %H:%M"
OBLIGATORIOS = ["titulo", "preguntas", "tipo_sesion"]


def fecha(valor, tz, campo, archivo):
    try:
        return datetime.strptime(str(valor), FMT).replace(tzinfo=tz)
    except ValueError:
        sys.exit(f"[{archivo}] '{campo}' debe tener formato AAAA-MM-DD HH:MM (vino: {valor!r})")


def cargar_eleccion(ruta, tz, cfg):
    d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    d["borrador"] = bool(d.get("borrador"))
    requeridos = list(OBLIGATORIOS)
    if not d["borrador"]:
        requeridos += ["apertura", "cierre"]
    faltan = [c for c in requeridos if not d.get(c)]
    if faltan:
        sys.exit(f"[{ruta.name}] faltan campos: {', '.join(faltan)}")
    d["slug"] = ruta.stem
    for campo in ("apertura", "cierre", "sesion_informativa", "plazo_poder"):
        if d.get(campo):
            d[campo] = fecha(d[campo], tz, campo, ruta.name)
    if d.get("apertura") and d.get("cierre") and d["cierre"] <= d["apertura"]:
        sys.exit(f"[{ruta.name}] el cierre debe ser posterior a la apertura")
    for i, p in enumerate(d["preguntas"], 1):
        if not p.get("pregunta") or len(p.get("opciones") or []) < 2:
            sys.exit(f"[{ruta.name}] la pregunta {i} necesita texto y al menos 2 opciones")
    tipo = d["tipo_sesion"]
    if tipo not in quorum.TIPOS:
        sys.exit(f"[{ruta.name}] tipo_sesion debe ser uno de: {', '.join(quorum.TIPOS)}")
    d["tipo_nombre"] = quorum.TIPOS[tipo]
    d["req_constituir"], d["req_aprobar"] = quorum.describir(tipo)
    total = cfg.get("total_unidades")
    d["num_constituir"] = d["num_aprobar"] = None
    if total and not d.get("ponderada"):
        d["num_constituir"], d["num_aprobar"] = quorum.umbrales(tipo, int(total))
        d["total_unidades"] = int(total)
    d["antecedentes_html"] = markdown.markdown(d.get("antecedentes") or "")
    d["documentos"] = [doc for doc in d.get("documentos") or [] if doc.get("url")]
    d["pendientes"] = [str(p).strip() for p in (d.get("pendientes") or []) if str(p).strip()]
    roles = d.get("roles") or {}
    admin = roles.get("administrador") or {}
    cred = roles.get("credenciales") or {}
    trustees = []
    for t in roles.get("trustees") or []:
        if isinstance(t, dict):
            trustees.append({
                "nombre": (t.get("nombre") or "").strip(),
                "detalle": (t.get("detalle") or "").strip(),
            })
    d["roles"] = {
        "administrador": {
            "nombre": (admin.get("nombre") or "").strip(),
            "detalle": (admin.get("detalle") or "").strip(),
        },
        "credenciales": {
            "nombre": (cred.get("nombre") or "").strip(),
            "detalle": (cred.get("detalle") or "").strip(),
        },
        "trustees": trustees,
        "trustees_umbral": int(roles["trustees_umbral"]) if roles.get("trustees_umbral") else (
            max(1, (len(trustees) + 1) // 2) if trustees else 0
        ),
    }
    d["roles_publicados"] = bool(
        d["roles"]["administrador"]["nombre"]
        or d["roles"]["credenciales"]["nombre"]
        or any(t["nombre"] for t in d["roles"]["trustees"])
    )
    if d["borrador"]:
        d["estado"] = "borrador"
    else:
        ahora = datetime.now(tz)
        d["estado"] = ("proxima" if ahora < d["apertura"]
                       else "abierta" if ahora < d["cierre"] else "cerrada")
    return d


def main():
    cfg = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg.get("zona_horaria", "America/Santiago"))
    elecciones = [cargar_eleccion(p, tz, cfg) for p in sorted((RAIZ / "elecciones").glob("*.y*ml"))]
    sin_fecha = datetime.min.replace(tzinfo=tz)
    elecciones.sort(key=lambda e: (bool(e.get("borrador")), e.get("apertura") or sin_fecha), reverse=True)
    print(f"OK: {len(elecciones)} votación(es) válidas")
    for e in elecciones:
        if e["estado"] not in ("cerrada", "borrador") and not e.get("url_belenios"):
            print(f"  aviso: '{e['slug']}' aún no tiene url_belenios")
    if "--check" in sys.argv:
        return

    env = Environment(loader=FileSystemLoader(RAIZ / "templates"),
                      autoescape=select_autoescape(["html"]))
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    env.filters["fecha"] = lambda d: f"{d.day} de {meses[d.month - 1]} de {d.year}, {d:%H:%M} h"
    env.filters["iso"] = lambda d: d.isoformat()

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "v").mkdir(parents=True)
    shutil.copytree(RAIZ / "static", SALIDA / "static")
    (SALIDA / ".nojekyll").touch()

    ctx = {"cfg": cfg, "generado": datetime.now(tz)}
    (SALIDA / "index.html").write_text(
        env.get_template("index.html").render(elecciones=elecciones, raiz=".", **ctx), encoding="utf-8")
    for e in elecciones:
        destino = SALIDA / "v" / e["slug"]
        destino.mkdir()
        (destino / "index.html").write_text(
            env.get_template("eleccion.html").render(e=e, raiz="../..", **ctx), encoding="utf-8")
    print(f"Sitio generado en {SALIDA}")


if __name__ == "__main__":
    main()
