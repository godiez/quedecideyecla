import json
import re

from actas.web import build, model
from actas.web.pages import entities


def _site(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    build.build_site(a.parent, db, out)
    return out


def test_every_folder_has_a_page_and_there_is_a_404(mini_analysis, tmp_path):
    out = _site(mini_analysis, tmp_path)
    folders = [p for p in out.rglob("*") if p.is_dir() and p.name != "static" and "static" not in p.parts]
    assert [p for p in folders if not (p / "index.html").exists()] == []
    for folder, target in [("decision", "../2026/decisiones/"), ("datos", "../como-se-ha-hecho/#datos")]:
        h = (out / folder / "index.html").read_text(encoding="utf-8")
        assert f'<meta http-equiv="refresh" content="0; url={target}">' in h
        assert '<meta name="robots" content="noindex">' in h and f'class="button" href="{target}"' in h
        assert "og:" not in h
    nf = (out / "404.html").read_text(encoding="utf-8")
    assert "og:" not in nf
    assert '<meta property="og:url" content="https://godiez.github.io/quedecideyecla/2026/dinero/">' in \
        (out / "2026" / "dinero" / "index.html").read_text(encoding="utf-8")
    assert "Esta página no existe" in nf and '<a class="button" href="./">Volver a la portada</a>' in nf
    assert nf.index('<base href="/quedecideyecla/">') < nf.index('<script>if (location.host !== "godiez.github.io")') \
        < nf.index('rel="stylesheet"')
    assert '<nav class="years"' not in nf
    assert '<a href="2026/dinero/">Dinero por entidad</a>' in nf and '<a href="entidad/">Todas las entidades</a>' in nf


def test_entities_directory(mini_analysis, tmp_path):
    out = _site(mini_analysis, tmp_path)
    h = (out / "entidad" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Todas las empresas, asociaciones e instituciones</h1>" in h
    assert '<table id="entities" data-page-size="50">' in h and 'data-filter-for="entities" hidden' in h
    assert '<tr data-text="actua, servicios y medio ambiente, s.l." data-type="empresa">' in h
    assert '<a href="../2026/permisos/">Permisos</a>' in h
    actua = (out / "entidad" / "actua-servicios-y-medio-ambiente-s-l" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../">← Todas las entidades</a>' in actua


def test_long_lists_are_paginated_and_search_has_no_year_selector(mini_analysis, tmp_path):
    out = _site(mini_analysis, tmp_path)
    assert '<table data-page-size="50">' in (out / "2026" / "dinero" / "index.html").read_text(encoding="utf-8")
    assert '<div class="editions" data-page-size="10">' in \
        (out / "2026" / "decisiones" / "todas" / "index.html").read_text(encoding="utf-8")
    assert 'data-page-size="25"' in (out / "votaciones" / "index.html").read_text(encoding="utf-8")
    s = (out / "buscar" / "index.html").read_text(encoding="utf-8")
    assert '<nav class="years"' not in s and '<div id="decision-list" data-page-size="25">' in s


def test_year_spans():
    assert entities.year_spans([2025, 2021, 2022, 2023]) == "2021–2023, 2025"
    assert entities.year_spans([2024]) == "2024"


def test_same_name_with_two_keys_is_one_entity():
    from types import SimpleNamespace
    old = SimpleNamespace(persons=set(), candidates={"AMPAS DE 5 ESCUELAS INFANTILES": ("AMPAS de escuelas infantiles",
                                                                                     "asociacion_institucion")})
    new = SimpleNamespace(persons=set(), candidates={"AMPAS DE ESCUELAS INFANTILES": ("AMPAS de escuelas infantiles",
                                                                                   "asociacion_institucion"),
                                                     "OTRA": ("Otra, S.L.", "empresa")})
    registry, _ = model.register([old, new])
    assert registry["AMPAS DE 5 ESCUELAS INFANTILES"] is registry["AMPAS DE ESCUELAS INFANTILES"]
    assert registry["OTRA"].slug == "otra-s-l"


def test_titles_follow_the_menu_and_say_the_town(mini_analysis, tmp_path):
    out = _site(mini_analysis, tmp_path)

    def title(page: str) -> str:
        h = (out / page / "index.html").read_text(encoding="utf-8")
        return h[h.index("<title>") + 7:h.index("</title>")]

    site = "Qué decide el Ayuntamiento · Yecla"
    assert title("") == site
    expected = {"2026": "Dinero de 2026", "2026/decisiones": "Decisiones de 2026",
                "2026/decisiones/2026-01": "Decisiones de enero de 2026", "2026/permisos": "Permisos de 2026",
                "votaciones": "Votaciones de 2023-2027", "buscar": "Buscar",
                "2026/dinero": "Todo el dinero de 2026, por entidad",
                "decision/2026-01-07_JGL_01-0": "Pago de facturas de recogida de basura (7 de enero de 2026)"}
    for page, name in expected.items():
        assert title(page) == f"{name} · {site}", page
    for f in out.rglob("*.html"):
        h = f.read_text(encoding="utf-8")
        if "<title>" in h:
            assert re.search(r"<title>[^<]*Qué decide el Ayuntamiento · Yecla</title>", h), f
