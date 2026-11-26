from actas.votes import CURRENT, legislature_of_year
from actas.web.fmt import slug as make_slug
from actas.web.texts import INFO_PATH


def home(year: int) -> str:
    return f"{year}/"


def money(year: int) -> str:
    return f"{year}/dinero/"


def decisions(year: int) -> str:
    return f"{year}/decisiones/"


def decisions_all(year: int) -> str:
    return f"{year}/decisiones/todas/"


def month(key: str) -> str:
    return f"{key[:4]}/decisiones/{key}/"


def permits(year: int) -> str:
    return f"{year}/permisos/"


def decision(slug: str) -> str:
    return f"decision/{slug}/"


def entities() -> str:
    return "entidad/"


def entity(slug: str) -> str:
    return f"entidad/{slug}/"


def votes(legislature: str) -> str:
    return "votaciones/" if legislature == CURRENT else f"votaciones/{legislature}/"


def vote_group(legislature: str, group: str) -> str:
    return f"{votes(legislature)}{make_slug(group)}/"


def money_csv(year: int) -> str:
    return f"datos/dinero-{year}.csv"


def decisions_csv(year: int) -> str:
    return f"datos/decisiones-{year}.csv"


def search() -> str:
    return "buscar/"


def search_index(year: int) -> str:
    return f"buscar/decisiones-{year}.json"


def search_entities() -> str:
    return "buscar/entidades.json"


def info() -> str:
    return INFO_PATH


def section(name: str | None, year: int) -> str:
    return {"decisions": decisions(year), "permits": permits(year),
            "votes": votes(legislature_of_year(year)), "search": search()}.get(name or "", home(year))
