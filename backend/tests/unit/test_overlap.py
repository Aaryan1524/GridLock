from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from gridlock.models.domain import (
    ConstructionWindow,
    EndpointMatch,
    EndpointMatchStatus,
    EndpointRole,
    Evidence,
    EvidenceLevel,
    GeometryMethod,
    GeometryResolution,
    Point,
    Project,
    ProjectType,
    SourceRef,
    SpatialTier,
    TimelineRelevance,
    TimelineType,
)
from gridlock.overlap import find_relationships
from gridlock.overlap.classify import spatial_tier, timeline_relation
from gridlock.overlap.geometry import Projector, geodesic_km, measure
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
PROJECTOR = Projector(BUNDLE.root.geometry.projected_crs)
CONFIG = BUNDLE.root.overlap
GAPS = BUNDLE.root.timeline_gap_days


def point(lon: float, lat: float) -> dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}


def line(*coordinates: tuple[float, float]) -> dict[str, Any]:
    return {"type": "LineString", "coordinates": [list(c) for c in coordinates]}


def _measure(a: dict[str, Any], b: dict[str, Any]):
    return measure(PROJECTOR.project(a), PROJECTOR.project(b), PROJECTOR, CONFIG.distance_decimals, CONFIG.coordinate_decimals)


# --- Geometry --------------------------------------------------------------------------------


def test_point_to_point_is_the_geodesic_distance() -> None:
    result = _measure(point(-81.0, 32.0), point(-81.0, 32.1))

    expected = geodesic_km(Point(lat=32.0, lon=-81.0), Point(lat=32.1, lon=-81.0))
    assert result.distance_km == pytest.approx(expected, abs=1e-3)
    assert result.touching is False


def test_point_to_line_uses_the_closest_point_on_the_line() -> None:
    result = _measure(point(-80.95, 32.1), line((-81.0, 32.0), (-81.0, 32.2)))

    _, on_line = result.closest_points
    assert on_line.lat == pytest.approx(32.1, abs=2e-3)
    assert result.distance_km == pytest.approx(geodesic_km(Point(lat=32.1, lon=-80.95), Point(lat=32.1, lon=-81.0)), abs=0.05)


def test_line_to_line_measures_the_gap_not_the_centres() -> None:
    near_ends = _measure(line((-81.0, 32.0), (-81.0, 32.2)), line((-80.99, 32.2), (-80.5, 32.2)))

    assert near_ends.distance_km < 1.0  # centre-to-centre would be about 24 km


def test_crossing_lines_are_zero_distance_with_one_contact_point() -> None:
    result = _measure(line((-81.0, 32.0), (-80.9, 32.1)), line((-81.0, 32.1), (-80.9, 32.0)))

    assert result.distance_km == 0.0
    assert result.touching is True
    assert result.closest_points[0] == result.closest_points[1]


def test_shared_endpoint_touches() -> None:
    result = _measure(point(-82.196, 33.66), line((-82.169, 33.544), (-82.196, 33.66)))

    assert result.touching is True and result.distance_km == 0.0


def test_endpoint_fallback_point_against_a_straight_line() -> None:
    single_endpoint = point(-81.1241558, 32.3606993)
    straight_line = line((-81.175, 32.352), (-81.21, 32.249))

    assert _measure(single_endpoint, straight_line).distance_km == pytest.approx(4.84, abs=0.1)


def test_distance_is_symmetric_and_reproducible() -> None:
    a, b = line((-81.12, 32.36), (-81.03, 32.33)), line((-81.18, 32.35), (-81.21, 32.25))

    first, again, swapped = _measure(a, b), _measure(a, b), _measure(b, a)

    assert first == again
    assert swapped.distance_km == first.distance_km
    assert swapped.closest_points == (first.closest_points[1], first.closest_points[0])


