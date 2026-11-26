from collections import Counter
from itertools import accumulate

from actas.votes import LEGISLATURES, agreements, legislature_of_year, stance
from actas.web import routes
from actas.web.fmt import date_with_year, e, rel, slug
from actas.web.pages.decisions import result_label
from actas.web.template import page, party
from actas.web.texts import section_title

STANCE_LABEL = {"favor": "A favor", "contra": "En contra", "abstencion": "Abstención", "dividido": "Dividido",
                None: "—"}


def legislatures(archive) -> list[str]:
    present = {v.legislature for v in archive.votes} | {legislature_of_year(y) for y in archive.years}
    return [k for k in reversed(LEGISLATURES) if k in present]


def _split_votes(archive, leg: str):
    return sorted((v for v in archive.votes if v.legislature == leg and v.final and not v.unanimous),
                  key=lambda v: (v.when, v.decision_id), reverse=True)


def _agreements(archive, leg: str):
    return agreements([{"final": v.final, "unanimidad": v.unanimous, "votos": v.votes}
                       for v in archive.votes if v.legislature == leg], LEGISLATURES[leg])


def _groups(path: str, leg: str, current: str | None = None) -> str:
    seats = LEGISLATURES[leg]
    items = []
    for g, n in seats.items():
        here = ' aria-current="page"' if g == current else ""
        items.append(f'<li><a href="{e(rel(path, routes.vote_group(leg, g)))}"{here}>'
                     f'<span class="group-name"><span class="visually-hidden">Cómo vota </span>{party(g)}</span>'
                     f'<span class="group-seats">{n} {"concejal" if n == 1 else "concejales"}</span></a></li>')
    return '<ul class="groups parties">' + "".join(items) + "</ul>"


def _seats(leg: str) -> str:
    seats = LEGISLATURES[leg]
    total = sum(seats.values())
    majority = total // 2 + 1
    # The space between groups is a column of its own (1px plus the two gaps): a margin on the first seat
    # would shrink that square. minmax(0, …) lets 21 squares fit on a 320px screen.
    columns = " 1px ".join(f"repeat({n}, minmax(0, 1fr))" for n in seats.values())
    squares = '<span class="group-gap"></span>'.join(f'<span class="seat party-{slug(g)}"></span>' * n
                                                     for g, n in seats.items())
    majority_columns = majority + sum(before < majority for before in list(accumulate(seats.values()))[:-1])
    label = ", ".join(f"{g} {n}" for g, n in seats.items())
    return (f'<figure class="pleno"><figcaption><b>{total} concejales.</b> Para tener mayoría absoluta hacen falta '
            f'{majority}.</figcaption>'
            f'<div class="seats" style="--columns: {columns}; --majority-columns: {majority_columns}" role="img" '
            f'aria-label="Concejales por grupo: {e(label)}">{squares}'
            f'<span class="majority" aria-hidden="true">mayoría: {majority}</span></div></figure>')


def _other_legislatures(path: str, archive, leg: str) -> str:
    others = [k for k in legislatures(archive) if k != leg]
    if not others:
        return ""
    links = " · ".join(f'<a href="{e(rel(path, routes.votes(k)))}">legislatura {k}</a>' for k in others)
    return f'<p class="hint">Otras legislaturas, con otros grupos: {links}.</p>'


def _card(v, d, groups) -> str:
    """The same vote for a phone (CSS shows it under 900px and hides the other cells)."""
    meta = f'<p class="vote-meta">{date_with_year(v.when)} · {e(result_label(d.result))}</p>'
    if len(groups) == 1:
        return f'{meta}<p class="vote-stance">Votó: <b>{STANCE_LABEL[stance(v.votes.get(groups[0]))]}</b></p>'
    by_stance: dict = {}
    for g in groups:
        by_stance.setdefault(stance(v.votes.get(g)), []).append(g)
    lines = "".join(f'<dt>{STANCE_LABEL[k] if k else "Sin dato"}</dt><dd>{" ".join(party(g) for g in by_stance[k])}</dd>'
                    for k in ("favor", "contra", "abstencion", "dividido", None) if k in by_stance)
    return f'{meta}<dl class="vote-groups">{lines}</dl>'


