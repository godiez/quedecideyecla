import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from actas import money, sources, votes
from actas.revision.data import find_pages
from actas.web.fmt import plain as _plain
from actas.web.fmt import slug as make_slug
from actas.web.fmt import topic as topic_of

PERMITS = ("licencia_obra", "licencia_actividad", "suelo_no_urbanizable", "urbanismo_planeamiento")
RECEIVING_PHASES = ("adjudicacion", "pago", "subvencion", "especie")
PUBLIC_TYPES = {t for t, c in money.TYPE_CLASS.items() if c == "publica"}
_DOC_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(JGL|PLENO)_(\d+)$")


_READING_NOTE = re.compile(r"\s*\([^()]*\b(ocr|dudos[oa] por|ilegible|mal le[ií]d[oa]|posible error)\b[^()]*\)", re.I)
_CASE_TOKEN = re.compile(r"\b\d{5,8}[A-Z]?\?|\b\d{5,8}[A-Z]\b")


def legible_case_file(raw: str | None, minutes: str | None) -> str | None:
    """Without the numbers that are not written as such in the minutes: in scanned minutes the AI sometimes adds or
    changes the final letter. minutes: text of the minutes without spaces, upper case."""
    if not raw:
        return None
    s = _READING_NOTE.sub("", raw)
    if minutes is not None:
        s = _CASE_TOKEN.sub(lambda m: m.group(0) if m.group(0) in minutes else "", s)
    else:
        s = re.sub(r"\b\d{5,8}[A-Z]?\?", "", s)
    s = re.sub(r"\s*,(\s*,)+", ",", s)
    s = re.sub(r"^[\s,;y]+|[\s,;]+$", "", re.sub(r"\(\s*\)", "", s)).strip()
    s = re.sub(r"^y\s+|\s+y$", "", s)
    if re.fullmatch(r"\([^()]*\)", s):
        s = s[1:-1].strip()
    return s or None


def is_income(d) -> bool:
    return money.is_income(d.title, d.summary)


def is_guarantee(d) -> bool:
    """The whole amount is a guarantee (fianza, aval): a deposit that is given back, not money spent."""
    lines = [i for i in d.amounts if isinstance(i.get("eur"), (int, float))]
    return bool(d.amount_eur and lines and all(money.GUARANTEE.search(i.get("concept") or "") for i in lines)
                and abs(sum(i["eur"] for i in lines) - d.amount_eur) <= 1)


# A grant the council only asks for: nobody has given anything yet.
_REQUEST = re.compile(r"^(se (pide|piden|solicita|solicitan)|solicitud|petici[oó]n|pide|piden|solicita)\b", re.I)
_GIVES = re.compile(r"da subvenci|financia|concede|otorga|aporta|subvenciona", re.I)


_ASKED = re.compile(r"\b(pedida|solicitada)s?\b", re.I)


def is_request(d) -> bool:
    return d.category == "subvencion_recibida" and bool(_REQUEST.search(d.title) or _ASKED.search(d.title))


def role_label(d, role: str | None) -> str | None:
    if role and is_request(d) and _GIVES.search(role) and "solicit" not in role:
        return "a quien se pide la subvención"
    return role


def spent(d) -> float:
    return 0 if is_income(d) or is_guarantee(d) or is_request(d) else d.amount_eur or 0


@dataclass
class Note:
    """`counted`: awarded euros to count instead of the minutes' amount (e.g. one year of a 12-year contract)."""
    year: int
    entity: str
    title: str
    text: str
    case_file: str | None = None
    counted: float | None = None


def load_notes(path: Path) -> list[Note]:
    out = []
    for n in _read(path).get("avisos", []) if path.exists() else []:
        out.append(Note(year=int(n["año"]), entity=n["entidad"], title=n["titulo"], text=n["texto"],
                        case_file=n.get("expediente"), counted=n.get("cuenta_adjudicado")))
    return out


@dataclass
class Vote:
    decision_id: str
    subject: str
    final: bool
    unanimous: bool
    result: str
    votes: dict[str, dict[str, int]]
    when: date
    legislature: str


