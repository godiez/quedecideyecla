import json

from actas.web import build
from actas.web.pages import search


def test_index_has_the_searchable_fields_and_no_people(archive):
    rows = search.decision_rows(archive, 2026)
    by_slug = {r[0]: r for r in rows}
    pay = by_slug["2026-01-07_JGL_01-0"]
    assert pay[1] == "Pago de facturas de recogida de basura"
    assert pay[2] == "Junta de Gobierno · 7 de enero de 2026 · 50.000 €"
    assert pay[4] == "Actúa, Servicios y Medio Ambiente, S.L." and pay[6] == "1186986R"
    rustic = by_slug["2026-01-07_JGL_01-3"]
    assert rustic[4] == "un particular" and rustic[5] == ""  # the house of a person: no address
    assert len(rows) == len(archive.sites[2026].decisions)
    ents = {r[1]: r for r in search.entity_rows(archive)}
    assert ents["Actúa, Servicios y Medio Ambiente, S.L."][2] == "Empresa · 2026"
    assert ents["Actúa, Servicios y Medio Ambiente, S.L."][3] == 2026


def test_built_site_has_search_page_and_indexes(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    build.build_site(a.parent, db, out)
    h = (out / "buscar" / "index.html").read_text(encoding="utf-8")
    assert '<input type="search" id="q" name="q"' in h and "<noscript>" in h
    assert 'src="../static/search.js?v=' in h
    config = json.loads(h.split('<script id="search-indexes" type="application/json">')[1].split("</script>")[0])
    assert config["years"]["2026"].startswith("decisiones-2026.json?v=")
    assert config["entities"].startswith("entidades.json?v=")
    assert json.loads((out / "buscar" / "decisiones-2026.json").read_text(encoding="utf-8"))
    assert (out / "static" / "search.js").exists()
    home = (out / "index.html").read_text(encoding="utf-8")
    assert '<form class="search-form compact" role="search" action="buscar/" method="get">' in home
    assert '<label for="q" class="visually-hidden">' in home
    assert 'placeholder="Busca en todas las actas"' in home
    assert "Resumen de las actas" not in home
    assert "Últimas decisiones de 2026" in home and "Lo último que se ha decidido" not in home
    assert '<a href="buscar/">Buscar</a>' in home
    decisions = (out / "2026" / "decisiones" / "index.html").read_text(encoding="utf-8")
    assert "Filtrar estas decisiones" in decisions
