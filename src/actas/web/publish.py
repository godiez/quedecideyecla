import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from actas.web.build import MARKER


def _git(cwd: Path, *args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], check=check, capture_output=True, text=True,
                          env={**os.environ, **env} if env else None)


def publish(out: Path, repo: Path, branch: str = "gh-pages", env: dict | None = None) -> str:
    if not (out / MARKER).exists():
        raise ValueError(f"{out} no es una web generada por «uv run actas web» (falta {MARKER})")
    git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
    current = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="publish-", dir=git_dir))
    tree = tmp / "tree"
    try:
        _git(repo, "worktree", "add", "-q", "--detach", str(tree))
        _git(tree, "rm", "-rfq", "--ignore-unmatch", ".")
        for p in tree.iterdir():
            if p.name != ".git":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        shutil.copytree(out, tree, dirs_exist_ok=True, ignore=shutil.ignore_patterns(MARKER))
        _git(tree, "add", "-A")
        new_tree = _git(tree, "write-tree").stdout.strip()
        if current and _git(repo, "rev-parse", f"{current}^{{tree}}").stdout.strip() == new_tree:
            return current
        # A single commit, without history, so the repository does not grow by megabytes on every publication.
        commit = _git(tree, "commit-tree", new_tree, "-m", f"Web generada el {date.today().isoformat()}",
                      env=env).stdout.strip()
        _git(repo, "update-ref", f"refs/heads/{branch}", commit)
        return commit
    finally:
        _git(repo, "worktree", "remove", "--force", str(tree), check=False)
        _git(repo, "worktree", "prune", check=False)
        shutil.rmtree(tmp, ignore_errors=True)
