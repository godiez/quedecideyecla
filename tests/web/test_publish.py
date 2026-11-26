import subprocess

import pytest

from actas.web.publish import publish


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "Prueba")
    git(r, "config", "user.email", "prueba@example.com")
    (r / "codigo.py").write_text("print(1)\n")
    git(r, "add", ".")
    git(r, "commit", "-qm", "inicio")
    return r


@pytest.fixture
def out(tmp_path):
    s = tmp_path / "web"
    (s / "static").mkdir(parents=True)
    (s / "index.html").write_text("<p>hola</p>")
    (s / "static" / "style.css").write_text("body{}")
    (s / ".nojekyll").write_text("")
    (s / ".generado-por-actas").write_text("x")
    return s


def test_publish_only_copies_the_site(repo, out):
    (repo / "sin_commit.txt").write_text("cambio local")
    h = publish(out, repo)
    assert git(repo, "rev-parse", "gh-pages") == h
    files = set(git(repo, "ls-tree", "-r", "gh-pages", "--name-only").splitlines())
    assert files == {"index.html", "static/style.css", ".nojekyll"}  # the marker only matters locally
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert (repo / "sin_commit.txt").read_text() == "cambio local"
    assert git(repo, "worktree", "list").count("\n") == 0
    assert git(repo, "log", "-1", "--format=%s", "gh-pages").startswith("Web generada el ")
    assert git(repo, "remote") == ""


def test_publish_without_changes_makes_no_commit(repo, out):
    h1 = publish(out, repo)
    h2 = publish(out, repo)
    assert h1 == h2
    (out / "index.html").write_text("<p>adiós</p>")
    (out / "static" / "style.css").unlink()
    h3 = publish(out, repo)
    assert h3 != h2
    assert "static/style.css" not in git(repo, "ls-tree", "-r", "gh-pages", "--name-only")


def test_publish_keeps_a_single_commit_without_history(repo, out):
    publish(out, repo)
    (out / "index.html").write_text("<p>adiós</p>")
    publish(out, repo)
    assert git(repo, "rev-list", "--count", "gh-pages") == "1"
    assert git(repo, "show", "gh-pages:index.html") == "<p>adiós</p>"
    assert git(repo, "rev-list", "--count", "main") == "1"


def test_publish_rejects_folder_without_marker(repo, out):
    (out / ".generado-por-actas").unlink()
    with pytest.raises(ValueError):
        publish(out, repo)


def test_cli_publish_rebuilds_the_site_first(monkeypatch, tmp_path):
    from actas import cli
    import actas.web.build as b
    import actas.public as public
    import actas.web.publish as pub
    order = []
    monkeypatch.setattr(b, "build_site", lambda *a, **k: order.append("build") or [])
    monkeypatch.setattr(public, "export", lambda *a, **k: order.append("export") or "def5678")
    monkeypatch.setattr(pub, "publish", lambda *a, **k: order.append("publish") or "abc1234")
    cli.main(["publish", "--out", str(tmp_path / "w"), "--to", str(tmp_path / "publico")])
    assert order == ["build", "export", "publish"]


def test_publish_can_sign_with_another_identity(repo, out):
    env = {"GIT_AUTHOR_NAME": "Web", "GIT_AUTHOR_EMAIL": "web@example.com",
           "GIT_COMMITTER_NAME": "Web", "GIT_COMMITTER_EMAIL": "web@example.com"}
    publish(out, repo, env=env)
    assert git(repo, "log", "-1", "--format=%an <%ae> %cn <%ce>", "gh-pages") == "Web <web@example.com> Web <web@example.com>"
