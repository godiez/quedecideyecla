import json
import re
import sqlite3
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote

from actas.revision import data

_DOC_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(JGL|PLENO)_(\d+)$")


def pdf_index(pdf_dir: Path, db_path: Path | None) -> dict[str, Path]:
    idx = {p.stem: p for p in pdf_dir.rglob("*.pdf") if _DOC_RE.match(p.stem)}
    if db_path and db_path.exists():
        conn = sqlite3.connect(db_path)
        for kind, num, local in conn.execute(
                "SELECT kind, session_number, local_path FROM minutes WHERE session_date IS NULL"
                " AND local_path IS NOT NULL AND session_number IS NOT NULL"):
            tag = "JGL" if kind == "jgl_minutes" else "PLENO"
            idx.setdefault(f"#{tag}_{num:02d}", pdf_dir.parents[1] / local)
        conn.close()
    return idx


class State:
    def __init__(self, analysis: Path, pdfs: dict[str, Path]):
        self.analysis = analysis
        self.revision_path = analysis / "revision.json"
        self.year = analysis.name if re.fullmatch(r"\d{4}", analysis.name) else None
        self.points = data.load_points(analysis)
        self.by_id = {p["id"]: p for p in self.points}
        self.pdfs = pdfs
        self.lock = threading.Lock()

    def pdf(self, doc: str) -> Path | None:
        m = _DOC_RE.match(doc)
        if not m or doc not in {p["doc"] for p in self.points}:
            return None
        return self.pdfs.get(doc) or self.pdfs.get(f"#{m.group(2)}_{m.group(3)}")


def _handler(state: State):
    page = resources.files("actas.revision").joinpath("page.html").read_bytes()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _local_host(self) -> bool:
            """Blocks DNS rebinding from a web page."""
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _same_origin(self) -> bool:
            """A cross-site form can't send a JSON body without a CORS preflight, which this server never answers."""
            port = self.server.server_address[1]
            origin = self.headers.get("Origin")
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            return (ctype == "application/json"
                    and (origin is None or origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")))

        def _send(self, code, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            if not self._local_host():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "solo desde este ordenador"})
            path = unquote(self.path.split("?", 1)[0])
            if path == "/":
                return self._send(200, page, "text/html; charset=utf-8")
            if path == "/api/points":
                with state.lock:
                    revs = data.load_reviews(state.revision_path)
                return self._json(200, {"year": state.year, "points": state.points, "reviews": revs,
                                        "categories": data.CATEGORIES, "results": data.RESULTS,
                                        "category_help": data.CATEGORY_HELP, "interest_help": data.INTEREST_HELP})
            m = re.match(r"^/pdf/([\w-]+)\.pdf$", path)
            if m:
                pdf = state.pdf(m.group(1))
                if not pdf or not pdf.exists():
                    return self._json(404, {"error": "PDF no encontrado"})
                return self._send(200, pdf.read_bytes(), "application/pdf")
            self._json(404, {"error": "no existe"})

        def do_POST(self):
            if not (self._local_host() and self._same_origin()):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "petición de otro origen"})
            m = re.match(r"^/api/review/([\w:-]+)$", unquote(self.path))
            if not m or m.group(1) not in state.by_id:
                return self._json(404, {"error": "punto desconocido"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                point = state.by_id[m.group(1)]
                changes = {k: v for k, v in (body.get("cambios") or {}).items() if point.get(k) != v}
                with state.lock:
                    rec = data.save_review(state.revision_path, m.group(1), body.get("estado", ""),
                                           changes, str(body.get("nota") or ""),
                                           original={k: point.get(k) for k in changes})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            self._json(200, rec)

    return H


def create_server(analysis: Path, pdf_dir: Path, db_path: Path | None, port: int = 8766) -> ThreadingHTTPServer:
    state = State(analysis, pdf_index(pdf_dir, db_path))
    return ThreadingHTTPServer(("127.0.0.1", port), _handler(state))
