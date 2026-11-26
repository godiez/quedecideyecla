import re

import pytest

from actas.web import model
from actas.web.pages import entities, info, votes

J1, P3 = "2026-01-07_JGL_01", "2026-03-02_PLENO_03"


@pytest.fixture
def site(mini_analysis):
    a, db = mini_analysis
    return model.build(a, db, 2026)


def test_entity_page_with_movements(site, archive):
    pages = dict(entities.generate_entities(archive))
    actua = next(x for x in site.entities.values() if x.name.startswith("Actúa"))
    h = pages[f"entidad/{actua.slug}/"]
    assert "Empresa" in h and "50.000,00 €" in h
    assert f'href="../../decision/{J1}-0/"' in h
    assert "Pago" in h
    gomez = next(x for x in site.entities.values() if x.name.startswith("Construcciones"))
    assert f'href="../../decision/{J1}-2/"' in pages[f"entidad/{gomez.slug}/"]


def test_permits_without_private_persons(site):
    h = dict(entities.generate(site))["2026/permisos/"]
    assert "Construcciones Gómez, S.L." in h
    assert "<h2>Suelo no urbanizable</h2>" in h
    assert "Vivienda en suelo no urbanizable" in h and "un particular" in h
    assert "C/ Mayor" not in h
    for slug in re.findall(r'href="\.\./\.\./entidad/([^/"]+)/"', h):
        assert slug in site.entities


def test_votes_six_pairs(archive):
    h = dict(votes.generate(archive))["votaciones/"]
    table = h[h.index("Cuántas veces votan igual"):]
    table = table[:table.index("</table>")]
    assert table.count("<tr>") == 7
    assert ('<span class="party party-psoe">PSOE</span> y <span class="party party-iu-verdes">IU‑Verdes</span>'
            in table and "1/1" in table)
    assert f'href="../decision/{P3}-0/"' in h
    assert h.count('<span class="seat party-') == 21 and h.count("seat party-pp") == 9
    assert "hacen falta 11" in h and 'aria-label="Concejales por grupo: PP 9, PSOE 7, Vox 3, IU-Verdes 2"' in h
    assert '<span class="group-seats">9 concejales</span>' in h and "El Pleno tiene" not in h


def test_how_it_was_made(archive):
    h = dict(info.generate(archive))["como-se-ha-hecho/"]
    assert 'href="https://yecla.es/2026-actas-jgl/"' in h
    assert 'href="https://yecla.es/sesiones-pleno-del-ayuntamiento-2026/"' in h
    assert "quedecideyecla@gmail.com" in h
    assert '<h2 id="proceso">Cómo se procesan</h2>' in h
    assert re.search(r'<video controls preload="none" playsinline poster="\.\./static/presentacion\.jpg\?v=\w+"', h)
    assert re.search(r'<source src="\.\./static/presentacion\.mp4\?v=\w+" type="video/mp4">', h)
    assert '<li><a href="../2026/permisos/">Permisos</a>: quién pide licencias de obra y de actividad.</li>' in h
    assert '<li><a href="../buscar/">Buscar</a>: una calle, un tema, una empresa o un número de expediente.</li>' in h
    assert "formada por el alcalde o la alcaldesa y algunos concejales y concejalas" in h
    assert "reúne a los 21 concejales y concejalas" in h and "Todos los concejales y concejalas presentes" in h
    rows = re.findall(r'<ul class="year-links">(.*?)</ul>', h, re.S)
    assert len(rows) == 2
    sources, downloads = (re.findall(r'<li><span class="year">(\d{4})</span> <a [^>]*>([^<]+)</a> · <a [^>]*>([^<]+)</a></li>', r)
                          for r in rows)
    assert sources[0] == ("2026", "Junta de Gobierno", "Pleno")
    assert downloads[0] == ("2026", "dinero por entidad", "todas las decisiones")
    assert "desde 2026:</p>" in h
    # Said only once on the page (the notice and the footer come from the template)
    main = h[h.index("<main"):h.index("</main>")]
    assert "no tiene relación" not in main and "Datos de las actas del" not in main
    assert main.count(">Junta de Gobierno<") <= 7 and '<dt id="pleno">' not in main and '<dt id="junta-de-gobierno">' not in main
    assert '<a href="#comprometido">comprometido</a>' in main and '<a href="#pendiente-de-clasificar">' in main


def test_votes_per_group_and_mobile_table(archive):
    pages = dict(votes.generate(archive))
    h = pages["votaciones/"]
    for g in ("pp", "psoe", "vox", "iu-verdes"):
        assert f'href="{g}/"' in h
    assert 'data-label="PSOE"' in h and 'data-label="IU-Verdes"' in h
    vox = pages["votaciones/vox/"]
    assert "<h1>Cómo vota Vox en el Pleno</h1>" in vox
    assert '<span class="visually-hidden">Cómo vota </span><span class="party party-vox">Vox</span>' in vox
    assert 'href="./" aria-current="page"' in vox and 'data-label="Vox" class="party-vox"' in vox
    assert "En contra" in vox and f'href="../../decision/{P3}-0/"' in vox
    assert "Aprobado" in vox


def test_same_result_in_votes_and_detail(archive):
    h = dict(votes.generate(archive))["votaciones/"]
    assert '<td data-label="Resultado">Aprobado</td>' in h and "aprobada" not in h


