import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

STATES = {"aprobado", "corregido", "descartado"}
EDITABLE_FIELDS = {"titulo", "resumen", "categoria", "importe_eur", "resultado", "interes", "entidades",
                    "lugar", "votacion", "hay_particulares", "importes"}
# Same definitions as analisis/INSTRUCCIONES.md: the AI classified with them.
CATEGORY_HELP = {
    "subvencion_concedida": "El Ayuntamiento da dinero: asociaciones, clubes, empresas, ONG, becas, premios, "
                            "convenios con aportación municipal.",
    "subvencion_recibida": "Otra administración (CARM, Estado, UE, Diputación…) da dinero al Ayuntamiento.",
    "contrato": "Adjudicación, prórroga, modificación, revisión de precios o devolución de fianza de un contrato.",
    "pago_factura": "Aprobación de facturas, liquidación de obligaciones, certificaciones de obra.",
    "licencia_obra": "Licencias urbanísticas, declaraciones responsables de obra, primera ocupación.",
    "licencia_actividad": "Licencias de actividad, apertura o ambientales. Construir una nave es licencia_obra; "
                          "aquí va el permiso para que funcione el negocio.",
    "suelo_no_urbanizable": "Autorizaciones excepcionales o de interés público en suelo rústico/no urbanizable.",
    "urbanismo_planeamiento": "Plan general, planes parciales, estudios de detalle, convenios urbanísticos, "
                              "reparcelaciones.",
    "convenio": "Convenios sin dinero municipal (colaboración institucional).",
    "personal": "Plantilla, oposiciones, nombramientos, retribuciones, comisiones de servicio.",
    "fiscal": "Bonificaciones, exenciones y devoluciones de impuestos y tasas, precios públicos, ordenanzas fiscales.",
    "patrimonio": "Compras, ventas, cesiones, donaciones o alquileres de bienes municipales.",
    "via_publica_eventos": "Ocupación de vía pública, terrazas, ferias, fiestas, cortes de calle, uso de "
                           "instalaciones municipales.",
    "presupuesto_hacienda": "Presupuesto, modificaciones de crédito, préstamos, cuenta general, informes de "
                            "morosidad o de Intervención.",
    "normativa": "Ordenanzas y reglamentos no fiscales.",
    "mocion_politica": "Mociones, declaraciones institucionales, ruegos y preguntas, debates políticos.",
    "organizacion": "Aprobación de actas anteriores, delegaciones, comisiones, calendario de sesiones, "
                    "representantes.",
    "informacion": "Comunicaciones «para conocimiento», resoluciones recibidas, dación de cuenta.",
    "reclamaciones": "Responsabilidad patrimonial, recursos, sanciones, sentencias, restauración de la "
                     "legalidad urbanística.",
    "servicios_actividades": "Programas, cursos y servicios que organiza el Ayuntamiento: cultura, deporte, "
                             "escuelas infantiles, juventud, turismo, conciliación, horarios de servicios.",
    "medio_ambiente": "Arbolado, zonas verdes, agua, vertidos, lodos, plagas, permisos de la Confederación "
                      "Hidrográfica del Segura (CHS).",
    "otros": "Nada de lo anterior encaja. Anota en la nota qué es, por si hace falta una categoría nueva.",
}
CATEGORIES = list(CATEGORY_HELP)
INTEREST_HELP = {
    "1": "Rutina: trámites que se repiten cada semana y no cambian nada para el vecino.",
    "2": "Relevante: dinero o permiso concreto que a alguien del pueblo le puede interesar.",
    "3": "Muy relevante: mucho dinero, deuda, polémica o votación dividida, suelo no urbanizable, empresas "
         "conocidas. Candidato a portada.",
}
RESULTS = ["aprobado", "denegado", "desestimado", "informado", "aplazado", "retirado", "otro"]
# A point's id is "<doc>:<position in puntos>"; a vote's, "<doc>:votos:<position in votaciones>". A vote only gets its
# literal quote corrected, for privacy: the site does not show it and the public copy applies it (`public.clean`).
VOTE_ID = re.compile(r"^(?P<doc>[^:]+):votos:(?P<index>\d+)$")
VOTE_EDITABLE_FIELDS = {"texto_acta"}


