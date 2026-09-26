"""Handoff section 28 metrics, computed from the run's own output; nothing is estimated."""

from __future__ import annotations

from collections import Counter

from gridlock.models.domain import EndpointMatchStatus, Metrics, Project, Relationship, SpatialTier, Zone


def compute_metrics(projects: list[Project], relationships: list[Relationship], zones: list[Zone], utility_order: list[str]) -> Metrics:
    def by_utility(items: list[Project]) -> dict[str, int]:
        counts = Counter(project.utility for project in items)
        return {code: counts.get(code, 0) for code in utility_order}

    named = [project for project in projects if project.endpoints]
    automatic = [
        project
        for project in named
        if project.geometry is not None
        and any(match.status is EndpointMatchStatus.MATCHED for match in project.geometry_resolution.matches)
    ]
    matches = [match for project in projects if project.geometry_resolution for match in project.geometry_resolution.matches]
    tiers = Counter(relationship.spatial_tier for relationship in relationships)
    return Metrics(
        projects=len(projects),
        projects_by_utility=by_utility(projects),
        located_projects=sum(project.geometry is not None for project in projects),
        not_assessed_by_utility=by_utility([project for project in projects if project.geometry is None]),
        projects_with_named_endpoints=len(named),
        automatic_resolution_rate=round(len(automatic) / len(named), 3) if named else 0.0,
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
