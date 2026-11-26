import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from datetime import date
from pathlib import Path

from actas import names
from actas.revision.data import VOTE_ID
from actas.web import privacy
from actas.web.texts import EMAIL, SITE_NAME

ALLOWED = [
    "pyproject.toml", "uv.lock", ".python-version", ".gitignore", "README.md", "AGENTS.md", "CLAUDE.md",
    "LICENSE", "LICENSE-DATOS",
    # Only code: a stray .env, key or database committed under src/ or tests/ by mistake is not published.
    "src/*.py", "src/*.html", "src/*.css", "src/*.js", "src/*/static/presentacion.mp4", "src/*/static/presentacion.jpg",
    "src/*/static/vista-previa.png", "tests/*.py", "video/record.py", "video/stage.html", "video/preview.py",
    "video/preview.html",
    "analisis/INSTRUCCIONES.md", "analisis/ocr.sh", "analisis/avisos.json", "analisis/municipio.json",
    "analisis/*/json/*.json", "analisis/*/votos/*.json", "analisis/*/alias.json", "analisis/*/revision.json",
    "analisis/*/reclasificacion.json", names.REVIEWED_PATH,
]
MARKDOWN = {"README.md", "AGENTS.md", "CLAUDE.md", "analisis/INSTRUCCIONES.md"}
AUTHOR = {"GIT_AUTHOR_NAME": SITE_NAME, "GIT_AUTHOR_EMAIL": EMAIL, "GIT_COMMITTER_NAME": SITE_NAME,
          "GIT_COMMITTER_EMAIL": EMAIL}
PRIVACY_NOTE = "Privacidad: se quita un dato que podía identificar a una persona."
NAMES_HINT = ("\nUn nombre real se corrige en revision.json con una nota que empiece por «Privacidad». Si no es una persona "
              "particular (una calle, una obra, un cargo público), su frase va en analisis/nombres_revisados.json.")
_REVISION = re.compile(r"^analisis/(\d{4})/revision\.json$")
_CASE_TOKEN = re.compile(r"(?<![A-Za-z0-9])\d{6,8}[A-Z](?![A-Za-z0-9])")
# «expte. 1129263X», «exptes. 509033Q, 1103035T y 941685X», «expediente aparte 1021064W», «"expediente": "1186986R"».
_LABELLED = re.compile(r"\bexp(?:tes?|edientes?)\b\"?\.?:?\s*\"?(?:n[º°o]s?\.?\s*)?(?:(?:de|del|la|sesi[oó]n|aparte)\s+){0,2}"
                       r"((?:\d{6,8}[A-Z](?:\s*(?:,|;|/|y|e|-)\s*)?)+)", re.I)
# After X, Y or Z it looks like a NIE, unless the letter is the conjunction «y» or «e» («509033Q y 1093901H»).
_NIE_PREFIX = re.compile(r"[XYZxyz][\s./-]{0,3}$")
_CONJUNCTION = re.compile(r"(?:^|[\s,;(])[ye] $")
# Tax id of an organisation: not K, L, M, X, Y or Z, which are people.
_CIF = re.compile(r"(?<![A-Za-z0-9])([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-J])(?![A-Za-z0-9])")


def valid_cif(digits: str, control: str) -> bool:
    odd = sum(sum(divmod(2 * int(d), 10)) for d in digits[0::2])
    even = sum(int(d) for d in digits[1::2])
    c = (10 - (odd + even) % 10) % 10
    return control in (str(c), "JABCDEFGHI"[c])


# Matches of the privacy check reviewed by hand, not personal data: (file, value as the check gives it).
REVIEWED: set[tuple[str, str]] = set()


def git(cwd: Path, *args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], check=check, capture_output=True,
                          env={**os.environ, **env} if env else None)


def is_allowed(path: str) -> bool:
    if path.endswith(".md") and path not in MARKDOWN:
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in ALLOWED)


def committed_files(repo: Path, ref: str = "HEAD") -> dict[str, bytes]:
    archive = git(repo, "archive", "--format=tar", ref).stdout
    out = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            if member.isfile() and is_allowed(member.name) and "__pycache__" not in member.name:
                out[member.name] = tar.extractfile(member).read()
    return out


def _is_privacy(review: dict) -> bool:
    return (review.get("nota") or "").startswith("Privacidad")


