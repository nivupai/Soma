"""Find the repository owning an output, independent of installed package location."""

import subprocess
import tomllib
from pathlib import Path


def output_repository(path: Path) -> Path | None:
    """Nearest Soma source tree, else enclosing Git worktree; None outside either.

    A source archive also protects its docs/source directories even without .git.
    Resolving the destination first prevents symlink escapes from changing which
    repository's output exclusions apply. No package-parent or cwd guess is used.
    """
    target = path.resolve()
    start = target if target.is_dir() else target.parent
    for parent in (start, *start.parents):
        project = parent / "pyproject.toml"
        if project.is_file() and (parent / "src/soma/__init__.py").is_file():
            values = tomllib.loads(project.read_text())
            if values.get("project", {}).get("name") == "soma-neuro":
                return parent
    existing = start
    while not existing.is_dir() and existing != existing.parent:
        existing = existing.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=existing,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None
