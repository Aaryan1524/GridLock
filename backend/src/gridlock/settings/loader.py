"""Load and cross-validate GridLock's YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import GeometryOverride, GeometryOverrides, GridlockConfig, UtilityConfig


class ConfigError(ValueError):
    """Raised when config files are malformed or disagree with each other."""


@dataclass(frozen=True)
class ConfigBundle:
    root: GridlockConfig
    utilities: tuple[UtilityConfig, ...]
    config_path: Path
    overrides: tuple[GeometryOverride, ...] = ()

    def utility(self, code: str) -> UtilityConfig:
        for utility in self.utilities:
            if utility.code == code:
                return utility
        raise ConfigError(f"no configured utility has code {code!r}")

    def summary(self) -> dict[str, Any]:
        """Return a stable, safe-to-display view of the resolved settings."""
        return {
            "config_path": str(self.config_path),
            "thresholds_km": self.root.thresholds_km.model_dump(),
            "utilities": [
                {
                    "id": utility.id,
                    "display_name": utility.display_name,
                    "included_sponsors": list(utility.included_sponsors),
                }
                for utility in self.utilities
            ],
        }


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as config_file:
            contents = yaml.safe_load(config_file)
    except OSError as error:
        raise ConfigError(f"cannot read config file {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(contents, dict):
        raise ConfigError(f"config file {path} must contain a mapping")
    return contents


def load_settings(config_path: str | Path) -> ConfigBundle:
    """Load root config and ensure its declared utility files match its scope."""
    path = Path(config_path).resolve()
    try:
        root = GridlockConfig.model_validate(_read_yaml(path))
    except ValidationError as error:
        raise ConfigError(f"invalid root configuration: {error}") from error

    utility_configs: list[UtilityConfig] = []
    for relative_path in root.utility_files:
        utility_path = path.parent / relative_path
        try:
            utility_configs.append(UtilityConfig.model_validate(_read_yaml(utility_path)))
        except ValidationError as error:
            raise ConfigError(f"invalid utility configuration {utility_path}: {error}") from error

    utility_codes = [utility.code for utility in utility_configs]
    if len(set(utility_codes)) != len(utility_codes):
        raise ConfigError("utility codes must not contain duplicates")
    utility_ids = tuple(utility.id for utility in utility_configs)
    if len(set(utility_ids)) != len(utility_ids):
        raise ConfigError("utility configuration IDs must not contain duplicates")
    if set(utility_ids) != set(root.utilities):
        raise ConfigError(
            "utility configuration IDs must exactly match root utilities "
            f"(expected {sorted(root.utilities)}, found {sorted(utility_ids)})"
        )

    overrides_path = path.parent / root.resolution.overrides_file
    try:
        overrides = GeometryOverrides.model_validate(_read_yaml(overrides_path)).overrides
    except ValidationError as error:
        raise ConfigError(f"invalid geometry overrides {overrides_path}: {error}") from error
    unknown = sorted({override.utility for override in overrides} - set(utility_codes))
    if unknown:
        raise ConfigError(f"geometry overrides name unknown utility codes {unknown}")

    return ConfigBundle(root=root, utilities=tuple(utility_configs), config_path=path, overrides=overrides)