@dataclass
class Decision:
    id: str
    slug: str
    doc: str
    ref: str
    title: str
    summary: str
    category: str
    topic: str
    amount_eur: float | None
    amounts: list[dict]
    result: str
    interest: int
    entities: list[dict]
    place: str | None
    case_file: str | None
    page: int
    pdf_url: str | None
    vote: Vote | None
    session_doc: str
    position: int = 0
    notes: list[Note] = field(default_factory=list)


@dataclass
class Session:
    doc: str
    body: str
    number: int | None
    date: date
    session_type: str
    pdf_url: str | None
    decisions: list[Decision] = field(default_factory=list)


@dataclass
class Entity:
    slug: str
    name: str
    entity_class: str
    committed: float = 0.0
    awarded: float = 0.0
    paid: float = 0.0
    grant: float = 0.0
    movements: list[dict] = field(default_factory=list)
    permits: list[Decision] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)


@dataclass
class Site:
    year: int
    sessions: list[Session]
    decisions: dict[str, Decision]
    entities: dict[str, Entity]
    ranking: list[Entity]
    totals: dict[str, float]
    votes: list[Vote]
    latest_session: Session
    years: list[int] = field(default_factory=list)
    first_date: date | None = None  # oldest minutes on the whole site (all years)
    last_date: date | None = None  # newest minutes on the whole site

    @property
    def period(self) -> tuple[date, date]:
        return (self.first_date or self.sessions[-1].date, self.last_date or self.sessions[0].date)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def catalog_urls(db_path: Path | None) -> dict[str, str]:
    if not db_path or not Path(db_path).exists():
        return {}
    out: dict[str, str] = {}
    conn = sqlite3.connect(db_path)
    try:
        for kind, when, num, local, url in conn.execute(
                "SELECT kind, session_date, session_number, local_path, url FROM minutes"):
            if local:
                out.setdefault(Path(local).stem, url)
            if when is None and num is not None:
                tag = "JGL" if kind == "jgl_minutes" else "PLENO"
                out.setdefault(f"#{tag}_{num:02d}", url)
    finally:
        conn.close()
    return out


def _doc_url(urls: dict[str, str], doc: str) -> str | None:
    if doc in urls:
        return urls[doc]
    m = _DOC_RE.match(doc)
    return urls.get(f"#{m.group(2)}_{m.group(3)}") if m else None


