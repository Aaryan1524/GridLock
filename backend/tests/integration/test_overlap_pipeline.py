from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridlock.georesolution.oracle import overlap_oracle_check
from gridlock.ingestion.documents.plans import raw_dir
from gridlock.overlap import run_overlap
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
RESOLVED = REPOSITORY_ROOT / BUNDLE.root.paths.normalized_dir / "projects_resolved.json"

pytestmark = pytest.mark.skipif(not RESOLVED.is_file(), reason="resolved projects missing")


@pytest.fixture(scope="module")
def relationships_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("overlap")
    run_overlap(BUNDLE, REPOSITORY_ROOT, output / "first.json")
    run_overlap(BUNDLE, REPOSITORY_ROOT, output / "second.json")
    assert (output / "first.json").read_bytes() == (output / "second.json").read_bytes()  # I-4
    return output / "first.json"


@pytest.fixture(scope="module")
def relationships(relationships_path: Path) -> list[dict]:
    return json.loads(relationships_path.read_text(encoding="utf-8"))


def test_phase_5_invariants(relationships) -> None:
    projects = {p["id"]: p for p in json.loads(RESOLVED.read_text(encoding="utf-8"))}

    assert relationships
    for relationship in relationships:
        a, b = projects[relationship["projectA"]], projects[relationship["projectB"]]
        assert a["utility"] != b["utility"]
        assert relationship["distanceKm"] < BUNDLE.root.thresholds_km.maximum
        assert len(relationship["closestPoints"]) == 2
        assert "unresolved" not in relationship["geometryMethods"]
        assert a["geometry"] is not None and b["geometry"] is not None
        assert relationship["timeline"]["type"] != "WINDOW_OVERLAP" or (a["constructionWindow"] and b["constructionWindow"])


@pytest.mark.skipif(
    not (raw_dir(BUNDLE, REPOSITORY_ROOT) / BUNDLE.root.oracle.file).is_file(), reason="sponsor spreadsheet not in the raw folder"
)
def test_every_sponsor_overlap_is_detected_with_the_same_date_gap(relationships_path: Path, tmp_path: Path) -> None:
    rows = overlap_oracle_check(BUNDLE, REPOSITORY_ROOT, relationships_path, tmp_path / "oracle_overlaps.csv")

    assert len(rows) == 6
    assert all(row.our_tier != "not_detected" for row in rows)
    assert all(row.our_gap_days == row.sheet_gap_days for row in rows)
    # Closest points can never be further apart than the sheet's centre points.
    assert all(row.our_km <= row.sheet_km for row in rows)


def test_sponsor_sheet_projects_overlap_exactly_where_the_sheet_says(relationships) -> None:
    """The sheet's other 19 cross-utility pairs are negative controls: most projects should not overlap."""
    sponsor_projects = set(BUNDLE.root.oracle.project_ids.values())
    ours = {(r["projectA"], r["projectB"]) for r in relationships if {r["projectA"], r["projectB"]} <= sponsor_projects}

    assert ours == {
        ("DESC-06367-D-G", "GPC-20065"),
        ("DESC-06367-D-G", "GPC-20277"),
        ("DESC-6808-S", "GPC-20065"),
        ("DESC-6808-S", "GPC-20277"),
        ("DESC-6809-E", "GPC-20793"),
        ("DESC-6810-A", "GPC-20793"),
    }
