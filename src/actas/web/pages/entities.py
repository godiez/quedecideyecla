from actas.web import routes
from actas.web.fmt import BODY, date_with_year, e, eur, eur_short, plain, rel
from actas.web.template import FLAG, mailto, page
from actas.web.texts import EMAIL, section_title
from datetime import date

CLASS_LABEL = {"empresa": "Empresa", "asociacion_institucion": "Asociación o institución",
               "publica": "Administración pública", "pendiente": "Pendiente de clasificar"}
SHORT_CLASS = {"empresa": "Empresa", "asociacion_institucion": "Asociación", "publica": "Pública",
               "pendiente": "Sin clasificar"}
PHASE_LABEL = {"adjudicacion": "Adjudicación", "pago": "Pago", "subvencion": "Subvención", "especie": "En especie"}
PERMIT_CATEGORY = {"licencia_obra": "Licencia de obra", "licencia_actividad": "Licencia de actividad",
                   "suelo_no_urbanizable": "Suelo no urbanizable",
                   "urbanismo_planeamiento": "Planeamiento urbanístico"}


def _short_date(s: str | None) -> str:
    return date.fromisoformat(s).strftime("%d/%m/%Y") if s else "—"


def _session(site, doc):
    return next(s for s in site.sessions if s.doc == doc)


