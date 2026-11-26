import json
import subprocess

import pytest

from actas import public


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _write(root, path, content):
    f = root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")


POINTS = [{"ref": "1", "titulo": "Renuncia de un conserje", "resumen": "Renuncia el conserje de la Universidad Popular, "
                                                                       "con discapacidad intelectual.",
           "expediente": "1234567X"},
          {"ref": "2", "titulo": "Subvención al club", "resumen": "Se dan 1.500 € al club.", "expediente": "765432Z"}]
REVIEW = {"2023-03-06_JGL_10:0": {"estado": "corregido", "cambios": {"resumen": "Renuncia un trabajador municipal."},
                                  "nota": "Privacidad: conserje de la Universidad Popular + discapacidad",
                                  "original": {"resumen": POINTS[0]["resumen"]}},
          "2023-03-06_JGL_10:1": {"estado": "corregido", "cambios": {"titulo": "Subvención de 1.500 € al club"},
                                  "nota": "Título más claro.", "original": {"titulo": "Subvención al club"}}}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "privado"
    for path, content in {
        "pyproject.toml": "[project]\n", "README.md": "# Proyecto\n", "LICENSE": "MIT\n", "LICENSE-DATOS": "CC BY\n", "AGENTS.md": "Reglas\n", "CLAUDE.md": "@AGENTS.md\n",
        "decisiones.md": "notas locales\n", "PENDIENTE.md": "local\n", "docs/plan.md": "plan\n",
        "src/actas/a.py": "x = 1\n", "tests/test_a.py": "def test(): pass\n",
        "analisis/INSTRUCCIONES.md": "Instrucciones\n", "analisis/2023/ESTADO.md": "estado\n",
        "analisis/2023/ENCARGO_AGENTES.md": "encargo\n", "analisis/2023/lotes.json": [["2023-03-06_JGL_10"]],
        "analisis/2023/json/2023-03-06_JGL_10.json": {"puntos": POINTS}, "analisis/2023/revision.json": REVIEW,
        "analisis/2023/alias.json": {}, "analisis/2023/votos/2023-03-06_PLENO_03.json": {"votaciones": []},
    }.items():
        _write(r, path, content)
    git(r.parent, "init", "-q", "-b", "main", str(r))
    git(r, "config", "user.name", "Persona")
    git(r, "config", "user.email", "persona@trabajo.example")
    git(r, "add", ".")
    git(r, "commit", "-qm", "inicio")
    return r


def test_only_the_allowed_files_are_published(repo, tmp_path):
    target = tmp_path / "publico"
    public.export(repo, target)
    files = sorted(git(target, "ls-files").splitlines())
    assert files == ["AGENTS.md", "CLAUDE.md", "LICENSE", "LICENSE-DATOS", "README.md", "analisis/2023/alias.json",
                     "analisis/2023/json/2023-03-06_JGL_10.json", "analisis/2023/revision.json",
                     "analisis/2023/votos/2023-03-06_PLENO_03.json", "analisis/INSTRUCCIONES.md", "pyproject.toml",
                     "src/actas/a.py", "tests/test_a.py"]


def test_code_folders_only_publish_code():
    for path in ["src/actas/a.py", "src/actas/revision/page.html", "src/actas/web/static/style.css",
                 "src/actas/web/static/filters.js", "src/actas/web/static/presentacion.mp4",
                 "src/actas/web/static/presentacion.jpg", "src/actas/web/static/vista-previa.png", "tests/web/conftest.py",
                 "video/record.py", "video/preview.py", "video/preview.html"]:
        assert public.is_allowed(path), path
    for path in ["src/actas/.env", "src/actas/clave.pem", "src/actas/datos.sqlite",
                 "src/actas/__pycache__/a.cpython-312.pyc", "src/actas/a.pyc", "src/notas.txt",
                 "tests/fixtures/acta.pdf", "tests/.env", "tests/style.css", "src/actas/foto.jpg",
                 "src/actas/web/static/otro.mp4", "src/actas/web/static/otra.png"]:
        assert not public.is_allowed(path), path


def test_what_is_not_committed_is_not_published(repo, tmp_path):
    _write(repo, "src/actas/nuevo.py", "y = 2\n")
    target = tmp_path / "publico"
    public.export(repo, target)
    assert not (target / "src/actas/nuevo.py").exists()


def test_privacy_corrections_are_applied_and_originals_removed(repo, tmp_path):
    target = tmp_path / "publico"
    public.export(repo, target)
    ai = json.loads((target / "analisis/2023/json/2023-03-06_JGL_10.json").read_text())
    review = json.loads((target / "analisis/2023/revision.json").read_text())
    everything = "".join(
        p.read_text() for p in (target / "analisis").rglob("*.json"))
    assert "Universidad Popular" not in everything and "discapacidad" not in everything
    assert ai["puntos"][0]["resumen"] == "Renuncia un trabajador municipal."
    assert ai["puntos"][1]["titulo"] == "Subvención al club"  # not a privacy fix: the AI's text stays
    assert review["2023-03-06_JGL_10:0"]["nota"] == public.PRIVACY_NOTE
    assert review["2023-03-06_JGL_10:1"]["nota"] == "Título más claro."
    assert all("original" not in r for r in review.values())


def test_personal_data_stops_the_export(repo, tmp_path):
    _write(repo, "analisis/2023/json/2023-03-06_JGL_10.json",
           {"puntos": POINTS + [{"ref": "3", "resumen": "Licencia al titular del DNI 12345678Z"}]})
    git(repo, "commit", "-qam", "dni")
    target = tmp_path / "publico"
    with pytest.raises(ValueError, match="12345678Z"):
        public.export(repo, target)
    assert not target.exists()


