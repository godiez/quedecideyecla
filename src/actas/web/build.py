import hashlib
import shutil
from pathlib import Path

from actas import money, sources
from actas.web import model, privacy
from actas.web.template import STATIC, static_file
from actas.web.pages import data, decisions, entities, fallback, info, legal, search, votes
from actas.web.pages import money as money_pages

MARKER = ".generado-por-actas"


def _clear(out: Path) -> None:
    if out.exists():
        if not (out / MARKER).exists():
            raise ValueError(f"{out} existe y no la generó esta herramienta: no la borro")
        shutil.rmtree(out)


def build_site(root: Path, db_path: Path | None, out: Path, years: list[int] | None = None) -> list[Path]:
    if out.exists() and not (out / MARKER).exists():
        raise ValueError(f"{out} existe y no la generó esta herramienta: no la borro")
    archive = model.build_archive(root, db_path, years)
    pages = []
    for y, site in archive.sites.items():
        pages.extend(money_pages.generate(site, root=site is archive.latest))
        pages.extend(decisions.generate(site))
        pages.extend(entities.generate(site))
    pages.extend(entities.generate_entities(archive))
    pages.extend(votes.generate(archive))
    pages.extend(info.generate(archive))
    pages.extend(legal.generate(archive))
    extra = [x for site in archive.sites.values() for x in data.files(site)] + search.files(archive)
    stamps = {p: hashlib.sha256(t.encode()).hexdigest()[:10] for p, t in extra}
    pages.extend(search.generate(archive, stamps))
    pages.extend(fallback.redirects(archive))
    paths = [p for p, _ in pages]
    repeated = sorted({p for p in paths if paths.count(p) > 1})
    if repeated:
        raise ValueError(f"rutas repetidas: {repeated}")
    _clear(out)
    written = []
    for path, html in pages:
        f = out / path / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
        written.append(f)
    extra.append(fallback.not_found(archive))
    for path, text in extra:
        f = out / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    (out / "static").mkdir()
    for f in sorted(STATIC.iterdir()):
        if f.is_file():
            (out / "static" / f.name).write_bytes(static_file(f.name))
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / MARKER).write_text("Carpeta generada por «uv run actas web». Se borra al regenerar.\n",
                              encoding="utf-8")
    allowed = {x for y in archive.years for d in sources.load_docs(root / str(y)) for p in d["puntos"]
               for x in money.case_files(p)}
    findings = privacy.check(out, allowed)
    if findings:
        shutil.rmtree(out)
        raise ValueError("control de privacidad: " + "; ".join(findings))
    return written
