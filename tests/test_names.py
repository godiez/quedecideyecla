import json

import pytest

from actas import names, public

DOC = "2023-03-06_JGL_10"
AI = f"analisis/2023/json/{DOC}.json"


@pytest.fixture
def analysis(tmp_path):
    """analisis/ with the text of one minute: the files themselves are passed as a dict, as `actas publish` does."""
    (tmp_path / "2023" / "txt").mkdir(parents=True)
    (tmp_path / "2023" / "txt" / f"{DOC}.txt").write_text(
        "1. Licencia de obra a D. Juan Pérez García, en calle Mayor.\n2. Terraza de Dña. Ana Ruiz López.\n",
        encoding="utf-8")
    return tmp_path


def _files(points, revision=None, votes=None, notes=None, doc=DOC):
    ai = {"doc": doc, "puntos": points, **({"notas": notes} if notes else {})}
    out = {f"analisis/2023/json/{doc}.json": json.dumps(ai, ensure_ascii=False).encode()}
    if revision:
        out["analisis/2023/revision.json"] = json.dumps(revision, ensure_ascii=False).encode()
    if votes:
        out[f"analisis/2023/votos/{doc}.json"] = json.dumps(votes, ensure_ascii=False).encode()
    return public.clean(out)


def _point(resumen, **kw):
    return {"titulo": "Licencia de obra", "resumen": resumen, "entidades": [], **kw}


def test_names_with_an_honorific():
    text = ("Comparecen D. Juan Pérez García, Dña. María de la Luz Gómez y DON JOSÉ RUIZ; la Sra. Concejala Delegada; "
            "la S.D. Hispania Bodegas; D. MAZA CONSTRUCCIONES; la calle San Ramón entre Don Lucio y Numancia.")
    assert names.honorific_names(text) == {"Juan Pérez", "María Luz", "JOSÉ RUIZ"}


def test_a_name_of_the_minute_in_what_is_published_is_found(analysis):
    files = _files([_point("Se concede licencia a Juan Pérez para reformar la casa."),
                    _point("Terraza de 10 m² para el bar de ANA RUIZ."),
                    _point("Se concede licencia a un particular.")])
    found, no_text = names.findings(files, analysis, {})
    assert found == [f"{AI} puntos[0].resumen: Juan Pérez", f"{AI} puntos[1].resumen: Ana Ruiz"]
    assert no_text == []


def test_the_names_of_another_minute_do_not_count(analysis):
    other = "2023-03-13_JGL_11"
    (analysis / "2023" / "txt" / f"{other}.txt").write_text("Licencia a un particular.", encoding="utf-8")
    assert names.findings(_files([_point("La calle Juan Pérez se asfalta.")], doc=other), analysis, {}) == ([], [])


def test_a_reviewed_phrase_only_allows_its_own_context(analysis):
    reviewed = names.load_reviewed('{"_nota": "comentario", "calle Juan Pérez": "calle"}')
    files = _files([_point("Se asfalta la calle Juan Pérez."), _point("Juan Pérez pide una licencia.")])
    assert names.findings(files, analysis, reviewed)[0] == [f"{AI} puntos[1].resumen: Juan Pérez"]


def test_an_honorific_in_what_is_published_counts_without_the_text_of_the_minute(analysis):
    other = "2023-03-13_JGL_11"
    found, no_text = names.findings(_files([_point("Se concede a Dña. Elena Martínez Soler una ayuda.")], doc=other),
                                    analysis, {})
    assert found == [f"analisis/2023/json/{other}.json puntos[0].resumen: Elena Martínez"]
    assert no_text == [other]


def test_votes_and_corrections_are_checked_but_not_what_is_not_published(analysis):
    revision = {f"{DOC}:0": {"estado": "corregido", "cambios": {"titulo": "Obra de Juan Pérez"}, "nota": "Título",
                             "original": {"titulo": "Licencia a Ana Ruiz"}}}
    votes = {"votaciones": [{"texto_acta": "aprobado con el voto en contra de D. Juan Pérez García"}]}
    files = _files([_point("Se concede la licencia.")], revision, votes, notes="OCR: D. Juan Pérez García")
    found, _ = names.findings(files, analysis, {})
    assert found == [f"analisis/2023/revision.json {DOC}:0.cambios.titulo: Juan Pérez",
                     f"analisis/2023/votos/{DOC}.json votaciones[0].texto_acta: Juan Pérez"]


def test_a_privacy_correction_clears_the_finding(analysis):
    revision = {f"{DOC}:0": {"estado": "corregido", "cambios": {"resumen": "Se concede licencia a un particular."},
                             "nota": "Privacidad: nombre de un vecino", "original": {}}}
    files = _files([_point("Se concede licencia a Juan Pérez.")], revision)
    assert names.findings(files, analysis, {})[0] == []


def test_entities_that_look_like_a_person_whatever_their_type(analysis):
    files = _files([_point("Se concede la licencia.", entidades=[
        {"nombre": "Rosa Gil Navarro", "tipo": "persona"}, {"nombre": "Rosa Gil Navarro, S.L.", "tipo": "empresa"},
        {"nombre": "particular", "tipo": "persona"}], importes=[{"entidad": "Pedro Gil Soler", "eur": 10}])])
    assert names.findings(files, analysis, {})[0] == [f"{AI} puntos[0]: Rosa Gil Navarro", f"{AI} puntos[0]: Pedro Gil Soler"]


def test_the_reviewed_list_is_published():
    assert public.is_allowed(names.REVIEWED_PATH)


def test_a_privacy_correction_of_a_vote_quote_clears_the_finding(analysis):
    quote = "aprobado con el voto en contra de D. Juan Pérez García"
    votes = {"votaciones": [{"texto_acta": quote}]}
    correction = {f"{DOC}:votos:0": {"estado": "corregido", "nota": "Privacidad: nombre de un concejal",
                                     "cambios": {"texto_acta": quote.replace("D. Juan Pérez García", "[un concejal]")},
                                     "original": {"texto_acta": quote}}}
    assert names.findings(_files([_point("Se aprueba.")], votes=votes), analysis, {})[0] != []
    assert names.findings(_files([_point("Se aprueba.")], correction, votes), analysis, {})[0] == []