def _year_table(h) -> str:
    """No total row: adding up «comprometido» across years could count twice a contract awarded one year and paid
    the next."""
    years = [(y, x) for y, x in h.years.items() if x.committed or x.awarded or x.paid or x.grant]
    if not years:
        return ""
    columns = [("Comprometido", "committed"), ("Adjudicado", "awarded"), ("Pagado", "paid"), ("Subvención", "grant")]
    columns = [c for c in columns if c[1] == "committed" or any(getattr(x, c[1]) for _, x in years)]
    if any(not x.awarded and x.paid for _, x in years) and ("Adjudicado", "awarded") not in columns:
        columns.insert(1, ("Adjudicado", "awarded"))

    def cell(x, attr: str) -> str:
        return "—" if attr == "awarded" and not x.awarded and x.paid else eur(getattr(x, attr))

    head = "".join(f'<th class="num">{label}</th>' for label, _ in columns)
    rows = "".join(f"<tr><th>{y}{FLAG if x.notes else ''}</th>" + "".join(f'<td class="num">{cell(x, attr)}</td>' for _, attr in columns)
                   + "</tr>" for y, x in years)
    return (f'<div class="table-scroll"><table><thead><tr><th>Año</th>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


def year_spans(years) -> str:
    ys = sorted(set(years))
    spans, start = [], None
    for i, y in enumerate(ys):
        start = y if start is None else start
        if i == len(ys) - 1 or ys[i + 1] != y + 1:
            spans.append(str(y) if start == y else f"{start}–{y}")
            start = None
    return ", ".join(spans)


def directory(archive) -> str:
    path = routes.entities()
    ents = sorted(archive.entities.values(), key=lambda h: plain(h.name))
    rows = "".join(
        f'<tr data-text="{e(plain(h.name))}" data-type="{e(h.entity_class)}"><td><a href="'
        f'{e(rel(path, routes.entity(h.slug)))}">{e(h.name)}</a></td>'
        f'<td>{SHORT_CLASS.get(h.entity_class, h.entity_class)}</td><td>{year_spans(h.years)}</td></tr>'
        for h in ents)
    counts = {k: sum(1 for h in ents if h.entity_class == k) for k in CLASS_LABEL}
    options = "".join(f'<option value="{k}">{label} ({counts[k]})</option>' for k, label in CLASS_LABEL.items()
                      if counts[k])
    return f"""<h1>Todas las empresas, asociaciones e instituciones</h1>
<p class="lede">Las {len(ents)} entidades que aparecen en las actas desde {archive.years[-1]} recibiendo dinero o pidiendo permisos, de la A a la Z. Cada ficha dice qué ha recibido cada año. Las personas no tienen ficha.</p>
<div class="list-filter" data-filter-for="entities" hidden>
<div><label for="entity-name">Buscar por nombre</label><input type="search" id="entity-name" autocomplete="off" placeholder="Ej.: Actúa, club, AMPA"></div>
<div><label for="entity-type">Tipo</label><select id="entity-type"><option value="">Todos los tipos</option>{options}</select></div>
<p class="counter" aria-live="polite"></p>
</div>
<div class="table-scroll"><table id="entities" data-page-size="50"><thead><tr><th>Nombre</th><th>Tipo</th><th>Años</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="hint">Tipo: «Asociación» incluye asociaciones, clubes e instituciones; «Pública», otras administraciones. Años: en los que la entidad recibe dinero o pide permisos. Para buscar también en las decisiones, usa el <a href="{e(rel(path, routes.search()))}">buscador</a>.</p>"""


def detail(archive, h) -> str:
    path = routes.entity(h.slug)
    parts = [f'<p class="breadcrumb"><a href="{e(rel(path, routes.entities()))}">← Todas las entidades</a></p>',
             f"<h1>{e(h.name)}</h1>", f'<p class="summary-line">{CLASS_LABEL.get(h.entity_class, h.entity_class)}</p>']
    with_money = [(y, x) for y, x in h.years.items() if x.committed]
    if with_money:
        y, x = with_money[0]
        parts.append(f'<p class="figure">{eur_short(x.committed)}</p>'
                     f'<p class="hint">{eur(x.committed)} comprometidos en {y}: lo adjudicado o lo pagado en el año '
                     f'(lo mayor de los dos), más las subvenciones. No es lo mismo que lo cobrado.</p>')
    for y, x in h.years.items():
        for n in x.notes:
            parts.append(f'<aside class="callout"><p><b>{e(n.title)} ({y}).</b> {e(n.text)}</p></aside>')
    table = _year_table(h)
    if table:
        parts.append(f"<h2>Cada año</h2>{table}")
        if any(x.notes for x in h.years.values()):
            parts.append('<p class="hint">* Ese año tiene un aviso: está explicado arriba.</p>')
        if any(not x.awarded and x.paid for x in h.years.values()):
            parts.append('<p class="hint">«—» en adjudicado: sin adjudicación en las actas de ese año. Los pagos '
                         'pueden corresponder a un contrato adjudicado en años anteriores.</p>')
    movements = h.movements
    if movements:
        phases = {m["fase"] for m in movements}
        with_phase = len(phases) > 1
        lines = "".join(
            f'<tr><td>{_short_date(m.get("fecha"))}</td>'
            f'<td><a href="{e(rel(path, routes.decision(m["decision_slug"])))}">'
            f'{e(m.get("concepto") or m.get("titulo"))}</a></td>'
            + (f'<td>{PHASE_LABEL.get(m["fase"], m["fase"])}</td>' if with_phase else "")
            + f'<td class="num">{eur(m["eur"])}</td></tr>'
            for m in movements)
        title = "Movimientos en las actas" if with_phase else \
            f"Movimientos en las actas: {PHASE_LABEL.get(next(iter(phases)), '').lower()}"
        parts.append(f'<h2>{title}</h2><div class="table-scroll"><table data-page-size="25"><thead><tr><th>Fecha</th>'
                     '<th>Concepto</th>' + ('<th>Fase</th>' if with_phase else "") + '<th class="num">Importe</th>'
                     f'</tr></thead><tbody>{lines}</tbody></table></div><p class="hint">Del más reciente al más '
                     'antiguo. Una adjudicación y sus pagos pueden aparecer en varias actas: las cifras de arriba '
                     'no los suman dos veces.</p>')
    if h.permits:
        items = "".join(
            f'<li class="news-item"><a href="{e(rel(path, routes.decision(d.slug)))}">{e(d.title)}</a>'
            f'<span class="meta">{PERMIT_CATEGORY.get(d.category, "")} · '
            f'{BODY.get(archive.sessions[d.session_doc].body, "")} · '
            f'{date_with_year(archive.sessions[d.session_doc].date)}</span></li>' for d in h.permits)
        parts.append(f'<h2>Permisos y licencias</h2><ul class="news" data-page-size="20">{items}</ul>')
    parts.append(f'<p class="note">¿Ves un error en esta ficha? Escríbenos a '
                 f'<a href="{e(mailto(f"Error en entidad {h.slug}"))}">{EMAIL}</a></p>')
    return "\n".join(parts)


def permits(site) -> str:
    path = routes.permits(site.year)
    applicants = sorted((x for x in site.entities.values() if x.permits), key=lambda x: (-len(x.permits), x.name))
    rows = "".join(f'<tr><td><a href="{e(rel(path, routes.entity(x.slug)))}">{e(x.name)}</a></td>'
                   f'<td>{CLASS_LABEL.get(x.entity_class, x.entity_class)}</td><td class="num">{len(x.permits)}</td></tr>'
                   for x in applicants)
    parts = [f"<h1>Quién pide permisos en {site.year}</h1>",
             '<p class="lede">Licencias de obra y de actividad, autorizaciones en suelo no urbanizable y '
             'planeamiento urbanístico que han pasado por la Junta de Gobierno o el Pleno. Solo se nombran '
             'empresas e instituciones; las personas aparecen como «un particular».</p>',
             "<h2>Quién pide licencias</h2>",
             '<div class="table-scroll"><table data-page-size="50"><thead><tr><th>Entidad</th><th>Tipo</th>'
             f'<th class="num">Permisos</th></tr></thead><tbody>{rows}</tbody></table></div>'
             if applicants else '<p class="note">Ninguna.</p>']
    rustic = sorted((d for d in site.decisions.values() if d.category == "suelo_no_urbanizable"),
                    key=lambda d: (_session(site, d.session_doc).date, d.slug), reverse=True)
    items = []
    for d in rustic:
        s = _session(site, d.session_doc)
        who = ", ".join(
            f'<a href="{e(rel(path, routes.entity(x["slug"])))}">{e(x["name"])}</a>' if x["slug"] else e(x["name"])
            for x in d.entities if x["name"] == "un particular" or x["slug"]) or "—"
        place = f" · {e(d.place)}" if d.place else ""
        items.append(f'<li class="news-item"><a href="{e(rel(path, routes.decision(d.slug)))}">{e(d.title)}</a>'
                     f'<span class="meta">{BODY.get(s.body, s.body)} · {date_with_year(s.date)} · {who}'
                     f'{place}</span></li>')
    parts.append("<h2>Suelo no urbanizable</h2>")
    parts.append('<p class="hint">Autorizaciones excepcionales para construir o usar suelo rústico.</p>')
    parts.append(f'<ul class="news" data-page-size="25">{"".join(items)}</ul>' if items else '<p class="note">Ninguna.</p>')
    return "\n".join(parts)


def generate(site) -> list[tuple[str, str]]:
    path = routes.permits(site.year)
    return [(path, page(path, section_title("permits", site.year), permits(site), site, "permits"))]


def generate_entities(archive) -> list[tuple[str, str]]:
    d = routes.entities()
    out = [(d, page(d, "Todas las entidades", directory(archive), archive.latest, "money", show_years=False))]
    for h in archive.entities.values():
        path = routes.entity(h.slug)
        out.append((path, page(path, h.name, detail(archive, h), archive.latest, "money")))
    return out
