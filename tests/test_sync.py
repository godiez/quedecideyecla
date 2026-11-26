from pathlib import Path

import pytest

from actas import catalog, sync

PAGE = """
<a href="https://yecla.es/wp-content/uploads/2022/11/2018_12_28_ac_56_jgl.pdf">Sesión nº 56,
 celebrada el 28 de diciembre de 2018</a>
<a href="https://yecla.es/wp-content/uploads/2026/09/ACTA-46.pdf">Sesión nº46, celebrada el 15 de Septiembre de 2026</a>
"""


class FakeFetcher:
    def __init__(self, pages=None, files=None):
        self.pages, self.files, self.requested = pages or {}, files or {}, []

    def get_text(self, url):
        if url not in self.pages:
            raise RuntimeError("404")
        return self.pages[url]

    def download(self, url):
        self.requested.append(url)
        data = self.files[url]
        return data if isinstance(data, tuple) else (data, None)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "PDF_DIR", tmp_path / "data" / "pdfs")
    return tmp_path, catalog.connect(tmp_path / "data" / "actas.sqlite")


def test_discover_registers_and_is_idempotent(env):
    _, conn = env
    f = FakeFetcher({"https://yecla.es/2018-actas-jgl/": PAGE})
    s = sync.discover(conn, f, first_year=2018, last_year=2018)
    assert s == {"pages": 1, "failed_pages": 1, "found": 2, "new": 2}
    assert sync.discover(conn, f, first_year=2018, last_year=2018)["new"] == 0
    rows = conn.execute("SELECT session_date, session_number FROM minutes ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("2018-12-28", 56), ("2026-09-15", 46)]


def test_fetch_reuses_local_copy_and_downloads_the_rest(env):
    root, conn = env
    sync.discover(conn, FakeFetcher({"https://yecla.es/2018-actas-jgl/": PAGE}), first_year=2018, last_year=2018)
    local = root / "otra"
    local.mkdir()
    (local / "2018_12_28_ac_56_jgl.pdf").write_bytes(b"%PDF-local")
    f = FakeFetcher(files={"https://yecla.es/wp-content/uploads/2026/09/ACTA-46.pdf": b"%PDF-web"})
    stats = sync.fetch(conn, f, [local])
    assert stats == {"reused": 1, "downloaded": 1, "failed": 0, "already": 0}
    assert f.requested == ["https://yecla.es/wp-content/uploads/2026/09/ACTA-46.pdf"]
    paths = [r[0] for r in conn.execute("SELECT local_path FROM minutes ORDER BY id")]
    assert paths == ["data/pdfs/jgl/2018/2018-12-28_JGL_56.pdf", "data/pdfs/jgl/2026/2026-09-15_JGL_46.pdf"]
    assert (root / paths[0]).read_bytes() == b"%PDF-local"
    assert sync.fetch(conn, f, [local])["already"] == 2


def test_fetch_rejects_non_pdf(env):
    _, conn = env
    catalog.upsert(conn, "jgl_minutes", "https://yecla.es/x/ACTA-1.pdf", "2020-01-01", 1, "t", "l")
    stats = sync.fetch(conn, FakeFetcher(files={"https://yecla.es/x/ACTA-1.pdf": b"<html>"}))
    assert stats["failed"] == 1


def test_same_session_twice_gets_distinct_names(env):
    _, conn = env
    for u in ("https://yecla.es/a/ACTA-1.pdf", "https://yecla.es/b/ACTA-1-corregida.pdf"):
        catalog.upsert(conn, "plenary_minutes", u, "2020-01-01", 1, "t", "l")
    f = FakeFetcher(files={"https://yecla.es/a/ACTA-1.pdf": b"%PDF-a",
                           "https://yecla.es/b/ACTA-1-corregida.pdf": b"%PDF-b"})
    sync.fetch(conn, f)
    paths = [Path(r[0]).name for r in conn.execute("SELECT local_path FROM minutes ORDER BY id")]
    assert paths == ["2020-01-01_PLENO_01.pdf", "2020-01-01_PLENO_01_id2.pdf"]


def test_extras_lists_unknown_pdfs(env):
    root, conn = env
    catalog.upsert(conn, "jgl_minutes", "https://yecla.es/x/ACTA-1.pdf", "2020-01-01", 1, "t", "l")
    sync.fetch(conn, FakeFetcher(files={"https://yecla.es/x/ACTA-1.pdf": b"%PDF-1"}))
    d = root / "sueltos"
    d.mkdir()
    (d / "copia.pdf").write_bytes(b"%PDF-1")
    (d / "otra.pdf").write_bytes(b"%PDF-2")
    assert [p.name for p in sync.extras(conn, [d])] == ["otra.pdf"]


def test_sede_link_gets_number_from_served_filename(env):
    _, conn = env
    url = "https://yecla.sedipualba.es/firma/documento.aspx?csv=H7AAAWDJDW9XK4YH922Q&modo=abrir"
    catalog.upsert(conn, "plenary_minutes", url, "2023-12-22", None, "Acta de la sesión", "l")  # typo
    f = FakeFetcher(files={url: (b"%PDF-x", "Acta Sesión Pleno nº 17 (27/12/2024) - SEFYCU 3483599.pdf")})
    sync.fetch(conn, f)
    row = conn.execute("SELECT session_number, local_path, source_filename FROM minutes").fetchone()
    assert row[0] == 17
    assert row[1] == "data/pdfs/pleno/2024/2024-12-27_PLENO_17.pdf"
    assert row[2].startswith("Acta Sesión Pleno nº 17")
