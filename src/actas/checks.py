import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from actas import money, names, public, sources, votes

VOTE_KEYS = ("favor", "contra", "abstencion")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def check_votes(analysis: Path) -> tuple[list[str], list[str], list[str]]:
    errors, warnings, finals = [], [], defaultdict(list)
    files = sorted((analysis / "votos").glob("*.json"))
    total = 0
    for f in files:
        d = _read(f)
        points = _read(analysis / "json" / f"{f.stem}.json")["puntos"]
        attendees = d.get("asistentes", {})
        legislature = votes.legislature_of(attendees, date.fromisoformat(f.stem[:10]))
        seats = votes.LEGISLATURES[legislature]
        if set(attendees) != set(seats):
            errors.append(f"{f.stem}: asistentes con grupos {sorted(attendees)} (legislatura {legislature}: "
                          f"{sorted(seats)})")
        for g, n in attendees.items():
            if n > seats.get(g, 0):
                errors.append(f"{f.stem}: {g} con {n} asistentes (máx. {seats.get(g, 0)})")
        for i, v in enumerate(d.get("votaciones", [])):
            total += 1
            tag = f"{f.stem} #{i} (ref {v.get('punto_ref')})"
            idx = v.get("punto_idx")
            if not isinstance(idx, int) or not 0 <= idx < len(points):
                errors.append(f"{tag}: punto_idx {idx} fuera de rango")
            elif str(points[idx].get("ref")) != str(v.get("punto_ref")):
                errors.append(f"{tag}: punto_ref no coincide con la ref del punto {idx} ({points[idx].get('ref')})")
            cast = v.get("votos", {})
            if set(cast) - set(seats):
                errors.append(f"{tag}: grupos desconocidos {sorted(set(cast) - set(seats))}")
            sums = dict.fromkeys(VOTE_KEYS, 0)
            for g in seats:
                gv = cast.get(g, {})
                s = sum(gv.get(k, 0) for k in VOTE_KEYS)
                if s > attendees.get(g, seats[g]):
                    errors.append(f"{tag}: {g} suma {s} > {attendees.get(g)} asistentes")
                for k in VOTE_KEYS:
                    sums[k] += gv.get(k, 0)
            if v.get("unanimidad") and (sums["contra"] or sums["abstencion"]):
                errors.append(f"{tag}: unanimidad con votos en contra o abstenciones")
            result = (v.get("resultado") or "").lower()
            casting = "calidad" in result
            if not casting and sums["favor"] != sums["contra"]:
                expected = "aprobada" if sums["favor"] > sums["contra"] else "rechazada"
                if not result.startswith(expected) and not result.startswith("empate"):
                    warnings.append(f"{tag}: resultado '{result}' con {sums['favor']} a favor y "
                                    f"{sums['contra']} en contra")
            if sums["favor"] == sums["contra"] and sums["favor"] and not casting and not result.startswith("empate"):
                warnings.append(f"{tag}: empate sin voto de calidad")
            if v.get("final"):
                finals[legislature].append(v)
    report = [f"ficheros: {len(files)} | votaciones: {total} | finales: {sum(map(len, finals.values()))} | "
              f"no unánimes: {sum(1 for vs in finals.values() for v in vs if not v.get('unanimidad'))}"]
    for legislature, vs in finals.items():
        split = [v for v in vs if not v.get("unanimidad")]
        if not split:
            continue
        seats = votes.LEGISLATURES[legislature]
        report.append(f"Coincidencia de voto en votaciones finales no unánimes ({legislature}):")
        for (a, b), (same, n) in votes.agreements(vs, seats).items():
            report.append(f"  {a:9} y {b:9}: {same}/{n} ({100 * same / n:.0f}%)" if n else f"  {a} y {b}: -")
        for g in seats:
            won = sum(1 for v in split if votes.stance(v["votos"].get(g)) == "favor" and v["resultado"].startswith("aprobada")
                      or votes.stance(v["votos"].get(g)) == "contra" and v["resultado"].startswith("rechazada"))
            report.append(f"  {g:9} vota con el resultado final en {won}/{len(split)}")
    return errors, warnings, report


def amount_variants(x: float) -> set[str]:
    x = round(float(x), 2)
    whole = int(x)
    cents = round((x - whole) * 100)
    thousands = f"{whole:,}".replace(",", ".")
    out = {f"{thousands},{cents:02d}", f"{whole},{cents:02d}", f"{whole}.{cents:02d}", f"{whole:,}.{cents:02d}"}
    if cents == 0:
        out |= {thousands, str(whole)}
    return out


def _join_numbers(text: str) -> str:
    """Joins numbers split by layout spaces and removes the dot leaders of the invoice indexes."""
    text = re.sub(r"\.{2,}|…+", " ", text)
    return re.sub(r"(?<=\d) (?=[\d.,]\d)|(?<=\d[.,]) (?=\d)", "", text)


