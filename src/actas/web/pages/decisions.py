import re

from actas import money
from actas.votes import LEGISLATURES
from actas.web import routes
from actas.web.fmt import BODY, MONTHS, TOPICS, date_with_year, e, eur, eur_short, plain, rel
from actas.web.model import is_guarantee, is_income, is_request, role_label
from actas.web.template import mailto, page, party
from actas.web.texts import EMAIL, INFO_PATH, INFO_TITLE, section_title

VISIBLE = 4
RESULT_LABEL = {"aprob": "Aprobado", "deneg": "Denegado", "rechaz": "Rechazado", "desestim": "Desestimado",
                "inform": "Informado", "aplaz": "Aplazado", "retir": "Retirado"}


def result_label(text: str | None) -> str:
    t = (text or "").strip().lower()
    for stem, label in RESULT_LABEL.items():
        if t.startswith(stem):
            return label
    return t.capitalize()


def month_key(s) -> str:
    return f"{s.date.year}-{s.date.month:02d}"


def month_name(key: str) -> str:
    year, m = key.split("-")
    return f"{MONTHS[int(m) - 1]} de {year}"


def session_path(s) -> str:
    return routes.month(month_key(s))


def _item(path: str, d) -> str:
    text = plain(" ".join([d.title, d.summary] + [x["name"] for x in d.entities]))
    line = " · ".join(x for x in (result_label(d.result), amount_label(d, short=True)) if x)
    return (f'<article class="item" data-topic="{e(d.topic)}" data-text="{e(text)}">'
            f'<a href="{e(rel(path, routes.decision(d.slug)))}">{e(d.title)}</a>'
            f'<span class="meta">{e(line)}</span></article>')


def _filters() -> str:
    options = "".join(f'<option value="{e(t)}">{e(t)}</option>' for t in TOPICS)
    # Without JavaScript they do nothing: they start hidden and filters.js shows them.
    return ('<div class="filters" hidden><div class="field"><label for="search">Filtrar estas decisiones</label>'
            '<input type="search" id="search" placeholder="Ej.: castillo, subvención" autocomplete="off"></div>'
            f'<div class="field"><label for="topic">Tema</label><select id="topic"><option value="">Todos los temas'
            f'</option>{options}</select></div>'
            '<div class="field"><label for="body">Reunión</label><select id="body"><option value="">Todas las '
            'reuniones</option><option value="JGL">Junta de Gobierno</option><option value="PLENO">Pleno'
            '</option></select></div><p class="counter" id="counter" aria-live="polite"></p>'
            '<p class="no-results" id="no-results" hidden><button type="button" id="clear">Quitar la búsqueda</button>'
            '</p></div>')


def _folded(path: str, rest) -> str:
    if not rest:
        return ""
    n = len(rest)
    hide = "Ocultar el asunto" if n == 1 else f"Ocultar los {n} asuntos"
    return (f'<details><summary><span class="when-closed">+ {n} {"asunto más" if n == 1 else "asuntos más"} de esta '
            f'reunión</span><span class="when-open">− {hide}</span></summary>'
            f'{"".join(_item(path, d) for d in rest)}'
            f'<button type="button" class="collapse" hidden>↑ {hide}</button></details>')


def _sessions(path: str, sessions) -> list[str]:
    parts = []
    for s in sessions:
        topics = sorted({d.topic for d in s.decisions})
        head = f"{BODY.get(s.body, s.body)} · <em>{date_with_year(s.date)}</em>"
        if s.session_type:
            head += f" · {e(s.session_type)}"
        shown = "".join(_item(path, d) for d in s.decisions[:VISIBLE])
        folded = _folded(path, s.decisions[VISIBLE:])
        parts.append(f'<section class="edition" id="{e(s.doc)}" data-body="{e(s.body)}" '
                     f'data-topics="{e("|".join(topics))}">'
                     f"<h2>{head}</h2>{shown}{folded}</section>")
    return parts


CHEVRON = ('<svg class="chevron" viewBox="0 0 12 8" width="12" height="8" aria-hidden="true">'
           '<path d="M1 1.5 6 6.5 11 1.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>')


def _heading(path: str, year: int, keys: list[str], current: str, h1: str) -> str:
    def link(target: str, text: str, here: bool, cls: str = "") -> str:
        return (f'<li{f" class=\"{cls}\"" if cls else ""}><a href="{e(rel(path, target))}"'
                f'{" aria-current=\"page\"" if here else ""}>{text}</a></li>')
    items = "".join(link(routes.month(k), MONTHS[int(k[5:]) - 1].capitalize(), k == current)
                    for k in sorted(keys))
    items += link(routes.decisions_all(year), f"Todo {year}, con buscador", current == "todas", "whole-year")
    return (f'<div class="month-head"><h1>{e(h1)}</h1><details class="month-picker">'
            f'<summary>Cambiar de mes{CHEVRON}</summary>'
            f'<nav class="month-list" aria-label="Meses de {year}"><ul>{items}</ul></nav></details></div>')


