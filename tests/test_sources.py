import json

from actas import sources


def _minutes(tmp_path, doc, points, **extra):
    (tmp_path / "json").mkdir(exist_ok=True)
    d = {"doc": doc, "organo": "JGL", "sesion": 1, "fecha": "2026-01-07", "puntos": points, **extra}
    (tmp_path / "json" / f"{doc}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_load_docs_applies_reclassification_and_review(tmp_path):
    doc = "2026-01-07_JGL_01"
    _minutes(tmp_path, doc, [
        {"ref": "1", "titulo": "Poda de pinos", "categoria": "otros"},
        {"ref": "2", "titulo": "Pago", "categoria": "pago_factura", "importe_eur": 100},
        {"ref": "3", "titulo": "Error", "categoria": "otros"},
    ])
    (tmp_path / "reclasificacion.json").write_text(json.dumps(
        {"_motivo": "x", f"{doc}:0": {"categoria": "medio_ambiente", "antes": "otros", "titulo": "Poda"}}))
    (tmp_path / "revision.json").write_text(json.dumps({
        f"{doc}:1": {"estado": "corregido", "cambios": {"importe_eur": 250}, "nota": "", "original": {}},
        f"{doc}:2": {"estado": "descartado", "cambios": {}, "nota": "", "original": {}},
    }))
    docs = sources.load_docs(tmp_path)
    assert [d["doc"] for d in docs] == [doc]
    pts = docs[0]["puntos"]
    assert [p["id"] for p in pts] == [f"{doc}:0", f"{doc}:1"]
    assert pts[0]["categoria"] == "medio_ambiente" and pts[0]["revision"] == "pendiente"
    assert pts[1]["importe_eur"] == 250 and pts[1]["revision"] == "corregido"


def test_human_review_beats_reclassification(tmp_path):
    doc = "2026-01-07_JGL_01"
    _minutes(tmp_path, doc, [{"ref": "1", "titulo": "Poda", "categoria": "otros"}])
    (tmp_path / "reclasificacion.json").write_text(json.dumps({f"{doc}:0": {"categoria": "medio_ambiente"}}))
    (tmp_path / "revision.json").write_text(json.dumps(
        {f"{doc}:0": {"estado": "corregido", "cambios": {"categoria": "servicios_actividades"}}}))
    assert sources.load_docs(tmp_path)[0]["puntos"][0]["categoria"] == "servicios_actividades"
