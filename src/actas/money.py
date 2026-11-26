import re
import unicodedata
from collections import Counter, defaultdict

from actas import municipality

RECEIVES = re.compile(r"cobra|contratista|adjudicatari|beneficiari|recibe|perceptor|proveedor", re.I)
REGIONAL = municipality.regional_pattern()
PUBLIC = re.compile(r"ayuntamiento|consejer|comunidad aut|ministerio|diputaci|servicio regional|"
                    r"delegaci[oó]n del gobierno|confederaci|"
                    r"uni[oó]n europea|next generation|secretar[ií]a de estado|direcci[oó]n general|"
                    r"consorcio" + (f"|{REGIONAL}" if REGIONAL else ""), re.I)
NO_RECEIVER = re.compile(rf"^\s*(excmo\.?\s*)?ayuntamiento de {re.escape(municipality.load().name.lower())}\b|"
                         r"^\s*(los |las |varios |diversos )?"
                         r"(patrocinadores|beneficiari[oa]s|premiad[oa]s|ganadores|participantes|varios|"
                         r"empresas|entidades|asociaciones|clubes|vecinos)\s*$", re.I)
LEGAL = r"(SOCIEDAD LIMITADA( UNIPERSONAL)?|SOCIEDAD ANONIMA|SLU|SLP|SLL|SL|SAU|SA|SCOOP|SCL|AIE|SC|CB|SAT)"

TENDER = re.compile(r"licita|se convoca|convocatoria|pliego|expediente de contrataci|inicio del expediente|"
                    r"se aprueba el expediente|se suspende|desierto|reserva de|presupuesto (de|para|total)", re.I)
PAY = re.compile(r"indemniz|compensaci|certificaci|factura|liquidaci[oó]n de obligaciones|"
                 r"\bpago\b|se paga|abono|segundo plazo|anticipo", re.I)
AWARD = re.compile(r"adjudic|contrato menor|se contrata|se encarga|prórroga|prorroga|modificad|compra", re.I)
JUSTIF = re.compile(r"justific", re.I)
# «padrón» and «recaudación» alone are also the register of residents and the tax office's staff, and «recibos del»
# only counts at the start: «Reparto de los recibos del IBI» is a contract (money that goes out).
INCOME = re.compile(r"taquilla|venta de entradas|\bpadr[oó]n(es)?:? (\d{4}|del?\b(?! \d)|de la|de los)|"
                    r"listas? (de cobro|cobratoria)|^recibos del|liquidaci[oó]n de ingresos|"
                    r"\brecaudaci[oó]n (del?|de la|de los|de las)\b|"
                    r"\bventa (directa|para desguace|a su ocupante)\b|\bchatarra\b|\bsubasta de la caza\b|"
                    r"\b(puestos?|carritos?) (provisional |eventual )?de venta\b|\bayuntamiento cobrar[aá]\b", re.I)
TICKETS = re.compile(r"taquilla|venta de entradas", re.I)


PAYS_COUNCIL = re.compile(r"\bpaga(r[aá]|n)? al ayuntamiento\b|a abonar por el adjudicatario|"
                          r"precio a pagar por el adjudicatario|previo pago (del?|de (los )?\d[\d.,]* (euros|€) de) precio p[uú]blico",
                          re.I)


def is_income(title: str, summary: str | None = None) -> bool:
    return bool(INCOME.search(title or "")) or bool(summary and PAYS_COUNCIL.search(summary))


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def key(name: str) -> str:
    k = strip_accents(name).upper()
    k = re.sub(r"(?<=\b[A-Z])\.(?=[A-Z]\b)|\.", "", k)
    k = re.sub(r"[\"'“”«»,;:()]", " ", k)
    k = re.sub(r"\s+", " ", k).strip()
    k = re.sub(rf"(\s|-)+{LEGAL}$", "", k).strip()
    return re.sub(r"^U ?T ?E\b", "UTE", k)


