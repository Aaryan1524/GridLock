"""Fetch public OSM power features once, then serve deterministic local cache reads."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

import httpx

from gridlock.settings.loader import ConfigBundle


class OsmIngestionError(ValueError):
    """Raised when the OSM cache is missing, invalid, or violates configured limits."""


@dataclass(frozen=True)
class OsmIngestionReport:
    feature_counts: dict[str, int]
    cache_path: Path
    metadata_path: Path
    operators_path: Path
    offline: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "feature_counts": self.feature_counts,
            "cache_path": str(self.cache_path),
            "metadata_path": str(self.metadata_path),
            "operators_path": str(self.operators_path),
            "offline": self.offline,
        }


def build_overpass_query(
    bbox: tuple[float, float, float, float], feature_types: tuple[str, ...], timeout_seconds: int
) -> str:
    """Build a bounded query for configured public power-feature types."""
    west, south, east, north = bbox
    type_expression = "|".join(sorted(feature_types))
    bounds = f"{south},{west},{north},{east}"
    return (
        f"[out:json][timeout:{timeout_seconds}];\n"
        "(\n"
        f'  node["power"~"^({type_expression})$"]({bounds});\n'
        f'  way["power"~"^({type_expression})$"]({bounds});\n'
        ");\n"
        "out body geom;"
    )


def overpass_to_feature_collection(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the Overpass JSON subset requested above into stable GeoJSON."""
    features: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        if element.get("type") == "node":
            geometry = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        elif element.get("type") == "way" and element.get("geometry"):
            coordinates = [[point["lon"], point["lat"]] for point in element["geometry"]]
            if len(coordinates) < 2:
                continue
            geometry_type = "Polygon" if coordinates[0] == coordinates[-1] and len(coordinates) >= 4 else "LineString"
            geometry = {"type": geometry_type, "coordinates": [coordinates] if geometry_type == "Polygon" else coordinates}
        else:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f'{element["type"]}/{element["id"]}',
                "properties": {"osm_type": element["type"], "osm_id": element["id"], **tags},
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _read_cache(cache_path: Path) -> dict[str, Any]:
    try:
        content = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OsmIngestionError(f"cannot read OSM cache {cache_path}: {error}") from error
    if content.get("type") != "FeatureCollection" or not isinstance(content.get("features"), list):
        raise OsmIngestionError(f"OSM cache {cache_path} is not a GeoJSON FeatureCollection")
    return content


def _write_operator_index(features: list[dict[str, Any]], path: Path) -> None:
    counts = Counter(
        str(feature.get("properties", {}).get("operator", "")).strip()
        for feature in features
        if str(feature.get("properties", {}).get("operator", "")).strip()
    )
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["operator", "count"])
        writer.writerows(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))


def _feature_counts(features: list[dict[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(feature.get("properties", {}).get("power", "unknown")) for feature in features).items())
    )


def _fetch_overpass(bundle: ConfigBundle) -> dict[str, Any]:
    config = bundle.root.osm
    query = build_overpass_query(bundle.root.geometry.bbox, config.feature_types, config.timeout_seconds)
    last_error: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            with httpx.Client(timeout=config.timeout_seconds, headers={"User-Agent": "GridLock/0.1 (public-data cache)"}) as client:
                response = client.post(config.overpass_url, data={"data": query})
                response.raise_for_status()
                if len(response.content) > config.max_response_bytes:
                    raise OsmIngestionError(
                        f"Overpass response exceeds configured {config.max_response_bytes}-byte limit"
                    )
                return response.json()
        except (httpx.HTTPError, ValueError, OsmIngestionError) as error:
            last_error = error
            if attempt < config.max_retries:
                sleep(2**attempt)
    raise OsmIngestionError(f"Overpass request failed after {config.max_retries + 1} attempts: {last_error}")


def ingest_osm(bundle: ConfigBundle, repository_root: Path, *, offline: bool) -> OsmIngestionReport:
    """Refresh the public OSM snapshot or read it strictly offline."""
    cache_dir = repository_root / bundle.root.paths.cache_dir
    cache_path = cache_dir / "osm_power.geojson"
    metadata_path = cache_dir / "osm_power.meta.json"
    operators_path = cache_dir / "osm_operators.csv"
    if offline:
        collection = _read_cache(cache_path)
    else:
        collection = overpass_to_feature_collection(_fetch_overpass(bundle))
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "source": "OpenStreetMap via Overpass",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "bbox": list(bundle.root.geometry.bbox),
                    "query_version": bundle.root.osm.query_version,
                    "feature_types": list(bundle.root.osm.feature_types),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    _write_operator_index(collection["features"], operators_path)
    return OsmIngestionReport(
        feature_counts=_feature_counts(collection["features"]),
        cache_path=cache_path,
        metadata_path=metadata_path,
        operators_path=operators_path,
        offline=offline,
    )