def _dump(data) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def clean(files: dict[str, bytes]) -> dict[str, bytes]:
    out = dict(files)
    for path, raw in files.items():
        if path.startswith("analisis/") and "/json/" in path:
            d = json.loads(raw)
            d.pop("notas", None)
            out[path] = _dump(d)
    for path, raw in files.items():
        if not (m := _REVISION.match(path)):
            continue
        reviews = json.loads(raw)
        # (folder, list) → doc → position → changes
        fixes: dict[tuple[str, str], dict[str, dict[int, dict]]] = {("json", "puntos"): {}, ("votos", "votaciones"): {}}
        for pid, r in reviews.items():
            r.pop("original", None)
            if _is_privacy(r):
                r["nota"] = PRIVACY_NOTE
                if vote := VOTE_ID.match(pid):
                    where, doc, i = ("votos", "votaciones"), vote["doc"], vote["index"]
                else:
                    where, (doc, i) = ("json", "puntos"), pid.rsplit(":", 1)
                fixes[where].setdefault(doc, {})[int(i)] = r.get("cambios") or {}
        out[path] = _dump(reviews)
        for (folder, key), by_doc in fixes.items():
            for doc, by_position in by_doc.items():
                target = f"analisis/{m.group(1)}/{folder}/{doc}.json"
                if target not in out:
                    continue
                d = json.loads(out[target])
                for i, changes in by_position.items():
                    if i < len(d.get(key, [])):
                        d[key][i].update(changes)
                out[target] = _dump(d)
    return out


def _known_case_files(path: str, text: str) -> set[str]:
    """Never any number of the free text: a DNI or NIE written in a note would allow itself."""
    out = set()
    for m in _LABELLED.finditer(text):
        out |= set(_CASE_TOKEN.findall(m.group(1)))
    if "/json/" in path:
        for p in json.loads(text).get("puntos", []):
            out |= set(_CASE_TOKEN.findall(str(p.get("expediente") or "")))
    return {c for c in out if not privacy.valid_dni(c)}


def _mask(text: str, known: set[str]) -> str:
    def case_file(m):
        before = text[max(0, m.start() - 6):m.start()]
        if m.group(0) not in known or (_NIE_PREFIX.search(before) and not _CONJUNCTION.search(before)):
            return m.group(0)
        return "EXPTE"

    text = _CASE_TOKEN.sub(case_file, text)
    return _CIF.sub(lambda m: "CIF" if valid_cif(m.group(2), m.group(3)) else m.group(0), text)


def findings(files: dict[str, bytes]) -> list[str]:
    out = []
    for path, raw in files.items():
        if not path.startswith("analisis/"):  # the tests of the check itself carry fake DNIs
            continue
        text = privacy.INVISIBLE.sub("", raw.decode("utf-8"))
        # Masked first, so «3 584326N» or «509033Q y 1093901H» is not taken for a DNI or a NIE.
        known = _known_case_files(path, text)
        out += [f"{path}: {v}" for v in privacy._findings(_mask(text, known), known) if (path, v) not in REVIEWED]
    return out


def export(repo: Path, target: Path, ref: str = "HEAD") -> str | None:
    files = clean(committed_files(repo, ref))
    named, no_text = names.findings(files, repo / "analisis", names.load_reviewed(files.get(names.REVIEWED_PATH)))
    found = findings(files) + named
    if found:
        raise ValueError("El control de privacidad ha encontrado datos que no se pueden publicar:\n  "
                         + "\n  ".join(found) + (NAMES_HINT if named else ""))
    if no_text:
        print(f"Aviso: {len(no_text)} actas sin texto en analisis/<año>/txt/: de ellas solo se han mirado los «D.» y "
              f"«Dña.» de lo publicado y las entidades, no los nombres del acta.")
    if not target.exists():
        target.mkdir(parents=True)
        git(target, "init", "-q", "-b", "main")
    elif not (target / ".git").exists():
        raise ValueError(f"{target} existe y no es un repositorio git")
    for p in target.iterdir():
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    for path, raw in files.items():
        dest = target / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    git(target, "add", "-A")
    tree = git(target, "write-tree").stdout.decode().strip()
    current = git(target, "rev-parse", "--verify", "--quiet", "refs/heads/main", check=False).stdout.decode().strip()
    if current and git(target, "rev-parse", f"{current}^{{tree}}").stdout.decode().strip() == tree:
        return None
    # A single commit without history, so a later privacy correction does not stay in an older commit.
    commit = git(target, "commit-tree", tree, "-m", f"Actualización del {date.today().isoformat()}",
                 env=AUTHOR).stdout.decode().strip()
    git(target, "update-ref", "refs/heads/main", commit)
    return commit
