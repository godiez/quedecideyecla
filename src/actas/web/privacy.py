import html
import re
from pathlib import Path

from actas.web.texts import EMAIL

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
SEP = r"[\s./-]{0,3}"
SEP_DIGITS = r"[.\s-]?"
# «1.222.463 m²» is a surface, not a DNI.
DNI = re.compile(rf"(?<!\d)(\d{{1,2}}{SEP_DIGITS}\d{{3}}{SEP_DIGITS}\d{{3}})({SEP})([A-HJ-NP-TV-Z])(?![A-Za-z0-9²³])",
                 re.I)
NIE = re.compile(rf"(?<![A-Za-z0-9])([XYZ]){SEP}(\d{{7}}){SEP}([A-Z])(?![A-Za-z0-9])", re.I)
CADASTRAL = [re.compile(r"\b\d{7}[A-Z]{2}\d{4}[A-Z]\d{4}[A-Z]{2}\b", re.I),   # urban
             re.compile(r"\b\d{5}[A-Z]\d{12}[A-Z]{2}\b", re.I)]               # rustic
LICENSE_PLATE = re.compile(r"\b\d{4}[\s-]?[BCDFGHJKLMNPRSTVWXYZ]{3}\b", re.I)
EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w.,=/#-])(?:\+34[\s.-]?)?[6-9]\d{2}(?:[\s.-]?\d{3}[\s.-]?\d{3}|[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})"
                   r"(?![\w,/-]|\.\d)")  # not inside a version stamp, a hash or a reference


INVISIBLE = re.compile("[­​-‍⁠﻿]")


def _clean(s: str) -> str:
    return re.sub(r"[\s./-]", "", s).upper()


def valid_dni(dni: str) -> bool:
    return len(dni) == 9 and dni[:8].isdigit() and DNI_LETTERS[int(dni[:8]) % 23] == dni[8]


def _valid_any(v: str) -> bool:
    """Valid with 8 digits or with 7 (old DNI, a leading zero)."""
    return valid_dni(v) or (len(v) == 8 and valid_dni("0" + v))


def _findings(text: str, allowed: set[str]) -> list[str]:
    out = []
    nies = [m.span() for m in NIE.finditer(text)]
    for m in DNI.finditer(text):
        if any(a <= m.start() < b for a, b in nies):
            continue
        v = _clean(m.group(0))
        # «de 3.114.363 a 3.281.026»: a lower-case letter after a space is a word, unless it makes a valid DNI.
        if m.group(3).islower() and re.search(r"\s", m.group(2)) and not _valid_any(v):
            continue
        # 8 digits with a valid letter never; 7 digits (case files) only if it is not a known case file.
        if v not in allowed or valid_dni(v):
            out.append(v)
    for m in NIE.finditer(text):
        v = _clean(m.group(0))
        if v not in allowed:
            out.append(v)
    for pattern in CADASTRAL:
        out += [m.group(0).upper() for m in pattern.finditer(text)]
    out += [_clean(m.group(0)) for m in LICENSE_PLATE.finditer(text)]
    out += [m.group(0) for m in EMAIL_ADDRESS.finditer(text) if m.group(0).lower() != EMAIL]
    out += [re.sub(r"\D", "", m.group(0)) for m in PHONE.finditer(text)]
    return out


def check(out: Path, allowed: set[str]) -> list[str]:
    findings = []
    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        try:
            text = INVISIBLE.sub("", html.unescape(f.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
        findings += [f"{f.relative_to(out).as_posix()}: {v}" for v in _findings(text, allowed)]
    return findings