# --- Spatial tiers (handoff section 24 boundaries) --------------------------------------------


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (0.0, SpatialTier.CROSSING),
        (1.599, SpatialTier.SHARED_CORRIDOR),
        (1.600, SpatialTier.SITE_LOGISTICS),
        (7.999, SpatialTier.SITE_LOGISTICS),
        (8.000, SpatialTier.CREWS_EQUIPMENT),
        (39.999, SpatialTier.CREWS_EQUIPMENT),
        (40.000, None),
        (55.0, None),
    ],
)
def test_tier_boundaries(distance: float, expected: SpatialTier | None) -> None:
    assert spatial_tier(distance, touching=False, thresholds=BUNDLE.root.thresholds_km) is expected


def test_touching_is_a_crossing() -> None:
    assert spatial_tier(0.0, touching=True, thresholds=BUNDLE.root.thresholds_km) is SpatialTier.CROSSING


# --- Timeline ----------------------------------------------------------------------------------


def project(
    identifier: str = "DESC-A",
    utility: str = "DESC",
    geometry: dict[str, Any] | None = None,
    in_service: date | None = date(2026, 6, 1),
    filed_start: date | None = None,
    window: tuple[date, date] | None = None,
    level: EvidenceLevel = EvidenceLevel.HIGH,
    score: int = 90,
    method: GeometryMethod = GeometryMethod.VERIFIED_SINGLE_ENDPOINT,
    approximate: bool = False,
    feature_id: str | None = None,
) -> Project:
    matches = []
    if feature_id:
        matches.append(
            EndpointMatch(endpoint="Site", role=EndpointRole.SINGLE, status=EndpointMatchStatus.MATCHED, feature_id=feature_id, feature_name="Site Substation")
        )
    return Project(
        id=identifier,
        utility=utility,
        project_name=identifier,
        project_type=ProjectType.TRANSMISSION_LINE,
        planned_in_service_date=in_service,
        filed_start_date=filed_start,
        construction_window=ConstructionWindow(start_date=window[0], end_date=window[1]) if window else None,
        source=SourceRef(document="filing.pdf", project_id_raw=identifier, page=1),
        geometry=geometry,
        geometry_resolution=GeometryResolution(method=method, is_approximation=approximate, matches=matches),
        evidence=Evidence(level=level, score=score),
    )


BASE = date(2026, 1, 1)


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, TimelineRelevance.STRONG),
        (90, TimelineRelevance.STRONG),
        (91, TimelineRelevance.MEANINGFUL),
        (180, TimelineRelevance.MEANINGFUL),
        (181, TimelineRelevance.POSSIBLE),
        (365, TimelineRelevance.POSSIBLE),
        (366, TimelineRelevance.WEAK),
    ],
)
def test_in_service_gap_buckets(days: int, expected: TimelineRelevance) -> None:
    timeline = timeline_relation(project(in_service=BASE), project(in_service=BASE + timedelta(days=days)), GAPS)

    assert timeline.type is TimelineType.IN_SERVICE_GAP
    assert timeline.gap_days == days
    assert timeline.relevance is expected


def test_missing_date_is_unresolved_not_guessed() -> None:
    timeline = timeline_relation(project(in_service=None), project(in_service=BASE), GAPS)

    assert timeline.type is TimelineType.UNRESOLVED
    assert timeline.gap_days is None
    assert timeline.relevance is TimelineRelevance.UNKNOWN


def test_true_window_overlap() -> None:
    a = project(window=(date(2026, 1, 1), date(2026, 12, 31)))
    b = project(window=(date(2026, 10, 1), date(2027, 6, 1)))

    timeline = timeline_relation(a, b, GAPS)

    assert timeline.type is TimelineType.WINDOW_OVERLAP
    assert timeline.overlap_days == 91
    assert timeline.relevance is TimelineRelevance.OVERLAPPING


def test_separate_windows_report_a_window_gap() -> None:
    timeline = timeline_relation(project(window=(date(2026, 1, 1), date(2026, 3, 1))), project(window=(date(2026, 5, 1), date(2026, 9, 1))), GAPS)

    assert timeline.type is TimelineType.WINDOW_GAP
    assert timeline.gap_days == 61