def by_month(site) -> dict[str, list]:
    out: dict[str, list] = {}
    for s in site.sessions:  # already from the most recent to the oldest
        out.setdefault(month_key(s), []).append(s)
    return out


def listing(site, path: str, key: str | None) -> str:
    months = by_month(site)
    keys = list(months)
    current = key or (keys[0] if keys else "")
    if key == "todas":
        sessions = site.sessions
        h1 = "Todo el año"
        lede = (f"Todas las reuniones de la Junta de Gobierno y del Pleno de {site.year}, de la más reciente a la "
                "más antigua. Usa el buscador para encontrar un asunto.")
    else:
        sessions = months.get(current, [])
        h1 = MONTHS[int(current[5:]) - 1].capitalize() if current else "Sin actas todavía"
        lede = ("Cada reunión de la Junta de Gobierno o del Pleno. Primero salen los asuntos con más dinero o más "
                "interés para el vecino, y los trámites de rutina, al final. "
                f'<a href="{e(rel(path, INFO_PATH))}#orden">Cómo se ordenan</a>.')
        if not key:
            lede = "El último mes con actas publicadas. " + lede
    parts = [_heading(path, site.year, keys, current, h1), f'<p class="lede">{lede}</p>', _filters()]
    if key == "todas":
        parts.append('<div class="editions" data-page-size="10">' + "".join(_sessions(path, sessions)) + "</div>")
    else:
        parts += _sessions(path, sessions)
    parts.append(f'<p class="hint"><a href="{e(rel(path, routes.decisions_csv(site.year)))}" download>'
                 f'Descargar todas las decisiones de {site.year} en CSV</a></p>')
    return "\n".join(parts)


def _entity_link(path: str, name: str, slug: str | None) -> str:
    if slug:
        return f'<a href="{e(rel(path, routes.entity(slug)))}">{e(name)}</a>'
    return e(name)


def _split(summary: str) -> tuple[str, str]:
    m = re.search(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡«])", summary or "")
    return (summary[:m.start()], summary[m.end():]) if m else (summary or "", "")


# «Rebaja del 50 % del impuesto de obras…»: its breakdown lists the cost of the works (the tax base), the tax and
# what is saved, all under the company, as if the council gave it that money.
TAX_REBATE = re.compile(r"\b(rebaja|bonificaci[oó]n)\b[^.]*?\d+\s?%", re.I)


def is_tax_rebate(d) -> bool:
    return d.category == "fiscal" and bool(TAX_REBATE.search(d.title))


TICKETS_NOTE = ("Es un ingreso: lo que se recaudó con las entradas vendidas. Las entradas que no se vendieron se "
                "anulan («baja») para cuadrar las cuentas: no es una pérdida. Lo que cuesta el espectáculo se "
                "aprueba en otro acuerdo.")


def amount_label(d, short: bool = False) -> str:
    if not d.amount_eur:
        return ""
    text = eur_short(d.amount_eur) if short else eur(d.amount_eur)
    note = "ingreso" if is_income(d) else "fianza" if is_guarantee(d) else "solicitud" if is_request(d) else ""
    return f"{text} ({note})" if note else text


def _breakdown_mismatch(d) -> str:
    lines = [i["eur"] for i in d.amounts if isinstance(i.get("eur"), (int, float))]
    if not d.amount_eur or not lines or abs(sum(lines) - d.amount_eur) <= 1:
        return ""
    return (f" Las cantidades de la tabla suman {eur(sum(lines))} y el importe de esta decisión es "
            f"{eur(d.amount_eur)}: el desglose recoge también otras cantidades que cita el acuerdo (fianzas, "
            f"entradas no vendidas, la parte que pagan otros…).")


def _breakdown_sum(d) -> str:
    lines = [i["eur"] for i in d.amounts if isinstance(i.get("eur"), (int, float))]
    if not d.amount_eur or len(lines) < 2 or abs(sum(lines) - d.amount_eur) > 1:
        return ""
    return " El importe de esta decisión es la suma de estas cantidades."


def _income_entities(d) -> str:
    if not is_income(d) or not any(i.get("entity") for i in d.amounts):
        return ""
    return " Es dinero que cobra el Ayuntamiento: la entidad de la tabla es quien lo recauda o lo paga, no quien lo recibe."


def _count_cell(n: int) -> str:
    return f'<td class="count{" zero" if not n else ""}">{n}</td>'


