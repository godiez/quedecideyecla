import json

import pytest

from actas.revision import data


@pytest.fixture
def analysis(tmp_path):
    (tmp_path / "json").mkdir()
    (tmp_path / "txt").mkdir()
    doc = {
        "doc": "2026-01-07_JGL_01", "organo": "JGL", "sesion": 1, "fecha": "2026-01-07",
        "puntos": [
            {"ref": "1", "titulo": "Comunicaciones", "categoria": "informacion", "expediente": "1207906Y",
             "importe_eur": None, "interes": 1},
            {"ref": "2.1", "titulo": "Pago de facturas a FCC Aqualia", "categoria": "pago_factura",
             "expediente": "1186986R", "importe_eur": 16243.77, "interes": 2,
             "entidades": [{"nombre": "FCC Aqualia, S.A.", "tipo": "empresa", "rol": "cobra"}]},
            {"ref": "3", "titulo": "Bonificación del IBI", "categoria": "fiscal", "expediente": "1059250F",
             "interes": 3},
        ],
    }
    (tmp_path / "json" / "2026-01-07_JGL_01.json").write_text(json.dumps(doc), encoding="utf-8")
    pages = ["1º.- DISPOSICIONES (EXPTE. 1207906Y)", "2º.- ASUNTOS ECONÓMICOS\nFCC Aqualia (Expte. 1186986R)",
             "3. Concesión de bonificación del Impuesto sobre Bienes Inmuebles (Expte. 1059250F)"]
    (tmp_path / "txt" / "2026-01-07_JGL_01.txt").write_text("\f".join(pages), encoding="utf-8")
    return tmp_path


def test_points_have_stable_ids_priority_and_page(analysis):
    pts = data.load_points(analysis)
    assert [p["id"] for p in pts] == ["2026-01-07_JGL_01:0", "2026-01-07_JGL_01:1", "2026-01-07_JGL_01:2"]
    assert [p["priority"] for p in pts] == [False, True, True]
    assert [p["page"] for p in pts] == [1, 2, 3]
    assert pts[1]["doc"] == "2026-01-07_JGL_01" and pts[1]["organo"] == "JGL"


def test_revision_roundtrip_and_apply(analysis):
    path = analysis / "revision.json"
    data.save_review(path, "2026-01-07_JGL_01:1", "corregido", {"importe_eur": 16000.0}, "importe mal leído")
    data.save_review(path, "2026-01-07_JGL_01:0", "descartado", {}, "")
    data.save_review(path, "2026-01-07_JGL_01:2", "aprobado", {}, "")
    rev = data.load_reviews(path)
    assert rev["2026-01-07_JGL_01:1"]["estado"] == "corregido"
    assert rev["2026-01-07_JGL_01:1"]["original"] == {"importe_eur": 16243.77}

    out = data.apply_reviews(data.load_points(analysis), rev)
    assert [p["id"] for p in out] == ["2026-01-07_JGL_01:1", "2026-01-07_JGL_01:2"]
    assert out[0]["importe_eur"] == 16000.0 and out[0]["revision"] == "corregido"


def test_revision_rejects_unknown_state_and_fields(analysis):
    path = analysis / "revision.json"
    with pytest.raises(ValueError):
        data.save_review(path, "x:0", "quizá", {}, "")
    with pytest.raises(ValueError):
        data.save_review(path, "x:0", "corregido", {"organo": "PLENO"}, "")


def test_corrected_without_changes_is_approved(analysis):
    path = analysis / "revision.json"
    data.save_review(path, "2026-01-07_JGL_01:1", "corregido", {}, "")
    assert data.load_reviews(path)["2026-01-07_JGL_01:1"]["estado"] == "aprobado"


def test_find_page_falls_back_to_title_words():
    pages = ["portada", "otra cosa", "Licitación de la restauración del castillo Hisn Yakka"]
    assert data.find_page(pages, {"titulo": "Se licita la restauración del castillo", "expediente": None}) == 3
    assert data.find_page(pages, {"titulo": "", "expediente": None}) == 1


def test_amounts_breakdown_is_editable(analysis):
    path = analysis / "revision.json"
    new = [{"entidad": "FCC Aqualia, S.A.", "concepto": "Agua colegios", "eur": 6491.12}]
    data.save_review(path, "2026-01-07_JGL_01:1", "corregido", {"importes": new}, "")
    out = data.apply_reviews(data.load_points(analysis), data.load_reviews(path))
    assert out[1]["importes"] == new


