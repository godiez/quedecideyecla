import re

import pytest

from actas.web import model
from actas.web.fmt import TOPICS, slug
from actas.web.pages import decisions as pd

J1, J7, P3 = "2026-01-07_JGL_01", "2026-02-03_JGL_07", "2026-03-02_PLENO_03"


@pytest.fixture
def site(mini_analysis):
    a, db = mini_analysis
    return model.build(a, db, 2026)


@pytest.fixture
def pages(site):
    return dict(pd.generate(site))


def test_one_section_per_session_in_order(pages):
    h = pages["2026/decisiones/todas/"]
    assert re.findall(r'<section class="edition" id="([^"]+)"', h) == [P3, J7, J1]
    assert "Pleno · <em>2 de marzo de 2026</em> · ordinaria" in h


def test_fifth_decision_folded(pages):
    h = pages["2026/decisiones/todas/"]
    j1 = h[h.index(f'id="{J1}"'):]
    j1 = j1[:j1.index("</section>")]
    folded = j1[j1.index("<details>"):]
    assert '<span class="when-closed">+ 1 asunto más de esta reunión</span>' in folded
    assert '<span class="when-open">− Ocultar el asunto</span>' in folded
    assert '<button type="button" class="collapse" hidden>↑ Ocultar el asunto</button>' in folded
    assert "Comisión de servicios de un policía" in folded
    assert "Comisión de servicios" not in j1[:j1.index("<details>")]


def test_articles_with_valid_topic(pages):
    h = pages["2026/decisiones/todas/"]
    topics = re.findall(r'<article class="item" data-topic="([^"]*)"', h)
    assert len(topics) == 10 and set(topics) <= set(TOPICS)
    assert 'data-text="visita guiada al castillo' in h
    for t in TOPICS:
        assert f'<option value="{t}">' in h.split('<select id="topic"')[1].split("</select>")[0]


def test_detail_with_vote(pages):
    h = pages[f"decision/{P3}-0/"]
    for g in ("PP", "PSOE", "Vox", "IU-Verdes"):
        assert f'<th><span class="party party-{slug(g)}">{g.replace("-", "‑")}</span></th>' in h
    assert "Ver el acta oficial (PDF), página" in h and "(aproximada)" in h
    assert 'href="https://yecla.es/actas/PLENO03.pdf#page=2"' in h
    assert "Resumen automático, sin revisar por una persona. <a href=\"../../como-se-ha-hecho/#proceso\">Cómo se ha hecho</a>" in h


def test_detail_without_pdf_and_reviewed(pages):
    assert "Enlace al acta no disponible" in pages[f"decision/{J7}-0/"]
    # Nothing is marked as reviewed on the site, even a decision corrected in revision.json
    assert "Revisado por una persona" not in pages[f"decision/{P3}-2/"]
    assert "sin revisar por una persona" in pages[f"decision/{P3}-2/"]


def test_discarded_not_generated_nor_linked(pages):
    assert f"decision/{P3}-1/" not in pages
    for h in pages.values():
        assert f"{P3}-1/" not in h


def test_mailto_and_private_person(pages):
    h = pages[f"decision/{J1}-3/"]
    assert f'href="mailto:quedecideyecla@gmail.com?subject=Error%20en%20{J1}-3"' in h
    assert "un particular" in h and "C/ Mayor" not in h
    actua = pages[f"decision/{J1}-0/"]
    assert re.search(r'href="\.\./\.\./entidad/[a-z0-9-]+/">Actúa', actua)


def test_decisions_home_only_latest_month(pages):
    h = pages["2026/decisiones/"]
    assert re.findall(r'<section class="edition" id="([^"]+)"', h) == [P3]
    assert 'href="2026-02/"' in h and 'href="2026-01/"' in h and 'href="todas/"' in h
    assert '<a href="2026-03/" aria-current="page">Marzo</a>' in h
    assert "<h1>Marzo</h1><details class=\"month-picker\"><summary>Cambiar de mes" in h
    assert h.index('href="2026-01/"') < h.index('href="2026-03/"')
    assert "Qué ha decidido" not in h


def test_month_and_whole_year_marked_in_selector(pages):
    jan = pages["2026/decisiones/2026-01/"]
    assert 'aria-current="page">Enero</a>' in jan and "<h1>Enero</h1>" in jan
    whole = pages["2026/decisiones/todas/"]
    assert 'aria-current="page">Todo 2026, con buscador</a>' in whole and "<h1>Todo el año</h1>" in whole


def test_official_record_opens_in_another_tab(pages):
    h = next(v for k, v in pages.items() if k.startswith("decision/") and "Ver el acta oficial" in v)
    assert 'target="_blank" rel="noopener">Ver el acta oficial' in h and "se abre en otra pestaña" in h


def test_monthly_pages_and_whole_year(pages):
    assert re.findall(r'<section class="edition" id="([^"]+)"', pages["2026/decisiones/2026-01/"]) == [J1]
    assert re.findall(r'<section class="edition" id="([^"]+)"', pages["2026/decisiones/2026-02/"]) == [J7]
    assert re.findall(r'<section class="edition" id="([^"]+)"', pages["2026/decisiones/todas/"]) == [P3, J7, J1]


