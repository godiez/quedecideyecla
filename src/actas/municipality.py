import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

PATH = Path(__file__).resolve().parents[2] / "analisis" / "municipio.json"
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Municipality:
    name: str
    council_url: str
    jgl_year_url: str
    plenary_year_url: str
    first_year: int
    unpublished_example: str
    regional_bodies: tuple[str, ...]
    legislatures: dict[str, dict[str, int]]
    starts: dict[str, date]
    colors: dict[str, str]
    site_name: str
    email: str
    responsible: str
    site_url: str = ""
    code_url: str = ""

    @property
    def council_domain(self) -> str:
        return urlparse(self.council_url).netloc

    @property
    def site_host(self) -> str:
        return urlparse(self.site_url).netloc

    @property
    def site_path(self) -> str:
        return urlparse(self.site_url).path or "/"

    @property
    def current(self) -> str:
        return max(self.starts, key=self.starts.get)

    @property
    def slug(self) -> str:
        plain = "".join(c for c in unicodedata.normalize("NFD", self.name) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _get(data: dict, key: str, where: str = ""):
    if key not in data:
        raise ValueError(f"municipio.json: falta «{where}{key}»")
    return data[key]


def _fields(data: dict) -> dict:
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _year_url(minutes: dict, key: str) -> str:
    url = _get(minutes, key, "actas_por_año.")
    if "{año}" not in url:
        raise ValueError(f"municipio.json: «actas_por_año.{key}» tiene que llevar {{año}}")
    return url.replace("{año}", "{year}")


def parse(data: dict) -> Municipality:
    minutes = _get(data, "actas_por_año")
    legislatures = _fields(_get(data, "legislaturas"))
    if not legislatures:
        raise ValueError("municipio.json: «legislaturas» está vacío")
    for key, leg in legislatures.items():
        _get(leg, "inicio", f"legislaturas.{key}.")
        _get(leg, "grupos", f"legislaturas.{key}.")
    colors = _fields(_get(data, "colores_grupos"))
    groups = {g for leg in legislatures.values() for g in leg["grupos"]}
    if missing := sorted(groups - set(colors)):
        raise ValueError(f"municipio.json: falta el color de {', '.join(missing)} en «colores_grupos»")
    if bad := sorted(g for g, c in colors.items() if not _COLOR.fullmatch(str(c))):
        raise ValueError(f"municipio.json: el color de {', '.join(bad)} tiene que ser #rrggbb")
    web = _get(data, "web")
    site_url, code_url = web.get("direccion") or "", web.get("codigo") or ""
    if site_url and not (site_url.startswith("https://") and site_url.endswith("/")):
        raise ValueError("municipio.json: «web.direccion» tiene que empezar por https:// y acabar en /")
    if code_url and not code_url.startswith("https://"):
        raise ValueError("municipio.json: «web.codigo» tiene que empezar por https://")
    return Municipality(
        name=_get(data, "municipio"), council_url=_get(data, "web_ayuntamiento"),
        jgl_year_url=_year_url(minutes, "junta_de_gobierno"), plenary_year_url=_year_url(minutes, "pleno"),
        first_year=int(_get(minutes, "primer_año", "actas_por_año.")),
        unpublished_example=data.get("ejemplo_acta_no_publicada") or "",
        regional_bodies=tuple(data.get("organismos_regionales") or ()),
        legislatures={k: dict(leg["grupos"]) for k, leg in legislatures.items()},
        starts={k: date.fromisoformat(leg["inicio"]) for k, leg in legislatures.items()},
        colors=colors, site_name=_get(web, "nombre", "web."), email=_get(web, "correo", "web."),
        responsible=_get(web, "responsable", "web."), site_url=site_url, code_url=code_url.rstrip("/"))


@cache
def load() -> Municipality:
    return parse(json.loads(PATH.read_text(encoding="utf-8")))


def regional_pattern() -> str:
    return "|".join(rf"\b{re.escape(b.lower())}\b" for b in load().regional_bodies)