def test_mixed_case_flags_isd_inside_a_filed_span_without_calling_it_an_overlap() -> None:
    desc = project(in_service=date(2025, 12, 31))
    gpc = project("GPC-1", "GPC", in_service=date(2026, 6, 1), filed_start=date(2024, 1, 1))
    later = project("GPC-2", "GPC", in_service=date(2027, 6, 1), filed_start=date(2026, 1, 1))

    inside, outside = timeline_relation(desc, gpc, GAPS), timeline_relation(desc, later, GAPS)

    assert inside.type is TimelineType.IN_SERVICE_GAP and inside.isd_within_filed_span is True
    assert inside.gap_days == 152 and inside.overlap_days is None
    assert outside.isd_within_filed_span is False


def test_one_window_and_one_date_falls_back_to_the_in_service_gap() -> None:
    timeline = timeline_relation(project(window=(date(2026, 1, 1), date(2026, 6, 1))), project("GPC-1", "GPC"), GAPS)

    assert timeline.type is TimelineType.IN_SERVICE_GAP


# --- Engine ------------------------------------------------------------------------------------


def test_only_located_cross_utility_pairs_within_the_maximum_become_relationships() -> None:
    projects = [
        project("GPC-1", "GPC", point(-81.0, 32.05)),
        project("DESC-1", "DESC", point(-81.0, 32.0)),
        project("DESC-2", "DESC", point(-81.0, 32.01)),  # same utility as DESC-1: never paired with it
        project("DESC-3", "DESC", None),  # unlocated: no spatial claims
        project("GPC-FAR", "GPC", point(-83.0, 34.0)),  # far beyond 40 km of every DESC project
    ]

    relationships, stats = find_relationships(projects, BUNDLE)

    assert [r.id for r in relationships] == ["REL-DESC-1-GPC-1", "REL-DESC-2-GPC-1"]
    assert all(r.project_a.startswith("DESC") and r.project_b.startswith("GPC") for r in relationships)
    assert stats["cross_utility_pairs"] == 4
    assert stats["measured_pairs"] == 2


def test_relationship_carries_playbook_methods_and_the_weaker_evidence() -> None:
    desc = project("DESC-1", "DESC", point(-81.0, 32.0), level=EvidenceLevel.HIGH, score=95)
    gpc = project(
        "GPC-1", "GPC", line((-81.0, 32.02), (-81.1, 32.1)), level=EvidenceLevel.LOW, score=40,
        method=GeometryMethod.VERIFIED_ENDPOINTS_STRAIGHT_LINE, approximate=True,
    )

    [relationship], _ = find_relationships([desc, gpc], BUNDLE)

    assert relationship.spatial_tier is SpatialTier.SITE_LOGISTICS
    assert relationship.coordination_playbook == list(CONFIG.playbooks[SpatialTier.SITE_LOGISTICS])
    assert relationship.geometry_methods == (GeometryMethod.VERIFIED_SINGLE_ENDPOINT, GeometryMethod.VERIFIED_ENDPOINTS_STRAIGHT_LINE)
    assert relationship.approximate is True
    assert (relationship.evidence.level, relationship.evidence.score) == (EvidenceLevel.LOW, 40)
    assert relationship.opportunity_priority is None


def test_low_evidence_never_hides_a_crossing() -> None:
    desc = project("DESC-1", "DESC", point(-82.196, 33.66), level=EvidenceLevel.LOW, score=20, feature_id="way/9")
    gpc = project("GPC-1", "GPC", line((-82.169, 33.544), (-82.196, 33.66)), level=EvidenceLevel.LOW, score=20, feature_id="way/9")

    [relationship], _ = find_relationships([desc, gpc], BUNDLE)

    assert relationship.spatial_tier is SpatialTier.CROSSING
    assert any("Both projects end at Site Substation (way/9)" in reason for reason in relationship.evidence.reasons)
