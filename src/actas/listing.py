import html
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

MONTHS = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
     "octubre", "noviembre", "diciembre"], 1)}
MONTHS["setiembre"] = 9

_LINK_RE = re.compile(
    r'<a\b[^>]*href="([^"]+?(?:\.pdf|sedipualba\.es/firma/documento\.aspx\?csv=[^"]+))"[^>]*>(.*?)</a>',
    re.S | re.I)
_SEDE_RE = re.compile(r"sedipualba\.es/firma/documento\.aspx", re.I)
_SKIP_RE = re.compile(r"arqueo|convocatoria|orden[_ -]del[_ -]d[ií]a|liquidaci", re.I)
_TEXT_RE = re.compile(
    r"sesi[oó]n\s*n[ºo°]?\.?\s*(\d+)\s*,?\s*celebrada\s+el\s+(?:d[ií]a\s+)?(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
    re.I)
_FILENAME_PATTERNS = [
    (re.compile(r"^(\d{4})_(\d{1,2})_(\d{1,2})_(?:ac|acta)_(\d+)", re.I), "ymdn"),
    (re.compile(r"^ac_(\d+)_(\d{1,2})_(\d{1,2})_(\d{4})", re.I), "ndmy"),
    (re.compile(r"acta[-_]?(?:no)?(\d+)[-_]+(?:jgl[-_]+)?(\d{1,2})-(\d{1,2})-(\d{2,4})", re.I), "ndmy"),
]
_FILENAME_NUMBER_ONLY = re.compile(r"^acta[-_]?(\d+)\.pdf$", re.I)
# There may be tags between the date and "Sesión" ("<strong>29-12-2022</strong> <span>Sesión ...").
_PLENARY_HEADING_RE = re.compile(
    r"(?<!\d)(\d{1,2})([/-])(\d{1,2})\2(\d{4})(?:\s|<[^>]*>|&nbsp;)*-?(?:\s|<[^>]*>|&nbsp;)*sesi[oó]n", re.I)
_PLENARY_NUMBER_RE = re.compile(r"(?:^|[^a-z])(?:n|no|n[ºo°])[_.\s-]*(\d{1,3})(?=[^0-9]|$)", re.I)
_PLENARY_PATTERNS = [
    re.compile(r"(?:^|[_-])(?:n|no)[_-](\d+)[_-](?:fecha-)?(\d{1,2})[-_](\d{1,2})[-_](\d{2,4})", re.I),
    re.compile(r"actapleno(\d+?)(\d{2})-(\d{2})-(\d{4})", re.I),
]


@dataclass(frozen=True)
class MinutesLink:
    kind: str
    url: str
    date: str | None
    number: int | None
    title: str


