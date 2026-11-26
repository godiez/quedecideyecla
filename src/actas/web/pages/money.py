from actas.web import routes
from actas.web.fmt import BODY, date_with_year, e, eur, eur_short, rel
from actas.web.pages.decisions import amount_label
from actas.web.texts import HOME_SEARCH_HINT, HOME_TITLE, INFO_PATH, SEARCH_LABEL, section_title
from actas.web.template import FLAG, bars, mailto, notes_footer, page

COMMITTED_NOTE = "Comprometido: lo adjudicado o lo pagado en el año (lo mayor de los dos), más las subvenciones."


def ranking_title(year: int) -> str:
    return f"Todo el dinero de {year}, por entidad"


def news_item(path: str, d, session) -> str:
    amount = f" · {amount_label(d, short=True)}" if d.amount_eur else ""
    return (f'<li class="news-item"><a href="{e(rel(path, routes.decision(d.slug)))}">{e(d.title)}</a>'
            f'<span class="meta">{BODY.get(session.body, session.body)} · {date_with_year(session.date)}'
            f'{amount}</span></li>')


def home(site, path: str) -> str:
    t = site.totals
    companies = [x for x in site.ranking if x.entity_class == "empresa"][:10]
    top = bars([(x.name, x.committed, rel(path, routes.entity(x.slug)), bool(x.notes)) for x in companies])
    top += notes_footer(path, [(x.name, routes.entity(x.slug), x.notes) for x in companies])
    kinds = bars([("Contratos y pagos a empresas", t["companies"], None),
                  ("Subvenciones a asociaciones e instituciones", t["associations"], None),
                  ("Pendiente de clasificar", t["pending"], None)])
    rest = (f"Además hay {eur_short(t['unassigned'])} en ayudas a particulares o con adjudicatario sin "
            f"identificar")
    rest += f", y {eur_short(t['pending'])} de entidades pendientes de clasificar." if t["pending"] > 0 else "."
    latest = "".join(news_item(path, d, s) for s in site.sessions[:3] for d in s.decisions[:2])
    return f"""<div class="home">
<section>
<h1>{HOME_TITLE}</h1>
<form class="search-form compact" role="search" action="{rel(path, routes.search())}" method="get">
<label for="q" class="visually-hidden">{SEARCH_LABEL}</label>
<div class="search-row"><input type="search" id="q" name="q" placeholder="{HOME_SEARCH_HINT}" autocomplete="off" enterkeyhint="search">
<button type="submit">Buscar</button></div>
</form>
<p class="lede">En {site.year} el Ayuntamiento ha comprometido <b>{eur_short(t["companies"])}</b> con empresas.</p>
{top}
<p class="more"><a href="{rel(path, routes.money(site.year))}">{ranking_title(site.year)} →</a></p>
<p class="hint">{COMMITTED_NOTE} <a href="{rel(path, INFO_PATH)}#glosario">Qué significa cada palabra</a>.</p>
</section>
<section>
<h2>Últimas decisiones de {site.year}</h2>
<ul class="news">{latest}</ul>
<p class="more"><a href="{rel(path, routes.decisions(site.year))}">Todas las decisiones →</a></p>
<h2>En qué se va el dinero</h2>
{kinds}
<p class="hint">{rest}</p>
</section>
</div>"""


def table(path: str, entities) -> str:
    rows = "".join(
        f'<tr><td><a href="{e(rel(path, routes.entity(x.slug)))}">{e(x.name)}</a>{FLAG if x.notes else ""}</td>'
        f'<td class="num">{eur(x.committed)}</td><td class="num">{eur(x.awarded)}</td>'
        f'<td class="num">{eur(x.paid)}</td><td class="num">{eur(x.grant)}</td></tr>' for x in entities)
    return (f'<div class="table-scroll"><table data-page-size="50"><thead><tr><th>Nombre</th><th class="num">Comprometido</th>'
            f'<th class="num">Adjudicado</th><th class="num">Pagado</th><th class="num">Subvención</th></tr>'
            f'</thead><tbody>{rows}</tbody></table></div>'
            + notes_footer(path, [(x.name, routes.entity(x.slug), x.notes) for x in entities]))


def ranking(site) -> str:
    path = routes.money(site.year)
    groups = [
        ("Empresas", [x for x in site.ranking if x.entity_class == "empresa"], ""),
        ("Asociaciones e instituciones",
         [x for x in site.ranking if x.entity_class in ("asociacion_institucion", "publica")],
         "Sobre todo subvenciones. Incluye otras administraciones públicas que reciben dinero."),
        ("Pendiente de clasificar", [x for x in site.ranking if x.entity_class == "pendiente"],
         f'Todavía no sabemos con seguridad qué tipo de entidad es. Si lo sabes, '
         f'<a href="{mailto("Clasificar entidad")}">avísanos</a>.'),
    ]
    parts = [f"<h1>{ranking_title(site.year)}</h1>",
             f'<p class="hint">{COMMITTED_NOTE} Adjudicado: contratos adjudicados en el año. Pagado: facturas y '
             f'certificaciones aprobadas. Los importes salen de las actas; la cifra «comprometido» no es lo '
             f'que la entidad ha cobrado. <a href="{rel(path, INFO_PATH)}#glosario">Qué significa cada '
             f'palabra</a> · <a href="{rel(path, routes.money_csv(site.year))}" download>Descargar en CSV</a> · '
             f'<a href="{rel(path, routes.entities())}">Todas las entidades de todos los años</a>'
             f'</p>']
    for title, ents, note in groups:
        total = sum(x.committed for x in ents)
        parts.append(f"<h2>{title}</h2>")
        parts.append(f'<p class="note">{len(ents)} entidades · {eur(total)} comprometidos. {note}</p>'
                     .replace(" .", "."))
        parts.append(table(path, ents) if ents else '<p class="note">Ninguna.</p>')
    return "\n".join(parts)


def generate(site, root: bool = False) -> list[tuple[str, str]]:
    h, m = routes.home(site.year), routes.money(site.year)
    out = [(h, page(h, section_title("money", site.year), home(site, h), site, "money")),
           (m, page(m, ranking_title(site.year), ranking(site), site, "money"))]
    if root:
        out.append(("", page("", "", home(site, ""), site, "money")))
    return out
