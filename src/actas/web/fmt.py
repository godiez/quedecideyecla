import html
import posixpath
import re
import unicodedata
from datetime import date

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
BODY = {"JGL": "Junta de Gobierno", "PLENO": "Pleno"}
TOPICS: dict[str, list[str]] = {
    "Contratos y pagos": ["contrato", "pago_factura"],
    "Subvenciones y convenios": ["subvencion_concedida", "subvencion_recibida", "convenio"],
    "Obras y licencias": ["licencia_obra", "licencia_actividad", "suelo_no_urbanizable", "urbanismo_planeamiento"],
    "Fiestas y vía pública": ["via_publica_eventos"],
    "Personal": ["personal"],
    "Impuestos y presupuesto": ["fiscal", "presupuesto_hacienda", "patrimonio"],
    "Medio ambiente": ["medio_ambiente"],
    "Servicios y actividades": ["servicios_actividades"],
    "Política y organización": ["mocion_politica", "organizacion", "normativa", "informacion"],
    "Otros": ["reclamaciones", "otros"],
}
_TOPIC_OF = {c: t for t, cats in TOPICS.items() for c in cats}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def eur(x: float) -> str:
    cents = round(abs(x) * 100)
    sign = "-" if x < 0 and cents else ""
    return f"{sign}{thousands(cents // 100)},{cents % 100:02d} €"


def eur_short(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.2f}".replace(".", ",") + " M€"
    return f"{'-' if x < 0 else ''}{thousands(round(abs(x)))} €"


def long_date(d: date) -> str:
    return f"{d.day} de {MONTHS[d.month - 1]}"


def date_with_year(d: date) -> str:
    return f"{long_date(d)} de {d.year}"


def plain(s: str) -> str:
    """The same normalization as filters.js."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", plain(text)).strip("-")
    s = s[:60].rstrip("-")
    return s or "entidad"


def topic(category: str) -> str:
    return _TOPIC_OF.get(category, "Otros")


def rel(src: str, dst: str) -> str:
    base = "/" + src
    target = "/" + dst
    r = posixpath.relpath(target, base if base.endswith("/") else posixpath.dirname(base))
    if dst.endswith("/") or dst == "":
        r = "./" if r == "." else r.rstrip("/") + "/"
    return r
