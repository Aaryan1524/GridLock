"""Fetch public OSM power features once, then serve deterministic local cache reads."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

import httpx
from shapely.geometry import LineString, mapping
from shapely.ops import polygonize, unary_union

from gridlock.settings.loader import ConfigBundle

CACHE_FILE = "osm_power.geojson"
METADATA_FILE = "osm_power.meta.json"
OPERATORS_FILE = "osm_operators.csv"


class OsmIngestionError(ValueError):
    """Raised when the OSM cache is missing, invalid, or violates configured limits."""


class OsmResponseTooLarge(OsmIngestionError):
    """Raised when Overpass returns more than the configured byte limit; retrying cannot help."""


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
    """Build a bounded query for configured public power-feature types.

    Relations are included because large substations are often mapped as multipolygons.
    """
    west, south, east, north = bbox
    type_expression = "|".join(sorted(feature_types))
    bounds = f"{south},{west},{north},{east}"
    selectors = "".join(
        f'  {element}["power"~"^({type_expression})$"]({bounds});\n' for element in ("node", "way", "relation")
    )
    return f"[out:json][timeout:{timeout_seconds}];\n(\n{selectors});\nout body geom;"


def _way_geometry(points: list[dict[str, float]]) -> dict[str, Any] | None:
    coordinates = [[point["lon"], point["lat"]] for point in points]
    if len(coordinates) < 2:
        return None
    if coordinates[0] == coordinates[-1] and len(coordinates) >= 4:
        return {"type": "Polygon", "coordinates": [coordinates]}
    return {"type": "LineString", "coordinates": coordinates}


def _relation_geometry(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Assemble a relation's member ways into polygons when they close, else keep them as lines."""
    lines = [
        LineString([(point["lon"], point["lat"]) for point in member["geometry"]])
        for member in members
        if member.get("type") == "way" and len(member.get("geometry") or []) >= 2
    ]
    if not lines:
        return None
    polygons = list(polygonize(lines))
    shape = unary_union(polygons) if polygons else unary_union(lines)
    return json.loads(json.dumps(mapping(shape)))


def overpass_to_feature_collection(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the Overpass JSON subset requested above into stable GeoJSON sorted by feature ID."""
    features: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        if element.get("type") == "node":
            geometry = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        elif element.get("type") == "way":
            geometry = _way_geometry(element.get("geometry") or [])
        elif element.get("type") == "relation":
            geometry = _relation_geometry(element.get("members") or [])
        else:
            geometry = None
        if geometry is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f'{element["type"]}/{element["id"]}',
                "properties": {"osm_type": element["type"], "osm_id": element["id"], **tags},
                "geometry": geometry,
            }
        )
    features.sort(key=lambda feature: (feature["properties"]["osm_type"], feature["properties"]["osm_id"]))
    return {"type": "FeatureCollection", "features": features}


def _serialize(collection: dict[str, Any]) -> str:
    """Compact JSON with one feature per line: small on disk, readable in diffs, byte-stable."""
    lines = [json.dumps(feature, separators=(",", ":"), sort_keys=True) for feature in collection["features"]]
    return '{"type":"FeatureCollection","features":[\n' + ",\n".join(lines) + "\n]}\n"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["operator", "count"])
        writer.writerows(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))


def _feature_counts(features: list[dict[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(feature.get("properties", {}).get("power", "unknown")) for feature in features).items())
    )


def _download(client: httpx.Client, url: str, query: str, max_bytes: int) -> bytes:
    """Stream the response and stop as soon as it passes the configured size limit."""
    body = bytearray()
    with client.stream("POST", url, data={"data": query}) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise OsmResponseTooLarge(f"Overpass response exceeds configured {max_bytes}-byte limit")
    return bytes(body)


def _fetch_overpass(bundle: ConfigBundle, query: str) -> dict[str, Any]:
    config = bundle.root.osm
    last_error: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            with httpx.Client(timeout=config.timeout_seconds, headers={"User-Agent": config.user_agent}) as client:
                return json.loads(_download(client, config.overpass_url, query, config.max_response_bytes))
        except OsmResponseTooLarge:
            raise
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
            if attempt < config.max_retries:
                sleep(config.backoff_seconds * 2**attempt)
    raise OsmIngestionError(f"Overpass request failed after {config.max_retries + 1} attempts: {last_error}")


def ingest_osm(bundle: ConfigBundle, repository_root: Path, *, offline: bool) -> OsmIngestionReport:
    """Refresh the public OSM snapshot or read it strictly offline."""
    cache_dir = repository_root / bundle.root.paths.cache_dir
    cache_path = cache_dir / CACHE_FILE
    metadata_path = cache_dir / METADATA_FILE
    operators_path = cache_dir / OPERATORS_FILE
    if offline:
        collection = _read_cache(cache_path)
    else:
        osm = bundle.root.osm
        query = build_overpass_query(bundle.root.geometry.bbox, osm.feature_types, osm.timeout_seconds)
        collection = overpass_to_feature_collection(_fetch_overpass(bundle, query))
        serialized = _serialize(collection)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(serialized, encoding="utf-8")
        metadata = {
            "source": "OpenStreetMap via Overpass",
            "license": "ODbL 1.0, © OpenStreetMap contributors",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "overpass_url": osm.overpass_url,
            "bbox": list(bundle.root.geometry.bbox),
            "query_version": osm.query_version,
            "query": query,
            "feature_types": list(osm.feature_types),
            "feature_count": len(collection["features"]),
            "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    _write_operator_index(collection["features"], operators_path)
    return OsmIngestionReport(
        feature_counts=_feature_counts(collection["features"]),
        cache_path=cache_path,
        metadata_path=metadata_path,
        operators_path=operators_path,
        offline=offline,
    )