def _row(path: str, archive, v, groups) -> str:
    d = archive.decisions[v.decision_id]
    cells = "".join(f'<td data-label="{e(g)}" class="party-{slug(g)}">{STANCE_LABEL[stance(v.votes.get(g))]}</td>'
                    for g in groups)
    return (f'<tr><td class="vote-item"><a href="{e(rel(path, routes.decision(d.slug)))}">{e(d.title)}</a>'
            f'<div class="vote-card">{_card(v, d, groups)}</div>'
            f'</td><td data-label="Fecha">{date_with_year(v.when)}</td>{cells}'
            f'<td data-label="Resultado">{e(result_label(d.result))}</td></tr>')


def body(archive, leg: str) -> str:
    path = routes.votes(leg)
    seats = LEGISLATURES[leg]
    pairs = "".join(
        f"<tr><td>{party(a)} y {party(b)}</td><td class=\"num\">{i}/{t}</td>"
        f"<td class=\"num\">{round(100 * i / t) if t else 0} %</td></tr>"
        for (a, b), (i, t) in _agreements(archive, leg).items())
    split = _split_votes(archive, leg)
    rows = "".join(_row(path, archive, v, seats) for v in split)
    head = "".join(f"<th>{party(g)}</th>" for g in seats)
    return f"""<h1>Cómo vota cada grupo en el Pleno</h1>
<p class="summary-line">Legislatura {leg}</p>
{_seats(leg)}
{_groups(path, leg)}
{_other_legislatures(path, archive, leg)}
<h2>Cuántas veces votan igual</h2>
<p class="hint">En las {len(split)} votaciones finales que no fueron por unanimidad. Se toma el voto de la mayoría de cada grupo.</p>
<div class="table-scroll"><table><thead><tr><th>Grupos</th><th class="num">Votan igual</th><th class="num">%</th></tr></thead><tbody>
{pairs}</tbody></table></div>
<h2>Votaciones sin unanimidad</h2>
<div class="table-scroll"><table class="votes-table" data-page-size="25"><thead><tr><th>Asunto</th><th>Fecha</th>{head}<th>Resultado</th></tr></thead><tbody>
{rows}</tbody></table></div>"""


def group(archive, leg: str, g: str) -> str:
    path = routes.vote_group(leg, g)
    seats = LEGISLATURES[leg]
    split = _split_votes(archive, leg)
    count = Counter(stance(v.votes.get(g)) for v in split)
    rows = "".join(_row(path, archive, v, [g]) for v in split)
    summary = " · ".join(f"{STANCE_LABEL[k]}: {count.get(k, 0)}" for k in ("favor", "contra", "abstencion"))
    if count.get("dividido"):
        summary += f" · Dividido: {count['dividido']}"
    return f"""<p class="breadcrumb"><a href="{e(rel(path, routes.votes(leg)))}">← Todos los grupos ({leg})</a></p>
<h1>Cómo vota {e(g)} en el Pleno</h1>
<p class="summary-line">Legislatura {leg}</p>
<p class="lede">{e(g)} tiene {seats[g]} de los {sum(seats.values())} concejales. En las {len(split)} votaciones finales que no fueron por unanimidad, su postura mayoritaria fue: {summary}.</p>
{_groups(path, leg, g)}
<div class="table-scroll"><table class="votes-table" data-page-size="25"><thead><tr><th>Asunto</th><th>Fecha</th><th>{party(g)}</th><th>Resultado</th></tr></thead><tbody>
{rows}</tbody></table></div>"""


def _site_for(archive, leg: str):
    years = [y for y in archive.years if legislature_of_year(y) == leg]
    return archive.sites[years[0]] if years else archive.latest


def generate(archive) -> list[tuple[str, str]]:
    out = []
    for leg in legislatures(archive):
        site = _site_for(archive, leg)
        path = routes.votes(leg)
        out.append((path, page(path, section_title("votes", leg), body(archive, leg), site, "votes")))
        for g in LEGISLATURES[leg]:
            path = routes.vote_group(leg, g)
            out.append((path, page(path, f"Cómo vota {g} ({leg})", group(archive, leg, g), site, "votes")))
    return out
