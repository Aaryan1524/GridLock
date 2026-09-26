from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gridlock.ingestion.documents import ingest_plans
from gridlock.ingestion.documents.plans import raw_dir
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
SOURCES_PRESENT = all(
    (raw_dir(BUNDLE, REPOSITORY_ROOT) / source.path).is_file() for utility in BUNDLE.utilities for source in utility.sources
)

# The ten projects in the sponsor's Projects_Overlaps.xlsx, mapped to our IDs, with the endpoints
# their titles name. The spreadsheet is only a test oracle; none of its coordinates are used.
SPONSOR_PROJECT_ENDPOINTS = {
    "DESC-6809-E": ["Stevens Creek", "Hooks"],
    "DESC-6810-A": ["Hooks", "Thurmond"],
    "DESC-06367-D-G": ["Jasper", "Okatie"],
    "DESC-6807-B": ["Queensboro", "Ft Johnson"],
    "DESC-6808-S": ["Okatie", "Bluffton"],
    "GPC-20793": ["EVANS PRIMARY", "THURMOND DAM #5"],
    "GPC-20277": ["MCINTOSH", "PURRYSBURG"],
    "GPC-20065": ["GOSHEN", "MCINTOSH"],
    "GPC-18492": ["MITCHELL", "NORTH TIFTON"],
    "GPC-11821": ["JESUP", "LUDOWICI PRIMARY"],
}


@pytest.fixture(scope="module")
def ingested(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, object], dict[str, dict]]:
    if not SOURCES_PRESENT:
        pytest.skip(f"raw source documents are not in {raw_dir(BUNDLE, REPOSITORY_ROOT)}")
    output_dir = tmp_path_factory.mktemp("ingestion")
    report = ingest_plans(BUNDLE, REPOSITORY_ROOT, output_dir / "projects.json", output_dir / "endpoint_review.csv")
    projects = json.loads(report.output_path.read_text(encoding="utf-8"))
    return report.as_dict(), {project["id"]: project for project in projects}


def test_counts_match_configured_scope(ingested) -> None:
    report, by_id = ingested

    assert report["projects_by_utility"] == {"DESC": 44, "GPC": 138}
    assert len(by_id) == 182
    assert {project["sponsor"] for project in by_id.values() if project["utility"] == "GPC"} == {"GPC", "SAV"}


def test_flagship_desc_record(ingested) -> None:
    _, by_id = ingested
    project = by_id["DESC-06367-D-G"]

    assert project["projectName"] == "Jasper – Okatie 230 kV #2: Construct"
    assert project["projectType"] == "transmission_line"
    assert project["voltageKv"] == [230]
    assert project["plannedInServiceDate"] == "2025-12-31"
    assert project["filedStartDate"] is None
    assert project["estimatedCostUsd"] == 23787423
    assert project["source"]["page"] == 23
    assert project["source"]["projectIdRaw"] == "06367 D - G"


def test_gpc_dates_are_in_service_plus_filed_start_never_a_construction_window(ingested) -> None:
    _, by_id = ingested

    assert by_id["GPC-20277"]["plannedInServiceDate"] == "2026-06-01"
    assert by_id["GPC-20277"]["filedStartDate"] == "2024-01-01"
    assert by_id["GPC-20277"]["source"]["page"] == 227
    assert by_id["GPC-20793"]["plannedInServiceDate"] == "2033-06-01"
    assert all(project["constructionWindow"] is None for project in by_id.values())


def test_redacted_cost_stays_null_with_raw_value(ingested) -> None:
    _, by_id = ingested

    assert by_id["GPC-20277"]["estimatedCostUsd"] is None
    assert by_id["GPC-20277"]["source"]["rawFields"]["estimated_cost"] == "REDACTED"


def test_conflicting_and_unparseable_dates_are_kept_with_warnings(ingested) -> None:
    _, by_id = ingested

    conflict = by_id["GPC-19523"]
    assert conflict["plannedInServiceDate"] == "2025-04-25"
    assert conflict["source"]["rawFields"]["summary_need_date"] == "1/1/2025"
    assert any("differs from detail page need date" in warning for warning in conflict["warnings"])

    phased = by_id["DESC-6859"]
    assert phased["plannedInServiceDate"] is None
    assert "phase 1" in phased["source"]["rawFields"]["in_service_date"]
    assert phased["warnings"]


@pytest.mark.parametrize(("project_id", "endpoints"), sorted(SPONSOR_PROJECT_ENDPOINTS.items()))
def test_sponsor_projects_have_clean_endpoints(ingested, project_id: str, endpoints: list[str]) -> None:
    _, by_id = ingested

    assert [endpoint["name"] for endpoint in by_id[project_id]["endpoints"]] == endpoints
    assert by_id[project_id]["endpointStatus"] == "explicit_pair"


def test_endpoint_names_carry_no_title_residue_unless_flagged(ingested) -> None:
    _, by_id = ingested
    residue = re.compile(r"\bkV\b|:|\(|\bREBUILD\b|\bCONSTRUCT\b", re.I)

    offenders = {
        project_id
        for project_id, project in by_id.items()
        for endpoint in project["endpoints"]
        if residue.search(endpoint["name"])
    }
    unflagged = [project_id for project_id in offenders if not any("malformed" in w for w in by_id[project_id]["warnings"])]
    # GPC-21046's title reads "23O KV" (letter O); it is flagged for review rather than guessed at.
    assert offenders == {"GPC-21046"}
    assert unflagged == []


def test_ceii_notice_is_not_stored(ingested) -> None:
    _, by_id = ingested

    assert not any("CRITICAL ENERGY INFRASTRUCTURE" in (project["source"]["rawText"] or "") for project in by_id.values())
