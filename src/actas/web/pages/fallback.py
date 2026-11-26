import json

from actas import municipality
from actas.votes import legislature_of_year
from actas.web import routes
from actas.web.fmt import e, rel
from actas.web.template import page
from actas.web.texts import INFO_PATH, INFO_TITLE, SEARCH_LABEL, SITE_NAME

NOT_FOUND_PATH = "404.html"
NOINDEX = '<meta name="robots" content="noindex">\n'
# GitHub Pages shows 404.html at the address that was asked for (it can be deep: /a/b/c), so its relative links
# would not work: this sets the base of the links to the site root before the style sheet loads.
GUESSED_BASE = ('<script>(function () { var s = location.pathname.split("/"); var b = document.createElement("base"); '
        'b.href = /\\.github\\.io$/.test(location.hostname) && s.length > 2 ? "/" + s[1] + "/" : "/"; '
        'document.head.appendChild(b); })();</script>\n')


def base() -> str:
    town = municipality.load()
    if not town.site_url:
        return GUESSED_BASE
    # Written in the HTML, so the browser fetches the style sheet from the right place before any script runs; the
    # script only serves a local preview, where the site is at the root.
    host = json.dumps(town.site_host).replace("<", "\\u003c")
    return (f'<base href="{e(town.site_path)}">\n<script>if (location.host !== {host}) '
            'document.querySelector("base").href = "/";</script>\n')


def _redirect(archive, path: str, target: str, title: str, text: str) -> tuple[str, str]:
    to = rel(path, target)
    head = f'{NOINDEX}<meta http-equiv="refresh" content="0; url={e(to)}">\n'
    content = (f"<h1>{e(title)}</h1><p class=\"lede\">{text}</p>"
               f'<a class="button" href="{e(to)}">Ir a {e(title.lower())}</a>')
    return path, page(path, title, content, archive.latest, None, head=head, show_years=False, preview=False)


def redirects(archive) -> list[tuple[str, str]]:
    latest = archive.latest.year
    return [
        _redirect(archive, "decision/", routes.decisions(latest), "Decisiones",
                  "Las decisiones están ordenadas por año y por mes. Te llevamos a las del último mes."),
        _redirect(archive, "datos/", f"{INFO_PATH}#datos", "Descargar los datos",
                  f"Los ficheros con los datos están explicados en «{INFO_TITLE}»."),
    ]


def not_found(archive) -> tuple[str, str]:
    latest = archive.latest.year
    content = f"""<h1>Esta página no existe</h1>
<p class="lede">Puede que la dirección esté mal escrita o que la página haya cambiado de sitio. Lo que buscabas seguramente sigue en {SITE_NAME}.</p>
<a class="button" href="./">Volver a la portada</a>
<form class="search-form" role="search" action="{routes.search()}" method="get">
<label for="q">{SEARCH_LABEL}</label>
<div class="search-row"><input type="search" id="q" name="q" autocomplete="off" enterkeyhint="search">
<button type="submit">Buscar</button></div>
</form>
<h2>Otras secciones</h2>
<ul class="groups">
<li><a href="{routes.decisions(latest)}">Decisiones</a></li>
<li><a href="{routes.money(latest)}">Dinero por entidad</a></li>
<li><a href="{routes.entities()}">Todas las entidades</a></li>
<li><a href="{routes.votes(legislature_of_year(latest))}">Votaciones</a></li>
</ul>"""
    return NOT_FOUND_PATH, page("", "Página no encontrada", content, archive.latest, None, head=NOINDEX + base(),
                                show_years=False, preview=False)
