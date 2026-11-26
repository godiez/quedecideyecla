import json
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_docs(analysis: Path) -> list[dict]:
    reviews = _read(analysis / "revision.json")
    reclass = _read(analysis / "reclasificacion.json")
    docs = []
    for f in sorted((analysis / "json").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d["doc"] = f.stem
        points = []
        for i, p in enumerate(d.get("puntos", [])):
            pid = f"{f.stem}:{i}"
            r = reviews.get(pid)
            if r and r.get("estado") == "descartado":
                continue
            auto = {"categoria": reclass[pid]["categoria"]} if pid in reclass else {}
            points.append({**p, **auto, **((r or {}).get("cambios") or {}), "id": pid,
                           "revision": r["estado"] if r else "pendiente"})
        d["puntos"] = points
        docs.append(d)
    return docs
