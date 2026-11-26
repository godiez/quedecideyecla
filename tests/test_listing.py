import pytest

from actas import listing as ym

JGL_HTML = """
<div><a href="https://www.yecla.es/wp-content/uploads/2022/11/2018_12_28_ac_56_jgl.pdf">Sesión nº 56,
 celebrada el 28 de diciembre de 2018</a>
<a href="/wp-content/uploads/2022/06/ACTA63_21-12-21.pdf"><span>Sesión nº 63, celebrada el 21 de diciembre de 2021</span></a>
<a href="https://yecla.es/wp-content/uploads/2026/09/ACTA-46.pdf">Sesión nº46, celebrada el 15 de Septiembre de 2026</a>
<a href="https://yecla.es/wp-content/uploads/2026/09/ACTA47.pdf">Sesión nº47,celebrada el 22 de septiembre de 2026</a>
<a href="https://yecla.es/wp-content/uploads/2020/x/2020_LIQUIDACION_ACTA_DE_ARQUEO.pdf">Acta de arqueo</a>
<a href="https://yecla.es/otra-pagina/">no es pdf</a></div>
"""

PLENO_HTML = """
<a href="https://yecla.es/wp-content/uploads/2025/11/CONVOCATORIA_PLENO_ORDINARIO_DICIEMBRE_2025_-_SEFYCU_3943768.pdf">Convocatoria</a>
<a href="https://yecla.es/u/Orden_de_publicacion_Area_General_del_tablon_de_anuncios_electronico_-_ACTA_PLENO_N_21_FECHA-1-12-25.pdf">Acta</a>
<a href="https://yecla.es/u/ACTA_PLENO_N_20_24-11-2025_-_SEFYCU_4012979.pdf">Acta</a>
<a href="https://yecla.es/u/Acta_Pleno_n_10_25-04-2025_Extraordinario_-_SEFYCU_3665572.pdf">Acta de la sesión</a>
<a href="https://yecla.es/u/ACTA-PLENO-EXTRAORDINARIO-No-15-14_10_2026-SEFYCU-4537547.pdf">Acta</a>
<a href="https://www.yecla.es/u/ACTAPLENO2322-12-2023FIRMADA_-_SEFYCU_2919768.pdf">Acta</a>
<a href="https://yecla.es/u/Orden_de_publicacion_-_Convocatoria_Pleno_Extraordinario.pdf">Acta</a>
"""


def test_parse_jgl_listing_uses_link_text():
    links = ym.parse_listing(JGL_HTML, "https://yecla.es/2018-actas-jgl/", "jgl_minutes")
    got = [(m.date, m.number) for m in links]
    assert got == [("2018-12-28", 56), ("2021-12-21", 63), ("2026-09-15", 46), ("2026-09-22", 47)]
    assert links[1].url == "https://yecla.es/wp-content/uploads/2022/06/ACTA63_21-12-21.pdf"
    assert links[0].kind == "jgl_minutes"


def test_parse_plenary_listing_uses_filename_and_skips_calls():
    links = ym.parse_listing(PLENO_HTML, "https://yecla.es/sesiones-pleno-del-ayuntamiento-2025/",
                             "plenary_minutes")
    got = [(m.date, m.number) for m in links]
    assert got == [("2025-12-01", 21), ("2025-11-24", 20), ("2025-04-25", 10), ("2026-10-14", 15),
                   ("2023-12-22", 23)]


SEDE_HTML = """
<h1>Sesiones Pleno del Ayuntamiento &#8211; 2024</h1>
<h2 class="elementor-heading-title">27/12/2024 - Sesión extraordinaria y urgente</h2>
<a href="https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAAULYUFJDLPKHRJTN&#038;modo=abrir"> Convocatoria </a>
<a href="https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAAWDJDW9XK4YH922Q&#038;modo=abrir"> Acta de la sesión </a>
<div> <strong>27-12-2021</strong> <span>Sesión extraordinaria y urgente</span>
<a href="https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AADLWYNDEQMUFCPURV&amp;modo=abrir">Ver orden del día</a>
<a href="https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAECLJ2N9DCJ4UJZRHWL&amp;modo=abrir">Ver acta</a>
07-03-2022 Sesión ordinaria
<a href="https://www.yecla.es/wp-content/uploads/2023/01/ACTAPLENO.0407-03-2022FIRMADA.pdf">Ver acta</a></div>
"""


