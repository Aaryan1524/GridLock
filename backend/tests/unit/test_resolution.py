from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from gridlock.evidence import score_evidence
from gridlock.georesolution.matching import build_index, match_project_endpoints
from gridlock.georesolution.names import name_score, normalize_name
from gridlock.georesolution.resolver import resolve_project
from gridlock.models.domain import (
    Endpoint,
    EndpointMatchStatus,
    EndpointRole,
    EndpointStatus,
    EvidenceLevel,
    GeometryMethod,
    Project,
    ProjectType,
    SourceRef,
)
from gridlock.settings.loader import load_settings
from gridlock.settings.models import GeometryOverride


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
RULES = BUNDLE.root.resolution
DESC = BUNDLE.utility("DESC")
GPC = BUNDLE.utility("GPC")

# Points inside each configured service area, and one inside GPC's Savannah (SAV) zone.
SC = (-80.9, 32.3)
GA = (-84.3, 33.6)
SAVANNAH = (-81.2, 32.2)


def feature(identifier: str, name: str, at: tuple[float, float], operator: str | None = None, voltage: str | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {"power": "substation", "name": name}
    if operator:
        properties["operator"] = operator
    if voltage:
        properties["voltage"] = voltage
    return {"type": "Feature", "id": identifier, "properties": properties, "geometry": {"type": "Point", "coordinates": list(at)}}


def project(
    utility: str,
    *endpoints: str,
    voltage: list[float] | None = None,
    title: str = "Test project",
    sponsor: str | None = None,
    qualifiers: dict[str, list[str]] | None = None,
    status: EndpointStatus | None = None,
    in_service: date | None = date(2026, 6, 1),
    filed_start: date | None = None,
) -> Project:
    roles = [EndpointRole.SINGLE] if len(endpoints) == 1 else [EndpointRole.FROM, *[EndpointRole.VIA] * (len(endpoints) - 2), EndpointRole.TO]
    return Project(
        id=f"{utility}-TEST",
        utility=utility,
        project_name=title,
        project_type=ProjectType.TRANSMISSION_LINE,
        sponsor=sponsor,
        voltage_kv=voltage or [],
        endpoints=[Endpoint(name=name, role=role, qualifiers=(qualifiers or {}).get(name, [])) for name, role in zip(endpoints, roles)],
        endpoint_status=status or (EndpointStatus.SINGLE_SITE if len(endpoints) == 1 else EndpointStatus.EXPLICIT_PAIR),
        planned_in_service_date=in_service,
        filed_start_date=filed_start,
        source=SourceRef(document="filing.pdf", project_id_raw="0001", page=1),
    )


def match(target: Project, features: list[dict[str, Any]], overrides: tuple[GeometryOverride, ...] = ()):
    utility = BUNDLE.utility(target.utility)
    return match_project_endpoints(target, utility, build_index(features, RULES), RULES, overrides)


# --- Names -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "osm_name"),
    [
        ("MITCHELL", "Mitchell Substation (230kV)"),
        ("Stevens Creek", "Stevens Creek Dam Substation"),
        ("Queensboro", "Queensborough Substation"),
        ("St George", "Saint George Switching Station"),
        ("N DUBLIN", "North Dublin Substation"),
        ("THURMOND DAM #5", "Thurmond Substation"),
    ],
)
def test_names_that_should_match(endpoint: str, osm_name: str) -> None:
    assert name_score(normalize_name(endpoint, RULES), normalize_name(osm_name, RULES)) >= RULES.name_match_threshold


@pytest.mark.parametrize(
    ("endpoint", "osm_name"),
    [
        ("EAST VILLA RICA", "West Villa Rica Substation"),
        ("SOUTH BAINBRIDGE", "Bainbridge Substation"),
        ("GAINESVILLE #2", "Gainesville Substation #1"),
        ("GRADY", "Gray Substation"),
        ("Williams St", "Saint Williams Substation"),
    ],
)
def test_names_that_must_not_match(endpoint: str, osm_name: str) -> None:
    assert name_score(normalize_name(endpoint, RULES), normalize_name(osm_name, RULES)) < RULES.name_match_threshold


# --- Operator, region and voltage vetoes -------------------------------------------------------


def test_exact_match_with_own_operator() -> None:
    [result] = match(project("DESC", "Jasper"), [feature("way/1", "Jasper Substation", SC, "Dominion Energy South Carolina")])

    assert result.status is EndpointMatchStatus.MATCHED
    assert result.operator_relation == "own"


def test_legacy_operator_name_counts_as_own() -> None:
    [result] = match(project("DESC", "Bluffton"), [feature("way/1", "Bluffton Substation", SC, "South Carolina Electric & Gas")])

    assert result.operator_relation == "own"


def test_missing_operator_is_not_a_veto() -> None:
    [result] = match(project("DESC", "Jasper"), [feature("way/1", "Jasper Substation", SC)])

    assert result.status is EndpointMatchStatus.MATCHED
    assert result.operator_relation == "untagged"


