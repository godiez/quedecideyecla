import re
import shutil
import sqlite3
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from actas import catalog, listing, municipality
from actas.config import KIND_DIR, KIND_TAG, PDF_DIR, ROOT


def discover(conn: sqlite3.Connection, fetcher, last_year: int | None = None,
             first_year: int | None = None) -> dict[str, int]:
    town = municipality.load()
    cfg = {"jgl_year_url": town.jgl_year_url, "plenary_year_url": town.plenary_year_url,
           "first_year": first_year or town.first_year}
    stats = {"pages": 0, "failed_pages": 0, "found": 0, "new": 0}
    for kind, url in listing.listing_urls(cfg, last_year or date.today().year):
        try:
            page = fetcher.get_text(url)
        except Exception as exc:
            print(f"Aviso: no se pudo leer {url}: {exc}")
            stats["failed_pages"] += 1
            continue
        stats["pages"] += 1
        for m in listing.parse_listing(page, url, kind):
            stats["found"] += 1
            stats["new"] += catalog.upsert(conn, m.kind, m.url, m.date, m.number, m.title, url)
        conn.commit()
    return stats


def _url_name(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:180]


def target_path(row: sqlite3.Row, taken: set[str]) -> Path:
    kind_dir, tag = KIND_DIR[row["kind"]], KIND_TAG[row["kind"]]
    if row["session_date"]:
        num = f"_{row['session_number']:02d}" if row["session_number"] is not None else ""
        rel = Path(kind_dir, row["session_date"][:4], f"{row['session_date']}_{tag}{num}.pdf")
    else:
        rel = Path(kind_dir, "sin-fecha", _safe(_url_name(row["url"])))
    if str(rel) in taken:  # two URLs for the same session (e.g. a corrected version)
        rel = rel.with_name(f"{rel.stem}_id{row['id']}.pdf")
    return PDF_DIR / rel


def index_local(dirs: Iterable[Path]) -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for d in dirs:
        for p in sorted(Path(d).expanduser().rglob("*")):
            if p.suffix.lower() == ".pdf" and p.is_file():
                idx.setdefault(p.name, p)
                idx.setdefault(_safe(p.name), p)
    return idx


def fetch(conn: sqlite3.Connection, fetcher, local_dirs: Iterable[Path] = (),
          limit: int | None = None) -> dict[str, int]:
    local = index_local(local_dirs)
    rows = conn.execute("SELECT * FROM minutes ORDER BY kind, session_date, id").fetchall()
    taken = {r["local_path"].removeprefix("data/pdfs/") for r in rows if r["local_path"]}
    pending = [r for r in rows if not (r["local_path"] and (ROOT / r["local_path"]).exists())]
    stats = {"reused": 0, "downloaded": 0, "failed": 0, "already": len(rows) - len(pending)}
    for r in pending[:limit] if limit else pending:
        name = _url_name(r["url"])
        src = local.get(name) or local.get(_safe(name))
        filename = name
        if src:
            data, origin = src.read_bytes(), "reused"
        else:
            try:
                data, served = fetcher.download(r["url"])
                origin, filename = "downloaded", served or name
            except Exception as exc:
                print(f"Aviso: no se pudo descargar {r['url']}: {exc}")
                stats["failed"] += 1
                continue
        if not data.startswith(b"%PDF"):
            print(f"Aviso: {r['url']} no es un PDF" + (f" (copia local {src})" if src else ""))
            stats["failed"] += 1
            continue
        # The downloaded file name is more reliable than the page heading (which sometimes has typos).
        served_date, served_number = (listing.session_from_filename(filename) if origin == "downloaded"
                                      else (None, None))
        if origin == "downloaded" and listing.looks_like_call(filename):
            print(f"Aviso: {r['url']} parece una convocatoria, no un acta ({filename})")
        number = r["session_number"] if r["session_number"] is not None else served_number
        when = served_date or r["session_date"]
        r = {**dict(r), "session_number": number, "session_date": when}
        if r["local_path"]:
            taken.discard(r["local_path"].removeprefix("data/pdfs/"))
        path = target_path(r, taken)
        path.parent.mkdir(parents=True, exist_ok=True)
        if src:
            shutil.copy2(src, path)
        else:
            path.write_bytes(data)
        rel = str(path.relative_to(ROOT))
        taken.add(rel.removeprefix("data/pdfs/"))
        conn.execute(
            "UPDATE minutes SET local_path = ?, sha256 = ?, size_bytes = ?, origin = ?, fetched_at = ?,"
            " source_filename = ?, session_number = ?, session_date = ? WHERE id = ?",
            (rel, catalog.sha256_file(path), path.stat().st_size, origin, catalog.now(), filename,
             number, when, r["id"]))
        conn.commit()
        stats[origin] += 1
    return stats


def extras(conn: sqlite3.Connection, dirs: Iterable[Path]) -> list[Path]:
    known = {r[0] for r in conn.execute("SELECT sha256 FROM minutes WHERE sha256 IS NOT NULL")}
    seen: set[str] = set()
    out = []
    for p in sorted({p for p in index_local(dirs).values()}):
        h = catalog.sha256_file(p)
        if h not in known and h not in seen:
            seen.add(h)
            out.append(p)
    return out
