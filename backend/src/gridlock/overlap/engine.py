"""Cross-utility overlap engine: every pair of located projects from different utilities (I-8)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from shapely.geometry.base import BaseGeometry

from gridlock.models.domain import (
    EndpointMatchStatus,
    Evidence,
    EvidenceLevel,
    Project,
    Relationship,
)
from gridlock.settings.loader import ConfigBundle

from .classify import playbook, spatial_tier, timeline_relation
from .geometry import Measurement, Projector, bounding_gap_m, measure

CHECK = "✓"
PARTIAL = "△"
_LEVEL_RANK = {EvidenceLevel.LOW: 0, EvidenceLevel.MEDIUM: 1, EvidenceLevel.HIGH: 2}
RESOLVED = {EndpointMatchStatus.MATCHED, EndpointMatchStatus.OVERRIDE}


def _shared_features(a: Project, b: Project) -> list[str]:
    def features(project: Project) -> dict[str, str]:
        matches = project.geometry_resolution.matches if project.geometry_resolution else []
        return {m.feature_id: m.feature_name or m.endpoint for m in matches if m.status in RESOLVED and m.feature_id}

    shared = features(a).keys() & features(b).keys()
    return sorted(f"{features(a)[feature_id]} ({feature_id})" for feature_id in shared)


def relationship_evidence(a: Project, b: Project, measurement: Measurement, touching_label: str | None) -> Evidence:
    """A relationship is only as trustworthy as its weaker project; evidence never changes the tier (I-9)."""
    weaker = min((a, b), key=lambda project: (_LEVEL_RANK[project.evidence.level], project.evidence.score, project.id))
    reasons = [f"{CHECK} Closest approach {measurement.distance_km:g} km between public geometries"]
    if touching_label:
        reasons.append(f"{CHECK} {touching_label}")
    reasons += [f"{project.id}: {project.evidence.level.value} evidence ({project.evidence.score})" for project in (a, b)]
    warnings = [
        f"{PARTIAL} {project.id} geometry is approximate ({project.geometry_resolution.method.value.replace('_', ' ')})"
        for project in (a, b)
        if project.geometry_resolution.is_approximation
    ]
    if measurement.touching and warnings and not touching_label:
        warnings.append(f"{PARTIAL} Contact found between approximate geometries; the real routes may not cross")
    return Evidence(
        level=weaker.evidence.level,
        score=weaker.evidence.score,
        breakdown={"project_a": a.evidence.score, "project_b": b.evidence.score},
        reasons=reasons,
        warnings=warnings,
    )


@dataclass(frozen=True)
class OverlapReport:
    output_path: Path
    located_projects: dict[str, int]
    cross_utility_pairs: int
    measured_pairs: int
    beyond_maximum: int
    relationships_by_tier: dict[str, int]
    timeline_types: dict[str, int]
    timeline_relevance: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "located_projects": self.located_projects,
            "cross_utility_pairs": self.cross_utility_pairs,
            "measured_after_prefilter": self.measured_pairs,
            "discarded_beyond_maximum": self.beyond_maximum,
            "relationships": sum(self.relationships_by_tier.values()),
            "relationships_by_tier": self.relationships_by_tier,
            "timeline_types": self.timeline_types,
            "timeline_relevance": self.timeline_relevance,
            "output_path": str(self.output_path),
        }


def find_relationships(projects: list[Project], bundle: ConfigBundle) -> tuple[list[Relationship], dict[str, int]]:
    """Measure and classify every cross-utility pair; unlocated projects make no spatial claims."""
    config = bundle.root.overlap
    thresholds = bundle.root.thresholds_km
    projector = Projector(bundle.root.geometry.projected_crs)
    order = {utility.code: rank for rank, utility in enumerate(bundle.utilities)}
    located = sorted((p for p in projects if p.geometry is not None), key=lambda p: (order[p.utility], p.id))
    shapes: dict[str, BaseGeometry] = {project.id: projector.project(project.geometry) for project in located}
    prefilter_m = thresholds.maximum * 1000 * (1 + config.prefilter_slack_ratio)

    stats = Counter()
    relationships: list[Relationship] = []
    for a, b in combinations(located, 2):
        if a.utility == b.utility:
            continue
        stats["cross_utility_pairs"] += 1
        if bounding_gap_m(shapes[a.id], shapes[b.id]) > prefilter_m:
            continue
        stats["measured_pairs"] += 1
        measurement = measure(shapes[a.id], shapes[b.id], projector, config.distance_decimals, config.coordinate_decimals)
        tier = spatial_tier(measurement.distance_km, measurement.touching, thresholds)
        if tier is None:
            stats["beyond_maximum"] += 1
            continue
        shared = _shared_features(a, b)
        touching_label = f"Both projects end at {', '.join(shared)}" if measurement.touching and shared else None
        relationships.append(
            Relationship(
                id=f"REL-{a.id}-{b.id}",
                project_a=a.id,
                project_b=b.id,
                distance_km=measurement.distance_km,
                closest_points=measurement.closest_points,
                spatial_tier=tier,
                geometry_methods=(a.geometry_resolution.method, b.geometry_resolution.method),
                approximate=a.geometry_resolution.is_approximation or b.geometry_resolution.is_approximation,
                timeline=timeline_relation(a, b, bundle.root.timeline_gap_days),
                coordination_playbook=playbook(tier, config),
                evidence=relationship_evidence(a, b, measurement, touching_label),
            )
        )
    return sorted(relationships, key=lambda relationship: relationship.id), dict(stats)


def run_overlap(bundle: ConfigBundle, repository_root: Path, output_path: Path | None = None) -> OverlapReport:
    paths = bundle.root.paths
    resolved_path = repository_root / paths.normalized_dir / "projects_resolved.json"
    projects = [Project.model_validate(item) for item in json.loads(resolved_path.read_text(encoding="utf-8"))]
    relationships, stats = find_relationships(projects, bundle)

    output_path = output_path or repository_root / paths.output_dir / "relationships.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([item.model_dump(mode="json", by_alias=True) for item in relationships], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tier_order = {tier: rank for rank, tier in enumerate(bundle.root.overlap.playbooks)}
    return OverlapReport(
        output_path=output_path,
        located_projects=dict(sorted(Counter(p.utility for p in projects if p.geometry is not None).items())),
        cross_utility_pairs=stats.get("cross_utility_pairs", 0),
        measured_pairs=stats.get("measured_pairs", 0),
        beyond_maximum=stats.get("beyond_maximum", 0),
        relationships_by_tier={
            tier.value: count
            for tier, count in sorted(Counter(r.spatial_tier for r in relationships).items(), key=lambda item: tier_order[item[0]])
        },
        timeline_types=dict(sorted(Counter(r.timeline.type.value for r in relationships).items())),
        timeline_relevance=dict(sorted(Counter(r.timeline.relevance.value for r in relationships).items())),
    )
