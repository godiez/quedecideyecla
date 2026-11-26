import json
import re
from pathlib import Path

import pytest

from actas.web.build import build_site
from actas.web.template import static_file, version


def _broken_links(out: Path) -> list[str]:
    broken = []
    for f in out.rglob("*.html"):
        html = f.read_text(encoding="utf-8")
        root = out if "<base " in html else f.parent
        for href in re.findall(r'(?:href|src)="([^"]+)"', re.sub(r"<base [^>]*>", "", html)):
            if href.startswith(("http://", "https://", "mailto:", "data:")) or href.startswith("#"):
                continue
            target = (root / href.split("#")[0].split("?")[0]).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append(f"{f.relative_to(out)} -> {href}")
    return broken


def test_build_mini(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    build_site(a.parent, db, out)
    for r in ["index.html", "2026/index.html", "2026/dinero/index.html", "2026/decisiones/index.html",
              "2026/permisos/index.html", "votaciones/index.html", "como-se-ha-hecho/index.html", "static/style.css", "static/filters.js",
              ".nojekyll", ".generado-por-actas"]:
        assert (out / r).exists(), r
    assert len([x for x in (out / "decision").iterdir() if x.is_dir()]) == 10
    assert (out / "decision" / "2026-01-07_JGL_01-0" / "index.html").exists()
    assert len(list((out / "entidad").iterdir())) >= 5
    for f in out.rglob("*.html"):
        h = re.sub(r'<base href="/quedecideyecla/">', "", f.read_text(encoding="utf-8"))
        assert 'href="/' not in h and 'src="/' not in h, f
    assert _broken_links(out) == []
    assert (out / "static" / "style.css").read_bytes() == static_file("style.css")
    assert f'style.css?v={version("style.css")}' in (out / "index.html").read_text(encoding="utf-8")


def test_build_fails_with_dni(mini_analysis, tmp_path):
    a, db = mini_analysis
    f = a / "json" / "2026-01-07_JGL_01.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["puntos"][4]["resumen"] = "Se concede a la persona con DNI 12345678Z."
    f.write_text(json.dumps(d), encoding="utf-8")
    out = tmp_path / "web"
    with pytest.raises(ValueError, match="12345678Z"):
        build_site(a.parent, db, out)
    assert not out.exists()


def test_does_not_delete_foreign_folder(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    out.mkdir()
    (out / "mio.txt").write_text("no tocar")
    with pytest.raises(ValueError):
        build_site(a.parent, db, out)
    assert (out / "mio.txt").read_text() == "no tocar"


def test_rebuild_replaces(mini_analysis, tmp_path):
    a, db = mini_analysis
    out = tmp_path / "web"
    build_site(a.parent, db, out)
    (out / "sobra.html").write_text("x")
    build_site(a.parent, db, out)
    assert not (out / "sobra.html").exists()


def test_build_two_years(two_years, tmp_path):
    root, db = two_years
    out = tmp_path / "web"
    build_site(root, db, out)
    for r in ["2022/index.html", "2022/decisiones/2022-05/index.html", "votaciones/2019-2023/cs/index.html",
              "votaciones/vox/index.html", "datos/dinero-2022.csv"]:
        assert (out / r).exists(), r
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="2022/"' in home and "En 2026 el Ayuntamiento" in home
    assert _broken_links(out) == []