def test_automatic_reclassification_sits_under_human_review(analysis):
    (analysis / "reclasificacion.json").write_text(json.dumps(
        {"_motivo": "x", "2026-01-07_JGL_01:0": {"categoria": "medio_ambiente", "antes": "informacion"}}),
        encoding="utf-8")
    pts = data.load_points(analysis)
    assert pts[0]["categoria"] == "medio_ambiente"
    path = analysis / "revision.json"
    data.save_review(path, "2026-01-07_JGL_01:0", "corregido", {"categoria": "otros"}, "")
    assert data.load_reviews(path)["2026-01-07_JGL_01:0"]["original"] == {"categoria": "medio_ambiente"}
    out = data.apply_reviews(data.load_points(analysis), data.load_reviews(path))
    assert out[0]["categoria"] == "otros"
    assert "medio_ambiente" in data.CATEGORIES and "servicios_actividades" in data.CATEGORIES


def test_find_page_with_already_normalized_pages():
    pages = ["Portada", "2º.- PAGO A FCC AQUALIA (Expte. 1186986R)", "Bonificación del IBI"]
    point = {"titulo": "Bonificación del impuesto", "expediente": None}
    flat = [data._plain(x) for x in pages]
    assert data.find_page(flat, point, already_normalized=True) == data.find_page(pages, point) == 3


def test_find_pages_ignores_the_case_file_list_of_a_section_heading():
    pages = ["4º.- CUESTIONES DE PERSONAL (EXPTES. 1082971C, 1264220M,\n1264269E, 910303K)\n1. Otra cosa",
             "nada", "3. Excedencia de una auxiliar (Expte. 1264220M)"]
    point = {"titulo": "Excedencia de dos auxiliares", "expediente": "1264220M"}
    assert data.find_pages(pages, [point]) == [3]


def test_find_pages_keeps_the_order_of_points_sharing_a_case_file():
    pages = ["portada", "Taquilla Magdalena y Santa Faz (Expte. 864552R) Festival de Bandas Semana Santa",
             "Taquilla Oración del Huerto y Romanos (Expte. 864552R) Festival de Bandas Semana Santa",
             "Taquilla de la obra teatral Momo, Teatro Concha Segura (Expte. 864552R)"]
    pts = [{"titulo": "Taquilla del Festival de Bandas de Semana Santa (Magdalena)", "expediente": "864552R"},
           {"titulo": "Taquilla del Festival de Bandas de Semana Santa (Oración del Huerto y Romanos)",
            "expediente": "864552R"},
           {"titulo": "Taquilla de la obra teatral Momo", "expediente": "864552R"}]
    assert data.find_pages(pages, pts) == [2, 3, 4]


def test_find_pages_a_stray_case_file_does_not_drag_the_rest():
    pages = ["Aprobación del acta de la sesión anterior", "Licencia (Expte. 111111A)", "Contrato (Expte. 222222B)",
             "Ruegos. Se cita de nuevo el expediente 111111A y la sesión anterior"]
    pts = [{"titulo": "Aprobación del acta de la sesión anterior", "expediente": None},
           {"titulo": "Licencia de obra", "expediente": "111111A"},
           {"titulo": "Contrato de limpieza", "expediente": "222222B"}]
    assert data.find_pages(pages, pts) == [1, 2, 3]


def test_a_vote_quote_can_be_corrected(analysis):
    (analysis / "votos").mkdir()
    quote = "aprobada por doce votos a favor (Grupo M. Popular y Dña. Ana Ruiz)"
    (analysis / "votos" / "2026-01-07_JGL_01.json").write_text(json.dumps({"votaciones": [{"texto_acta": quote}]}),
                                                                encoding="utf-8")
    path = analysis / "revision.json"
    rec = data.save_review(path, "2026-01-07_JGL_01:votos:0", "corregido",
                           {"texto_acta": quote.replace("Dña. Ana Ruiz", "[una concejala]")}, "Privacidad: nombre")
    assert rec["original"] == {"texto_acta": quote}
    with pytest.raises(ValueError, match="no editables"):
        data.save_review(path, "2026-01-07_JGL_01:votos:0", "corregido", {"votos": {}}, "")
    with pytest.raises(ValueError, match="votación desconocida"):
        data.save_review(path, "2026-01-07_JGL_01:votos:5", "corregido", {"texto_acta": "x"}, "")
    assert [p["revision"] for p in data.apply_reviews(data.load_points(analysis), data.load_reviews(path))] == \
        ["pendiente"] * 3