class Entities:
    def __init__(self, aliases: dict):
        self.no_merge = {tuple(x) for x in aliases.get("_no_unir", [])}
        self.alias = {key(a): key(c) for a, c in aliases.items() if not a.startswith("_")}
        self.names: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.seen_keys: set[str] = set()

    def learn(self, name: str) -> None:
        if name:
            self.seen_keys.add(key(name))
        m = re.search(r"\(([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ.\-]{2,})\)", name)
        if m:
            acr = key(m.group(1).replace(".", ""))
            full = key(name[: m.start()])
            self.alias.setdefault(acr, full)
            self.alias.setdefault(key(name), full)

    def learn_all_done(self) -> list[tuple[str, str]]:
        """Merges keys that abbreviate another one ("PROMOCIONES MUSIC GET IN" -> "PROMOCIONES MUSICALES GET IN")."""
        stop = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E"}
        toks = {k: [t for t in k.split() if t not in stop] for k in sorted(self.seen_keys) if not k.startswith("UTE")}
        merges = []
        for a, ta in toks.items():
            if len(ta) < 2 or a in self.alias:
                continue
            for b, tb in toks.items():
                if a == b or not tb or ta[0] != tb[0] or len(tb) < len(ta) or len(tb) > len(ta) + 2 or b in self.alias:
                    continue
                used, ok = set(), True
                for t in ta:
                    j = next((j for j, u in enumerate(tb) if j not in used and u.startswith(t)), None)
                    if j is None:
                        ok = False
                        break
                    used.add(j)
                if ok and (a, b) not in self.no_merge and (len(tb) > len(ta) or a < b):
                    self.alias[a] = b
                    merges.append((a, b))
                    break
        return merges

    def canon(self, name: str) -> str:
        k = key(name)
        seen = set()
        while k in self.alias and k not in seen:
            seen.add(k)
            k = self.alias[k]
        return k

    def add(self, name: str) -> str:
        c = self.canon(name)
        self.names[c][name] += 1
        return c

    def display(self, c: str) -> str:
        variants = self.names.get(c)
        return max(variants, key=variants.get) if variants else c


def phase(p: dict) -> str:
    cat, text = p.get("categoria"), f"{p.get('titulo', '')} {p.get('resumen', '')}"
    if is_income(p.get("titulo"), p.get("resumen")):
        return "ingreso"
    if re.search(r"penalidad|penalizaci|multa|sanci[oó]n|reintegro|incautaci", p.get("titulo", ""), re.I):
        return "otro"
    if cat == "pago_factura":
        return "pago"
    if cat == "contrato":
        if PAY.search(p.get("titulo", "")) and not AWARD.search(p.get("titulo", "")):
            return "pago"
        if TENDER.search(text) and not re.search(r"adjudic", text, re.I):
            return "licitacion"
        return "adjudicacion"
    if cat == "subvencion_concedida":
        if JUSTIF.search(p.get("titulo", "")) and not re.search(r"pag|conced|anticip|convenio|nuevo", p.get("titulo", ""), re.I):
            return "justificacion"
        return "subvencion"
    if cat == "via_publica_eventos":
        return "especie"
    if cat == "reclamaciones" and PAY.search(text):
        return "pago"
    return "otro"


GUARANTEE = re.compile(r"\bgarant[ií]a|\bfianza|\baval\b", re.I)
FEE_TO_COUNCIL = re.compile(r"\bcanon\b|paga(n)? al Ayuntamiento", re.I)
# «A cargo de la partida/aplicación…» is municipal accounting and does not count.
PAYER = re.compile(r"\ba cargo de(?!l? (la )?(partida|aplicaci|presupuesto|cr[eé]dito))|\blo paga|"
                   r"\bpagad[oa]s? por|\bfinanciad[oa]s? por|\bcorre(n)? a cargo", re.I)
IN_KIND = re.compile(r"uso gratuito|en especie|valoraci[oó]n|recursos municipales|cesi[oó]n gratuita|"
                     r"no (es|supone) dinero", re.I)
YEAR = re.compile(r"\b(20\d\d)\b")


def line_phase(ph: str, concept: str | None, year: int | None = None) -> str:
    c = concept or ""
    if FEE_TO_COUNCIL.search(c):
        return "ingreso"
    if GUARANTEE.search(c) or PAYER.search(c):
        return "otro"
    if ph in ("subvencion", "adjudicacion") and IN_KIND.search(c):
        return "especie"
    # A grant for future years is not this year's money. December invoices from the previous year paid now are.
    years = {int(y) for y in YEAR.findall(c)}
    if ph == "subvencion" and year and years and min(years) > year:
        return "otro"
    return ph


