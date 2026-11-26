import json

import pytest

from actas import checks


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def year(tmp_path):
    a = tmp_path / "2023"
    points = [
        {"ref": "1", "titulo": "Actas anteriores", "categoria": "organizacion", "entidades": []},
        {"ref": "2", "titulo": "Subvención al club", "categoria": "subvencion_concedida", "importe_eur": 1500.0,
         "entidades": [{"nombre": "Club Deportivo Yecla", "tipo": "club", "rol": "recibe"}]},
        {"ref": "3", "titulo": "Facturas", "categoria": "pago_factura", "importe_eur": 300.0,
         "importes": [{"concepto": "a", "eur": 100.0, "entidad": "Talleres Uno, S.L."},
                      {"concepto": "b", "eur": 200.0, "entidad": "Talleres Dos, S.L."}], "entidades": []},
        {"ref": "4", "titulo": "Obra calculada", "categoria": "contrato", "importe_eur": 999.99, "entidades": []},
    ]
    _write(a / "json" / "2023-03-06_PLENO_03.json", {"organo": "PLENO", "fecha": "2023-03-06", "paginas": 3,
                                                       "puntos": points})
    (a / "txt").mkdir()
    (a / "txt" / "2023-03-06_PLENO_03.txt").write_text(
        "se concede 1.500,00 euros al club\fFacturas: 1 00,00 € y 200,00 €\f", encoding="utf-8")
    seats = {"PP": 12, "PSOE": 5, "Cs": 2, "IU-Verdes": 2}  # legislature 2019-2023
    _write(a / "votos" / "2023-03-06_PLENO_03.json", {"asistentes": seats, "votaciones": [
        {"punto_idx": 1, "punto_ref": "2", "final": True, "unanimidad": True, "resultado": "aprobada",
         "votos": {g: {"favor": n, "contra": 0, "abstencion": 0} for g, n in seats.items()}},
        {"punto_idx": 3, "punto_ref": "4", "final": True, "unanimidad": False, "resultado": "aprobada",
         "votos": {"PP": {"favor": 12}, "PSOE": {"contra": 5}, "Cs": {"abstencion": 2},
                   "IU-Verdes": {"contra": 2}}},
    ]})
    return a


def test_votes_are_checked_against_the_pleno_of_their_legislature(year):
    errors, warnings, report = checks.check_votes(year)
    assert errors == [] and warnings == []
    assert "votaciones: 2" in report[0] and any("(2019-2023)" in r for r in report)


def test_votes_with_wrong_groups_point_or_sums_are_errors(year):
    f = year / "votos" / "2023-03-06_PLENO_03.json"
    d = json.loads(f.read_text())
    d["asistentes"] = {"PP": 9, "PSOE": 7, "Vox": 3, "IU-Verdes": 2, "Cs": 2}  # groups of two legislatures
    d["votaciones"][0]["punto_ref"] = "3"
    d["votaciones"][1]["votos"]["PSOE"] = {"contra": 8}
    f.write_text(json.dumps(d))
    errors, _, _ = checks.check_votes(year)
    text = "\n".join(errors)
    assert "asistentes con grupos" in text and "punto_ref no coincide" in text and "PSOE suma 8" in text


def test_a_result_that_does_not_match_the_votes_is_a_warning(year):
    f = year / "votos" / "2023-03-06_PLENO_03.json"
    d = json.loads(f.read_text())
    d["votaciones"][1]["resultado"] = "rechazada"
    f.write_text(json.dumps(d))
    _, warnings, _ = checks.check_votes(year)
    assert len(warnings) == 1 and "12 a favor y 7 en contra" in warnings[0]


def test_amount_variants():
    assert checks.amount_variants(365314.87) >= {"365.314,87", "365314,87", "365314.87", "365,314.87"}
    assert {"1.500", "1500"} <= checks.amount_variants(1500)


def test_amounts_not_in_the_minutes_are_listed(year):
    found, missing, no_text = checks.check_amounts(year)
    # 1.500 found; the two lines found (one split by a layout space) and their total is their sum; 999,99 is not.
    assert (found, no_text) == (4, 0)
    assert [m["id"] for m in missing] == ["2023-03-06_PLENO_03:3"]
    assert json.loads((year / "no_encontrados.json").read_text()) == missing


def test_minutes_without_text_are_counted_not_failed(year):
    (year / "txt" / "2023-03-06_PLENO_03.txt").unlink()
    assert checks.check_amounts(year) == (0, [], 1)


def test_money_and_summary_are_written(year):
    assert any("entidades con dinero" in line for line in checks.write_money(year))
    assert (year / "dinero.json").exists()
    checks.write_summary(year)
    summary = json.loads((year / "resumen.json").read_text())
    assert summary["actas"] == 1 and summary["por_organo"]["PLENO"]["puntos"] == 4
    assert summary["top_dinero"][0]["nombre"] == "Club Deportivo Yecla"


def test_run_returns_the_number_of_vote_errors(year, capsys):
    assert checks.run(year) == 0
    assert "Importes: 4 encontrados" in capsys.readouterr().out


def test_a_name_of_the_minute_in_what_is_published_is_an_error(year, capsys):
    txt = year / "txt" / "2023-03-06_PLENO_03.txt"
    txt.write_text(txt.read_text(encoding="utf-8") + "Moción de D. Juan Pérez García\f", encoding="utf-8")
    path = year / "json" / "2023-03-06_PLENO_03.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    d["puntos"][0]["resumen"] = "Juan Pérez presenta una moción."
    _write(path, d)
    assert checks.run(year) == 1
    out = capsys.readouterr().out
    assert "ERROR analisis/2023/json/2023-03-06_PLENO_03.json puntos[0].resumen: Juan Pérez" in out
    (year.parent / "nombres_revisados.json").write_text('{"Juan Pérez presenta": "prueba"}', encoding="utf-8")
    assert checks.run(year) == 0
