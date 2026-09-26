from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from gridlock.graph import GraphError, build_graph, components
from gridlock.models.domain import (
    EndpointMatch,
    EndpointMatchStatus,
    EndpointRole,
    Evidence,
    EvidenceLevel,
    GeometryMethod,
    GeometryResolution,
    Point,
    Priority,
    Project,
    ProjectType,
    SourceRef,
    SpatialTier,
    TimelineRelevance,
)
from gridlock.overlap import find_relationships
from gridlock.pipeline import assemble_payload
from gridlock.ranking import opportunity_priority, rank_relationships
from gridlock.settings.loader import load_settings
from gridlock.zones import build_zones


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
LAT = 32.3
KM_PER_DEGREE_LON = 94.3  # at this latitude; only used to lay out test points roughly


def site(identifier: str, utility: str, km_east: float, name: str | None = None, level: EvidenceLevel = EvidenceLevel.MEDIUM, score: int = 65) -> Project:
    lon = -81.5 + km_east / KM_PER_DEGREE_LON
    match = EndpointMatch(
        endpoint=name or identifier,
        role=EndpointRole.SINGLE,
        status=EndpointMatchStatus.MATCHED,
        feature_id=f"way/{identifier}",
        feature_name=f"{name or identifier} Substation",
        point=Point(lat=LAT, lon=round(lon, 7)),
    )
    return Project(
        id=identifier,
        utility=utility,
        project_name=identifier,
        project_type=ProjectType.SUBSTATION,
        planned_in_service_date=date(2026, 6, 1),
        source=SourceRef(document="filing.pdf", project_id_raw=identifier, page=1),
        geometry={"type": "Point", "coordinates": [round(lon, 7), LAT]},
        geometry_resolution=GeometryResolution(method=GeometryMethod.VERIFIED_SINGLE_ENDPOINT, is_approximation=False, matches=[match]),
        evidence=Evidence(level=level, score=score),
    )


def bundle_with(**zone_overrides: Any):
    zones = BUNDLE.root.zones.model_copy(update=zone_overrides)
    return type(BUNDLE)(root=BUNDLE.root.model_copy(update={"zones": zones}), utilities=BUNDLE.utilities, config_path=BUNDLE.config_path, overrides=BUNDLE.overrides)


def zones_for(projects: list[Project], bundle=BUNDLE):
    relationships, _ = find_relationships(projects, bundle)
    ranked = rank_relationships(relationships, bundle.root.priority)
    return ranked, build_zones(build_graph(projects, ranked), projects, bundle)


# --- Graph -------------------------------------------------------------------------------------


def test_isolated_project_is_a_node_without_a_zone() -> None:
    ranked, zones = zones_for([site("DESC-A", "DESC", 0), site("GPC-FAR", "GPC", 300)])

    assert ranked == [] and zones == []
    assert set(build_graph([site("DESC-A", "DESC", 0)], []).nodes) == {"DESC-A"}


def test_one_edge_is_one_zone() -> None:
    _, zones = zones_for([site("DESC-A", "DESC", 0, "Alpha"), site("GPC-B", "GPC", 5, "Bravo")])

    assert len(zones) == 1
    assert zones[0].project_ids == ["DESC-A", "GPC-B"]
    assert zones[0].name == "Alpha – Bravo"


def test_multi_edge_component_is_one_zone() -> None:
    projects = [site("DESC-A", "DESC", 0), site("GPC-B", "GPC", 5), site("DESC-C", "DESC", 10), site("GPC-D", "GPC", 12)]
    ranked, zones = zones_for(projects)

    assert len(components(build_graph(projects, ranked))) == 1
    assert len(zones) == 1
    assert sorted(zones[0].relationship_ids) == sorted(relationship.id for relationship in ranked)


def test_chain_beyond_the_span_guard_is_split_without_losing_relationships() -> None:
    # A - B - C - D, 25 km apart: the chain spans 75 km against a 60 km guard.
    projects = [site("DESC-A", "DESC", 0), site("GPC-B", "GPC", 25), site("DESC-C", "DESC", 50), site("GPC-D", "GPC", 75)]
    ranked, zones = zones_for(projects)

    assert len(components(build_graph(projects, ranked))) == 1
    assert len(zones) >= 2
    assigned = [relationship_id for zone in zones for relationship_id in zone.relationship_ids]
    assert sorted(assigned) == sorted(relationship.id for relationship in ranked)  # each exactly once
    assert all(zone.geographic_span_km <= BUNDLE.root.zones.max_geographic_span_km for zone in zones)


