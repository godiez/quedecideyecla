import copy
import json
from datetime import date

import pytest

from actas import money, municipality, public, votes
from actas.web import template, texts

DATA = {
    "_nota": "comentario",
    "municipio": "Villanueva del Río",
    "web_ayuntamiento": "https://www.villanueva.example/",
    "actas_por_año": {"junta_de_gobierno": "https://www.villanueva.example/jgl-{año}/",
                      "pleno": "https://www.villanueva.example/pleno/{año}", "primer_año": 2019},
    "organismos_regionales": ["Junta de Andalucía", "SAS"],
    "legislaturas": {
        "_nota": "comentario",
        "2023-2027": {"inicio": "2023-06-17", "grupos": {"PSOE": 9, "PP": 6, "IU": 2}},
        "2019-2023": {"inicio": "2019-06-15", "grupos": {"PSOE": 10, "PP": 7}},
    },
    "colores_grupos": {"_nota": "comentario", "PSOE": "#ff0000", "PP": "#21599e", "IU": "#9b1b30"},
    "web": {"nombre": "Qué decide Villanueva", "correo": "web@villanueva.example", "responsable": "Ana",
            "direccion": "https://ana.github.io/villanueva/", "codigo": "https://github.com/ana/villanueva/"},
}


def test_another_town_is_read_from_its_file():
    town = municipality.parse(DATA)
    assert town.name == "Villanueva del Río" and town.slug == "villanueva-del-rio"
    assert town.council_domain == "www.villanueva.example"
    assert town.jgl_year_url.format(year=2024) == "https://www.villanueva.example/jgl-2024/"
    assert town.first_year == 2019 and town.unpublished_example == ""
    assert town.current == "2023-2027"  # the last one that started, whatever the order in the file
    assert list(town.legislatures["2023-2027"]) == ["PSOE", "PP", "IU"]
    assert town.starts["2019-2023"] == date(2019, 6, 15)
    assert "_nota" not in town.colors and "_nota" not in town.legislatures
    assert (town.site_host, town.site_path, town.code_url) == ("ana.github.io", "/villanueva/",
                                                               "https://github.com/ana/villanueva")


def test_the_addresses_of_the_site_are_optional():
    data = copy.deepcopy(DATA)
    del data["web"]["direccion"], data["web"]["codigo"]
    town = municipality.parse(data)
    assert town.site_url == "" and town.code_url == ""


@pytest.mark.parametrize("change, message", [
    (lambda d: d["colores_grupos"].pop("IU"), "falta el color de IU"),
    (lambda d: d["colores_grupos"].update(PP="azul"), "el color de PP tiene que ser #rrggbb"),
    (lambda d: d["actas_por_año"].update(pleno="https://www.villanueva.example/pleno/"), "tiene que llevar {año}"),
    (lambda d: d.pop("web_ayuntamiento"), "falta «web_ayuntamiento»"),
    (lambda d: d["web"].pop("correo"), "falta «web.correo»"),
    (lambda d: d["legislaturas"]["2019-2023"].pop("inicio"), "falta «legislaturas.2019-2023.inicio»"),
    (lambda d: d["web"].update(direccion="https://ana.github.io/villanueva"), "acabar en /"),
    (lambda d: d["web"].update(codigo="github.com/ana/villanueva"), "empezar por https://"),
])
def test_a_wrong_file_says_what_is_wrong(change, message):
    data = copy.deepcopy(DATA)
    change(data)
    with pytest.raises(ValueError, match=message):
        municipality.parse(data)


def test_yecla_comes_from_its_file():
    raw = json.loads(municipality.PATH.read_text(encoding="utf-8"))
    town = municipality.load()
    assert texts.TOWN == raw["municipio"] == "Yecla" and texts.EMAIL == raw["web"]["correo"]
    assert texts.SOURCE == "Fuente: actas oficiales publicadas en yecla.es."
    assert votes.CURRENT == "2023-2027" and votes.GROUPS == ["PP", "PSOE", "Vox", "IU-Verdes"]
    assert sum(votes.LEGISLATURES[votes.CURRENT].values()) == 21
    assert town.jgl_year_url.format(year=2026) == "https://yecla.es/2026-actas-jgl/"


def test_regional_bodies_and_the_council_itself():
    assert money.PUBLIC.search("Instituto Murciano de Acción Social") and money.PUBLIC.search("CARM")
    assert not money.PUBLIC.search("Carmen Ruiz")
    assert money.NO_RECEIVER.search("Excmo. Ayuntamiento de Yecla")


def test_the_colours_of_the_groups_go_into_the_style_sheet():
    css = template.static_file("style.css").decode()
    assert template.PARTY_COLORS not in css
    assert ".party-iu-verdes { --party: #9b1b30; }" in css and ".party-cs { --party: #ff5824; }" in css
    assert template.version("style.css") != template.version("filters.js")


def test_the_file_is_published():
    assert public.is_allowed("analisis/municipio.json")
