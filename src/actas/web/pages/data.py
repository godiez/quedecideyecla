import csv
import io

from actas.web import routes
from actas.web.fmt import BODY
from actas.web.pages.decisions import result_label
from actas.web.pages.entities import CLASS_LABEL


class Num(str):
    """Not neutralized: a negative number must stay a number."""


def cell(v) -> str:
    """Anything starting with = + - @ is neutralized so the spreadsheet does not run it."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def number(x: float | None) -> str:
    return Num("" if x is None else f"{x:.2f}".replace(".", ","))


def _csv(rows: list[list]) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    for r in rows:
        w.writerow([c if isinstance(c, Num) else cell(c) for c in r])
    # UTF-8 with BOM and «;»: it opens with a double click in a spreadsheet set to Spanish.
    return "﻿" + out.getvalue()


def money_csv(site) -> str:
    rows = [["Entidad", "Tipo", "Comprometido (€)", "Adjudicado (€)", "Pagado (€)", "Subvención (€)", "Ficha", "Aviso"]]
    for x in site.ranking:
        rows.append([x.name, CLASS_LABEL.get(x.entity_class, x.entity_class), number(x.committed), number(x.awarded),
                     number(x.paid), number(x.grant), routes.entity(x.slug),
                     " ".join(f"{n.title}. {n.text}" for n in x.notes)])
    return _csv(rows)


def decisions_csv(site) -> str:
    rows = [["Fecha", "Órgano", "Punto", "Título", "Tema", "Resultado", "Importe (€)", "Expediente", "Ficha",
             "Acta (PDF)"]]
    for s in site.sessions:
        for d in s.decisions:
            # «Punto 3.1» and not «3.1»: a spreadsheet in Spanish would read 3.1 as the number 31.
            point = f"Punto {d.ref}" if d.ref else ""
            rows.append([s.date.isoformat(), BODY.get(s.body, s.body), point, d.title, d.topic,
                         result_label(d.result), number(d.amount_eur), d.case_file or "",
                         routes.decision(d.slug), d.pdf_url or ""])
    return _csv(rows)


def files(site) -> list[tuple[str, str]]:
    return [(routes.money_csv(site.year), money_csv(site)),
            (routes.decisions_csv(site.year), decisions_csv(site))]
