import csv
import io

import pytest

from actas.web import model
from actas.web.build import build_site
from actas.web.pages import data

J1, P3 = "2026-01-07_JGL_01", "2026-03-02_PLENO_03"


@pytest.fixture
def site(mini_analysis):
    a, db = mini_analysis
    return model.build(a, db, 2026)


def _read(text):
    assert text.startswith("﻿")  # BOM: Excel opens accents correctly
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


def test_money_csv(site):
    f = dict(data.files(site))
    rows = _read(f["datos/dinero-2026.csv"])
    assert rows[0][:3] == ["Entidad", "Tipo", "Comprometido (€)"]
    actua = next(r for r in rows if r[0].startswith("Actúa"))
    assert actua[1] == "Empresa" and actua[2] == "50000,00"


def test_decisions_csv_without_personal_data(site):
    rows = _read(dict(data.files(site))["datos/decisiones-2026.csv"])
    head = rows[0]
    assert "Fecha" in head and "Ficha" in head and "Lugar" not in head
    text = "\n".join(";".join(r) for r in rows)
    assert "C/ Mayor" not in text and "Préstamo de 349.077 euros" in text
    assert len(rows) == 1 + len(site.decisions)


def test_csv_neutralizes_formulas():
    assert data.cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert data.cell("-5") == "'-5" and data.cell("Normal") == "Normal"


def test_build_writes_csv_and_links_them(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    build_site(a.parent, db, out)
    assert (out / "datos" / "dinero-2026.csv").exists()
    assert (out / "datos" / "decisiones-2026.csv").exists()
    assert 'href="../../datos/dinero-2026.csv"' in (out / "2026" / "dinero" / "index.html").read_text(encoding="utf-8")
    info = (out / "como-se-ha-hecho" / "index.html").read_text(encoding="utf-8")
    assert 'id="glosario"' in info and 'id="comprometido"' in info and 'id="en-especie"' in info
    assert "datos/decisiones-2026.csv" in info


def test_notes_link_to_glossary(site):
    from actas.web.pages import money as pm
    h = dict(pm.generate(site, root=True))[""]
    assert 'href="como-se-ha-hecho/#glosario"' in h