TYPE_CLASS = {
    **dict.fromkeys(["empresa", "negocio", "comercio", "establecimiento"], "empresa"),
    **dict.fromkeys(["asociacion", "club", "fundacion", "colegio", "centro_educativo", "escuela", "federacion",
                     "cofradia", "entidad_religiosa", "institucion_religiosa", "institucion", "ong", "peña", "pena",
                     "sindicato", "universidad", "colegio_profesional", "comunidad_regantes",
                     "entidad_urbanistica"], "asociacion_institucion"),
    **dict.fromkeys(["administracion", "organismo_publico", "consorcio_publico", "organismo", "ue"], "publica"),
    **dict.fromkeys(["particular", "persona", "persona_fisica", "autonomo", "autónomo"], "persona"),
}
CLASSES = ("empresa", "asociacion_institucion", "publica", "pendiente", "persona")


PRIVATE_PERSON = re.compile(r"^\s*(un|una|el|la|los|las)?\s*particular(es)?\b", re.I)
HONORIFIC = re.compile(r"^\s*(d\.|d[ñn]a\.|don|do[ñn]a|sr\.|sra\.)\s", re.I)
FIRST_NAMES = set("""
ANTONIO JOSE MANUEL FRANCISCO JUAN DAVID JAVIER JESUS DANIEL CARLOS MIGUEL ALEJANDRO RAFAEL PEDRO ANGEL
PABLO LUIS SERGIO FERNANDO JORGE ALBERTO ALVARO DIEGO ADRIAN RAUL ENRIQUE RAMON VICENTE IVAN RUBEN OSCAR
ANDRES JOAQUIN SANTIAGO EDUARDO VICTOR ROBERTO JAIME MARIO IGNACIO ALFONSO SALVADOR RICARDO MARCOS JORDI
EMILIO JULIAN JULIO GUILLERMO GABRIEL TOMAS AGUSTIN MARTIN FELIX JOAN GONZALO HUGO ISMAEL CRISTIAN
MARIANO DOMINGO SEBASTIAN NICOLAS GREGORIO GINES BLAS PASCUAL BARTOLOME CRISTOBAL ESTEBAN ARTURO
MARIA CARMEN ANA ISABEL LAURA DOLORES PILAR TERESA CRISTINA MARTA FRANCISCA ANTONIA LUCIA ELENA ROSA MERCEDES
MANUELA RAQUEL SARA PAULA JOSEFA ROCIO CONCEPCION BEATRIZ JULIA ROSARIO ENCARNACION SILVIA NURIA IRENE PATRICIA
MONTSERRAT ANDREA ALBA ROCIO INMACULADA SONIA ALICIA MARINA ESTHER NATALIA CLAUDIA ANGELA EVA VERONICA
SUSANA YOLANDA AMPARO CATALINA ASCENSION FUENSANTA REMEDIOS NOELIA LORENA ALEJANDRA LIDIA MIRIAM
""".split())


def is_private_person(name: str | None, kind: str | None = None) -> bool:
    return bool(PRIVATE_PERSON.match(name or "")) or TYPE_CLASS.get(str(kind or "").strip().lower()) == "persona"


def looks_like_person(name: str) -> bool:
    if HONORIFIC.match(name or "") or PRIVATE_PERSON.match(name or ""):
        return True
    if legal_form(name):
        return False
    words = [w for w in re.split(r"\s+", strip_accents(name or "").upper().strip()) if w]
    words = [w for w in words if w not in {"DE", "DEL", "LA", "LAS", "LOS", "Y"}]
    return (3 <= len(words) <= 5 and words[0] in FIRST_NAMES and all(w.isalpha() for w in words))


def legal_form(name: str) -> str | None:
    k = strip_accents(name).upper().replace(".", "")
    k = re.sub(r"[\"'“”«»,;:()]", " ", k)
    k = re.sub(r"\s+", " ", k).strip()
    if re.match(r"^U ?T ?E\b", k):
        return "UTE"
    m = re.search(rf"(\s|-)+{LEGAL}$", k)
    return m.group(2) if m else None


def entity_class(canon_key: str, names: list[str], kinds: Counter, manual: dict) -> str:
    if canon_key in manual:
        return manual[canon_key]
    for n in names:
        if n in manual:
            return manual[n]
    # Natural person at the slightest doubt: one mention as a private person or one person-like name is enough.
    if any(TYPE_CLASS.get(t) == "persona" for t in kinds) or any(looks_like_person(n) for n in names):
        return "persona"
    if any(PUBLIC.search(n) for n in names) or PUBLIC.search(canon_key):
        return "publica"
    votes = Counter()
    for t, n in kinds.items():
        c = TYPE_CLASS.get(t)
        if c:
            votes[c] += n
    if votes:
        top = votes.most_common(2)
        if len(top) == 2 and top[0][1] == top[1][1]:
            return "pendiente"
        return top[0][0]
    forms = {legal_form(n) for n in names}
    if forms & {"UTE"} or any(f and f != "CB" for f in forms):
        return "empresa"
    return "pendiente"


