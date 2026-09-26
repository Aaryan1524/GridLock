"""Handoff section 21 invariants I-1 to I-10, checked against the real built payload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridlock.api.app import create_app
from gridlock.evidence import score_evidence
from gridlock.models.domain import Payload
from gridlock.overlap.classify import spatial_tier
from gridlock.overlap.geometry import Projector, measure
from gridlock.pipeline import build_payload
from gridlock.ranking import opportunity_priority
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
STAGE_OUTPUTS = [
    REPOSITORY_ROOT / BUNDLE.root.paths.normalized_dir / "projects_resolved.json",
    REPOSITORY_ROOT / BUNDLE.root.paths.output_dir / "relationships.json",
]

pytestmark = pytest.mark.skipif(not all(path.is_file() for path in STAGE_OUTPUTS), reason="stage outputs missing")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Payload, Path]:
    output = tmp_path_factory.mktemp("payload")
    first = build_payload(BUNDLE, REPOSITORY_ROOT, output / "first.json")
    second = build_payload(BUNDLE, REPOSITORY_ROOT, output / "second.json")
    assert first.output_path.read_bytes() == second.output_path.read_bytes()
    return first.payload, first.output_path


@pytest.fixture(scope="module")
def payload(built) -> Payload:
    return built[0]


def test_payload_file_passes_the_contract(built) -> None:
    Payload.model_validate_json(built[1].read_text(encoding="utf-8"))


def test_i1_every_project_points_to_a_public_source_record(payload: Payload) -> None:
    documents = {source.path for utility in BUNDLE.utilities for source in utility.sources}
    for project in payload.projects:
        assert project.source.document in documents
        assert project.source.page >= 1 and project.source.project_id_raw


def test_i2_unknown_values_stay_unknown(payload: Payload) -> None:
    for project in payload.projects:
        if project.source.raw_fields.get("estimated_cost") == "REDACTED":
            assert project.estimated_cost_usd is None
        if project.utility == "DESC":
            assert project.filed_start_date is None and project.construction_window is None
        if project.planned_in_service_date is None and "in_service_date" in project.source.raw_fields:
            assert project.warnings


def test_i3_geometry_comes_only_from_resolved_public_or_reviewed_points(payload: Payload) -> None:
    for project in payload.projects:
        if project.geometry is None:
            continue
        points = [
            [match.point.lon, match.point.lat]
            for match in project.geometry_resolution.matches
            if match.status.value in {"matched", "override"}
        ]
        coordinates = project.geometry["coordinates"]
        assert (coordinates == points) if project.geometry["type"] == "LineString" else ([coordinates] == points)


def test_i4_distances_reproduce_from_the_geometries(payload: Payload) -> None:
    projects = {project.id: project for project in payload.projects}
    projector, overlap = Projector(BUNDLE.root.geometry.projected_crs), BUNDLE.root.overlap
    for relationship in payload.relationships:
        again = measure(
            projector.project(projects[relationship.project_a].geometry),
            projector.project(projects[relationship.project_b].geometry),
            projector,
            overlap.distance_decimals,
            overlap.coordinate_decimals,
        )
        assert again.distance_km == relationship.distance_km
        assert again.closest_points == relationship.closest_points


def test_i5_one_threshold_source(payload: Payload) -> None:
    assert payload.metadata.thresholds_km == BUNDLE.root.thresholds_km.model_dump()
    for relationship in payload.relationships:
        assert relationship.spatial_tier is spatial_tier(relationship.distance_km, relationship.distance_km == 0, BUNDLE.root.thresholds_km)


def test_i6_in_service_gaps_are_never_called_window_overlaps(payload: Payload) -> None:
    projects = {project.id: project for project in payload.projects}
    for relationship in payload.relationships:
        both_windows = projects[relationship.project_a].construction_window and projects[relationship.project_b].construction_window
        if relationship.timeline.type.value in {"WINDOW_OVERLAP", "WINDOW_GAP"}:
            assert both_windows
        if relationship.timeline.overlap_days is not None:
            assert relationship.timeline.type.value == "WINDOW_OVERLAP"


def test_i7_evidence_rescores_identically(payload: Payload) -> None:
    for project in payload.projects:
        assert score_evidence(project, project.geometry_resolution, BUNDLE.root.evidence) == project.evidence


def test_i8_edges_join_different_utilities(payload: Payload) -> None:
    utilities = {project.id: project.utility for project in payload.projects}
    for relationship in payload.relationships:
        assert utilities[relationship.project_a] != utilities[relationship.project_b]


def test_i9_evidence_never_changes_tier_or_priority(payload: Payload) -> None:
    for relationship in payload.relationships:
        assert relationship.spatial_tier is spatial_tier(relationship.distance_km, relationship.distance_km == 0, BUNDLE.root.thresholds_km)
        assert relationship.opportunity_priority is opportunity_priority(relationship, BUNDLE.root.priority)
        if relationship.spatial_tier.value == "CROSSING":
            gap = relationship.timeline.gap_days
            assert relationship.opportunity_priority.value == ("HIGH" if gap is None or gap <= 730 else "MEDIUM")


def test_zone_headline_figures_all_come_from_the_top_relationship(payload: Payload) -> None:
    relationships = {relationship.id: relationship for relationship in payload.relationships}
    for zone in payload.zones:
        top = relationships[zone.top_relationship_id]
        headline = zone.headline
        assert headline.relationship_id == top.id
        assert (headline.project_a, headline.project_b) == (top.project_a, top.project_b)
        assert (headline.distance_km, headline.spatial_tier) == (top.distance_km, top.spatial_tier)
        assert (headline.gap_days, headline.timeline_type, headline.timeline_relevance) == (top.timeline.gap_days, top.timeline.type, top.timeline.relevance)
        assert headline.opportunity_priority is top.opportunity_priority
        assert top.id == min(zone.relationship_ids, key=lambda rid: relationships[rid].rank)


def test_savannah_leads_and_thurmond_stays_a_crossing(payload: Payload) -> None:
    first, second = payload.zones[0], payload.zones[1]
    assert first.headline.relationship_id == "REL-DESC-06367-D-G-GPC-20277"
    assert first.opportunity_priority.value == "HIGH"
    assert second.headline.spatial_tier.value == "CROSSING" and second.headline.distance_km == 0
    assert second.opportunity_priority.value == "MEDIUM"


def test_i10_approximations_are_disclosed(payload: Payload) -> None:
    projects = {project.id: project for project in payload.projects}
    for project in payload.projects:
        if project.geometry_resolution.method.value == "verified_endpoints_straight_line":
            assert project.geometry_resolution.is_approximation
    for relationship in payload.relationships:
        expected = projects[relationship.project_a].geometry_resolution.is_approximation or projects[relationship.project_b].geometry_resolution.is_approximation
        assert relationship.approximate == expected


def test_zones_partition_every_relationship_and_metrics_agree(payload: Payload) -> None:
    assigned = [relationship_id for zone in payload.zones for relationship_id in zone.relationship_ids]
    assert sorted(assigned) == sorted(relationship.id for relationship in payload.relationships)
    assert [zone.rank for zone in payload.zones] == list(range(1, len(payload.zones) + 1))
    assert len({zone.name for zone in payload.zones}) == len(payload.zones)
    metrics = payload.metrics
    assert metrics.zones == len(payload.zones) and metrics.relationships == len(payload.relationships)
    assert metrics.attention_compression_ratio == round(len(payload.relationships) / len(payload.zones), 2)
    assert metrics.located_projects + sum(metrics.not_assessed_by_utility.values()) == metrics.projects


def test_api_serves_the_payload_read_only(built) -> None:
    _, path = built
    bundle = type(BUNDLE)(
        root=BUNDLE.root.model_copy(update={"api": BUNDLE.root.api.model_copy(update={"payload_file": path.name})}),
        utilities=BUNDLE.utilities,
        config_path=BUNDLE.config_path,
        overrides=BUNDLE.overrides,
    )
    root = path.parent.parent / "root"
    (root / BUNDLE.root.paths.output_dir).mkdir(parents=True, exist_ok=True)
    (root / BUNDLE.root.paths.output_dir / path.name).write_bytes(path.read_bytes())
    client = TestClient(create_app(bundle, root))

    assert client.get("/api/health").json() == {"service": BUNDLE.root.api.service_name, "status": "ok", "payloadAvailable": True}
    assert client.get("/api/payload").json() == json.loads(path.read_text(encoding="utf-8"))
    first_zone = json.loads(path.read_text(encoding="utf-8"))["zones"][0]["id"]
    assert client.get(f"/api/zones/{first_zone}").json()["zone"]["id"] == first_zone
    assert client.get("/api/zones/NOPE").status_code == 404
    assert client.post("/api/payload").status_code == 405
