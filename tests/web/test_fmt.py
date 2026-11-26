from datetime import date

from actas.revision.data import CATEGORIES
from actas.web import fmt as f


def test_eur():
    assert f.eur(16243.77) == "16.243,77 €"
    assert f.eur(0) == "0,00 €"
    assert f.eur(1234567.891) == "1.234.567,89 €"


def test_eur_short():
    assert f.eur_short(4110843) == "4,11 M€"
    assert f.eur_short(850000) == "850.000 €"
    assert f.eur_short(9850) == "9.850 €"


def test_long_date():
    assert f.long_date(date(2026, 10, 14)) == "14 de octubre"
    assert f.long_date(date(2026, 1, 1)) == "1 de enero"


def test_slug():
    assert f.slug('Asociación "Amigos" <Yecla> & Cía / 2026') == "asociacion-amigos-yecla-cia-2026"
    assert f.slug("¡¡!!") == "entidad"
    assert len(f.slug("a" * 200)) <= 60
    assert not f.slug("a" * 59 + " b").endswith("-")


def test_rel():
    assert f.rel("entidad/actua/", "decision/x-1/") == "../../decision/x-1/"
    assert f.rel("", "dinero/") == "dinero/"
    assert f.rel("dinero/", "") == "../"
    assert f.rel("", "") == "./"
    assert f.rel("dinero/", "static/style.css") == "../static/style.css"


def test_topics_cover_every_category():
    every = [c for cats in f.TOPICS.values() for c in cats]
    assert sorted(every) == sorted(CATEGORIES)
    assert len(every) == len(set(every))
    assert f.topic("via_publica_eventos") == "Fiestas y vía pública"
    assert f.topic("desconocida") == "Otros"


def test_e_escapes():
    assert f.e('<a href="x">&') == "&lt;a href=&quot;x&quot;&gt;&amp;"
    assert f.e(None) == ""
