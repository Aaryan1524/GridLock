from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridlock.georesolution import resolve_projects
from gridlock.georesolution.oracle import oracle_check
from gridlock.ingestion.documents.plans import raw_dir
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
CACHE = REPOSITORY_ROOT / BUNDLE.root.paths.cache_dir / "osm_power.geojson"
NORMALIZED = REPOSITORY_ROOT / BUNDLE.root.paths.normalized_dir / "projects.json"

pytestmark = pytest.mark.skipif(not (CACHE.is_file() and NORMALIZED.is_file()), reason="OSM cache or normalized projects missing")


@pytest.fixture(scope="module")
def resolved_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("resolution")
    resolve_projects(BUNDLE, REPOSITORY_ROOT, output / "first.json", output / "first.csv")
    resolve_projects(BUNDLE, REPOSITORY_ROOT, output / "second.json", output / "second.csv")
    assert (output / "first.json").read_bytes() == (output / "second.json").read_bytes()
    assert (output / "first.csv").read_bytes() == (output / "second.csv").read_bytes()
    return output / "first.json"


@pytest.fixture(scope="module")
def resolved(resolved_path: Path) -> dict[str, dict]:
    return {project["id"]: project for project in json.loads(resolved_path.read_text(encoding="utf-8"))}


def _matches(project: dict) -> dict[str, dict]:
    return {match["endpoint"]: match for match in project["geometryResolution"]["matches"]}


def test_known_false_friends_stay_rejected(resolved) -> None:
    assert _matches(resolved["DESC-6859"])["Dawson"]["status"] == "vetoed"  # Dawson, Georgia
    for project_id in ("GPC-19287", "GPC-20474", "GPC-21139"):
        assert _matches(resolved[project_id])["GRADY"]["status"] == "vetoed"  # Grady, Florida
    assert _matches(resolved["GPC-20797"])["EAST VILLA RICA"]["status"] == "no_candidate"


def test_topology_and_zone_rules_pick_the_right_namesakes(resolved) -> None:
    assert _matches(resolved["GPC-19636"])["HAMMOND"]["featureName"] == "Hammod Substation"
    assert _matches(resolved["GPC-20065"])["GOSHEN"]["point"]["lat"] == pytest.approx(32.249, abs=0.01)


def test_unresolved_endpoints_never_carry_a_point(resolved) -> None:
    for project in resolved.values():
        for match in project["geometryResolution"]["matches"]:
            if match["status"] not in {"matched", "override"}:
                assert match["point"] is None


def test_every_geometry_is_disclosed_and_scored(resolved) -> None:
    for project in resolved.values():
        resolution, evidence = project["geometryResolution"], project["evidence"]
        assert (project["geometry"] is None) == (resolution["method"] == "unresolved")
        assert evidence["score"] == sum(evidence["breakdown"].values())
        if resolution["method"] == "verified_endpoints_straight_line":
            assert resolution["isApproximation"] is True


@pytest.mark.skipif(
    not (raw_dir(BUNDLE, REPOSITORY_ROOT) / BUNDLE.root.oracle.file).is_file(), reason="sponsor spreadsheet not in the raw folder"
)
def test_resolved_sponsor_endpoints_agree_with_the_sponsor_sheet(resolved_path: Path, tmp_path: Path) -> None:
    rows = oracle_check(BUNDLE, REPOSITORY_ROOT, tmp_path / "oracle.csv", resolved_path)
    compared = [row for row in rows if row.distance_km is not None]

    assert len(compared) >= 14
    assert max(row.distance_km for row in compared) < 1.0
