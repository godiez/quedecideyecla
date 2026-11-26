from actas.web import model

J1, J7, P3 = "2026-01-07_JGL_01", "2026-02-03_JGL_07", "2026-03-02_PLENO_03"


def _site(mini_analysis, with_db=True):
    a, db = mini_analysis
    return model.build(a, db if with_db else None, 2026)


def test_sessions_sorted_and_decisions_by_importance(mini_analysis):
    s = _site(mini_analysis)
    assert [x.doc for x in s.sessions] == [P3, J7, J1]
    assert s.latest_session.doc == P3
    j1 = s.sessions[2]
    assert [d.id for d in j1.decisions] == [f"{J1}:3", f"{J1}:0", f"{J1}:1", f"{J1}:2", f"{J1}:4"]
    assert s.decisions[f"{J1}:0"].slug == f"{J1}-0"
    assert s.decisions[f"{J1}:0"].topic == "Contratos y pagos"


def test_discarded_not_shown_nor_its_vote(mini_analysis):
    s = _site(mini_analysis)
    assert f"{P3}:1" not in s.decisions
    assert all(v.decision_id in s.decisions for v in s.votes)
    assert [v.decision_id for v in s.votes] == [f"{P3}:0"]
    assert s.decisions[f"{P3}:0"].vote.votes["Vox"]["contra"] == 3


def test_private_place_with_number_is_hidden(mini_analysis):
    assert _site(mini_analysis).decisions[f"{J1}:3"].place is None


def test_pdf_url_with_page_and_minutes_without_url(mini_analysis):
    s = _site(mini_analysis)
    d = s.decisions[f"{J1}:0"]
    assert d.page == 2
    assert d.pdf_url == "https://yecla.es/actas/ACTA01.pdf#page=2"
    assert s.decisions[f"{J7}:0"].pdf_url is None
    assert next(x for x in s.sessions if x.doc == J7).pdf_url is None


def test_without_catalog(mini_analysis):
    s = _site(mini_analysis, with_db=False)
    assert all(d.pdf_url is None for d in s.decisions.values())


def test_private_entity_without_slug(mini_analysis):
    s = _site(mini_analysis)
    ent = s.decisions[f"{J1}:3"].entities[0]
    assert ent["slug"] is None and ent["name"] == "un particular"
    actua = s.decisions[f"{J1}:0"].entities[0]
    assert actua["slug"] in s.entities


def test_totals_by_class(mini_analysis):
    s = _site(mini_analysis)
    assert s.totals["companies"] == 50000
    assert s.totals["associations"] == 7500
    assert s.totals["pending"] == 12000
    classes = {e.name: e.entity_class for e in s.ranking}
    assert classes["Talleres Pérez C.B."] == "pendiente"
    assert "Construcciones Gómez, S.L." not in classes
    gomez = next(e for e in s.entities.values() if e.name == "Construcciones Gómez, S.L.")
    assert gomez.entity_class == "empresa" and [p.id for p in gomez.permits] == [f"{J1}:2"]
    actua = next(e for e in s.ranking if e.name.startswith("Actúa"))
    assert actua.movements[0]["decision_slug"] == f"{J1}-0"


def test_votes_carry_their_legislature(mini_analysis):
    s = _site(mini_analysis)
    assert {v.legislature for v in s.votes} == {"2023-2027"}
    from actas.votes import agreements
    a = agreements([{"final": v.final, "unanimidad": v.unanimous, "votos": v.votes} for v in s.votes])
    assert a[("PSOE", "IU-Verdes")] == (1, 1) and a[("PP", "Vox")] == (0, 1)


def test_archive_joins_years_and_hides_a_person_of_any_year(two_years):
    import json
    root, db = two_years
    f = root / "2022" / "json" / "2022-05-10_JGL_19.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["puntos"][0]["entidades"].append({"nombre": "Talleres Pérez C.B.", "tipo": "particular", "rol": "x"})
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    arc = model.build_archive(root, db)
    assert arc.years == [2026, 2022] and arc.latest.year == 2026
    assert all(s.years == [2026, 2022] for s in arc.sites.values())
    assert not any(h.name.startswith("Talleres Pérez") for h in arc.entities.values())
    assert "2022-05-10_JGL_19:0" in arc.decisions


