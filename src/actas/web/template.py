import hashlib
from functools import cache
from pathlib import Path

from actas import municipality
from actas.web import routes
from actas.web.fmt import date_with_year, e, eur_short, rel, slug
from actas.web.texts import (EMAIL, INFO_PATH, INFO_TITLE, LEGAL_PATH, LEGAL_TITLE, MENU, META_DESCRIPTION,
                                   NOTICE, PREVIEW_ALT, SITE_NAME, SOURCE, TOWN, UNOFFICIAL)

STATIC = Path(__file__).resolve().parent / "static"
PARTY_COLORS = "/* party colours: analisis/municipio.json */"
PREVIEW_IMAGE = "vista-previa.png"


@cache
def static_file(filename: str) -> bytes:
    raw = (STATIC / filename).read_bytes()
    if filename == "style.css":
        rules = "\n".join(f".party-{slug(g)} {{ --party: {c}; }}" for g, c in municipality.load().colors.items())
        raw = raw.replace(PARTY_COLORS.encode(), rules.encode())
    return raw


@cache
def version(filename: str) -> str:
    return hashlib.sha256(static_file(filename)).hexdigest()[:10]


def mailto(subject: str | None = None) -> str:
    from urllib.parse import quote
    return f"mailto:{EMAIL}" + (f"?subject={quote(subject)}" if subject else "")


def full_title(title: str) -> str:
    site = f"{SITE_NAME} · {TOWN}"
    return f"{title} · {site}" if title else site


def preview_tags(path: str, title: str) -> str:
    """The card that WhatsApp, LinkedIn or X show for a shared link; they need absolute addresses."""
    url = municipality.load().site_url
    if not url:
        return ""
    tags = [("og:type", "website"), ("og:locale", "es_ES"), ("og:site_name", full_title("")),
            ("og:title", title or full_title("")), ("og:description", META_DESCRIPTION), ("og:url", url + path),
            ("og:image", f"{url}static/{PREVIEW_IMAGE}?v={version(PREVIEW_IMAGE)}"), ("og:image:width", "1200"),
            ("og:image:height", "630"), ("og:image:alt", PREVIEW_ALT)]
    return ("".join(f'<meta property="{k}" content="{e(v)}">\n' for k, v in tags)
            + '<meta name="twitter:card" content="summary_large_image">\n')


def page(path: str, title: str, content: str, site, section: str | None, head: str = "",
         show_years: bool = True, preview: bool = True) -> str:
    def a(dst: str) -> str:
        return e(rel(path, dst))

    menu = "".join(f'<li><a href="{a(routes.section(k, site.year))}"{" aria-current=\"page\"" if k == section else ""}>'
                   f'{t}</a></li>' for k, t in MENU)
    years = "".join(f'<li><a href="{a(routes.section(section, y))}"{" aria-current=\"true\"" if y == site.year else ""}>'
                    f'{y}</a></li>' for y in site.years)
    year_nav = (f'<nav class="years" aria-label="Año"><ul>{years}</ul></nav>'
                if show_years and section != "search" else "")
    info_current = ' aria-current="page"' if section == "info" else ""
    notice = e(NOTICE).replace(EMAIL, f'<a href="{mailto()}">{EMAIL}</a>')
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title(title))}</title>
<meta name="description" content="{e(META_DESCRIPTION)}">
{preview_tags(path, title) if preview else ""}<link rel="icon" href="data:,">
{head}<link rel="stylesheet" href="{a("static/style.css")}?v={version("style.css")}">
</head>
<body>
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<div class="notice" role="note"><p>{notice}</p><button type="button" class="close-notice" hidden aria-label="Cerrar el aviso">×</button></div>
<header class="masthead">
<a class="brand" href="{a(routes.home(site.year))}"><span class="t">{SITE_NAME}</span><span class="s">{TOWN}</span></a>
{year_nav}
</header>
<nav class="menu" aria-label="Secciones"><ul>{menu}<li class="info"><a href="{a(INFO_PATH)}"{info_current}>{INFO_TITLE}</a></li></ul></nav>
<main id="contenido" tabindex="-1">
{content}
</main>
<footer class="site-footer">
<p>{data_period(site)}</p>
<p><a href="{a(INFO_PATH)}">{INFO_TITLE}</a> · <a href="{a(LEGAL_PATH)}">{LEGAL_TITLE}</a> · <a href="{mailto()}">{EMAIL}</a></p>
<p>{SOURCE} {UNOFFICIAL}</p>
</footer>
<a class="to-top" href="#" hidden><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="visually-hidden">Ir arriba del todo</span></a>
<script src="{a("static/filters.js")}?v={version("filters.js")}" defer></script>
</body>
</html>
"""


def code_link(text: str) -> str:
    url = municipality.load().code_url
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{text}</a>' if url else text


def party(group: str) -> str:
    """«IU‑Verdes» with a hyphen that does not break."""
    return f'<span class="party party-{slug(group)}">{e(group.replace("-", "‑"))}</span>'


FLAG = '<sup class="flag" title="Ver el aviso">*<span class="visually-hidden"> (tiene una nota debajo)</span></sup>'


def notes_footer(path: str, rows: list[tuple[str, str, list]]) -> str:
    items = "".join(f'<p class="hint flag-note">* <a href="{e(rel(path, link))}">{e(name)}</a>: '
                    + " ".join(f"{e(n.title)}. {e(n.text)}" for n in notes) + "</p>"
                    for name, link, notes in rows if notes)
    return items


def data_period(site) -> str:
    first, last = site.period
    return f"Datos de las actas del {date_with_year(first)} al {date_with_year(last)}."


def bars(rows: list[tuple], max_width: int = 100) -> str:
    if not rows:
        return ""
    largest = max(r[1] for r in rows) or 1
    items = []
    for label, value, link, *flag in rows:
        width = max(0, round(max_width * value / largest))
        name = f'<a href="{e(link)}">{e(label)}</a>' if link else e(label)
        name += FLAG if flag and flag[0] else ""
        items.append(f'<li><span class="n">{name}</span><span class="v">{eur_short(value)}</span>'
                     f'<span class="b" style="width:{width}%" aria-hidden="true"></span></li>')
    return f'<ol class="bars">{"".join(items)}</ol>'
