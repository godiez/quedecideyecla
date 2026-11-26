import re

import pytest

from actas.web import model
from actas.web.pages import money as pm


@pytest.fixture
def site(mini_analysis):
    a, db = mini_analysis
    return model.build(a, db, 2026)


def _pages(site):
    return dict(pm.generate(site, root=True))


def test_home_headline_and_total(site):
    h = _pages(site)[""]
    assert "<h1>¿A dónde va el dinero de Yecla?</h1>" in h
    assert "En 2026 el Ayuntamiento ha comprometido <b>50.000 €</b> con empresas." in h
    assert 'href="2026/decisiones/"' in h
    assert '<a href="2026/dinero/">Todo el dinero de 2026, por entidad →</a>' in h and "Ver todas" not in h
    year_home = _pages(site)["2026/"]
    assert '<a href="dinero/">Todo el dinero de 2026, por entidad →</a>' in year_home
    assert 'href="decisiones/"' in year_home


def test_top_only_companies(site):
    h = _pages(site)[""]
    top = re.search(r'<ol class="bars">.*?</ol>', h, re.S).group(0)
    assert "Actúa" in top
    assert "Talleres" not in top and "SPANDY" not in top


def test_pending_line(site):
    h = _pages(site)[""]
    assert "y 12.000 € de entidades pendientes de clasificar." in h


def test_latest_decided(site):
    h = _pages(site)[""]
    assert "Préstamo de 349.077 euros" in h
    assert "Pleno · 2 de marzo" in h


def test_money_three_sections(site):
    h = _pages(site)["2026/dinero/"]
    for t in ("Empresas", "Asociaciones e instituciones", "Pendiente de clasificar"):
        assert f"<h2>{t}</h2>" in h
    assert "Consorcio de las Vías Verdes" in h
    assert "Todavía no sabemos con seguridad qué tipo de entidad es. Si lo sabes, <a href=\"mailto:quedecideyecla@gmail.com" in h


def test_no_link_to_missing_entity(site):
    for path, h in pm.generate(site):
        for slug in re.findall(r'href="(?:\.\./)*entidad/([^/"]+)/"', h):
            assert slug in site.entities, (path, slug)
