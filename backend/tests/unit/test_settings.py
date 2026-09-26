from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from gridlock.settings.loader import ConfigError, load_settings
from gridlock.settings.models import GridlockConfig


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ROOT_CONFIG = REPOSITORY_ROOT / "config" / "gridlock.yaml"


def _repository_config() -> dict[str, Any]:
    return yaml.safe_load(ROOT_CONFIG.read_text(encoding="utf-8"))


def test_repository_configuration_resolves() -> None:
    bundle = load_settings(ROOT_CONFIG)

    assert bundle.root.thresholds_km.near == 1.6
    assert bundle.root.thresholds_km.local == 8.0
    assert bundle.root.thresholds_km.maximum == 40.0
    assert [utility.id for utility in bundle.utilities] == ["desc", "gpc"]
    assert [utility.code for utility in bundle.utilities] == ["DESC", "GPC"]
    assert bundle.utilities[1].included_sponsors == ("GPC", "SAV")


def test_unordered_thresholds_are_rejected() -> None:
    config = _repository_config()
    config["thresholds_km"] = {"near": 8, "local": 1.6, "maximum": 40}

    with pytest.raises(ValueError, match="near < local < maximum"):
        GridlockConfig.model_validate(config)


def test_unknown_project_type_in_rules_is_rejected() -> None:
    config = _repository_config()
    config["normalization"]["project_types"]["rules"][0]["type"] = "power_plant"

    with pytest.raises(ValueError, match="unknown project type"):
        GridlockConfig.model_validate(config)


def test_invalid_normalization_pattern_is_rejected() -> None:
    config = _repository_config()
    config["normalization"]["voltage_pattern"] = "(unclosed"

    with pytest.raises(ValueError, match="invalid regular expression"):
        GridlockConfig.model_validate(config)


def _write_config(directory: Path, utility_files: dict[str, dict[str, Any]]) -> Path:
    config = _repository_config()
    config["utilities"] = [utility["id"] for utility in utility_files.values()]
    config["utility_files"] = [f"utilities/{name}" for name in utility_files]
    (directory / "utilities").mkdir()
    for name, utility in utility_files.items():
        (directory / "utilities" / name).write_text(yaml.safe_dump(utility), encoding="utf-8")
    root = directory / "gridlock.yaml"
    root.write_text(yaml.safe_dump(config), encoding="utf-8")
    return root


def _utility(identifier: str, code: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "code": code,
        "display_name": "Test Utility",
        "color": "#000000",
        "states": ["GA"],
        "sources": [{"id": "test", "parser": "test", "path": "test.pdf"}],
    }


def test_unknown_utility_file_id_is_rejected(tmp_path: Path) -> None:
    root = _write_config(tmp_path, {"other.yaml": _utility("other", "OTHER")})
    root.write_text(root.read_text(encoding="utf-8").replace("- other", "- desc"), encoding="utf-8")

    with pytest.raises(ConfigError, match="must exactly match root utilities"):
        load_settings(root)


def test_duplicate_utility_codes_are_rejected(tmp_path: Path) -> None:
    root = _write_config(tmp_path, {"a.yaml": _utility("a", "SAME"), "b.yaml": _utility("b", "SAME")})

    with pytest.raises(ConfigError, match="utility codes must not contain duplicates"):
        load_settings(root)
