from datetime import date
from itertools import combinations

from actas import municipality

LEGISLATURES = municipality.load().legislatures
STARTS = municipality.load().starts
CURRENT = municipality.load().current
GROUPS = list(LEGISLATURES[CURRENT])
GROUP_SIZE = LEGISLATURES[CURRENT]


def _by_date(when: date) -> str:
    started = [k for k, d in STARTS.items() if d <= when]
    return max(started, key=STARTS.get) if started else min(STARTS, key=STARTS.get)


def legislature_of(votes: dict, when: date) -> str:
    """On 17-06-2023 there are two plenary sessions, one of each council, so the date alone is not enough."""
    groups = set(votes)
    fits = [k for k, seats in LEGISLATURES.items() if groups and groups <= set(seats)]
    return fits[0] if len(fits) == 1 else _by_date(when)


def legislature_of_year(year: int) -> str:
    return _by_date(date(year, 12, 31))


def stance(v: dict) -> str | None:
    if not v or not sum(v.values()):
        return None
    order = sorted(("favor", "contra", "abstencion"), key=lambda k: -v.get(k, 0))
    if v.get(order[0], 0) == v.get(order[1], 0):
        return "dividido"
    return order[0]


def agreements(votes: list[dict], seats: dict[str, int] | None = None) -> dict[tuple[str, str], tuple[int, int]]:
    split = [v for v in votes if v.get("final") and not v.get("unanimidad")]
    out = {}
    for a, b in combinations(list(seats or GROUP_SIZE), 2):
        pairs = [(stance(v["votos"].get(a)), stance(v["votos"].get(b))) for v in split]
        pairs = [p for p in pairs if None not in p and "dividido" not in p]
        out[(a, b)] = (sum(1 for x, y in pairs if x == y), len(pairs))
    return out