def test_same_utility_edge_is_rejected() -> None:
    a, b = site("DESC-A", "DESC", 0), site("DESC-B", "DESC", 1)
    [relationship], _ = find_relationships([a, site("GPC-X", "GPC", 0.5)], BUNDLE)
    bad = relationship.model_copy(update={"project_b": "DESC-B"})

    with pytest.raises(GraphError, match="I-8"):
        build_graph([a, b], [bad])


def test_timeline_guard_splits_only_in_split_mode() -> None:
    early = site("DESC-A", "DESC", 0).model_copy(update={"planned_in_service_date": date(2024, 1, 1)})
    late = site("GPC-B", "GPC", 5).model_copy(update={"planned_in_service_date": date(2033, 1, 1)})
    later = site("GPC-C", "GPC", 8).model_copy(update={"planned_in_service_date": date(2024, 2, 1)})

    _, warned = zones_for([early, late, later], bundle_with(timeline_guard="warn"))
    _, split = zones_for([early, late, later], bundle_with(timeline_guard="split"))

    assert len(warned) == 1 and any("730-day guideline" in warning for warning in warned[0].warnings)
    assert len(split) == 2


def test_zone_names_are_unique() -> None:
    projects = [site("DESC-A", "DESC", 0, "Same"), site("GPC-B", "GPC", 5, "Other"), site("DESC-C", "DESC", 70, "Same"), site("GPC-D", "GPC", 75, "Other")]
    _, zones = zones_for(projects)

    assert len({zone.name for zone in zones}) == len(zones)


# --- Priority and ranking ----------------------------------------------------------------------


def _relationship(tier: SpatialTier, relevance: TimelineRelevance):
    [relationship], _ = find_relationships([site("DESC-A", "DESC", 0), site("GPC-B", "GPC", 5)], BUNDLE)
    return relationship.model_copy(update={"spatial_tier": tier, "timeline": relationship.timeline.model_copy(update={"relevance": relevance})})


@pytest.mark.parametrize(
    ("tier", "relevance", "expected"),
    [
        (SpatialTier.CROSSING, TimelineRelevance.WEAK, Priority.HIGH),
        (SpatialTier.SHARED_CORRIDOR, TimelineRelevance.UNKNOWN, Priority.HIGH),
        (SpatialTier.SITE_LOGISTICS, TimelineRelevance.MEANINGFUL, Priority.HIGH),
        (SpatialTier.SITE_LOGISTICS, TimelineRelevance.WEAK, Priority.MEDIUM),
        (SpatialTier.CREWS_EQUIPMENT, TimelineRelevance.STRONG, Priority.MEDIUM),
        (SpatialTier.CREWS_EQUIPMENT, TimelineRelevance.WEAK, Priority.LOW),
    ],
)
def test_priority_rules(tier: SpatialTier, relevance: TimelineRelevance, expected: Priority) -> None:
    assert opportunity_priority(_relationship(tier, relevance), BUNDLE.root.priority) is expected


def test_low_evidence_crossing_still_ranks_first_with_a_warning() -> None:
    """I-9: evidence affects trust presentation, never the physical classification or priority."""
    crossing_a = site("DESC-A", "DESC", 0, level=EvidenceLevel.LOW, score=20)
    crossing_b = site("GPC-B", "GPC", 0, level=EvidenceLevel.LOW, score=20).model_copy(
        update={"geometry_resolution": site("GPC-B", "GPC", 0).geometry_resolution.model_copy(update={"is_approximation": True})}
    )
    strong_c = site("DESC-C", "DESC", 100, level=EvidenceLevel.HIGH, score=95)
    strong_d = site("GPC-D", "GPC", 103, level=EvidenceLevel.HIGH, score=95)

    payload = assemble_payload(BUNDLE, REPOSITORY_ROOT, [crossing_a, crossing_b, strong_c, strong_d], find_relationships([crossing_a, crossing_b, strong_c, strong_d], BUNDLE)[0])

    top = payload.relationships[0]
    assert top.spatial_tier is SpatialTier.CROSSING and top.opportunity_priority is Priority.HIGH
    assert top.evidence.level is EvidenceLevel.LOW and top.evidence.warnings
    assert payload.zones[0].top_relationship_id == top.id
