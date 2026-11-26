import json

from actas.web import routes
from actas.web.fmt import BODY, date_with_year, e, rel
from actas.web.pages.decisions import amount_label
from actas.web.pages.entities import CLASS_LABEL
from actas.web.template import page, version
from actas.web.texts import SEARCH_LABEL, SEARCH_TITLE

EXAMPLES = ["castillo", "piscina cubierta", "calle Rambla", "subvención fiestas"]


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def decision_rows(archive, year: int) -> list[list]:
    rows = []
    for s in archive.sites[year].sessions:
        for d in s.decisions:
            meta = " · ".join(x for x in (BODY.get(s.body, s.body), date_with_year(s.date),
                                          amount_label(d, short=True)) if x)
            concepts = " · ".join(x for x in dict.fromkeys(i["concept"] or "" for i in d.amounts) if x)
            entities = " · ".join(dict.fromkeys(x["name"] for x in d.entities))
            # Each decision is a list, not an object, to keep the files small.
            rows.append([d.slug, d.title, meta, d.summary, entities, d.place or "", d.case_file or "", concepts])
    return rows


def _span(years: list[int]) -> str:
    first, last = min(years), max(years)
    return str(first) if first == last else f"{first}–{last}"


def entity_rows(archive) -> list[list]:
    return [[h.slug, h.name, f"{CLASS_LABEL.get(h.entity_class, h.entity_class)} · {_span(list(h.years))}",
             max(h.years)] for h in archive.entities.values()]


def files(archive) -> list[tuple[str, str]]:
    out = [(routes.search_index(y), _dump(decision_rows(archive, y))) for y in archive.years]
    out.append((routes.search_entities(), _dump(entity_rows(archive))))
    return out


def body(archive, path: str, stamps: dict[str, str]) -> str:
    """stamps: path of each index file -> content stamp."""
    years = "".join(f'<option value="{y}">{y}</option>' for y in archive.years)
    indexes = _dump({"entities": f'{rel(path, routes.search_entities())}?v={stamps[routes.search_entities()]}',
                     "years": {str(y): f'{rel(path, routes.search_index(y))}?v={stamps[routes.search_index(y)]}'
                               for y in archive.years}})
    examples = " · ".join(f'<a href="?q={e(x)}">{e(x)}</a>' for x in EXAMPLES)
    return f"""<h1>{SEARCH_TITLE}</h1>
<form class="search-form" role="search" action="" method="get">
<label for="q">{SEARCH_LABEL}</label>
<div class="search-row"><input type="search" id="q" name="q" autocomplete="off" enterkeyhint="search">
<button type="submit">Buscar</button></div>
<div class="field" id="year-field" hidden><label for="year">Año</label><select id="year" name="año">
<option value="">Todos los años</option>{years}</select></div>
</form>
<p class="hint">Por ejemplo: {examples}. Busca en las decisiones de la Junta de Gobierno y del Pleno desde {archive.years[-1]}, y en las empresas, asociaciones e instituciones que tienen ficha.</p>
<noscript><p class="lede">El buscador necesita JavaScript. Sin él puedes ver las decisiones mes a mes en <a href="{e(rel(path, routes.decisions(archive.latest.year)))}">Decisiones</a>.</p></noscript>
<p class="counter" id="status" aria-live="polite"></p>
<section id="entity-results" hidden><h2>Empresas y entidades</h2><ul class="news" id="entity-list"></ul></section>
<section id="decision-results" hidden><h2>Decisiones</h2><div id="decision-list" data-page-size="25"></div></section>
<script id="search-indexes" type="application/json">{indexes}</script>
<script src="{e(rel(path, "static/search.js"))}?v={version("search.js")}" defer></script>"""


def generate(archive, stamps: dict[str, str]) -> list[tuple[str, str]]:
    path = routes.search()
    return [(path, page(path, SEARCH_TITLE, body(archive, path, stamps), archive.latest, "search"))]