def check_amounts(analysis: Path) -> tuple[int, list[dict], int]:
    found, missing, no_text = 0, [], 0
    for f in sorted((analysis / "json").glob("*.json")):
        txt = analysis / "txt" / f"{f.stem}.txt"
        if not txt.exists():
            no_text += 1
            continue
        text = _join_numbers(txt.read_text(encoding="utf-8"))
        for i, p in enumerate(_read(f)["puntos"]):
            candidates = [("total", p["importe_eur"], None)] if p.get("importe_eur") else []
            candidates += [("linea", line["eur"], line.get("entidad")) for line in p.get("importes") or [] if line.get("eur")]
            lines_sum = sum(line.get("eur") or 0 for line in p.get("importes") or [])
            for kind, eur, entity in candidates:
                if any(re.search(r"(?<![\d.,])" + re.escape(s) + r"(?!\d)", text) for s in amount_variants(eur)):
                    found += 1
                elif kind == "total" and p.get("importes") and abs(lines_sum - eur) < 1:
                    found += 1
                else:
                    missing.append({"id": f"{f.stem}:{i}", "tipo": kind, "eur": eur, "entidad": entity,
                                    "titulo": p.get("titulo"), "categoria": p.get("categoria"),
                                    "n_lineas": len(p.get("importes") or [])})
    _write(analysis / "no_encontrados.json", missing)
    return found, missing, no_text


def write_money(analysis: Path) -> list[str]:
    aliases_path = analysis / "alias.json"
    aliases = _read(aliases_path) if aliases_path.exists() else {}
    out = money.compute(sources.load_docs(analysis), aliases)
    _write(analysis / "dinero.json", out)
    by_phase = defaultdict(lambda: [0, 0.0])
    for m in out["movimientos"]:
        by_phase[m["fase"]][0] += 1
        by_phase[m["fase"]][1] += m["eur"]
    by_class = defaultdict(lambda: [0, 0.0])
    for r in out["ranking"]:
        by_class[r["clase"]][0] += 1
        by_class[r["clase"]][1] += r["comprometido"]
    unassigned = out["sin_asignar"]
    return [f"movimientos por fase: {({k: (n, round(e)) for k, (n, e) in sorted(by_phase.items())})}",
            f"sin asignar: {len(unassigned)} {round(sum(u['eur'] for u in unassigned))} €",
            f"entidades con dinero: {len(out['ranking'])} | grupos adjudicación+pago unidos: "
            f"{len(out['adjudicacion_y_pago_unidos'])} | nombres unificados: {len(out['variantes_unificadas'])} | "
            f"uniones aproximadas: {len(out['uniones_aproximadas'])}",
            f"comprometido por clase: {({k: (n, round(e)) for k, (n, e) in sorted(by_class.items())})} | "
            f"personas excluidas: {len(out['excluidas'])}"]


MONEY_OUT = {"subvencion_concedida", "contrato", "pago_factura"}
PERMITS = {"licencia_obra", "licencia_actividad", "suelo_no_urbanizable", "via_publica_eventos",
           "urbanismo_planeamiento"}
PUBLIC = re.compile(r"ayuntamiento|consejer|comunidad aut|ministerio|diputaci|servicio regional|"
                    r"gobierno|confederaci|uni[oó]n europea|secretar[ií]a de estado|direcci[oó]n general|estado"
                    + (f"|{money.REGIONAL}" if money.REGIONAL else ""), re.I)


def _entity_key(name: str) -> str:
    n = re.sub(r"\s+", " ", re.sub(r"[.,]", "", name.upper())).strip()
    return re.sub(r" (SLU?|SAU?|SCOOP|SLL)$", "", n)


def _private(name: str) -> bool:
    return not name or name.lower().startswith("particular")