def _iso(y: str, m: int | str, d: str) -> str | None:
    year = int(y)
    if year < 100:
        year += 2000
    try:
        return date(year, int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_minutes_filename(name: str) -> tuple[str | None, int] | None:
    if _SKIP_RE.search(name):
        return None
    for rx, order in _FILENAME_PATTERNS:
        m = rx.search(name)
        if m:
            vals = dict(zip(order, m.groups()))
            return _iso(vals["y"], vals["m"], vals["d"]), int(vals["n"])
    m = _FILENAME_NUMBER_ONLY.search(name)
    if m:
        return None, int(m.group(1))
    return None


def _parse_plenary_filename(name: str) -> tuple[str | None, int] | None:
    for rx in _PLENARY_PATTERNS:
        m = rx.search(name)
        if m:
            n, d, mo, y = m.groups()
            return _iso(y, mo, d), int(n)
    return None


def _plenary_from_context(name: str, heading_date: str | None) -> tuple[str | None, int | None] | None:
    parsed = _parse_plenary_filename(name)
    m = _PLENARY_NUMBER_RE.search(name.replace("PLENO", " "))
    number = parsed[1] if parsed else (int(m.group(1)) if m else None)
    when = heading_date or (parsed[0] if parsed else None)
    if when is None and number is None:
        return None
    return when, number


def parse_listing(page_html: str, base_url: str, kind: str) -> list[MinutesLink]:
    out: list[MinutesLink] = []
    seen: set[str] = set()
    headings = [(m.start(), _iso(m.group(4), m.group(3), m.group(1)))
                for m in _PLENARY_HEADING_RE.finditer(page_html)]
    for link in _LINK_RE.finditer(page_html):
        href, inner = link.groups()
        url = urljoin(base_url, html.unescape(href))
        # A link to the e-office has no file name: the date only comes from the heading.
        name = "" if _SEDE_RE.search(url) else url.rsplit("/", 1)[-1]
        text = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(inner)).split())
        if url in seen or _SKIP_RE.search(name):
            continue
        if kind != "plenary_minutes" and not name:
            continue
        if kind == "plenary_minutes":
            if not re.search(r"\bacta\b", text, re.I):
                continue
            before = [d for pos, d in headings if pos < link.start()]
            parsed = _plenary_from_context(name, before[-1] if before else None)
        else:
            m = _TEXT_RE.search(text)
            month = MONTHS.get(m.group(3).lower()) if m else None
            if m and month:
                parsed = (_iso(m.group(4), month, m.group(2)), int(m.group(1)))
            else:
                parsed = parse_minutes_filename(name)
        if not parsed:
            continue
        seen.add(url)
        title = text or name or url
        if kind == "plenary_minutes":
            title = "Acta del Pleno" + (f" nº {parsed[1]}" if parsed[1] else "") + (f" ({parsed[0]})" if parsed[0] else "")
        out.append(MinutesLink(kind, url, parsed[0], parsed[1], title))
    return out


def listing_urls(cfg: dict, last_year: int) -> list[tuple[str, str]]:
    urls = []
    for year in range(int(cfg["first_year"]), last_year + 1):
        if cfg.get("jgl_year_url"):
            urls.append(("jgl_minutes", cfg["jgl_year_url"].format(year=year)))
        if cfg.get("plenary_year_url"):
            urls.append(("plenary_minutes", cfg["plenary_year_url"].format(year=year)))
    return urls


# Names the e-office gives on download: "Acta Sesión Pleno nº 17 (27/12/2024)", "ACTA PLENO Nº 18(29-12-2022)",
# "Pleno Nº12(29-07-2022)", "ACTAPLENO.02(13-02-2023)FIRMADA".
_DOWNLOAD_RE = re.compile(
    r"pleno[_\s.-]*(?:n[ºo°]?\.?)?[_\s.-]*(\d{1,3})[_\s-]*\((\d{1,2})[-/](\d{1,2})[-/](\d{4})\)", re.I)
_DOWNLOAD_NUMBER_RES = [
    re.compile(r"pleno[_\s.-]*(?:extra[_\s.-]*)?(?:n[ºo°]?\.?)?[_\s.-]*(\d{1,3})(?!\d)", re.I),
    re.compile(r"(?:^|[\s_-])ac(\d{1,3})\s*\(", re.I),  # "Ac20(21-12-2020)"
]
_DOWNLOAD_CALL_RE = re.compile(r"convo|orden[_\s.-]+del[_\s.-]+d[ií]a", re.I)


def looks_like_call(filename: str) -> bool:
    """The site sometimes links the call to the meeting as if it were the minutes."""
    return bool(_DOWNLOAD_CALL_RE.search(re.sub(r"^Orden de publicaci[oó]n.*? - ", "", filename or "")))


def session_from_filename(filename: str) -> tuple[str | None, int | None]:
    m = _DOWNLOAD_RE.search(filename or "")
    if m:
        n, d, mo, y = m.groups()
        return _iso(y, mo, d), int(n)
    for rx in _DOWNLOAD_NUMBER_RES:
        m = rx.search(filename or "")
        if m:
            return None, int(m.group(1))
    return None, None


def session_number_from_filename(filename: str) -> int | None:
    return session_from_filename(filename)[1]