CASE_FILE = re.compile(r"\b\d{6,8}[A-Z]\b")
QUOTED_CASE_FILE = re.compile(r"\b(?:expediente|expte)\b\.?(?:\s+(?:n\.?º|nº|núm\.?|aparte))?\s+(\d{6,8}[A-Z])\b", re.I)


def case_files(p: dict) -> list[str]:
    out = CASE_FILE.findall(str(p.get("expediente") or ""))
    texts = [p.get("titulo"), p.get("resumen")] + [i.get("concepto") for i in p.get("importes") or []]
    for t in texts:
        out += QUOTED_CASE_FILE.findall(str(t or ""))
    return list(dict.fromkeys(out))


def unify_entities(docs: list[dict], aliases: dict) -> tuple["Entities", dict[str, Counter], dict[str, str], list]:
    ents = Entities(aliases)
    for d in docs:
        for p in d["puntos"]:
            for e in p.get("entidades", []):
                ents.learn(e.get("nombre") or "")
            for i in p.get("importes") or []:
                ents.learn(str(i.get("entidad") or ""))

    fuzzy = ents.learn_all_done()
    kinds: dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        for p in d["puntos"]:
            for e in p.get("entidades", []):
                if e.get("nombre") and e.get("tipo"):
                    kinds[ents.canon(e["nombre"])][str(e["tipo"]).strip().lower()] += 1
    manual = {}
    for n, c in (aliases.get("_clase") or {}).items():
        if c not in CLASSES:
            raise ValueError(f"alias.json → _clase: «{n}» tiene clase «{c}»; debe ser una de {CLASSES}")
        manual[n] = c
        manual[ents.canon(n)] = c
    return ents, kinds, manual, fuzzy