def write_summary(analysis: Path) -> list[str]:
    docs = sources.load_docs(analysis)
    bodies = defaultdict(lambda: {"actas": 0, "puntos": 0, "paginas": 0, "categorias": Counter(), "importe": 0.0})
    entities = defaultdict(lambda: {"nombres": Counter(), "tipo": Counter(), "roles": Counter(),
                                    "importe_recibe": 0.0, "puntos": [], "categorias": Counter()})
    highlights = []
    for d in docs:
        body = bodies[d.get("organo", "?")]
        body["actas"] += 1
        body["paginas"] += d.get("paginas") or 0
        for p in d.get("puntos", []):
            cat = p.get("categoria", "otros")
            body["puntos"] += 1
            body["categorias"][cat] += 1
            amount = p.get("importe_eur") or 0
            if cat in MONEY_OUT:
                body["importe"] += amount
            ref = {"doc": d["doc"], "ref": p.get("ref"), "titulo": p.get("titulo"), "categoria": cat,
                   "importe_eur": p.get("importe_eur"), "fecha": d.get("fecha")}
            if (p.get("interes") or 1) >= 3:
                highlights.append(ref)
            detail = [i for i in p.get("importes") or [] if i.get("entidad") and i.get("eur")
                      and not _private(str(i["entidad"]))]
            for e in p.get("entidades", []):
                name = e.get("nombre") or ""
                if _private(name):
                    continue
                ent = entities[_entity_key(name)]
                ent["nombres"][name] += 1
                ent["tipo"][e.get("tipo") or "?"] += 1
                ent["roles"][e.get("rol") or "?"] += 1
                ent["categorias"][cat] += 1
                ent["puntos"].append(ref)
                if cat in MONEY_OUT and not detail and amount and len(p["entidades"]) == 1:
                    ent["importe_recibe"] += amount
            if cat in MONEY_OUT:
                for i in detail:
                    entities[_entity_key(i["entidad"])]["importe_recibe"] += i["eur"]
                    entities[_entity_key(i["entidad"])]["nombres"][i["entidad"]] += 1

    def row(key, v):
        return {"nombre": v["nombres"].most_common(1)[0][0] if v["nombres"] else key,
                "tipo": v["tipo"].most_common(1)[0][0] if v["tipo"] else "?",
                "apariciones": len(v["puntos"]), "importe_recibe": round(v["importe_recibe"], 2),
                "categorias": dict(v["categorias"].most_common()), "roles": dict(v["roles"].most_common(4))}

    rows = [row(k, v) for k, v in entities.items()]
    others = [r for r in rows if not PUBLIC.search(r["nombre"])]
    land = [{"doc": d["doc"], "ref": p.get("ref"), "titulo": p.get("titulo"),
             "entidades": [e.get("nombre") for e in p.get("entidades", [])], "resultado": p.get("resultado"),
             "lugar": p.get("lugar")}
            for d in docs for p in d.get("puntos", []) if p.get("categoria") == "suelo_no_urbanizable"]
    out = {
        "actas": len(docs),
        "por_organo": {k: {**v, "categorias": dict(v["categorias"].most_common()), "importe": round(v["importe"], 2)}
                       for k, v in bodies.items()},
        "top_dinero": sorted([r for r in others if r["importe_recibe"]], key=lambda r: -r["importe_recibe"])[:40],
        "top_apariciones": sorted(others, key=lambda r: -r["apariciones"])[:40],
        "permisos": sorted([r for r in others if any(c in PERMITS for c in r["categorias"])],
                           key=lambda r: -sum(n for c, n in r["categorias"].items() if c in PERMITS))[:40],
        "suelo_no_urbanizable": land,
        "financiadores": sorted([r for r in rows if PUBLIC.search(r["nombre"])], key=lambda r: -r["apariciones"])[:20],
        "destacados": highlights,
    }
    _write(analysis / "resumen.json", out)
    lines = [f"{k}: {v['actas']} actas, {v['puntos']} puntos, {v['paginas']} págs, {v['importe']:,.0f} €"
             for k, v in out["por_organo"].items()]
    return lines + [f"entidades: {len(rows)} | destacados: {len(highlights)} | suelo no urbanizable: {len(land)}"]


def check_names(analysis: Path) -> tuple[list[str], list[str]]:
    year = analysis.name
    paths = [*analysis.glob("json/*.json"), *analysis.glob("votos/*.json"), analysis / "revision.json"]
    files = {f"analisis/{year}/{p.relative_to(analysis).as_posix()}": p.read_bytes() for p in paths if p.exists()}
    reviewed = analysis.parent / "nombres_revisados.json"
    return names.findings(public.clean(files), analysis.parent,
                          names.load_reviewed(reviewed.read_bytes() if reviewed.exists() else None))


def run(analysis: Path) -> int:
    print(f"== {analysis.name}")
    errors = []
    if (analysis / "votos").is_dir():
        errors, warnings, report = check_votes(analysis)
        print("Votaciones:", *report, sep="\n  ")
        for e in errors:
            print("  ERROR", e)
        for w in warnings:
            print("  AVISO", w)
    found, missing, no_text = check_amounts(analysis)
    print(f"Importes: {found} encontrados en el acta | {len(missing)} no encontrados, a revisar a mano "
          f"(no_encontrados.json)" + (f" | {no_text} actas sin texto" if no_text else ""))
    named, without_text = check_names(analysis)
    print(f"Nombres de personas en lo que se publica: {len(named)}"
          + (f" | {len(without_text)} actas sin texto: solo se miran los «D.» y «Dña.» de lo publicado y las entidades"
             if without_text else ""))
    for n in named:
        print("  ERROR", n)
    if named:
        print("  " + public.NAMES_HINT.strip())
    print("Dinero (dinero.json):", *write_money(analysis), sep="\n  ")
    print("Resumen (resumen.json):", *write_summary(analysis), sep="\n  ")
    return len(errors) + len(named)
