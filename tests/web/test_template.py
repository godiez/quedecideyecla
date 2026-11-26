import dataclasses
import re
import struct

from actas import municipality
from actas.web import model
from actas.web.template import STATIC, bars, page
from actas.web.texts import META_DESCRIPTION, NOTICE


def test_page_has_notice_menu_and_is_relative(mini_analysis):
    a, db = mini_analysis
    s = model.build(a, db, 2026)
    h = page("2026/dinero/", "Todo el dinero", "<p>hola</p>", s, "money")
    assert h.startswith("<!doctype html>") and 'lang="es"' in h
    assert "<title>Todo el dinero · Qué decide el Ayuntamiento · Yecla</title>" in h
    assert "Esta web no tiene relación con el Ayuntamiento de Yecla ni con ningún partido político. Construida " \
           "a partir de las actas del Ayuntamiento. Puede contener errores. ¿Ves uno? Escríbenos a" in h
    assert '<button type="button" class="close-notice" hidden aria-label="Cerrar el aviso">' in h
    footer = h[h.index('<footer class="site-footer">'):]
    assert "no tiene relación con el Ayuntamiento de Yecla ni con ningún partido político" in footer
    assert 'href="mailto:quedecideyecla@gmail.com"' in h
    assert 'href="/' not in h and "src=\"/" not in h
    assert re.search(r'href="\.\./\.\./static/style\.css\?v=[0-9a-f]{10}"', h)
    current = re.findall(r'<a [^>]*aria-current="page"[^>]*>([^<]+)</a>', h)
    assert current == ["Dinero"]
    assert '<span class="s">Yecla</span>' in h and "Qué decide el Ayuntamiento" in h
    assert '<nav class="years" aria-label="Año">' in h and '<a href="../" aria-current="true">2026</a>' in h
    # «Año» is only read aloud (aria-label), not written.
    assert 'class="label"' not in h
    assert "Datos de las actas del 7 de enero de 2026 al 2 de marzo de 2026.</p>" in h and "Actualizado" not in h
    assert 'href="../../como-se-ha-hecho/"' in h
    assert "@" not in NOTICE.replace("quedecideyecla@gmail.com", "")


def test_bars_escape_and_scale():
    h = bars([("A <b>", 200.0, "entidad/a/"), ("B", 50.0, None)])
    assert "A &lt;b&gt;" in h
    assert "width:100%" in h and "width:25%" in h
    assert 'href="entidad/a/"' in h
    assert h.count("<li") == 2
    assert bars([]) == ""


def test_year_selector_goes_to_the_same_section_of_each_year(mini_analysis):
    a, db = mini_analysis
    s = model.build(a, db, 2026)
    s.years = [2026, 2025, 2022]
    h = page("decision/x/", "Una ficha", "", s, "decisions")
    years = h[h.index('<nav class="years"'):h.index("</nav>", h.index('<nav class="years"'))]
    assert re.findall(r'href="([^"]+)"', years) == ["../../2026/decisiones/", "../../2025/decisiones/",
                                                     "../../2022/decisiones/"]
    menu = h[h.index('<nav class="menu"'):]
    assert 'href="../../2026/permisos/"' in menu and 'href="../../votaciones/"' in menu
    s.year = 2022
    h = page("2022/permisos/", "Permisos", "", s, "votes")
    assert 'href="../../votaciones/2019-2023/"' in h


def test_footer_period_covers_every_year(two_years):
    root, db = two_years
    archive = model.build_archive(root, db)
    old = archive.sites[2022]
    h = page("2022/", "Portada", "", old, "money")
    assert "Datos de las actas del 10 de mayo de 2022 al 2 de marzo de 2026." in h


def test_to_top_link_hidden_until_javascript_shows_it(mini_analysis):
    a, db = mini_analysis
    site = model.build(a, db, 2026)
    h = page("decision/x/", "Una ficha", "", site, "decisions")
    assert '<a class="to-top" href="#" hidden>' in h and '<span class="visually-hidden">Ir arriba del todo</span>' in h


def test_a_shared_link_shows_the_preview_card(mini_analysis):
    a, db = mini_analysis
    s = model.build(a, db, 2026)
    h = page("2026/dinero/", "Todo el dinero", "<p>hola</p>", s, "money")
    meta = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)">', h))
    assert meta["og:title"] == "Todo el dinero" and meta["og:description"] == META_DESCRIPTION
    assert meta["og:url"] == "https://godiez.github.io/quedecideyecla/2026/dinero/"
    assert re.fullmatch(r"https://godiez\.github\.io/quedecideyecla/static/vista-previa\.png\?v=[0-9a-f]{10}",
                        meta["og:image"])
    assert (meta["og:image:width"], meta["og:image:height"]) == ("1200", "630")
    assert "Web no oficial" in meta["og:image:alt"] and meta["twitter:card"] == "summary_large_image"
    home = page("", "", "<p>hola</p>", s, "money")
    assert '<meta property="og:title" content="Qué decide el Ayuntamiento · Yecla">' in home
    assert '<meta property="og:url" content="https://godiez.github.io/quedecideyecla/">' in home


def test_no_preview_card_without_the_address_of_the_site_or_on_pages_not_to_share(mini_analysis, monkeypatch):
    a, db = mini_analysis
    s = model.build(a, db, 2026)
    assert "og:" not in page("2026/", "Error", "<p>hola</p>", s, None, preview=False)
    town = municipality.load()
    monkeypatch.setattr(municipality, "load", lambda: dataclasses.replace(town, site_url=""))
    assert "og:" not in page("2026/dinero/", "Todo el dinero", "<p>hola</p>", s, "money")


def test_the_preview_image_is_small_enough_for_whatsapp():
    png = (STATIC / "vista-previa.png").read_bytes()
    assert png.startswith(b"\x89PNG") and struct.unpack(">II", png[16:24]) == (1200, 630)
    assert len(png) < 300_000
