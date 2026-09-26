from __future__ import annotations

from pathlib import Path

import pytest

from gridlock.settings.loader import ConfigError, load_settings
from gridlock.settings.models import GridlockConfig


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_repository_configuration_resolves() -> None:
    bundle = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")

    assert bundle.root.thresholds_km.near == 1.6
    assert bundle.root.thresholds_km.local == 8.0
    assert bundle.root.thresholds_km.maximum == 40.0
    assert [utility.id for utility in bundle.utilities] == ["desc", "gpc"]
    assert bundle.utilities[1].included_sponsors == ("GPC", "SAV")


def test_unordered_thresholds_are_rejected() -> None:
    with pytest.raises(ValueError, match="near < local < maximum"):
        GridlockConfig.model_validate(
            {
                "paths": {
                    "raw_dir": "raw",
                    "cache_dir": "cache",
                    "normalized_dir": "normalized",
                    "output_dir": "output",
                    "review_dir": "review",
                },
                "utilities": ["desc"],
                "utility_files": ["utilities/desc.yaml"],
                "thresholds_km": {"near": 8, "local": 1.6, "maximum": 40},
                "timeline_gap_days": {"near": 90, "moderate": 180, "distant": 365},
                "display": {"distance_unit": "km", "timezone": "America/New_York"},
                "geometry": {
                    "projected_crs": "EPSG:5070",
                    "bbox": [-85, 30, -78, 36],
                },
                "osm": {
                    "overpass_url": "https://overpass-api.de/api/interpreter",
                    "timeout_seconds": 60,
                    "max_retries": 3,
                    "max_response_bytes": 52428800,
                    "feature_types": ["substation", "line"],
                    "query_version": "v1",
                },
                "ai": {"enabled": False},
            }
        )


def test_unknown_utility_file_id_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "gridlock.yaml"
    utilities = tmp_path / "utilities"
    utilities.mkdir()
    root.write_text(
        """
paths: {raw_dir: raw, cache_dir: cache, normalized_dir: normalized, output_dir: output, review_dir: review}
utilities: [desc]
utility_files: [utilities/other.yaml]
thresholds_km: {near: 1.6, local: 8, maximum: 40}
timeline_gap_days: {near: 90, moderate: 180, distant: 365}
display: {distance_unit: km, timezone: America/New_York}
geometry: {projected_crs: EPSG:5070, bbox: [-85, 30, -78, 36]}
osm: {overpass_url: https://overpass-api.de/api/interpreter, timeout_seconds: 60, max_retries: 3, max_response_bytes: 52428800, feature_types: [substation, line], query_version: v1}
ai: {enabled: false}
""".strip(),
        encoding="utf-8",
    )
    (utilities / "other.yaml").write_text(
        """
id: other
display_name: Other Utility
color: '#000000'
states: [GA]
sources: [{id: test, parser: test, path: test.pdf}]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="must exactly match root utilities"):
        load_settings(root)
