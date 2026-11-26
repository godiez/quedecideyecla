import json

import pytest

from actas import money
from actas.web import model
from actas.web.pages import data, decisions, entities
from actas.web.pages import money as pm


def _award(doc, eur_lines, case_file="712712D"):
    return {"doc": doc, "fecha": doc[:10], "organo": "PLENO", "puntos": [{
        "id": f"{doc}:0", "ref": "1", "titulo": "Adjudicación de la basura", "categoria": "contrato",
        "importe_eur": max(eur_lines), "expediente": case_file,
        "entidades": [{"nombre": "Actúa, S.L.", "tipo": "empresa", "rol": "adjudicatario"}],
        "importes": [{"entidad": "Actúa, S.L.", "concepto": c, "eur": v} for c, v in eur_lines.items()]}]}


def test_counted_replaces_the_award_of_the_case_file_only():
    docs = [_award("2024-11-04_PLENO_15", {"Precio anual con IVA": 4383778.45, "Total 12 años": 52605341.40})]
    plain = money.compute(docs, {})["ranking"][0]
    assert plain["adjudicado"] == 52605341.40
    r = money.compute(docs, {}, {("Actúa, S.L.", "712712D"): 4383778.45})
    assert r["ranking"][0]["adjudicado"] == r["ranking"][0]["comprometido"] == 4383778.45
    assert max(m["eur"] for m in r["movimientos"]) == 52605341.40
    other = money.compute(docs, {}, {("Actúa, S.L.", "999999Z"): 1.0})["ranking"][0]
    assert other["adjudicado"] == 52605341.40


NOTE = {"año": 2026, "entidad": "Actúa, Servicios y Medio Ambiente, S.L.", "expediente": "1186986R",
        "titulo": "Contrato de 12 años", "texto": "Se cuenta un solo año."}


@pytest.fixture
def noted(mini_analysis):
    a, db = mini_analysis
    (a.parent / "avisos.json").write_text(json.dumps({"avisos": [NOTE]}, ensure_ascii=False), encoding="utf-8")
    return model.build_archive(a.parent, db)


def test_note_shows_on_home_ranking_entity_decision_and_csv(noted):
    site = noted.latest
    actua = next(x for x in site.ranking if x.name.startswith("Actúa"))
    assert [n.title for n in actua.notes] == ["Contrato de 12 años"]
    home = dict(pm.generate(site))["2026/"]
    assert 'Actúa, Servicios y Medio Ambiente, S.L.</a><sup class="flag"' in home
    assert "* <a href=\"../entidad/" in home and "Contrato de 12 años. Se cuenta un solo año." in home
    ranking = dict(pm.generate(site))["2026/dinero/"]
    assert ranking.count('<sup class="flag"') == 1 and "Contrato de 12 años. Se cuenta un solo año." in ranking
    h = noted.entities[actua.slug]
    page = entities.detail(noted, h)
    assert '<aside class="callout"><p><b>Contrato de 12 años (2026).</b> Se cuenta un solo año.</p></aside>' in page
    assert '<th>2026<sup class="flag"' in page
    d = next(x for x in site.decisions.values() if x.case_file == "1186986R")
    assert "<b>Contrato de 12 años.</b>" in decisions.detail(site, d)
    others = [x for x in site.decisions.values() if x.case_file != "1186986R"]
    assert all(not x.notes for x in others)
    assert "Contrato de 12 años. Se cuenta un solo año." in data.money_csv(site)


def test_note_for_an_entity_without_page_fails(mini_analysis):
    a, db = mini_analysis
    bad = {**NOTE, "entidad": "Empresa que no existe, S.L."}
    (a.parent / "avisos.json").write_text(json.dumps({"avisos": [bad]}), encoding="utf-8")
    with pytest.raises(ValueError, match="no tiene ficha en 2026"):
        model.build_archive(a.parent, db)


def test_no_notes_file_is_fine(archive):
    assert all(not x.notes for x in archive.latest.entities.values())
