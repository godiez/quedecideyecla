import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS minutes (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- jgl_minutes / plenary_minutes
    url TEXT NOT NULL UNIQUE,
    session_date TEXT,               -- ISO, may be missing
    session_number INTEGER,
    title TEXT NOT NULL DEFAULT '',
    listing_url TEXT,                -- yearly page where it appeared
    local_path TEXT,                 -- relative to the project root
    sha256 TEXT,
    size_bytes INTEGER,
    origin TEXT,                     -- downloaded / reused
    source_filename TEXT,            -- source file name (URL or Content-Disposition)
    discovered_at TEXT NOT NULL,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS minutes_date ON minutes (kind, session_date);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, kind: str, url: str, session_date: str | None,
           session_number: int | None, title: str, listing_url: str) -> bool:
    cur = conn.execute(
        "INSERT INTO minutes (kind, url, session_date, session_number, title, listing_url, discovered_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(url) DO NOTHING",
        (kind, url, session_date, session_number, title, listing_url, now()))
    if cur.rowcount:
        return True
    conn.execute(
        "UPDATE minutes SET session_date = COALESCE(?, session_date),"
        " session_number = COALESCE(?, session_number), title = ? WHERE url = ?",
        (session_date, session_number, title, url))
    return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