def test_person_only_in_permits_is_not_named(mini_analysis):
    a, db = mini_analysis
    (a / "alias.json").write_text('{"_clase": {"Construcciones Gómez, S.L.": "persona"}}', encoding="utf-8")
    s = model.build(a, db, 2026)
    assert s.decisions[f"{J1}:2"].entities[0] == {"name": "un particular", "slug": None, "type": "empresa",
                                                   "role": "solicita"}
    assert not any(e.name.startswith("Construcciones") for e in s.entities.values())


def test_body_and_votes_sanitized(mini_analysis):
    import json
    a, db = mini_analysis
    f = a / "json" / f"{J7}.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["organo"] = "<script>x</script>"
    f.write_text(json.dumps(d), encoding="utf-8")
    v = a / "votos" / f"{P3}.json"
    dv = json.loads(v.read_text(encoding="utf-8"))
    dv["votaciones"][0]["votos"]["PP"]["favor"] = "<b>9</b>"
    dv["votaciones"][0]["votos"]["Raro<"] = {"favor": 1}
    v.write_text(json.dumps(dv), encoding="utf-8")
    s = model.build(a, db, 2026)
    assert next(x for x in s.sessions if x.doc == J7).body == "JGL"
    votes = s.decisions[f"{P3}:0"].vote.votes
    assert votes["PP"]["favor"] == 0 and set(votes) == {"PP", "PSOE", "Vox", "IU-Verdes"}
    assert all(isinstance(n, int) for g in votes.values() for n in g.values())


def test_natural_person_hidden_in_any_point(mini_analysis):
    import json
    a, db = mini_analysis
    f = a / "json" / f"{P3}.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["puntos"] += [
        {"ref": "4", "titulo": "Reclamación de daños", "categoria": "reclamaciones", "resumen": "x",
         "entidades": [{"nombre": "José Martínez López", "tipo": None, "rol": "reclamante"},
                       {"nombre": "Talleres Ruiz", "tipo": "empresa", "rol": "interesado"}]},
        {"ref": "5", "titulo": "Licencia de obra", "categoria": "licencia_obra", "resumen": "x",
         "entidades": [{"nombre": "Talleres Ruiz", "tipo": "empresa", "rol": "solicita"},
                       {"nombre": "Un particular", "tipo": None, "rol": "solicita"}]}]
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (a / "alias.json").write_text(json.dumps({"_clase": {"Talleres Ruiz": "persona"}}), encoding="utf-8")
    s = model.build(a, db, 2026)
    names = [e["name"] for x in s.decisions.values() for e in x.entities]
    assert "José Martínez López" not in names and "Talleres Ruiz" not in names
    assert not any("ruiz" in sl or "martinez" in sl or "particular" in sl for sl in s.entities)


def test_case_file_only_as_written_in_the_minutes():
    from actas.web.model import legible_case_file as legible
    minutes = "DEYECLA(EXPTE.479634)Y483985CYLICENCIA188/2023(EXPTE.861567X)504539Z(512/2020)"
    assert legible("479634J", minutes) is None
    assert legible("483985Q, 483985C", minutes) == "483985C"
    assert legible("861567X (licencia 188/2023)", minutes) == "861567X (licencia 188/2023)"
    assert legible("504539Z (dudoso por OCR)", minutes) == "504539Z"
    assert legible("477251? (OCR: 4772517)", minutes) is None
    assert legible("492617Q (512/2020)", minutes) == "512/2020"
    assert legible("C.SE. 16/22", minutes) == "C.SE. 16/22"
    assert legible("504539Z (dudoso por OCR)", None) == "504539Z"


def test_a_year_without_minutes_says_so(mini_analysis):
    import pytest
    a, db = mini_analysis
    with pytest.raises(ValueError, match="sin actas analizadas en 1999"):
        model.build_archive(a, db, [1999])