def test_detail_links_to_its_month(pages):
    assert f'href="../../2026/decisiones/2026-01/#{J1}"' in pages[f"decision/{J1}-0/"]


def test_filters_hidden_without_javascript(pages):
    h = pages["2026/decisiones/todas/"]
    assert '<div class="filters" hidden>' in h
    assert 'aria-live="polite"' in h


def test_detail_without_repeated_result_below_the_vote(pages):
    h = pages[f"decision/{P3}-0/"]
    assert "Resultado: aprobada" not in h
    assert '<p class="summary-line">Aprobado · 349.077,00 € · Pleno, 2 de marzo de 2026</p>' in h


def test_folded_with_many_items_says_how_many_when_hiding(site):
    from actas.web.pages.decisions import _folded
    h = _folded("2026/decisiones/todas/", site.sessions[2].decisions * 7)
    n = len(site.sessions[2].decisions) * 7
    assert f'<span class="when-open">− Ocultar los {n} asuntos</span>' in h


def test_filter_by_body(pages):
    h = pages["2026/decisiones/todas/"]
    sel = h.split('<select id="body"')[1].split("</select>")[0]
    assert '<option value="JGL">Junta de Gobierno</option>' in sel and '<option value="PLENO">Pleno</option>' in sel
    assert f'<section class="edition" id="{P3}" data-body="PLENO"' in h
    assert f'<section class="edition" id="{J1}" data-body="JGL"' in h


def test_lede_explains_the_order_and_links_to_how_it_was_made(pages, archive):
    from actas.web.pages import info
    h = pages["2026/decisiones/2026-01/"]
    assert "Primero salen los asuntos con más dinero o más interés para el vecino" in h
    assert 'href="../../../como-se-ha-hecho/#orden">Cómo se ordenan</a>' in h
    assert '<li id="orden">' in dict(info.generate(archive))["como-se-ha-hecho/"]


def test_vote_counts_centred_and_zeros_marked(pages):
    h = pages[f"decision/{P3}-0/"]
    assert '<th class="count">A favor</th>' in h
    assert '<td class="count zero">0</td>' in h and re.search(r'<td class="count">[1-9]\d*</td>', h)


def test_tax_rebates_show_no_breakdown(site):
    from dataclasses import replace
    d = next(x for x in site.decisions.values() if x.amounts)
    rebate = replace(d, category="fiscal", title="Rebaja del 50 % del impuesto de obras a Almazara por su nave")
    assert pd.is_tax_rebate(rebate) and "Desglose del dinero" not in pd.detail(site, rebate)
    assert "Desglose del dinero" in pd.detail(site, d)
    assert not pd.is_tax_rebate(replace(d, category="fiscal", title="Padrón del impuesto de vehículos 2024"))
    assert not pd.is_tax_rebate(replace(d, category="pago_factura", title="Rebaja del 10 % en la factura de luz"))


def test_income_says_so_and_ticket_sales_explain_the_write_off(site):
    from dataclasses import replace
    d = next(x for x in site.decisions.values() if x.amount_eur)
    tickets = replace(d, title="Taquilla del espectáculo 'Miradas' en el Teatro Concha Segura", amount_eur=2226.0)
    assert pd.amount_label(tickets) == "2.226,00 € (ingreso)"
    h = pd.detail(site, tickets)
    assert "<th>Importe</th><td>2.226,00 € (ingreso)</td>" in h and "no es una pérdida" in h
    roll = replace(d, title="Padrón 2022 de la tasa de vados", amount_eur=457671.0)
    assert pd.amount_label(roll).endswith("(ingreso)") and "no es una pérdida" not in pd.detail(site, roll)
    assert "(ingreso)" not in pd.amount_label(d)


def test_income_does_not_count_when_ordering():
    from types import SimpleNamespace as N
    roll = N(title="Padrón del impuesto de vehículos 2024", amount_eur=1_900_000.0, amounts=[], category="fiscal", summary="")
    works = N(title="Asfaltado de la calle Mayor", amount_eur=50_000.0, amounts=[], category="contrato", summary="")
    assert model.spent(roll) == 0 and model.spent(works) == 50_000.0
    assert sorted([roll, works], key=lambda d: -model.spent(d))[0] is works


@pytest.mark.parametrize("title, income", [
    ("Padrón del impuesto de vehículos 2024", True), ("Padrones 2025: cotos de caza y kioscos", True),
    ("Recaudación del Concierto de Santa Cecilia", True), ("Taquilla de 'Pinocho'", True),
    ("Moción para multar el empadronamiento irregular", False), ("Yecla se suma a las ayudas para el padrón", False),
    ("Comunicaciones: padrón de 35.957 vecinos", False), ("Auxiliar interino para la Oficina de Recaudación", False),
    ("Liquidación de la venta de entradas de un concierto", True), ("Recibos del agua y de la basura", True),
    ("Reparto de los recibos del IBI urbano para Envíos Megarejo", False),
    ("Venta para desguace de los coches abandonados del depósito", True), ("Tres puestos de venta ambulante", True),
    ("Alquiler de un almacén para la Brigada de Obras", False),
])
def test_income_titles(title, income):
    from types import SimpleNamespace as N
    assert model.is_income(N(title=title, summary="")) is income