def test_unrelated_operator_is_vetoed_and_gets_no_point() -> None:
    [result] = match(project("DESC", "Jasper"), [feature("way/1", "Jasper Substation", SC, "Duke Energy Florida")])

    assert result.status is EndpointMatchStatus.VETOED
    assert result.point is None
    assert "operated by Duke Energy Florida" in result.notes[0]


def test_neighbour_substation_needs_the_filing_to_mark_a_tie() -> None:
    features = [feature("way/1", "Grady Substation", GA, "Florida Power & Light")]

    [unmarked] = match(project("GPC", "GRADY"), features)
    [qualified] = match(project("GPC", "GRADY", qualifiers={"GRADY": ["FPL"]}), features)
    [tie] = match(project("GPC", "GRADY", title="GRADY 115KV TIE REBUILD"), features)

    assert unmarked.status is EndpointMatchStatus.VETOED
    assert qualified.status is EndpointMatchStatus.MATCHED and qualified.operator_relation == "interconnection"
    assert tie.status is EndpointMatchStatus.MATCHED


def test_bus_tie_equipment_does_not_count_as_a_tie() -> None:
    features = [feature("way/1", "Grady Substation", GA, "Florida Power & Light")]

    [result] = match(project("GPC", "GRADY", title="GRADY 230KV BUS 1-3 SERIES BUS TIE BREAKER INSTALLATION"), features)

    assert result.status is EndpointMatchStatus.VETOED


def test_co_owner_substation_is_always_allowed() -> None:
    [result] = match(project("GPC", "BRASELTON"), [feature("way/1", "Braselton Substation", GA, "Georgia Transmission Corporation")])

    assert result.status is EndpointMatchStatus.MATCHED
    assert result.operator_relation == "interconnection"


def test_namesake_outside_the_service_area_is_vetoed() -> None:
    [result] = match(project("DESC", "Dawson", voltage=[230]), [feature("way/1", "Dawson Substation", (-84.43, 31.76), voltage="115000")])

    assert result.status is EndpointMatchStatus.VETOED
    assert "outside the project's service area" in result.notes[0]


def test_voltage_only_conflicts_when_the_project_exceeds_the_substation() -> None:
    higher = match(project("GPC", "MORROW", voltage=[115]), [feature("way/1", "Morrow Substation", GA, voltage="230000")])
    lower = match(project("GPC", "BUZZARD ROOST", voltage=[230]), [feature("way/2", "Buzzard Roost Dam Substation", GA, voltage="44000")])

    assert higher[0].status is EndpointMatchStatus.MATCHED
    assert lower[0].status is EndpointMatchStatus.VETOED


def test_sponsor_zone_picks_the_local_namesake() -> None:
    features = [feature("way/1", "Goshen Substation", (-82.0, 33.32)), feature("way/2", "Goshen Substation", SAVANNAH)]

    [savannah] = match(project("GPC", "GOSHEN", sponsor="SAV"), features)
    [statewide] = match(project("GPC", "GOSHEN", sponsor="GPC"), features)

    assert savannah.feature_id == "way/2"
    assert statewide.status is EndpointMatchStatus.AMBIGUOUS


# --- Choosing among candidates -----------------------------------------------------------------


def test_topology_prefers_the_namesake_near_the_other_endpoint() -> None:
    features = [
        feature("way/1", "Hammonds Substation", (-80.86, 33.73)),  # higher score, but in South Carolina
        feature("way/2", "Hammod Substation", (-85.35, 34.25)),
        feature("way/3", "Weiss Substation", (-85.79, 34.13)),
    ]

    hammond, weiss = match(project("GPC", "HAMMOND", "WEISS DAM"), features)

    assert hammond.feature_id == "way/2"
    assert "plausibly together" in hammond.notes[0]
    assert weiss.feature_id == "way/3"


def test_equal_namesakes_far_apart_are_ambiguous() -> None:
    features = [feature("way/1", "Coleman Substation", (-81.12, 32.10)), feature("way/2", "Coleman Substation", (-81.23, 32.11))]

    [result] = match(project("GPC", "COLEMAN", sponsor="SAV"), features)

    assert result.status is EndpointMatchStatus.AMBIGUOUS
    assert result.point is None


def test_equal_namesakes_within_the_site_radius_are_one_site() -> None:
    features = [feature("way/1", "Arkwright Substation", (-83.699, 32.927)), feature("way/2", "Arkwright Substation", (-83.726, 32.922))]

    [result] = match(project("GPC", "ARKWRIGHT"), features)

    assert result.status is EndpointMatchStatus.MATCHED
    assert "treated as one site" in result.notes[0]


