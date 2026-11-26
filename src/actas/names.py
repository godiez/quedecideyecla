import json
import re
from bisect import bisect_right
from collections.abc import Iterator
from itertools import accumulate
from pathlib import Path

from actas import money

REVIEWED_PATH = "analisis/nombres_revisados.json"
_SEPARATOR = "\x00\x00"
_AI_JSON = re.compile(r"^analisis/(\d{4})/json/([^/]+)\.json$")
_WORD = r"[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñüç]+(?:-[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñüç]+)?"
PARTICLES = {"de", "del", "la", "las", "los", "y"}
# Not «y»: «entre Don Lucio y Numancia» is two streets.
_GLUE = r"(?:(?:de|del|la|las|los)[ \t]+)*"
# On one line: the next line of the minute («Calle», «Placeta») does not become a surname.
# Not after a letter or a dot: «S.D. Hispania» and «A.D. Albatros» are clubs.
HONORIFIC = re.compile(rf"(?=[DS])(?<![\w.])(?:D\.ª|Dª|D\.|Dña\.?|Doña|DOÑA|Don|DON|Sr\.|Sra\.)[ \t]+"
                       rf"({_WORD}(?:[ \t]+{_GLUE}{_WORD}){{1,3}})")
POSTS = {"alcalde", "alcaldesa", "concejal", "concejala", "secretario", "secretaria", "interventor", "interventora",
         "tesorero", "tesorera", "consejero", "consejera", "presidente", "presidenta", "director", "directora",
         "portavoz", "teniente", "diputado", "diputada", "delegado", "delegada", "jefe", "jefa", "arquitecto",
         "arquitecta", "ingeniero", "ingeniera", "tecnico", "tecnica", "letrado", "letrada", "gerente", "ministro",
         "ministra", "rector", "rectora", "juez", "jueza", "notario", "notaria", "registrador", "registradora"}


_ACCENTS = str.maketrans("áàâäéèêëíìîïóòôöúùûüñçÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜÑÇ", "aaaaeeeeiiiioooouuuuncAAAAEEEEIIIIOOOOUUUUNC")


def normalize(s: str) -> str:
    """A table, not unicodedata: it runs on every published text."""
    return s.translate(_ACCENTS).casefold()


def honorific_names(text: str) -> set[str]:
    out = {}
    for m in HONORIFIC.finditer(text):
        words = [w for w in m.group(1).split() if w.lower() not in PARTICLES]
        if len(words) < 2 or normalize(words[0]) in POSTS:
            continue
        # The minutes also write companies and headings in capitals («MAZA CONSTRUCCIONES»).
        if words[0].isupper() and money.strip_accents(words[0]) not in money.FIRST_NAMES:
            continue
        name = " ".join(words[:2])
        out.setdefault(normalize(name), name)
    return set(out.values())


def _words_pattern(words: list[str], glue: str) -> str:
    return r"\b" + glue.join(re.escape(normalize(w)) for w in words) + r"\b"


def _names_regex(names: set[str], text: str) -> tuple[re.Pattern, list[str]] | None:
    # Almost none of the minute's names reach what is published, and searching for them is most of the run time.
    words = set(re.findall(r"\w+", text))
    ordered = sorted(n for n in names if all(w in words for w in re.findall(r"\w+", normalize(n))))
    if not ordered:
        return None
    glue = r"\s+(?:(?:de|del|la|las|los|y)\s+)*"
    body = "|".join(f"(?P<n{i}>{glue.join(re.escape(normalize(w)) for w in n.split())})" for i, n in enumerate(ordered))
    return re.compile(rf"\b(?:{body})\b"), ordered


def load_reviewed(raw: bytes | str | None) -> dict[str, str]:
    data = json.loads(raw) if raw else {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _phrases(reviewed: dict[str, str]) -> list[re.Pattern]:
    return [re.compile(_words_pattern(p.split(), r"\s+")) for p in reviewed]


def _allowed(text: str, start: int, end: int, phrases: list[re.Pattern]) -> bool:
    return any(m.start() < end and start < m.end() for p in phrases for m in p.finditer(text))


def _strings(value, where: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{where}.{k}" if where else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{where}[{i}]")


def _copied(sources: list[tuple[str, object]], minute_names: set[str], phrases: list[re.Pattern]) -> list[str]:
    out = []
    for path, data in sources:
        items = [(where, s) for where, s in _strings(data) if len(s) >= 7]  # shorter: a date, a type, a reference
        if not items:
            continue
        # One search per file; the separator is neither a letter nor a space, so no name spans two texts.
        joined = _SEPARATOR.join(s for _, s in items)
        texts = [normalize(s) for _, s in items]
        text = _SEPARATOR.join(texts)
        starts = list(accumulate((len(t) + len(_SEPARATOR) for t in texts[:-1]), initial=0))
        compiled = _names_regex(minute_names | honorific_names(joined), text)
        if not compiled:
            continue
        regex, ordered = compiled
        seen = set()
        for m in regex.finditer(text):
            i = bisect_right(starts, m.start()) - 1
            name = ordered[int(m.lastgroup[1:])]
            if (i, normalize(name)) in seen or _allowed(texts[i], m.start() - starts[i], m.end() - starts[i], phrases):
                continue
            seen.add((i, normalize(name)))
            out.append(f"{path} {items[i][0]}: {name}")
    return out


def _entities(path: str, ai: dict, review: dict, doc: str, phrases: list[re.Pattern]) -> list[str]:
    """Whatever type the AI gave them: one marked as a person is hidden by the site, but its JSON is published."""
    out = []
    for i, p in enumerate(ai.get("puntos") or []):
        changes = (review.get(f"{doc}:{i}") or {}).get("cambios") or {}
        for source, point in (("", p), (" (revision)", changes)):
            names = [e.get("nombre") or "" for e in point.get("entidades") or []]
            names += [str(a.get("entidad") or "") for a in point.get("importes") or []]
            for name in names:
                if (money.looks_like_person(name) and not money.PRIVATE_PERSON.match(name)
                        and not _allowed(normalize(name), 0, len(normalize(name)), phrases)):
                    out.append(f"{path} puntos[{i}]{source}: {name}")
    return out


def findings(files: dict[str, bytes], analysis: Path, reviewed: dict[str, str]) -> tuple[list[str], list[str]]:
    phrases = _phrases(reviewed)
    out, no_text = [], []
    for path, raw in sorted(files.items()):
        if not (m := _AI_JSON.match(path)):
            continue
        year, doc = m.groups()
        ai = json.loads(raw)
        ai.pop("notas", None)
        review_path, votes_path = f"analisis/{year}/revision.json", f"analisis/{year}/votos/{doc}.json"
        review = {k: v for k, v in json.loads(files.get(review_path) or b"{}").items() if k.split(":", 1)[0] == doc}
        sources = [(path, ai), (review_path, review)]
        if votes_path in files:
            sources.append((votes_path, json.loads(files[votes_path])))
        txt = analysis / year / "txt" / f"{doc}.txt"
        if txt.exists():
            minute_names = honorific_names(txt.read_text(encoding="utf-8", errors="replace"))
        else:
            minute_names = set()
            no_text.append(doc)
        out += _copied(sources, minute_names, phrases)
        out += _entities(path, ai, review, doc, phrases)
    return out, no_text