def detail(site, d) -> str:
    path = routes.decision(d.slug)
    s = next(x for x in site.sessions if x.doc == d.session_doc)
    body = BODY.get(s.body, s.body)
    when = f"{body} · {date_with_year(s.date)}"
    line = " · ".join(x for x in (result_label(d.result), amount_label(d),
                                  f"{body}, {date_with_year(s.date)}") if x)
    rows = [("Resultado", e(result_label(d.result)) or "—"),
            ("Importe", amount_label(d) or "—"),
            ("Reunión", f'<a href="{e(rel(path, session_path(s)))}#{e(s.doc)}">{when}</a>'),
            ("Tema", e(d.topic)),
            ("Punto del acta", e(d.ref) or "—"),
            ("Expediente", e(d.case_file) or "—")]
    if d.place:
        rows.append(("Lugar", e(d.place)))
    first, rest = _split(d.summary)
    parts = [f'<p class="breadcrumb"><a href="{e(rel(path, session_path(s)))}#{e(s.doc)}">← Decisiones de '
             f'{month_name(month_key(s))}</a></p>',
             f"<h1>{e(d.title)}</h1>", f'<p class="summary-line">{e(line)}</p>',
             f'<p class="lede">{e(first)}</p>']
    if rest:
        parts.append(f"<p>{e(rest)}</p>")
    if money.TICKETS.search(d.title):
        parts.append(f'<p class="hint">{TICKETS_NOTE}</p>')
    for n in d.notes:
        parts.append(f'<aside class="callout"><p><b>{e(n.title)}.</b> {e(n.text)}</p></aside>')
    parts.append('<div class="table-scroll"><table class="facts"><tbody>'
                 + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows) + "</tbody></table></div>")
    if d.amounts and not is_tax_rebate(d):
        lines = "".join(
            f'<tr><td>{_entity_link(path, i["entity"] or "—", i["slug"])}</td><td>{e(i["concept"]) or "—"}</td>'
            f'<td class="num">{eur(i["eur"]) if i["eur"] else "—"}</td></tr>' for i in d.amounts)
        parts.append('<h2>Desglose del dinero</h2><div class="table-scroll"><table><thead><tr><th>Entidad</th>'
                     f'<th>Concepto</th><th class="num">Importe</th></tr></thead><tbody>{lines}</tbody></table>'
                     f'</div><p class="hint">Importes tal como aparecen en el acta.'
                     f'{_income_entities(d) or " Un importe adjudicado no es lo mismo que un importe cobrado."}'
                     f'{_breakdown_sum(d)}{_breakdown_mismatch(d)}</p>')
    if d.entities:
        items = "".join(f"<li>{_entity_link(path, x['name'], x['slug'])}"
                        f"{' — ' + e(role_label(d, x['role'])) if x.get('role') else ''}</li>" for x in d.entities)
        parts.append(f'<h2>Quién aparece</h2><ul class="entities">{items}</ul>')
    if d.vote:
        v = d.vote
        vote_rows = "".join(
            f"<tr><th>{party(g)}</th>" + "".join(_count_cell(v.votes.get(g, {}).get(k, 0))
                                          for k in ("favor", "contra", "abstencion")) + "</tr>"
            for g in LEGISLATURES[v.legislature])
        parts.append('<h2>Cómo se votó en el Pleno</h2><div class="table-scroll"><table><thead><tr><th>Grupo</th>'
                     '<th class="count">A favor</th><th class="count">En contra</th><th class="count">Abstención</th>'
                     f'</tr></thead><tbody>{vote_rows}</tbody></table></div>'
                     + ('<p>Por unanimidad.</p>' if v.unanimous else ""))
    if d.pdf_url:
        parts.append(f'<a class="button" href="{e(d.pdf_url)}" target="_blank" rel="noopener">Ver el acta oficial '
                     f'(PDF), página {d.page} (aproximada)<span class="visually-hidden"> (se abre en otra pestaña)</span></a>')
    else:
        parts.append('<p class="button unavailable">Enlace al acta no disponible</p>')
    parts.append(f'<p class="review-mark">Resumen automático, sin revisar por una persona. '
                 f'<a href="{e(rel(path, INFO_PATH))}#proceso">{INFO_TITLE}</a></p>')
    parts.append(f'<p class="note">¿Ves un error en esta ficha? Escríbenos a '
                 f'<a href="{e(mailto(f"Error en {d.slug}"))}">{EMAIL}</a></p>')
    return "\n".join(parts)


def generate(site) -> list[tuple[str, str]]:
    first, whole = routes.decisions(site.year), routes.decisions_all(site.year)
    out = [(first, page(first, section_title("decisions", site.year), listing(site, first, None), site, "decisions")),
           (whole, page(whole, f"Todas las decisiones de {site.year}", listing(site, whole, "todas"), site,
                        "decisions"))]
    for k in by_month(site):
        path = routes.month(k)
        out.append((path, page(path, section_title("decisions", month_name(k)), listing(site, path, k), site,
                               "decisions")))
    for s in site.sessions:
        for d in s.decisions:
            path = routes.decision(d.slug)
            out.append((path, page(path, f"{d.title} ({date_with_year(s.date)})", detail(site, d), site, "decisions")))
    return out