def test_confirmed_voltage_breaks_a_tie() -> None:
    features = [feature("way/1", "Wadley Substation", (-82.416, 32.885), voltage="500000"), feature("way/2", "Wadley Substation", (-82.397, 32.809), voltage="115000")]

    [result] = match(project("GPC", "WADLEY", voltage=[115]), features)

    assert result.feature_id == "way/2"


def test_no_plausible_combination_is_rejected_not_guessed() -> None:
    features = [feature("way/1", "Alpha Substation", (-85.9, 30.3)), feature("way/2", "Omega Substation", (-80.8, 35.0))]

    results = match(project("GPC", "ALPHA", "OMEGA"), features)

    assert {result.status for result in results} == {EndpointMatchStatus.SEPARATION_REJECTED}


def test_override_supplies_a_point_osm_lacks() -> None:
    override = GeometryOverride(utility="DESC", endpoint="Okatie", lat=32.33, lon=-81.03, source="public filing p.1", reviewer="tester", note="checked")

    [result] = match(project("DESC", "Okatie"), [], (override,))

    assert result.status is EndpointMatchStatus.OVERRIDE
    assert (result.point.lat, result.point.lon) == (32.33, -81.03)


def test_override_outside_the_service_area_is_rejected() -> None:
    override = GeometryOverride(utility="DESC", endpoint="Okatie", lat=31.0, lon=-85.0, source="x", reviewer="tester", note="typo")

    [result] = match(project("DESC", "Okatie"), [], (override,))

    assert result.status is EndpointMatchStatus.VETOED


# --- Geometry ladder and Evidence Quality -----------------------------------------------------


def _resolve(target: Project, features: list[dict[str, Any]]) -> Project:
    return resolve_project(target, BUNDLE.utility(target.utility), build_index(features, RULES), BUNDLE)


PAIR_FEATURES = [
    feature("way/1", "Jasper Substation", (-81.124, 32.361), "Dominion Energy South Carolina", "230000;115000"),
    feature("way/2", "Okatie Substation", (-81.032, 32.334), "Dominion Energy South Carolina", "230000;115000"),
]


def test_both_endpoints_give_an_approximate_straight_line_with_high_evidence() -> None:
    resolved = _resolve(project("DESC", "Jasper", "Okatie", voltage=[230], filed_start=date(2024, 1, 1)), PAIR_FEATURES)

    assert resolved.geometry["type"] == "LineString"
    assert resolved.geometry_resolution.method is GeometryMethod.VERIFIED_ENDPOINTS_STRAIGHT_LINE
    assert resolved.geometry_resolution.is_approximation is True
    assert resolved.evidence.breakdown == {"source": 20, "identity": 30, "geometry": 30, "timeline": 15}
    assert resolved.evidence.score == 95
    assert resolved.evidence.level is EvidenceLevel.HIGH
    assert any("Full planned route geometry unavailable" in reason for reason in resolved.evidence.reasons)


def test_one_resolved_end_downgrades_geometry_and_evidence() -> None:
    resolved = _resolve(project("DESC", "Jasper", "Nowhere", voltage=[230]), PAIR_FEATURES)

    assert resolved.geometry_resolution.method is GeometryMethod.VERIFIED_SINGLE_ENDPOINT
    assert resolved.geometry_resolution.is_approximation is True
    assert resolved.evidence.breakdown["geometry"] == 15
    assert any("Nowhere not resolved" in reason for reason in resolved.evidence.reasons)


def test_single_site_project_is_fully_located_by_its_site() -> None:
    resolved = _resolve(project("DESC", "Jasper", voltage=[230]), PAIR_FEATURES)

    assert resolved.geometry["type"] == "Point"
    assert resolved.geometry_resolution.is_approximation is False


def test_unresolved_project_keeps_no_geometry_and_is_marked_unresolved() -> None:
    resolved = _resolve(project("DESC", "Nowhere", "Elsewhere"), PAIR_FEATURES)

    assert resolved.geometry is None
    assert resolved.geometry_resolution.method is GeometryMethod.UNRESOLVED
    assert resolved.evidence.level is EvidenceLevel.UNRESOLVED
    assert resolved.evidence.breakdown["identity"] == 0


def test_untagged_operator_and_voltage_withhold_identity_points() -> None:
    features = [feature("way/1", "Jasper Substation", SC), feature("way/2", "Okatie Substation", (-80.95, 32.33))]

    resolved = _resolve(project("DESC", "Jasper", "Okatie", voltage=[230]), features)

    assert resolved.evidence.breakdown["identity"] == 15  # name 10 + region 5; operator and voltage unconfirmed
    assert any("no operator tag" in reason for reason in resolved.evidence.reasons)


def test_evidence_is_reproducible() -> None:
    target = project("DESC", "Jasper", "Okatie", voltage=[230])

    first = _resolve(target, PAIR_FEATURES)
    second = _resolve(target, PAIR_FEATURES)

    assert first.model_dump() == second.model_dump()
    assert score_evidence(target, first.geometry_resolution, BUNDLE.root.evidence) == first.evidence