def _int(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _clean_votes(v: dict, seats: dict[str, int]) -> dict[str, dict[str, int]]:
    return {g: {k: _int((v.get(g) or {}).get(k, 0)) for k in ("favor", "contra", "abstencion")} for g in seats}


def _is_private(name: str, kind: str | None) -> bool:
    return money.is_private_person(name, kind)


@dataclass
class Prepared:
    docs: list[dict]
    ents: object
    ledger: dict
    rows: dict[str, dict]
    persons: set[str]
    candidates: dict[str, tuple[str, str]]  # key -> (name, class) of every entity that gets a page


@dataclass
class Registered:
    slug: str
    name: str
    entity_class: str


def prepare(analysis: Path, notes: list[Note] = ()) -> Prepared:
    docs = sources.load_docs(analysis)
    aliases = _read(analysis / "alias.json")
    counted = {(n.entity, n.case_file): n.counted for n in notes if n.case_file and n.counted is not None}
    ledger = money.compute(docs, aliases, counted)
    ents, kinds, manual, _ = money.unify_entities(docs, aliases)
    persons = {x["clave"] for x in ledger.get("excluidas", [])}
    # Natural person in any point (not only in the ranking or the permits): their name never shows.
    every: dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        for p in d["puntos"]:
            for en in p.get("entidades", []):
                if en.get("nombre"):
                    every[ents.canon(en["nombre"])][en["nombre"]] += 1
            for i in p.get("importes") or []:
                if i.get("entidad"):
                    every[ents.canon(str(i["entidad"]))][str(i["entidad"])] += 1
    for canon_key, variants in every.items():
        if money.entity_class(canon_key, list(variants), kinds.get(canon_key, Counter()), manual) == "persona":
            persons.add(canon_key)

    rows = {r["clave"]: r for r in ledger["ranking"]}
    permit_names: dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        for p in d["puntos"]:
            if p.get("categoria") not in PERMITS:
                continue
            for en in p.get("entidades", []):
                n = en.get("nombre") or ""
                if not n or _is_private(n, en.get("tipo")) or money.PUBLIC.search(n):
                    continue
                if (en.get("tipo") or "").lower() in PUBLIC_TYPES:
                    continue
                permit_names[ents.canon(n)][n] += 1
    candidates: dict[str, tuple[str, str]] = {}
    for canon_key in sorted(set(rows) | set(permit_names)):
        if canon_key in persons:
            continue
        if canon_key in rows:
            name, cls = rows[canon_key]["entidad"], rows[canon_key]["clase"]
        else:
            variants = permit_names[canon_key]
            name = max(variants, key=variants.get)
            cls = money.entity_class(canon_key, list(variants), kinds.get(canon_key, Counter()), manual)
        if cls == "persona":
            persons.add(canon_key)
            continue
        candidates[canon_key] = (name, cls)
    return Prepared(docs=docs, ents=ents, ledger=ledger, rows=rows, persons=persons, candidates=candidates)


def register(prepared: list[Prepared]) -> tuple[dict[str, Registered], set[str]]:
    """prepared: oldest to newest year (name and class: those of the latest year)."""
    persons = set().union(*(p.persons for p in prepared)) if prepared else set()
    latest: dict[str, tuple[str, str]] = {}
    for p in prepared:
        latest.update(p.candidates)
    out: dict[str, Registered] = {}
    used: set[str] = set()
    by_name: dict[str, Registered] = {}
    for canon_key in sorted(latest):
        if canon_key in persons:
            continue
        name, cls = latest[canon_key]
        same = by_name.get(_plain(name))
        if same:
            out[canon_key] = same
            continue
        base = make_slug(name)
        s, n = base, 2
        while s in used:
            s, n = f"{base}-{n}", n + 1
        used.add(s)
        out[canon_key] = by_name[_plain(name)] = Registered(slug=s, name=name, entity_class=cls)
    return out, persons


def build(analysis: Path, db_path: Path | None, year: int, prepared: Prepared | None = None,
          registry: dict[str, Registered] | None = None, all_persons: set[str] | None = None,
          notes: list[Note] = ()) -> Site:
    prepared = prepared or prepare(analysis, notes)
    if registry is None:
        registry, all_persons = register([prepared])
    persons = prepared.persons | (all_persons or set())
    docs, ents, ledger, rows = prepared.docs, prepared.ents, prepared.ledger, prepared.rows
    urls = catalog_urls(db_path)
    by_key: dict[str, Entity] = {}
    by_slug: dict[str, Entity] = {}
    for canon_key in prepared.candidates:
        if canon_key in persons or canon_key not in registry:
            continue
        reg = registry[canon_key]
        ent = by_slug.setdefault(reg.slug, Entity(slug=reg.slug, name=reg.name, entity_class=reg.entity_class))
        if canon_key in rows:
            r = rows[canon_key]
            ent.committed += r["comprometido"]
            ent.awarded += r["adjudicado"]
            ent.paid += r["pagado"]
            ent.grant += r["subvencion"]
        by_key[canon_key] = ent

    def entity_page(name: str) -> Entity | None:
        return by_key.get(ents.canon(name)) if name else None

    for n in notes:
        ent = entity_page(n.entity)
        if not ent:
            raise ValueError(f"avisos.json: {n.entity!r} no tiene ficha en {year}")
        ent.notes.append(n)

    votes_by_id: dict[str, list[dict]] = defaultdict(list)
    for f in sorted((analysis / "votos").glob("*.json")) if (analysis / "votos").exists() else []:
        for v in _read(f).get("votaciones", []):
            if isinstance(v.get("punto_idx"), int):
                votes_by_id[f"{f.stem}:{v['punto_idx']}"].append(v)

    sessions, decisions, all_votes = [], {}, []
    for d in docs:
        doc = d["doc"]
        txt = analysis / "txt" / f"{doc}.txt"
        # Normalized once per minutes, not once per point.
        raw_text = txt.read_text(encoding="utf-8") if txt.exists() else None
        pages = [_plain(x) for x in raw_text.split("\f")] if raw_text else []
        minutes = re.sub(r"\s+", "", raw_text).upper() if raw_text else None
        url = _doc_url(urls, doc)
        when = date.fromisoformat(d.get("fecha") or doc[:10])
        m = _DOC_RE.match(doc)
        body = d.get("organo") if d.get("organo") in ("JGL", "PLENO") else (m.group(2) if m else "JGL")
        ses = Session(doc=doc, body=body, number=d.get("sesion"), date=when,
                      session_type=d.get("tipo_sesion") or "", pdf_url=url)
        where = find_pages(pages, d["puntos"], already_normalized=True)
        for p, page in zip(d["puntos"], where):
            pid = p["id"]
            pos = int(pid.rsplit(":", 1)[1])
            vote = None
            vs = votes_by_id.get(pid, [])
            for v in vs:
                leg = votes.legislature_of(v.get("votos") or {}, when)
                obj = Vote(decision_id=pid, subject=v.get("que") or "", final=bool(v.get("final")),
                           unanimous=bool(v.get("unanimidad")), result=v.get("resultado") or "",
                           votes=_clean_votes(v.get("votos") or {}, votes.LEGISLATURES[leg]), when=when,
                           legislature=leg)
                all_votes.append(obj)
                if obj.final or vote is None:
                    vote = obj
            place = p.get("lugar") or None
            if place and p.get("hay_particulares") and re.search(r"\d", place):
                place = None
            entities = []
            for en in p.get("entidades", []):
                n, t = en.get("nombre") or "", en.get("tipo")
                fe = None if _is_private(n, t) else entity_page(n)
                private = _is_private(n, t) or ents.canon(n) in persons
                entities.append({"name": "un particular" if private else n, "slug": fe.slug if fe else None,
                                 "type": t, "role": en.get("rol")})
            amounts = []
            for i in p.get("importes") or []:
                n = str(i.get("entidad") or "")
                private = _is_private(n, None) or (n and ents.canon(n) in persons)
                fe = None if private else entity_page(n)
                amounts.append({"entity": "un particular" if private else n, "slug": fe.slug if fe else None,
                                "concept": i.get("concepto"), "eur": i.get("eur")})
            dec = Decision(
                id=pid, slug=f"{doc}-{pos}", doc=doc, ref=str(p.get("ref") or ""), title=p.get("titulo") or "",
                summary=p.get("resumen") or "", category=p.get("categoria") or "otros",
                topic=topic_of(p.get("categoria") or "otros"), amount_eur=p.get("importe_eur"), amounts=amounts,
                result=p.get("resultado") or "", interest=int(p.get("interes") or 1), entities=entities,
                place=place, case_file=legible_case_file(p.get("expediente"), minutes), page=page,
                pdf_url=f"{url}#page={page}" if url else None,
                vote=vote, session_doc=doc,
                position=pos)
            decisions[pid] = dec
            files = set(money.case_files(p))
            dec.notes = [n for n in notes if n.case_file and n.case_file in files]
            ses.decisions.append(dec)
            if dec.category in PERMITS:
                seen = set()
                for en in p.get("entidades", []):
                    fe = None if _is_private(en.get("nombre"), en.get("tipo")) else entity_page(en.get("nombre") or "")
                    if fe and fe.slug not in seen:
                        seen.add(fe.slug)
                        fe.permits.append(dec)
        ses.decisions.sort(key=lambda x: (-x.interest, -spent(x), x.position))
        sessions.append(ses)
    sessions.sort(key=lambda s: (s.date, s.doc), reverse=True)

    for m in ledger["movimientos"]:
        ent = by_key.get(m.get("entidad") or "")
        if ent and m["fase"] in RECEIVING_PHASES and m.get("id") in decisions:
            ent.movements.append({**m, "decision_slug": decisions[m["id"]].slug})
    for ent in by_key.values():
        ent.movements.sort(key=lambda m: (m.get("fecha") or "", m.get("id") or ""))

    ranking = sorted({id(ent): ent for k, ent in by_key.items() if k in rows}.values(),
                     key=lambda x: (-x.committed, x.slug))
    tot = Counter()
    for ent in ranking:
        tot["asociacion_institucion" if ent.entity_class == "publica" else ent.entity_class] += ent.committed
    totals = {"companies": round(tot["empresa"], 2), "associations": round(tot["asociacion_institucion"], 2),
              "pending": round(tot["pendiente"], 2)}
    totals["unassigned"] = round(sum(u["eur"] for u in ledger["sin_asignar"]), 2)
    return Site(year=year, sessions=sessions, decisions=decisions,
                entities={x.slug: x for x in by_key.values()}, ranking=ranking, totals=totals,
                votes=all_votes, latest_session=sessions[0], years=[year])


@dataclass
class EntityHistory:
    slug: str
    name: str
    entity_class: str
    years: dict[int, Entity]

    @property
    def movements(self) -> list[dict]:
        return sorted((m for x in self.years.values() for m in x.movements),
                      key=lambda m: (m.get("fecha") or "", m.get("id") or ""), reverse=True)

    @property
    def permits(self) -> list[Decision]:
        return sorted((d for x in self.years.values() for d in x.permits), key=lambda d: d.slug, reverse=True)


@dataclass
class Archive:
    sites: dict[int, Site]  # newest first
    entities: dict[str, EntityHistory]
    decisions: dict[str, Decision]
    sessions: dict[str, Session]
    votes: list[Vote]

    @property
    def years(self) -> list[int]:
        return list(self.sites)

    @property
    def latest(self) -> Site:
        return next(iter(self.sites.values()))


def available_years(root: Path) -> list[int]:
    return sorted((int(p.name) for p in root.iterdir() if p.name.isdigit() and any((p / "json").glob("*.json"))),
                  reverse=True) if root.exists() else []


def build_archive(root: Path, db_path: Path | None, years: list[int] | None = None) -> Archive:
    years = sorted(years or available_years(root), reverse=True)
    if not years:
        raise ValueError(f"no hay actas analizadas en {root}")
    empty = [y for y in years if y not in available_years(root)]
    if empty:
        raise ValueError(f"sin actas analizadas en {', '.join(map(str, empty))} ({root})")
    notes = load_notes(root / "avisos.json")
    by_year = {y: [n for n in notes if n.year == y] for y in years}
    prepared = {y: prepare(root / str(y), by_year[y]) for y in years}
    registry, persons = register([prepared[y] for y in reversed(years)])
    if persons:
        print(f"{len(persons)} entidades tratadas como persona física: sin nombre ni ficha")
    sites = {y: build(root / str(y), db_path, y, prepared[y], registry, persons, by_year[y]) for y in years}
    first = min(s.sessions[-1].date for s in sites.values())
    last = max(s.sessions[0].date for s in sites.values())
    for s in sites.values():
        s.years, s.first_date, s.last_date = list(years), first, last
    entities: dict[str, EntityHistory] = {}
    for y, s in sites.items():
        for x in s.entities.values():
            h = entities.setdefault(x.slug, EntityHistory(slug=x.slug, name=x.name, entity_class=x.entity_class,
                                                         years={}))
            h.years[y] = x
    return Archive(sites=sites, entities=dict(sorted(entities.items())),
                   decisions={k: d for s in sites.values() for k, d in s.decisions.items()},
                   sessions={x.doc: x for s in sites.values() for x in s.sessions},
                   votes=[v for s in sites.values() for v in s.votes])
