from __future__ import annotations

import json
from pathlib import Path

import pytest

import httpx

from gridlock.ingestion.osm import cache as osm_cache
from gridlock.ingestion.osm.cache import (
    OsmIngestionError,
    OsmResponseTooLarge,
    build_overpass_query,
    ingest_osm,
    overpass_to_feature_collection,
)
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REAL_CLIENT = httpx.Client


def test_query_uses_configured_feature_types_and_bbox() -> None:
    query = build_overpass_query((-85.0, 30.0, -78.0, 36.0), ("substation", "line"), 60)

    for element in ("node", "way", "relation"):
        assert f'{element}["power"~"^(line|substation)$"](30.0,-85.0,36.0,-78.0)' in query
    assert "[timeout:60]" in query
    assert query.endswith("out body geom;")


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


def _square(lon: float, lat: float, size: float) -> list[list[dict[str, float]]]:
    """Two open member ways that only close into a ring together, as multipolygon outers often do."""
    corners = [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)]
    first = [{"lon": x, "lat": y} for x, y in corners[:3]]
    second = [{"lon": x, "lat": y} for x, y in corners[2:] + corners[:1]]
    return [first, second]


def test_relation_members_are_assembled_into_a_polygon() -> None:
    members = [{"type": "way", "role": "outer", "geometry": ring} for ring in _square(-81.0, 32.0, 0.01)]
    collection = overpass_to_feature_collection(
        {"elements": [{"type": "relation", "id": 9, "members": members, "tags": {"power": "substation", "name": "Big Yard"}}]}
    )

    feature = collection["features"][0]
    assert feature["id"] == "relation/9"
    assert feature["geometry"]["type"] == "Polygon"


def test_features_are_sorted_so_reordered_responses_serialize_identically() -> None:
    elements = [
        {"type": "way", "id": 5, "geometry": [{"lat": 32.0, "lon": -81.0}, {"lat": 32.1, "lon": -81.1}], "tags": {"power": "line"}},
        {"type": "node", "id": 7, "lat": 32.0, "lon": -81.0, "tags": {"power": "substation"}},
        {"type": "node", "id": 3, "lat": 32.0, "lon": -81.0, "tags": {"power": "substation"}},
    ]
    forward = osm_cache._serialize(overpass_to_feature_collection({"elements": elements}))
    backward = osm_cache._serialize(overpass_to_feature_collection({"elements": list(reversed(elements))}))

    assert forward == backward
    assert ['"id":"node/3"' in forward.splitlines()[1], '"id":"node/7"' in forward.splitlines()[2]] == [True, True]


def _bundle_with(**osm_overrides):
    bundle = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
    osm = bundle.root.osm.model_copy(update=osm_overrides)
    return type(bundle)(root=bundle.root.model_copy(update={"osm": osm}), utilities=bundle.utilities, config_path=bundle.config_path)


def test_oversized_response_fails_without_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x" * 2048)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(osm_cache.httpx, "Client", lambda **kwargs: REAL_CLIENT(transport=transport, **kwargs))
    monkeypatch.setattr(osm_cache, "sleep", lambda seconds: None)

    with pytest.raises(OsmResponseTooLarge):
        osm_cache._fetch_overpass(_bundle_with(max_response_bytes=1024, max_retries=3), "query")
    assert len(calls) == 1


def test_transient_failures_back_off_then_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([httpx.Response(429), httpx.Response(504), httpx.Response(200, json={"elements": []})])
    waits: list[float] = []
    transport = httpx.MockTransport(lambda request: next(responses))
    monkeypatch.setattr(osm_cache.httpx, "Client", lambda **kwargs: REAL_CLIENT(transport=transport, **kwargs))
    monkeypatch.setattr(osm_cache, "sleep", waits.append)

    assert osm_cache._fetch_overpass(_bundle_with(backoff_seconds=5, max_retries=3), "query") == {"elements": []}
    assert waits == [5, 10]
