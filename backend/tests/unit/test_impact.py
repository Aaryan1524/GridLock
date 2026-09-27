"""S2 coordination impact estimator: which pairs count, the arithmetic, and what it refuses to estimate."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from gridlock.impact import cluster_pairs, estimate_impact, estimate_zone_impact
from gridlock.models.domain import (
    Bounds,
    Evidence,
    EvidenceLevel,
    GeometryMethod,
    ImpactStatus,
    Point,
    Priority,
    Project,
    ProjectType,
    Relationship,
    SourceRef,
    SpatialTier,
    Timeline,
    TimelineRelevance,
    TimelineType,
    Zone,
)
from gridlock.settings.loader import load_settings
from gridlock.settings.models import ImpactConfig

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
CONFIG = BUNDLE.root.impact
LABELS = {**BUNDLE.root.labels, "playbook": dict(BUNDLE.root.overlap.playbook_labels)}
SHARE = CONFIG.assumptions.mobilization_share.high
CAP = CONFIG.assumptions.avoidable_share.high
ACRES = CONFIG.assumptions.yard_acres


def project(identifier: str, cost: float | None) -> Project:
    return Project(
        id=identifier,
        utility=identifier.split("-")[0],
        project_name=identifier,
        project_type=ProjectType.TRANSMISSION_LINE,
        estimated_cost_usd=cost,
        planned_in_service_date=date(2026, 6, 1),
        source=SourceRef(document="filing.pdf", project_id_raw=identifier, page=1),
    )


def pair(
    a: str,
    b: str,
    tier: SpatialTier,
    relevance: TimelineRelevance,
    priority: Priority,
    gap: int | None = 100,
    playbook: tuple[str, ...] = ("staging_yards",),
) -> Relationship:
    return Relationship(
        id=f"REL-{a}-{b}",
        project_a=a,
        project_b=b,
        distance_km=1.0,
        closest_points=(Point(lat=32.0, lon=-81.0), Point(lat=32.0, lon=-81.01)),
        spatial_tier=tier,
        geometry_methods=(GeometryMethod.VERIFIED_SINGLE_ENDPOINT, GeometryMethod.VERIFIED_SINGLE_ENDPOINT),
        approximate=False,
        timeline=Timeline(type=TimelineType.IN_SERVICE_GAP, gap_days=gap, relevance=relevance),
        opportunity_priority=priority,
        coordination_playbook=list(playbook),
        evidence=Evidence(level=EvidenceLevel.MEDIUM, score=70),
    )


def zone(relationships: list[Relationship]) -> Zone:
    members = sorted({pid for item in relationships for pid in (item.project_a, item.project_b)})
    return Zone(
        id="ZONE-01",
        name="Test",
        project_ids=members,
        relationship_ids=[item.id for item in relationships],
        closest_distance_km=0,
        opportunity_priority=Priority.HIGH,
        evidence_level=EvidenceLevel.MEDIUM,
        bounds=Bounds(west=-82, south=31, east=-80, north=33),
    )


def estimate(relationships: list[Relationship], projects: list[Project]):
    return estimate_zone_impact(zone(relationships), {item.id: item for item in relationships}, {item.id: item for item in projects}, CONFIG, LABELS)


SITE, CREWS, CROSSING = SpatialTier.SITE_LOGISTICS, SpatialTier.CREWS_EQUIPMENT, SpatialTier.CROSSING
MEANINGFUL, STRONG, WEAK = TimelineRelevance.MEANINGFUL, TimelineRelevance.STRONG, TimelineRelevance.WEAK
HIGH, MEDIUM, LOW = Priority.HIGH, Priority.MEDIUM, Priority.LOW


def test_cluster_pairs_joins_connected_projects_in_a_stable_order():
    groups = cluster_pairs([pair("B", "C", SITE, STRONG, HIGH), pair("A", "B", SITE, STRONG, HIGH), pair("X", "Y", SITE, STRONG, HIGH)])
    assert groups == [(["A", "B", "C"], ["REL-A-B", "REL-B-C"]), (["X", "Y"], ["REL-X-Y"])]


def test_one_timely_site_logistics_pair_is_one_yard_and_one_mobilization():
    result = estimate([pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH)], [project("DESC-1", 20_000_000), project("GPC-1", None)])
    assert result.status is ImpactStatus.ESTIMATED
    assert (result.staging_yards.low, result.staging_yards.high) == (1, 1)
    assert (result.temporary_acres.low, result.temporary_acres.high) == (ACRES.low, ACRES.high)
    assert (result.mobilizations.low, result.mobilizations.high) == (1, 1)
    assert result.budget_in_play_usd.low is None and result.budget_in_play_usd.high == round(20_000_000 * SHARE)
    assert result.expected_saving_usd.high == round(20_000_000 * SHARE * CAP)


def test_unpublished_costs_are_never_estimated():
    result = estimate([pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH)], [project("DESC-1", 10_000_000), project("GPC-1", None)])
    cluster = result.clusters[-1]
    assert cluster.costed_project_ids == ["DESC-1"] and cluster.uncosted_project_ids == ["GPC-1"]
    assert cluster.published_cost_usd == 10_000_000
    assert any("GPC-1" in note and "no published cost" in note for note in result.notes)


def test_no_published_cost_anywhere_gives_counts_but_no_dollars():
    result = estimate([pair("GPC-1", "GPC-2", SITE, STRONG, HIGH)], [project("GPC-1", None), project("GPC-2", None)])
    assert result.status is ImpactStatus.ESTIMATED
    assert result.mobilizations.high == 1
    assert result.budget_in_play_usd is None and result.expected_saving_usd is None


def test_low_priority_pairs_never_count_even_when_timely():
    relationships = [pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH), pair("DESC-2", "GPC-2", CREWS, MEANINGFUL, LOW)]
    result = estimate(relationships, [project("DESC-1", 1_000_000), project("GPC-1", None), project("DESC-2", 9_000_000), project("GPC-2", None)])
    counted = {pid for cluster in result.clusters for pid in cluster.project_ids}
    assert "DESC-2" not in counted and result.budget_in_play_usd.high == round(1_000_000 * SHARE)


def test_crews_distance_counts_for_mobilization_but_not_staging():
    result = estimate([pair("DESC-1", "GPC-1", CREWS, STRONG, MEDIUM)], [project("DESC-1", 1_000_000), project("GPC-1", None)])
    assert result.staging_yards is None and result.temporary_acres is None
    assert result.mobilizations.high == 1
    assert any("staging" in note for note in result.notes)


def test_bigger_clusters_widen_the_range_but_the_saving_share_stays_capped():
    relationships = [pair("DESC-1", "GPC-1", SITE, STRONG, HIGH), pair("GPC-1", "GPC-2", SITE, STRONG, HIGH)]
    result = estimate(relationships, [project("DESC-1", 1_000_000), project("GPC-1", None), project("GPC-2", None)])
    assert (result.staging_yards.low, result.staging_yards.high) == (1, 2)
    assert (result.mobilizations.low, result.mobilizations.high) == (1, 2)
    assert all(cluster.avoidable_share == CAP for cluster in result.clusters)  # (3-1)/3 is capped at the approved 1/2


def test_high_priority_pairs_years_apart_are_sequencing_not_sharing():
    result = estimate([pair("DESC-1", "GPC-1", CROSSING, WEAK, MEDIUM, gap=3074, playbook=("crossing_structures",))], [project("DESC-1", 1), project("GPC-1", None)])
    assert result.status is ImpactStatus.NOT_ESTIMATED
    assert "3,074 days apart" in result.reason and "sequencing" in result.reason
    assert result.themes == ["crossing_structures"]
    assert result.budget_in_play_usd is None and result.clusters == []


def test_a_zone_without_high_or_medium_pairs_gives_a_reason_not_a_zero():
    result = estimate([pair("DESC-1", "GPC-1", CREWS, STRONG, LOW)], [project("DESC-1", 1), project("GPC-1", None)])
    assert result.status is ImpactStatus.NOT_ESTIMATED
    assert result.reason and result.mobilizations is None and result.expected_saving_usd is None


def test_every_dollar_step_cites_its_assumptions():
    result = estimate([pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH)], [project("DESC-1", 5_000_000), project("GPC-1", None)])
    cited = {step.label: step.assumption_ids for step in result.steps}
    roles = CONFIG.assumptions
    assert cited["Temporary footprint"] == [roles.yard_acres.id]
    assert roles.mobilization_share.id in cited["Budget in play (a ceiling, not a saving)"]
    assert set(cited["Expected saving"]) == {roles.mobilization_share.id, roles.avoidable_share.id}
    assert cited["Cross-check"] == [roles.cross_check.id]


def test_counted_pairs_on_approximate_geometry_are_disclosed():
    approximate = pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH).model_copy(update={"approximate": True})
    result = estimate([approximate], [project("DESC-1", 1_000_000), project("GPC-1", None)])
    assert any("1 of 1 counted pair use approximate geometry" in note for note in result.notes)
    exact = estimate([pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH)], [project("DESC-1", 1_000_000), project("GPC-1", None)])
    assert not any("approximate geometry" in note for note in exact.notes)


def test_estimates_do_not_modify_their_inputs():
    relationships = [pair("DESC-1", "GPC-1", SITE, MEANINGFUL, HIGH)]
    projects = [project("DESC-1", 5_000_000), project("GPC-1", None)]
    before = [item.model_dump() for item in relationships + projects]
    estimate_impact([zone(relationships)], relationships, projects, CONFIG, LABELS)
    assert [item.model_dump() for item in relationships + projects] == before


def _impact_config(**assumption_changes) -> dict:
    raw = yaml.safe_load((REPOSITORY_ROOT / "config" / "gridlock.yaml").read_text(encoding="utf-8"))["impact"]
    for role, changes in assumption_changes.items():
        raw["assumptions"][role].update(changes)
    return raw


def test_config_rejects_a_public_source_without_a_link():
    with pytest.raises(ValidationError, match="source_url"):
        ImpactConfig.model_validate(_impact_config(yard_acres={"source_url": None}))


def test_config_rejects_an_unapproved_assumption():
    raw = _impact_config()
    del raw["assumptions"]["mobilization_share"]["approved_by"]
    with pytest.raises(ValidationError, match="approved_by"):
        ImpactConfig.model_validate(raw)


def test_config_rejects_a_share_above_one_and_an_inverted_range():
    with pytest.raises(ValidationError, match="at most 1"):
        ImpactConfig.model_validate(_impact_config(avoidable_share={"high": 1.5}))
    with pytest.raises(ValidationError, match="above high"):
        ImpactConfig.model_validate(_impact_config(yard_acres={"low": 30, "high": 20}))