def compute(docs: list[dict], aliases: dict, counted: dict[tuple[str, str], float] | None = None) -> dict:
    """counted: {(entity, case file): euros} awarded amount to count instead of what the minutes say (e.g. one year
    of a 12-year contract). Movements keep the amounts of the minutes."""
    ents, kinds, manual, fuzzy = unify_entities(docs, aliases)
    moves, unassigned = [], []
    for d in docs:
        for p in d["puntos"]:
            amount = p.get("importe_eur")
            if not amount and not p.get("importes"):
                continue
            ph = phase(p)
            base = {"id": p.get("id"), "doc": d["doc"], "fecha": d.get("fecha"), "organo": d.get("organo"), "ref": p.get("ref"),
                    "titulo": p.get("titulo"), "categoria": p.get("categoria"), "fase": ph,
                    "expedientes": case_files(p), "pdf_pagina": None}
            year = int(str(d.get("fecha") or "")[:4] or 0) or None
            detail = [i for i in p.get("importes") or [] if i.get("eur") and i.get("entidad")
                      and not is_private_person(str(i["entidad"])) and not NO_RECEIVER.search(str(i["entidad"]))]
            receivers = [e for e in p.get("entidades", []) if RECEIVES.search(e.get("rol") or "")
                         and not is_private_person(e.get("nombre"), e.get("tipo"))
                         and not PUBLIC.search(e.get("nombre") or "")
                         and not NO_RECEIVER.search(e.get("nombre") or "")]
            if ph in ("pago", "adjudicacion", "subvencion", "especie") and detail:
                for i in detail:
                    if PUBLIC.search(i["entidad"]) and ph != "subvencion":
                        continue
                    moves.append({**base, "fase": line_phase(ph, i.get("concepto"), year), "entidad": ents.add(i["entidad"]),
                                  "eur": round(i["eur"], 2), "concepto": i.get("concepto")})
            elif ph in ("pago", "adjudicacion", "subvencion", "especie") and len(receivers) == 1 and amount:
                moves.append({**base, "entidad": ents.add(receivers[0]["nombre"]), "eur": round(amount, 2),
                              "concepto": None})
            elif ph in ("pago", "adjudicacion", "subvencion") and amount:
                unassigned.append({**base, "eur": amount, "motivo": f"{len(receivers)} receptores y sin desglose"})
            else:
                moves.append({**base, "entidad": None, "eur": round(amount or 0, 2), "concepto": None})

    groups: dict[tuple, dict] = defaultdict(lambda: {"adjudicacion": 0.0, "pago": 0.0, "subvencion": 0.0,
                                                     "especie": 0.0, "movs": []})
    for i, m in enumerate(moves):
        if not m["entidad"] or m["fase"] not in ("adjudicacion", "pago", "subvencion", "especie"):
            continue
        g = groups[(m["entidad"], m["expedientes"][0] if m["expedientes"] else f"#{i}")]
        g["movs"].append(i)
        if m["fase"] == "subvencion":
            # The same grant shows up when it is granted and when it is paid: keep the largest per case file.
            g["subvencion"] = max(g["subvencion"], m["eur"]) if m["expedientes"] else g["subvencion"] + m["eur"]
        elif m["fase"] == "adjudicacion":
            # An amendment or a correction repeats the total amount: within a case file the largest one counts.
            g["adjudicacion"] = max(g["adjudicacion"], m["eur"])
        else:
            g[m["fase"]] += m["eur"]

    for (name, case_file), eur in (counted or {}).items():
        g = groups.get((ents.canon(name), case_file))
        if g and g["adjudicacion"]:
            g["adjudicacion"] = eur

    ranking = defaultdict(lambda: {"comprometido": 0.0, "adjudicado": 0.0, "pagado": 0.0, "subvencion": 0.0,
                                   "especie": 0.0, "movimientos": 0, "expedientes": set()})
    merged = []
    for (ent, case_file), g in groups.items():
        r = ranking[ent]
        r["adjudicado"] += g["adjudicacion"]
        r["pagado"] += g["pago"]
        r["subvencion"] += g["subvencion"]
        r["especie"] += g["especie"]
        r["movimientos"] += len(g["movs"])
        if not case_file.startswith("#"):
            r["expedientes"].add(case_file)
        if g["adjudicacion"] and g["pago"]:
            merged.append({"entidad": ents.display(ent), "expediente": case_file,
                           "adjudicado": round(g["adjudicacion"], 2), "pagado": round(g["pago"], 2)})

    # Not the sum: a payment cannot be safely linked to its award (invoices are approved in bulk).
    for r in ranking.values():
        r["comprometido"] = max(r["adjudicado"], r["pagado"]) + r["subvencion"]
    rows, excluded = [], []
    for k, v in ranking.items():
        cls = entity_class(k, list(ents.names.get(k, {})), kinds.get(k, Counter()), manual)
        if not any(round(v[f], 2) for f in ("comprometido", "adjudicado", "pagado", "subvencion", "especie")):
            continue
        if cls == "persona":
            eur = round(v["comprometido"], 2)
            excluded.append({"clave": k, "eur": eur})
            first = next(m for m in moves if m["entidad"] == k)
            unassigned.append({f: first.get(f) for f in ("id", "doc", "fecha", "organo", "ref", "titulo",
                                                         "categoria", "fase", "expedientes")}
                              | {"eur": eur, "motivo": "persona física"})
            continue
        rows.append({"entidad": ents.display(k), "clave": k, "publica": bool(PUBLIC.search(ents.display(k))),
                     "clase": cls,
                     **{f: round(v[f], 2) for f in ("comprometido", "adjudicado", "pagado", "subvencion", "especie")},
                     "movimientos": v["movimientos"], "expedientes": sorted(v["expedientes"])})
    rows.sort(key=lambda r: -r["comprometido"])
    if excluded:
        print(f"{len(excluded)} entidades excluidas del ranking como persona física (ver excluidas en dinero.json)")
    persons = {e["clave"] for e in excluded}
    for m in moves:
        if m["entidad"] in persons:
            m["entidad"] = None
            m["concepto"] = None
    merged = [g for g in merged if g["entidad"] not in {ents.display(k) for k in persons}]
    for m in moves:
        if m["entidad"]:
            m["entidad_nombre"] = ents.display(m["entidad"])
    variants = {ents.display(c): sorted(v) for c, v in ents.names.items() if len(v) > 1 and c not in persons}
    out = {"movimientos": moves, "sin_asignar": unassigned, "ranking": rows, "excluidas": excluded,
           "adjudicacion_y_pago_unidos": merged, "variantes_unificadas": variants,
           "uniones_aproximadas": [{"corta": a, "larga": b} for a, b in fuzzy]}
    return out
