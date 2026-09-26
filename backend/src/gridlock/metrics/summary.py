"""Handoff section 28 metrics, computed from the run's own output; nothing is estimated.

Every project falls in exactly one resolution bucket, and every count below is derived from those
buckets, so figures with different denominators always reconcile.
"""

from __future__ import annotations

from collections import Counter

from gridlock.models.domain import (
    EndpointMatchStatus,
    Metrics,
    Project,
    Relationship,
    ResolutionBreakdown,
    SpatialTier,
    Zone,
)

LOCATED_AUTOMATICALLY = "located_automatically"
LOCATED_HUMAN_VERIFIED_ONLY = "located_human_verified_only"
NOT_LOCATED_UNRESOLVED = "not_located_unresolved"
NOT_LOCATED_NO_NAMED_SITE = "not_located_no_named_site"


def resolution_bucket(project: Project) -> str:
    if project.geometry is not None:
        matched = any(match.status is EndpointMatchStatus.MATCHED for match in project.geometry_resolution.matches)
        return LOCATED_AUTOMATICALLY if matched else LOCATED_HUMAN_VERIFIED_ONLY
    return NOT_LOCATED_UNRESOLVED if project.endpoints else NOT_LOCATED_NO_NAMED_SITE


def _breakdown(projects: list[Project]) -> ResolutionBreakdown:
    counts = Counter(resolution_bucket(project) for project in projects)
    return ResolutionBreakdown(
        located_automatically=counts[LOCATED_AUTOMATICALLY],
        located_human_verified_only=counts[LOCATED_HUMAN_VERIFIED_ONLY],
        not_located_unresolved=counts[NOT_LOCATED_UNRESOLVED],
        not_located_no_named_site=counts[NOT_LOCATED_NO_NAMED_SITE],
    )


def compute_metrics(projects: list[Project], relationships: list[Relationship], zones: list[Zone], utility_order: list[str]) -> Metrics:
    per_utility = {code: [project for project in projects if project.utility == code] for code in utility_order}
    breakdown = _breakdown(projects)
    by_utility = {code: _breakdown(items) for code, items in per_utility.items()}
    named = breakdown.total - breakdown.not_located_no_named_site
    matches = [match for project in projects if project.geometry_resolution for match in project.geometry_resolution.matches]
    tiers = Counter(relationship.spatial_tier for relationship in relationships)
    return Metrics(
        projects=breakdown.total,
        projects_by_utility={code: part.total for code, part in by_utility.items()},
        located_projects=breakdown.located,
        not_assessed_by_utility={code: part.not_located for code, part in by_utility.items()},
        resolution=breakdown,
        resolution_by_utility=by_utility,
        projects_with_named_endpoints=named,
        automatic_resolution_rate=round(breakdown.located_automatically / named, 3) if named else 0.0,
        human_verified_endpoints=sum(match.status is EndpointMatchStatus.OVERRIDE for match in matches),
        relationships=len(relationships),
        relationships_by_tier={tier.value: tiers.get(tier, 0) for tier in SpatialTier},
        zones=len(zones),
        attention_compression_ratio=round(len(relationships) / len(zones), 2) if zones else None,
        evidence_distribution=dict(sorted(Counter(project.evidence.level.value for project in projects if project.evidence).items())),
        geometry_distribution=dict(
            sorted(Counter(project.geometry_resolution.method.value for project in projects if project.geometry_resolution).items())
        ),
    )