def _plain(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
    return s.lower()


# «(EXPTES. a, b, c)» at the head of a section lists the case files of every point in it: it does not say where each
# point is. Also the rest of such a list when it goes on in the next page (normalized text).
_CASE_LIST = re.compile(r"\(exptes?\.?\s*\d{5,8}[a-z]?(?:\s*(?:,|\by\b)\s*\d{5,8}[a-z]?)+\s*\)?")
_CASE_RUN = re.compile(r"(?:\d{5,8}[a-z]\s*,\s*){2,}\d{5,8}[a-z]\s*\)?")
_CASE = re.compile(r"\d{6,8}[A-Z]")
_WORD = re.compile(r"[a-zñ]{5,}")


def find_pages(pages: list[str], points: list[dict], already_normalized: bool = False) -> list[int]:
    """The points go in order, so pages never go back: of all the assignments in order, the one with the highest
    total score is taken (ties: the earlier page)."""
    if not pages:
        return [1] * len(points)
    clean = [_CASE_RUN.sub(" ", _CASE_LIST.sub(" ", t if already_normalized else _plain(t))) for t in pages]
    scores = []
    for p in points:
        cases = [c.lower() for c in _CASE.findall(str(p.get("expediente") or ""))]
        words = set(_WORD.findall(_plain(p.get("titulo", ""))))
        scores.append([10 * sum(c in t for c in cases) + sum(w in t for w in words) for t in clean])
    n = len(clean)
    # total[k][i]: best score of points 0..k with point k on page i+1; back[k][i]: page index of point k-1 then
    total, back = [], []
    for k, sc in enumerate(scores):
        row, brow, run, run_i = [], [], None, None
        for i in range(n):
            if k:
                if run is None or total[k - 1][i] > run:
                    run, run_i = total[k - 1][i], i
                row.append(sc[i] + run)
                brow.append(run_i)
            else:
                row.append(sc[i])
                brow.append(None)
        total.append(row)
        back.append(brow)
    out = [1] * len(points)
    i = max(range(n), key=lambda j: (total[-1][j], -j)) if points else 0
    for k in range(len(points) - 1, -1, -1):
        out[k] = i + 1
        if k:
            i = back[k][i]
    return out


def find_page(pages: list[str], point: dict, already_normalized: bool = False) -> int:
    return find_pages(pages, [point], already_normalized)[0]


def is_priority(p: dict) -> bool:
    return bool(p.get("importe_eur") or p.get("importes") or p.get("interes") == 3
                or p.get("categoria") == "suelo_no_urbanizable")


def load_points(analysis: Path) -> list[dict]:
    rc = analysis / "reclasificacion.json"
    reclass = json.loads(rc.read_text(encoding="utf-8")) if rc.exists() else {}
    out = []
    for f in sorted((analysis / "json").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        txt = analysis / "txt" / f"{f.stem}.txt"
        pages = txt.read_text(encoding="utf-8").split("\f") if txt.exists() else []
        where = find_pages(pages, d.get("puntos", []))
        for i, p in enumerate(d.get("puntos", [])):
            if f"{f.stem}:{i}" in reclass:
                p = {**p, "categoria": reclass[f"{f.stem}:{i}"]["categoria"]}
            out.append({**p, "id": f"{f.stem}:{i}", "doc": f.stem, "organo": d.get("organo"),
                        "fecha": d.get("fecha"), "sesion": d.get("sesion"), "priority": is_priority(p),
                        "page": where[i]})
    return out


def load_vote(analysis: Path, vote_id: str) -> dict | None:
    m = VOTE_ID.match(vote_id)
    f = analysis / "votos" / f"{m['doc']}.json" if m else None
    if not f or not f.exists():
        return None
    votes = json.loads(f.read_text(encoding="utf-8")).get("votaciones") or []
    return votes[int(m["index"])] if int(m["index"]) < len(votes) else None


def load_reviews(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_review(path: Path, point_id: str, state: str, changes: dict, note: str,
                original: dict | None = None) -> dict:
    if state not in STATES:
        raise ValueError(f"estado desconocido: {state}")
    vote = VOTE_ID.match(point_id)
    unknown = set(changes) - (VOTE_EDITABLE_FIELDS if vote else EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"campos no editables: {sorted(unknown)}")
    if state == "corregido" and not changes:
        state = "aprobado"
    revs = load_reviews(path)
    previous = revs.get(point_id, {})
    if original is None:
        original = previous.get("original", {})
        if not original and changes and vote:
            v = load_vote(path.parent, point_id)
            if v is None:
                raise ValueError(f"votación desconocida: {point_id}")
            original = {k: v.get(k) for k in changes}
        elif not original and changes:
            for p in load_points(path.parent):
                if p["id"] == point_id:
                    original = {k: p.get(k) for k in changes}
                    break
    rec = {"estado": state, "cambios": changes, "nota": note,
           "original": {k: v for k, v in original.items() if k in changes},
           "cuando": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    revs[point_id] = rec
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".revision-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(revs, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return rec


def apply_reviews(points: list[dict], reviews: dict[str, dict]) -> list[dict]:
    out = []
    for p in points:
        r = reviews.get(p["id"])
        if r and r["estado"] == "descartado":
            continue
        out.append({**p, **(r["cambios"] if r else {}), "revision": r["estado"] if r else "pendiente"})
    return out