def test_entity_page_short_figure_and_no_repeated_phase_column(site, archive):
    pages = dict(entities.generate_entities(archive))
    actua = next(x for x in site.entities.values() if x.name.startswith("Actúa"))
    h = pages[f"entidad/{actua.slug}/"]
    assert '<p class="figure">50.000 €</p>' in h and "50.000,00 €" in h
    assert "<th>Fase</th>" not in h  # all its movements are payments
    assert "comprometidos en 2026" in h
    assert "«—» en adjudicado: sin adjudicación en las actas de ese año" in h


def test_entity_page_one_row_per_year(two_years):
    root, db = two_years
    arc = model.build_archive(root, db)
    actua = next(h for h in arc.entities.values() if h.name.startswith("Actúa"))
    assert list(actua.years) == [2026, 2022]
    h = dict(entities.generate_entities(arc))[f"entidad/{actua.slug}/"]
    table = h[h.index("<h2>Cada año</h2>"):]
    table = table[:table.index("</table>")]
    assert re.findall(r"<tr><th>(\d{4})</th>", table) == ["2026", "2022"]
    assert "30.000,00 €" in table and "50.000,00 €" in table and "Total" not in table
    assert '<p class="figure">50.000 €</p>' in h and "comprometidos en 2026" in h
    movements = h[h.index("Movimientos en las actas"):]
    assert movements.index("2026") < movements.index("2022")


def test_votes_per_legislature_with_their_own_groups(two_years):
    root, db = two_years
    pages = dict(votes.generate(model.build_archive(root, db)))
    old = pages["votaciones/2019-2023/"]
    assert "Legislatura 2019-2023" in old and "party-vox" not in old
    assert '<span class="group-seats">12 concejales</span>' in old and "seat party-cs" in old
    assert 'href="../"' in old
    assert "votaciones/2019-2023/cs/" in pages and "votaciones/vox/" in pages
    assert "Moción sobre el agua" not in pages["votaciones/"]


def test_vote_card_for_phones_gathers_groups_by_stance(archive):
    pages = dict(votes.generate(archive))
    h = pages["votaciones/"]
    card = h[h.index('<div class="vote-card">'):]
    card = card[:card.index("</div>")]
    assert '<p class="vote-meta">' in card and " · Aprobado</p>" in card
    assert '<dl class="vote-groups"><dt>A favor</dt>' in card
    assert card.count('<span class="party ') == 4
    vox = pages["votaciones/vox/"]
    assert '<p class="vote-stance">Votó: <b>' in vox and '<dl class="vote-groups">' not in vox


def test_seat_strip_separates_groups_with_seats_of_the_same_size(archive):
    h = dict(votes.generate(archive))["votaciones/"]
    assert h.count('<span class="group-gap"></span>') == 3  # four groups: a gap before each but the first
    assert ("--columns: repeat(9, minmax(0, 1fr)) 1px repeat(7, minmax(0, 1fr)) 1px repeat(3, minmax(0, 1fr)) 1px "
            "repeat(2, minmax(0, 1fr))") in h
    assert "--majority-columns: 12" in h  # 11 seats and the gap between PP and PSOE
    assert "group-start" not in h


def test_the_majority_bracket_counts_only_the_gaps_it_crosses(monkeypatch):
    monkeypatch.setitem(votes.LEGISLATURES, "2019-2023", {"PP": 11, "PSOE": 6, "Cs": 2, "IU-Verdes": 2})
    assert "--majority-columns: 11" in votes._seats("2019-2023")


def test_info_promises_no_review_and_links_to_errors(archive):
    from actas.web.pages import info
    h = dict(info.generate(archive))["como-se-ha-hecho/"]
    assert "En el futuro" not in h and "revisa todavía" not in h
    assert "Revisado por una persona" not in h
    assert 'href="#errores">avísanos</a>' in h and '<h2 id="errores">Avísanos de los errores</h2>' in h


def test_legal_notice_linked_from_every_footer(archive):
    from actas.web.pages import info, legal
    h = dict(legal.generate(archive))["aviso-legal/"]
    assert "<h1>Aviso legal</h1>" in h and "No está hecha contra nadie" in h
    assert '<h2>Responsable</h2>\n<p>Diego Ibáñez Ortuño, a título personal. Contacto: <a href="mailto:quedecideyecla@gmail.com">' in h
    assert "linkedin" not in h.lower()
    assert "artículo 13 de la Ley de Propiedad Intelectual" in h and "no usa cookies" in h
    assert 'href="../como-se-ha-hecho/#proceso"' in h
    assert 'href="../aviso-legal/">Aviso legal</a>' in dict(info.generate(archive))["como-se-ha-hecho/"]


def test_the_code_is_linked_from_the_legal_notice_and_how_it_is_made(archive):
    from actas.web.pages import info, legal
    link = '<a href="https://github.com/godiez/quedecideyecla" target="_blank" rel="noopener">'
    assert f"{link}El código de la web</a> es libre, con licencia MIT." in dict(legal.generate(archive))["aviso-legal/"]
    assert f"{link}github.com/godiez/quedecideyecla</a>." in dict(info.generate(archive))["como-se-ha-hecho/"]
