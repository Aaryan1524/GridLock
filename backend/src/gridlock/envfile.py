"""Read the repository-root .env for the backend, the same file the frontend uses.

Real environment variables always win; blank values in the file mean "not set" so config defaults
apply. Only simple KEY=VALUE lines are read; nothing in the file is ever executed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _LINE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_root_env(root: Path = REPOSITORY_ROOT) -> dict[str, str]:
    """Apply non-empty .env values that the real environment does not already set; return what was applied."""
    applied = {}
    for key, value in parse_env_file(root / ".env").items():
        if value and key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    return applied


def repository_path(value: str | Path, root: Path = REPOSITORY_ROOT) -> Path:
    """Relative paths in settings mean relative to the repository root, whatever the working directory."""
    path = Path(value)
    return path if path.is_absolute() else root / path
