import json
import threading
import urllib.error
import urllib.request

import pytest

from actas.revision import server as review_server


@pytest.fixture
def server(tmp_path):
    analysis = tmp_path / "analisis"
    (analysis / "json").mkdir(parents=True)
    (analysis / "txt").mkdir()
    doc = {"organo": "JGL", "fecha": "2026-01-07", "puntos": [
        {"ref": "2.1", "titulo": "Pago a FCC Aqualia", "categoria": "pago_factura", "importe_eur": 100.0}]}
    (analysis / "json" / "2026-01-07_JGL_01.json").write_text(json.dumps(doc), encoding="utf-8")
    (analysis / "txt" / "2026-01-07_JGL_01.txt").write_text("a\fPago a FCC Aqualia", encoding="utf-8")
    pdfs = tmp_path / "data" / "pdfs" / "jgl" / "2026"
    pdfs.mkdir(parents=True)
    (pdfs / "2026-01-07_JGL_01.pdf").write_bytes(b"%PDF-1.4 test")
    srv = review_server.create_server(analysis, tmp_path / "data" / "pdfs", None, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", analysis
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_page_points_and_pdf(server):
    base, _ = server
    assert _get(base + "/")[1].startswith("text/html")
    data = json.loads(_get(base + "/api/points")[2])
    assert data["points"][0]["id"] == "2026-01-07_JGL_01:0" and data["points"][0]["page"] == 2
    assert data["year"] is None  # the folder is not a year (analisis/<año>/ in real use)
    assert _get(base + "/pdf/2026-01-07_JGL_01.pdf")[2].startswith(b"%PDF")


def test_post_revision_keeps_original_and_ignores_unchanged_fields(server):
    base, analysis = server
    rec = _post(base + "/api/review/2026-01-07_JGL_01:0",
                {"estado": "corregido", "cambios": {"importe_eur": 90.0, "titulo": "Pago a FCC Aqualia"}, "nota": "x"})
    assert rec["cambios"] == {"importe_eur": 90.0} and rec["original"] == {"importe_eur": 100.0}
    saved = json.loads((analysis / "revision.json").read_text())
    assert saved["2026-01-07_JGL_01:0"]["estado"] == "corregido"


def test_unknown_point_and_traversal_are_rejected(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(base + "/api/review/nada:0", {"estado": "aprobado"})
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + "/pdf/..%2F..%2Fetc.pdf")
    assert e.value.code == 404


def _post_raw(url, body: bytes, headers: dict):
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req) as r:
        return r.status


@pytest.mark.parametrize("headers", [
    {"Content-Type": "application/json", "Origin": "https://evil.example"},   # another website (CSRF)
    {"Content-Type": "text/plain"},                                           # simple cross-site form/fetch
    {"Content-Type": "application/json", "Host": "evil.example:8766"},        # DNS rebinding
])
def test_post_from_another_origin_is_rejected(server, headers):
    base, analysis = server
    with pytest.raises(urllib.error.HTTPError) as e:
        _post_raw(base + "/api/review/2026-01-07_JGL_01:0", json.dumps({"estado": "aprobado"}).encode(), headers)
    assert e.value.code == 403
    assert not (analysis / "revision.json").exists()


def test_get_with_foreign_host_is_rejected(server):
    base, _ = server
    req = urllib.request.Request(base + "/api/points", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_post_with_own_origin_is_accepted(server):
    base, _ = server
    status = _post_raw(base + "/api/review/2026-01-07_JGL_01:0", json.dumps({"estado": "aprobado"}).encode(),
                       {"Content-Type": "application/json", "Origin": base})
    assert status == 200


def test_page_escapes_every_interpolated_point_field():
    import re
    from importlib import resources
    page = resources.files("actas.revision").joinpath("page.html").read_text(encoding="utf-8")
    # A data value interpolated as-is: ${p.fecha}, ${v.importe_eur ?? ""}, ${current.page}, ${c}, ${x}…
    direct = re.compile(r'^((p|v|i|e|current|r)\.\w+( \?\? "")?|c|x)$')
    raw = [m for m in re.findall(r"\$\{([^}]*)\}", page) if direct.match(m.strip())]
    assert raw == []


def test_the_page_shows_the_year_being_reviewed(tmp_path):
    from importlib import resources
    analysis = tmp_path / "2024"
    (analysis / "json").mkdir(parents=True)
    assert review_server.State(analysis, {}).year == "2024"
    page = resources.files("actas.revision").joinpath("page.html").read_text(encoding="utf-8")
    assert "<h1>Revisión de actas</h1>" in page and "2026" not in page.split("<script>")[0]
