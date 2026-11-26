import json
from pathlib import Path

import pytest

from actas import money, sources

ANALYSIS = Path(__file__).resolve().parents[1] / "analisis" / "2026"


def _docs(*points, doc="2026-01-07_JGL_01"):
    return [{"doc": doc, "fecha": "2026-01-07", "organo": "JGL",
             "puntos": [{**p, "id": f"{doc}:{i}", "revision": "pendiente"} for i, p in enumerate(points)]}]


def test_fee_and_guarantee_do_not_count_as_income():
    p = {"ref": "1", "titulo": "Adjudicación de la concesión de la zona azul", "categoria": "contrato",
         "importe_eur": 66000, "entidades": [{"nombre": "Continental Parking, S.L.", "tipo": "empresa",
                                              "rol": "adjudicatario"}],
         "importes": [
             {"entidad": "Continental Parking, S.L.",
              "concepto": "Canon anual que paga la concesionaria al Ayuntamiento", "eur": 63000},
             {"entidad": "Continental Parking, S.L.", "concepto": "garantía definitiva", "eur": 3000}]}
    out = money.compute(_docs(p), {})
    assert not any("CONTINENTAL" in r["clave"] for r in out["ranking"])


def test_movements_carry_point_id():
    p = {"ref": "1", "titulo": "Pago de facturas", "categoria": "pago_factura", "importe_eur": 100,
         "entidades": [{"nombre": "FCC Aqualia, S.A.", "tipo": "empresa", "rol": "cobra"}]}
    out = money.compute(_docs(p), {})
    assert out["movimientos"][0]["id"] == "2026-01-07_JGL_01:0"


@pytest.mark.skipif(not (ANALYSIS / "json").exists(), reason="sin datos reales")
def test_regression_2026():
    alias = json.loads((ANALYSIS / "alias.json").read_text(encoding="utf-8"))
    out = money.compute(sources.load_docs(ANALYSIS), alias)
    assert out["ranking"][0]["entidad"].startswith("Actúa")
    private = sum(r["comprometido"] for r in out["ranking"] if not r["publica"])
    assert 16.6e6 < private < 16.8e6


def _grant(name, kind, eur=1000, cat="subvencion_concedida", title="Subvención nominativa"):
    ent = {"nombre": name, "rol": "beneficiario"}
    if kind:
        ent["tipo"] = kind
    return {"ref": "1", "titulo": title, "categoria": cat, "importe_eur": eur, "entidades": [ent]}


def _classes(*points, aliases=None):
    out = money.compute(_docs(*points), aliases or {})
    return {r["entidad"]: r["clase"] for r in out["ranking"]}, out


def test_class_by_type_and_legal_form():
    classes, _ = _classes(
        _grant("Actúa, Servicios y Medio Ambiente, S.L.", "empresa", cat="pago_factura", title="Pago de facturas"),
        _grant("Sociedad Protectora de Animales de Yecla (SPANDY)", "asociacion"),
        _grant("U.T.E. Edificio de Cazadores", None, cat="pago_factura", title="Pago de facturas"),
        _grant("Talleres Pérez C.B.", None, cat="pago_factura", title="Pago de facturas"),
    )
    assert classes["Actúa, Servicios y Medio Ambiente, S.L."] == "empresa"
    assert classes["Sociedad Protectora de Animales de Yecla (SPANDY)"] == "asociacion_institucion"
    assert classes["U.T.E. Edificio de Cazadores"] == "empresa"
    assert classes["Talleres Pérez C.B."] == "pendiente"


def test_manual_class_wins():
    classes, _ = _classes(_grant("Talleres Pérez C.B.", None, cat="pago_factura", title="Pago de facturas"),
                        aliases={"_clase": {"Talleres Pérez C.B.": "empresa"}})
    assert classes["Talleres Pérez C.B."] == "empresa"


def test_tied_types_is_pending():
    a = _grant("Grupo Raro", "empresa")
    b = _grant("Grupo Raro", "asociacion")
    classes, _ = _classes(a, b)
    assert classes["Grupo Raro"] == "pendiente"


def test_natural_person_excluded():
    p = {"ref": "1", "titulo": "Pago de facturas", "categoria": "pago_factura", "importe_eur": 1234,
         "entidades": [{"nombre": "Juan García López", "tipo": "particular", "rol": "cobra"}],
         "importes": [{"entidad": "Juan García López", "concepto": "reparación", "eur": 1234}]}
    classes, out = _classes(p)
    assert classes == {}
    assert out["excluidas"] == [{"clave": money.key("Juan García López"), "eur": 1234}]
    assert any(u["eur"] == 1234 and u["motivo"] == "persona física" for u in out["sin_asignar"])
    assert "García" not in json.dumps(out["sin_asignar"], ensure_ascii=False)


def _contract(name, kind=None, role="adjudicatario", eur=1000, **kw):
    return {"ref": "1", "titulo": "Contrato menor de suministro", "categoria": "contrato", "importe_eur": eur,
            "entidades": [{"nombre": name, "tipo": kind, "rol": role}], **kw}


