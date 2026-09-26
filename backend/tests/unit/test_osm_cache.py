from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridlock.ingestion.osm.cache import OsmIngestionError, build_overpass_query, ingest_osm, overpass_to_feature_collection
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_query_uses_configured_feature_types_and_bbox() -> None:
    query = build_overpass_query((-85.0, 30.0, -78.0, 36.0), ("substation", "line"), 60)

    assert '["power"~"^(line|substation)$"](30.0,-85.0,36.0,-78.0)' in query
    assert "[timeout:60]" in query


def test_overpass_conversion_preserves_point_line_and_polygon() -> None:
    collection = overpass_to_feature_collection(
        {
            "elements": [
                {"type": "node", "id": 1, "lat": 32.0, "lon": -81.0, "tags": {"power": "substation"}},
                {
                    "type": "way",
                    "id": 2,
                    "geometry": [{"lat": 32.0, "lon": -81.0}, {"lat": 32.1, "lon": -81.1}],
                    "tags": {"power": "line", "operator": "Example Utility"},
                },
                {
                    "type": "way",
                    "id": 3,
                    "geometry": [
                        {"lat": 32.0, "lon": -81.0}, {"lat": 32.0, "lon": -81.1},
                        {"lat": 32.1, "lon": -81.1}, {"lat": 32.0, "lon": -81.0},
                    ],
                    "tags": {"power": "substation"},
                },
            ]
        }
    )

    assert [feature["geometry"]["type"] for feature in collection["features"]] == ["Point", "LineString", "Polygon"]
    assert collection["features"][1]["id"] == "way/2"


def test_offline_mode_uses_only_cache(tmp_path: Path) -> None:
    bundle = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
    cache_dir = tmp_path / "data" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "osm_power.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "node/1",
                        "properties": {"power": "substation", "operator": "Example Utility"},
                        "geometry": {"type": "Point", "coordinates": [-81.0, 32.0]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = ingest_osm(bundle, tmp_path, offline=True)

    assert report.feature_counts == {"substation": 1}
    assert (cache_dir / "osm_operators.csv").read_text(encoding="utf-8") == "operator,count\nExample Utility,1\n"


def test_offline_mode_rejects_missing_cache(tmp_path: Path) -> None:
    bundle = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")

    with pytest.raises(OsmIngestionError, match="cannot read OSM cache"):
        ingest_osm(bundle, tmp_path, offline=True)
