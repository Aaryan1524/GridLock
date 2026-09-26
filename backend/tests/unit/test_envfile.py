from __future__ import annotations

import os
from pathlib import Path

import pytest

from gridlock.envfile import load_root_env, parse_env_file, repository_path


def test_env_file_values_apply_but_real_environment_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(
        "# comment\n"
        "GRIDLOCK_API_PORT=8040\n"
        "GRIDLOCK_API_HOST=\n"
        'export GRIDLOCK_RAW_DIR="data/raw"\n'
        "GRIDLOCK_CONFIG=from-file.yaml\n"
        "not a line\n",
        encoding="utf-8",
    )
    for key in ("GRIDLOCK_API_PORT", "GRIDLOCK_API_HOST", "GRIDLOCK_RAW_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GRIDLOCK_CONFIG", "real.yaml")

    applied = load_root_env(tmp_path)

    assert applied == {"GRIDLOCK_API_PORT": "8040", "GRIDLOCK_RAW_DIR": "data/raw"}  # blank value skipped
    assert os.environ["GRIDLOCK_CONFIG"] == "real.yaml"  # the real environment wins


def test_parser_ignores_comments_and_malformed_lines(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("A=1\n# B=2\n  \n$(rm -rf /)\nC='x y'\n", encoding="utf-8")

    assert parse_env_file(tmp_path / ".env") == {"A": "1", "C": "x y"}


def test_relative_paths_resolve_against_the_repository_root(tmp_path: Path) -> None:
    assert repository_path("config/gridlock.yaml", tmp_path) == tmp_path / "config" / "gridlock.yaml"
    assert repository_path("/abs/file.yaml", tmp_path) == Path("/abs/file.yaml")