@pytest.mark.parametrize("name,kind", [
    ("Un particular", None), ("una particular", None), ("Particulares", None),
    ("José Martínez López", None), ("María Pérez Gómez", "empresa"), ("D. Juan García López", None),
    ("Dña. Ana Ruiz", None), ("Pedro Sánchez Ortega", "autonomo"), ("Luis Gil Soria", "persona"),
])
def test_natural_person_never_reaches_ranking(name, kind):
    out = money.compute(_docs(_contract(name, kind)), {})
    assert out["ranking"] == []


def test_person_in_amounts_neither():
    p = {"ref": "1", "titulo": "Pago de facturas", "categoria": "pago_factura", "importe_eur": 500,
         "entidades": [], "importes": [{"entidad": "María Pérez Gómez", "concepto": "factura", "eur": 500}]}
    assert money.compute(_docs(p), {})["ranking"] == []


def test_one_mention_as_private_person_is_enough():
    p1 = _contract("Talleres Ruiz", "particular")
    p2 = _contract("Talleres Ruiz", "empresa")
    assert money.compute(_docs(p1, p2), {})["ranking"] == []


def test_companies_with_person_name_and_legal_form_do_show():
    out = money.compute(_docs(_contract("José Martínez López, S.L.", "empresa")), {})
    assert [r["entidad"] for r in out["ranking"]] == ["José Martínez López, S.L."]


def test_manual_class_is_validated():
    with pytest.raises(ValueError):
        money.compute(_docs(_contract("Talleres Ruiz", "empresa")), {"_clase": {"Talleres Ruiz": "Persona"}})


def test_payer_is_not_receiver():
    p = {"ref": "1", "titulo": "Premios del concurso de carrozas", "categoria": "subvencion_concedida",
         "importe_eur": 19950, "entidades": [], "importes": [
             {"entidad": "Ayuntamiento de Yecla", "concepto": "Premios a cargo del Ayuntamiento", "eur": 8500},
             {"entidad": "patrocinadores", "concepto": "Premios a cargo de patrocinadores", "eur": 5850},
             {"entidad": "Fundación Aladina", "concepto": "Actividad que lo paga la fundación", "eur": 1800}]}
    assert money.compute(_docs(p), {})["ranking"] == []


def test_council_never_receives():
    p = {"ref": "1", "titulo": "Subvención", "categoria": "subvencion_concedida", "importe_eur": 100,
         "entidades": [], "importes": [{"entidad": "Ayuntamiento de Yecla", "concepto": "premios", "eur": 100}]}
    assert money.compute(_docs(p), {})["ranking"] == []


def test_grant_counts_only_this_years_money_and_not_in_kind():
    p = {"ref": "1", "titulo": "Convenio con el club de tenis", "categoria": "subvencion_concedida",
         "importe_eur": 61000, "expediente": "1200009Z", "entidades": [], "importes": [
             {"entidad": "Yecla Club de Tenis", "concepto": "Subvención 2026", "eur": 12000},
             {"entidad": "Yecla Club de Tenis", "concepto": "Subvención 2028", "eur": 16000},
             {"entidad": "Yecla Club de Tenis", "concepto": "Aportación de recursos municipales (estimada)",
              "eur": 18000},
             {"entidad": "Yecla Club de Tenis", "concepto": "Uso gratuito de instalaciones", "eur": 1147}]}
    out = money.compute(_docs(p), {})
    r = out["ranking"][0]
    assert r["subvencion"] == 12000
    assert r["especie"] == 19147


def test_entity_without_any_amount_not_in_ranking():
    p = {"ref": "1", "titulo": "Ocupación de vía pública", "categoria": "via_publica_eventos", "importe_eur": 0,
         "entidades": [], "importes": [{"entidad": "Cruz Roja", "concepto": "lo paga Cruz Roja", "eur": 300}]}
    assert money.compute(_docs(p), {})["ranking"] == []


def test_name_without_useful_words_does_not_break():
    out = money.compute(_docs(_contract("Construcciones Pérez, S.L."), _contract("La"), _contract("...")), {})
    assert any(r["entidad"].startswith("Construcciones") for r in out["ranking"])


@pytest.mark.skipif(not (ANALYSIS / "json").exists(), reason="sin datos reales")
def test_regression_without_known_duplicates():
    alias = json.loads((ANALYSIS / "alias.json").read_text(encoding="utf-8"))
    keys = [r["clave"] for r in money.compute(sources.load_docs(ANALYSIS), alias)["ranking"]]
    for a in ("TEATROPIAXXI TEATRO MUSICAL", "PROCEED EVENTS", "ING ANVAZ DE COMUN Y SIST",
              "AFEDECO ASOCIACION DE FORMACION Y DESARROLLO COMUNITARIO EN YECLA"):
        assert a not in keys