def test_parse_plenary_listing_with_sede_links_and_both_heading_formats():
    links = ym.parse_listing(SEDE_HTML, "https://yecla.es/sesiones-pleno-del-ayuntamiento-2024/",
                             "plenary_minutes")
    got = [(m.url, m.date, m.number) for m in links]
    assert got == [
        ("https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAAWDJDW9XK4YH922Q&modo=abrir", "2024-12-27", None),
        ("https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAECLJ2N9DCJ4UJZRHWL&modo=abrir", "2021-12-27", None),
        ("https://www.yecla.es/wp-content/uploads/2023/01/ACTAPLENO.0407-03-2022FIRMADA.pdf", "2022-03-07", None),
    ]


@pytest.mark.parametrize("filename,expected", [
    ("Acta Sesión Pleno nº 17 (27/12/2024) - SEFYCU 3483599.pdf", 17),
    ("ACTA_PLENO_N_20_24-11-2025_-_SEFYCU_4012979.pdf", 20),
    ("Acta sesion ordinaria.pdf", None),
])
def test_session_number_from_download_name(filename, expected):
    assert ym.session_number_from_filename(filename) == expected


@pytest.mark.parametrize("filename,expected", [
    ("Acta Sesión Pleno nº 17 (27/12/2024) - SEFYCU 3483599.pdf", ("2024-12-27", 17)),
    ("ACTA PLENO Nº 18(29-12-2022) - SEFYCU 2465668.pdf", ("2022-12-29", 18)),
    ("Pleno Nº12(29-07-2022) - SEFYCU 2327850.pdf", ("2022-07-29", 12)),
    ("ACTAPLENO.02(13-02-2023)FIRMADA - SEFYCU 2541370.pdf", ("2023-02-13", 2)),
    ("Orden de publicación Área 'General' del tablón de anuncios electrónico", (None, None)),
    ("Orden de publicación Área 'General' del tablón de edictos - Ac20(21-12-2020) - SEFYCU 1875459.pdf", (None, 20)),
    ("Orden de publicación Área 'General' del tablón de edictos - ACTA.PLENO.Nº2.FIRMADA - SEFYCU 1884059.pdf", (None, 2)),
    ("Orden de publicación Área 'General' - ACTAPLENO.12 (2/8/24) - SEFYCU 3279415.pdf", (None, 12)),
    ("ACTAPLENO.0407-03-2022FIRMADA.pdf", (None, None)),
])
def test_session_from_download_name(filename, expected):
    assert ym.session_from_filename(filename) == expected


@pytest.mark.parametrize("name,expected", [
    ("ACTA01-07-01-2026-anonimizada.pdf", ("2026-01-07", 1)),
    ("Acta-no27-JGL_-26-05-2026-ANONIMIZADA-SEFYCU-4313236.pdf", ("2026-05-26", 27)),
    ("2018_12_28_ac_56_jgl.pdf", ("2018-12-28", 56)),
    ("ACTA64_29-12-21.pdf", ("2021-12-29", 64)),
    ("ACTA-68-JGL-02-12-2025-ANONIMIZADA-SEFYCU-4020334.pdf", ("2025-12-02", 68)),
    ("2020_12_11_ACTA_64_jgl.pdf", ("2020-12-11", 64)),
    ("ac_2_05_01_2018_jgl.pdf", ("2018-01-05", 2)),
    ("ACTA-43.pdf", (None, 43)),
    ("2021_LIQUIDACION_ACTA_DE_ARQUEO.pdf", None),
])
def test_parse_minutes_filename(name, expected):
    assert ym.parse_minutes_filename(name) == expected


def test_year_urls_from_territory_patterns():
    cfg = {"jgl_year_url": "https://yecla.es/{year}-actas-jgl/",
           "plenary_year_url": "https://yecla.es/sesiones-pleno-del-ayuntamiento-{year}/",
           "first_year": 2025}
    assert ym.listing_urls(cfg, last_year=2026) == [
        ("jgl_minutes", "https://yecla.es/2025-actas-jgl/"),
        ("plenary_minutes", "https://yecla.es/sesiones-pleno-del-ayuntamiento-2025/"),
        ("jgl_minutes", "https://yecla.es/2026-actas-jgl/"),
        ("plenary_minutes", "https://yecla.es/sesiones-pleno-del-ayuntamiento-2026/"),
    ]


@pytest.mark.parametrize("filename,expected", [
    ("CONVOPLENO.EXTRA.Nº10(07-06-2021.19'20horas) - SEFYCU 1907294.pdf", True),
    ("Orden de publicación Área 'General' del tablón de edictos - Ac20(21-12-2020) - SEFYCU 1875459.pdf", False),
    ("ACTA PLENO Nº 18(29-12-2022) - SEFYCU 2465668.pdf", False),
])
def test_looks_like_call(filename, expected):
    assert ym.looks_like_call(filename) is expected