def test_privacy_corrections_of_a_vote_quote_are_applied(repo, tmp_path):
    quote = "aprobada por doce votos a favor (Grupo M. Popular y Dña. Ana Ruiz)"
    _write(repo, "analisis/2023/votos/2023-03-06_PLENO_03.json", {"votaciones": [{"texto_acta": quote}]})
    _write(repo, "analisis/2023/revision.json", {**REVIEW, "2023-03-06_PLENO_03:votos:0": {
        "estado": "corregido", "cambios": {"texto_acta": quote.replace("Dña. Ana Ruiz", "[una concejala]")},
        "nota": "Privacidad: nombre de una concejala", "original": {"texto_acta": quote}}})
    git(repo, "commit", "-qam", "voto")
    target = tmp_path / "publico"
    public.export(repo, target)
    everything = "".join(p.read_text() for p in (target / "analisis").rglob("*.json"))
    assert "Ana Ruiz" not in everything
    votes = json.loads((target / "analisis/2023/votos/2023-03-06_PLENO_03.json").read_text())
    assert votes["votaciones"][0]["texto_acta"].endswith("(Grupo M. Popular y [una concejala])")


def test_a_name_of_the_minute_stops_the_export(repo, tmp_path):
    # The text of the minutes is not versioned: it is read from the folder, not from the commit.
    _write(repo, "analisis/2023/txt/2023-03-06_JGL_10.txt", "Renuncia de D. Luis Gómez Soler, conserje.")
    _write(repo, "analisis/2023/json/2023-03-06_JGL_10.json",
           {"puntos": POINTS + [{"ref": "3", "resumen": "Renuncia Luis Gómez a su puesto."}]})
    git(repo, "commit", "-qam", "nombre")
    target = tmp_path / "publico"
    with pytest.raises(ValueError, match="puntos\\[2\\].resumen: Luis Gómez") as err:
        public.export(repo, target)
    assert "nombres_revisados.json" in str(err.value)
    assert not target.exists()


def _ai(notes, case_files):
    return {"analisis/2023/json/a.json": json.dumps(
        {"notas": notes, "puntos": [{"expediente": c} for c in case_files]}, ensure_ascii=False).encode()}


def test_case_files_glued_to_a_number_or_a_y_are_not_personal_data():
    assert public.findings(_ai("la del 3 584326N; aprobados 509033Q y 1093901H", ["584326N", "1093901H"])) == []


def test_case_files_labelled_by_the_text_are_known():
    assert public.findings(_ai("Sesión urgente (expte. de sesión 1129263X); exptes. 509033Q, 1103035T y 941685X; "
                               "gastos (expediente aparte 1021064W)", [])) == []
    assert public.findings({"analisis/INSTRUCCIONES.md": b'{"expediente": "1186986R"}'}) == []


def test_the_tax_id_of_an_organisation_is_not_a_dni():
    assert public.valid_cif("2800402", "F") and public.valid_cif("1234567", "D")
    assert public.findings(_ai("CIF R2800402F y B1234567D", [])) == []
    # The wrong control: not a tax id, so the digits are checked as a DNI.
    assert public.findings(_ai("CIF B1234567A", [])) == ["analisis/2023/json/a.json: 1234567A"]


def test_a_nie_is_found_even_if_its_digits_are_a_case_file():
    assert public.findings(_ai("NIE Y 1093901H", ["1093901H"])) == ["analisis/2023/json/a.json: Y1093901H"]
    assert public.findings(_ai("expediente del extranjero Y 1234567X", [])) == ["analisis/2023/json/a.json: Y1234567X"]


def test_case_files_only_count_in_their_own_file():
    files = {**_ai("", ["1234567L"]), "analisis/2023/json/b.json": json.dumps({"resumen": "DNI 1234567L"}).encode()}
    assert public.findings(files) == ["analisis/2023/json/b.json: 1234567L"]


def test_the_working_notes_of_the_ai_are_not_published(repo, tmp_path):
    _write(repo, "analisis/2023/json/2023-03-06_JGL_10.json", {"puntos": POINTS, "notas": "OCR: 3 584326N"})
    git(repo, "commit", "-qam", "notas")
    target = tmp_path / "publico"
    public.export(repo, target)
    assert "notas" not in json.loads((target / "analisis/2023/json/2023-03-06_JGL_10.json").read_text())


def test_a_nie_or_dni_in_free_text_does_not_allow_itself():
    assert public.findings(_ai("con NIE Y 1234567X", ["765432Z"])) == ["analisis/2023/json/a.json: Y1234567X"]
    assert set(public.findings(_ai("DNI 12345678Z", ["12345678Z"]))) == {"analisis/2023/json/a.json: 12345678Z"}


def test_commits_use_the_site_identity_and_repeat_nothing(repo, tmp_path):
    target = tmp_path / "publico"
    first = public.export(repo, target)
    assert first and git(target, "log", "-1", "--format=%an <%ae>") == f"Qué decide el Ayuntamiento <{public.EMAIL}>"
    assert public.export(repo, target) is None
    _write(repo, "src/actas/a.py", "x = 2\n")
    git(repo, "commit", "-qam", "cambio")
    second = public.export(repo, target)
    assert second not in (None, first)
    # A single commit without history: what an earlier publication said does not stay in the public repository.
    assert git(target, "rev-list", "--count", "main") == "1" and git(target, "rev-parse", "HEAD") == second
    assert git(target, "status", "--porcelain") == ""


def test_a_folder_that_is_not_a_repository_is_refused(repo, tmp_path):
    target = tmp_path / "publico"
    target.mkdir()
    (target / "algo.txt").write_text("x")
    with pytest.raises(ValueError, match="no es un repositorio"):
        public.export(repo, target)
    assert (target / "algo.txt").exists()
