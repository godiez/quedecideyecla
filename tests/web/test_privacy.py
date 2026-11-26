from actas.web import privacy


def _web(tmp_path, html):
    (tmp_path / "decision").mkdir()
    (tmp_path / "decision" / "index.html").write_text(html, encoding="utf-8")
    return tmp_path


def test_privacy_allowed_case_file_and_dni_not(tmp_path):
    w = _web(tmp_path, "<p>Expte. 12661545Q</p>")
    assert privacy.check(w, {"12661545Q"}) == []
    (w / "otra.html").write_text("<p>Un vecino con DNI 12345678Z pide…</p>", encoding="utf-8")
    found = privacy.check(w, {"12661545Q"})
    assert found == ["otra.html: 12345678Z"]


def test_privacy_nie_cadastral_plate(tmp_path):
    w = _web(tmp_path, "X1234567L 1234567AB1234C0001DE 30043A012000340000XY 1234 BCD")
    found = privacy.check(w, set())
    assert len(found) == 4


def test_dni_with_valid_letter_never_allowed(tmp_path):
    w = _web(tmp_path, "<p>Expte. 12345678Z</p>")
    assert privacy.check(w, {"12345678Z"}) == ["decision/index.html: 12345678Z"]


def test_dni_with_separators_lower_case_or_entities(tmp_path):
    w = _web(tmp_path, "<p>12.345.678-Z</p><p>12345678z</p><p>12345678&#90;</p><p>x1234567-l</p>")
    found = privacy.check(w, set())
    assert sorted(found) == sorted(["decision/index.html: 12345678Z"] * 3 + ["decision/index.html: X1234567L"])


def test_scans_any_text_file(tmp_path):
    w = _web(tmp_path, "<p>nada</p>")
    (w / "datos.csv").write_text("12345678Z", encoding="utf-8")
    assert privacy.check(w, set()) == ["datos.csv: 12345678Z"]


def test_dni_stuck_to_letters_or_with_invisible_characters(tmp_path):
    w = _web(tmp_path, "<p>DNI nº12345678Z</p><p>DNI.12345678Z</p><p>12345­678Z</p><p>1234​5678Z</p>")
    assert privacy.check(w, set()) == ["decision/index.html: 12345678Z"] * 4


def test_common_dni_and_plate_formats(tmp_path):
    w = _web(tmp_path, "<p>1234567-L</p><p>12345678/Z</p><p>12.345.678 - Z</p><p>1234-BCD</p><p>1234 bcd</p>")
    assert len(privacy.check(w, set())) == 5


def test_7_digit_case_file_allowed_even_if_letter_matches(tmp_path):
    # 1234567L: 1234567 % 23 = 19 -> L.
    w = _web(tmp_path, "<p>Expte. 1234567L</p>")
    assert privacy.check(w, {"1234567L"}) == []


def test_case_file_with_slash_and_dash_not_joined_into_a_dni(tmp_path):
    w = _web(tmp_path, "<p>Expte. T.A.5/24 - 903616Y</p>")
    assert privacy.check(w, {"903616Y"}) == []


def test_dni_with_dashes_between_digits(tmp_path):
    w = _web(tmp_path, "<p>12-345-678-Z</p>")
    assert privacy.check(w, set()) == ["decision/index.html: 12345678Z"]


def test_surfaces_volumes_and_words_after_a_number_are_not_dni(tmp_path):
    w = _web(tmp_path, "<p>Una finca de 1.222.463 m² y 3.114.363 m³ al año; sube de 3.114.363 a 3.281.026 m³.</p>")
    assert privacy.check(w, set()) == []


def test_lower_case_letter_after_a_space_still_counts_when_it_is_a_valid_dni(tmp_path):
    w = _web(tmp_path, "<p>12.345.678 z</p><p>1.234.568 l</p>")
    assert privacy.check(w, set()) == ["decision/index.html: 12345678Z"]


def test_case_file_quoted_in_the_text_is_known():
    from actas import money
    p = {"expediente": "1186986R", "importes": [{"concepto": "Gastos del evento (expediente aparte 1021064W)"}],
         "resumen": "Ver el expte. 1300000A y el Expte. nº 1300001B."}
    assert set(money.case_files(p)) == {"1186986R", "1021064W", "1300000A", "1300001B"}


def test_emails_and_phones_are_caught_but_not_amounts():
    from actas.web.privacy import _findings
    assert _findings("Llama al 968 75 41 00", set()) == ["968754100"]
    assert _findings("escribe a pepe@gmail.com o a quedecideyecla@gmail.com", set()) == ["pepe@gmail.com"]
    assert _findings("1.938.126,53 € y 968.754.100,50 €", set()) == []