def test_one_income_rule_for_the_ledger_and_the_web():
    from actas import money
    title = "Liquidación de la venta de entradas de un concierto en el Teatro Concha Segura"
    assert money.phase({"titulo": title, "categoria": "presupuesto_hacienda"}) == "ingreso"
    assert money.TICKETS.search(title)
    assert money.phase({"titulo": "Contrato para ensobrar y enviar los recibos del IBI 2025",
                        "categoria": "contrato"}) != "ingreso"


def test_no_results_message_is_in_the_live_counter(pages):
    h = pages["2026/decisiones/todas/"]
    # filters.js writes «Ninguna decisión coincide.» in the counter (aria-live); the paragraph only has the button
    assert '<p class="counter" id="counter" aria-live="polite"></p>' in h
    assert '<p class="no-results" id="no-results" hidden><button type="button" id="clear">' in h


def test_breakdown_that_does_not_add_up_says_so(site):
    from dataclasses import replace
    d = next(x for x in site.decisions.values() if x.amounts)
    lines = [{"entity": "FCC Aqualia, S.A.", "slug": None, "concept": "Agua", "eur": 600.0},
             {"entity": "FCC Aqualia, S.A.", "slug": None, "concept": "Canon", "eur": 400.0}]
    assert "suman 1.000,00 €" in pd.detail(site, replace(d, amounts=lines, amount_eur=600.0))
    assert "suman" not in pd.detail(site, replace(d, amounts=lines, amount_eur=1000.0))
    assert "es la suma de estas cantidades" in pd.detail(site, replace(d, amounts=lines, amount_eur=1000.0))
    assert "es la suma" not in pd.detail(site, replace(d, amounts=lines, amount_eur=600.0))
    assert "es la suma" not in pd.detail(site, replace(d, amounts=lines[:1], amount_eur=600.0))


def test_a_guarantee_says_so_and_does_not_count_when_ordering(site):
    from dataclasses import replace
    from actas.web import model as m
    d = next(x for x in site.decisions.values() if x.amounts)
    lines = [{"entity": None, "slug": None, "concept": "Fianza por reposición de urbanización", "eur": 347.23},
             {"entity": None, "slug": None, "concept": "Fianza por cables de alumbrado", "eur": 175.51}]
    g = replace(d, title="Licencia para demoler un inmueble", amounts=lines, amount_eur=522.74)
    assert pd.amount_label(g) == "522,74 € (fianza)" and m.spent(g) == 0
    mixed = replace(g, amounts=lines + [{"entity": None, "slug": None, "concept": "Precio", "eur": 1000.0}])
    assert not m.is_guarantee(mixed)


def test_a_grant_request_is_not_shown_as_money_received(site):
    from dataclasses import replace
    from actas.web import model as m
    d = next(x for x in site.decisions.values() if x.amount_eur)
    req = replace(d, category="subvencion_recibida", title="Se piden 22.165 € a Juventud para orientar a jóvenes",
                  amount_eur=22165.0, entities=[{"name": "Dirección General de Juventud", "slug": None,
                                                 "type": "organismo_publico", "role": "da subvención"}])
    assert pd.amount_label(req) == "22.165,00 € (solicitud)" and m.spent(req) == 0
    assert "a quien se pide la subvención" in pd.detail(site, req) and "da subvención" not in pd.detail(site, req)
    got = replace(req, title="Se acepta una subvención de 22.165 € de Juventud")
    assert pd.amount_label(got) == "22.165,00 €"


def test_income_told_by_the_summary_when_the_title_does_not():
    from actas import money
    bar = "Se adjudica el bar de las Fiestas de San Isidro a quien más paga: 4.650 €, que paga al Ayuntamiento."
    assert money.is_income("Adjudicado el bar de las Fiestas de San Isidro", bar)
    assert money.is_income("Auditorio para una boda civil", "Se autoriza, previo pago del precio público de 120 €.")
    assert not money.is_income("Auditorio gratis para una asociación", "Se cede sin pagar el precio público de 120 €.")
    assert not money.is_income("Reforma del bar del centro de mayores", "Se adjudica la obra por 30.000 €.")


def test_income_breakdown_says_the_entity_collects_it(site):
    from dataclasses import replace
    d = next(x for x in site.decisions.values() if x.amounts)
    roll = replace(d, title="Padrones del agua y de la basura", amount_eur=1000.0,
                   amounts=[{"entity": "FCC Aqualia, S.A.", "slug": None, "concept": "Tasa de basura", "eur": 1000.0}])
    assert "quien lo recauda o lo paga, no quien lo recibe" in pd.detail(site, roll)
