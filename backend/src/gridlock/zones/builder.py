"""Coordination zones (handoff section 14): compress pairwise relationships into regional situations.

Zones partition the relationships, strongest first: a zone starts from the strongest unassigned
relationship and grows through adjacent relationships while it stays within the configured guards.
Every relationship lands in exactly one zone, so compression never hides an opportunity; a project
may appear in more than one zone when it genuinely sits in two situations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations

import networkx as nx
from pyproj import Geod

from gridlock.models.domain import (
    Bounds,
    DateRange,
    EndpointMatchStatus,
    EvidenceLevel,
    Point,
    Project,
    Relationship,
    Zone,
)
from gridlock.ranking import PRIORITY_ORDER, relationship_key
from gridlock.settings.loader import ConfigBundle
from gridlock.settings.models import ZonesConfig

GEOD = Geod(ellps="WGS84")
_EVIDENCE_ORDER = {EvidenceLevel.UNRESOLVED: 0, EvidenceLevel.LOW: 1, EvidenceLevel.MEDIUM: 2, EvidenceLevel.HIGH: 3}
RESOLVED = {EndpointMatchStatus.MATCHED, EndpointMatchStatus.OVERRIDE}


def _coordinates(project: Project) -> list[tuple[float, float]]:
    geometry = project.geometry or {}
    if geometry.get("type") == "Point":
        return [tuple(geometry["coordinates"])]
    if geometry.get("type") == "LineString":
        return [tuple(point) for point in geometry["coordinates"]]
    return []


def geographic_span_km(projects: list[Project]) -> float:
    """Largest geodesic distance between any two vertices of the member geometries."""
    points = sorted({point for project in projects for point in _coordinates(project)})
    return max((GEOD.inv(a[0], a[1], b[0], b[1])[2] / 1000 for a, b in combinations(points, 2)), default=0.0)


def in_service_range(projects: list[Project]) -> DateRange:
    dates = sorted(project.planned_in_service_date for project in projects if project.planned_in_service_date)
    return DateRange(start=dates[0], end=dates[-1]) if dates else DateRange()


def _timeline_span(dates: DateRange) -> int | None:
    return (dates.end - dates.start).days if dates.start and dates.end else None


@dataclass
class _Group:
    relationships: list[Relationship]
    project_ids: set[str]
    warnings: list[str] = field(default_factory=list)


def _within_guards(project_ids: set[str], projects: dict[str, Project], config: ZonesConfig) -> bool:
    members = [projects[project_id] for project_id in project_ids]
    if config.max_projects is not None and len(members) > config.max_projects:
        return False
    if geographic_span_km(members) > config.max_geographic_span_km:
        return False
    span = _timeline_span(in_service_range(members))
    return not (config.timeline_guard == "split" and span is not None and span > config.max_timeline_span_days)


def group_relationships(graph: nx.Graph, projects: dict[str, Project], config: ZonesConfig) -> list[_Group]:
    """Greedy, deterministic partition of the graph's relationships into guarded groups."""
    ranked = sorted((data["relationship"] for _, _, data in graph.edges(data=True)), key=relationship_key)
    unassigned = list(ranked)
    groups: list[_Group] = []
    while unassigned:
        seed = unassigned.pop(0)
        group = _Group([seed], {seed.project_a, seed.project_b})
        grew = True
        while grew:
            grew = False
            for candidate in unassigned:
                ends = {candidate.project_a, candidate.project_b}
                if ends & group.project_ids and _within_guards(group.project_ids | ends, projects, config):
                    group.relationships.append(candidate)
                    group.project_ids |= ends
                    unassigned.remove(candidate)
                    grew = True
                    break
        groups.append(group)
    return groups


def _place_names(project: Project, near: Point, config: ZonesConfig) -> list[str]:
    """The project's resolved endpoints as readable place names, nearest to `near` first."""
    matches = [m for m in project.geometry_resolution.matches if m.status in RESOLVED and m.point] if project.geometry_resolution else []
    matches.sort(key=lambda m: (GEOD.inv(near.lon, near.lat, m.point.lon, m.point.lat)[2], m.endpoint))
    names: list[str] = []
    for match in matches:
        name = re.sub(r"\([^)]*\)", " ", match.feature_name or match.endpoint)
        for word in config.name_strip_words:
            name = re.sub(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", " ", name, flags=re.I)
        name = " ".join(name.split())
        name = name if name != name.upper() else name.title()
        if name not in names:
            names.append(name)
    return names or [project.project_name]


def _name_candidates(top: Relationship, projects: dict[str, Project], config: ZonesConfig) -> list[str]:
    """Zone names from the top relationship's endpoints, most specific (nearest the contact) first."""
    near_a, near_b = top.closest_points
    side_a = _place_names(projects[top.project_a], near_a, config)
    side_b = _place_names(projects[top.project_b], near_b, config)
    pairs = sorted(((i, j) for i in range(len(side_a)) for j in range(len(side_b))), key=lambda ij: (ij[0] + ij[1], ij[0]))
    candidates: list[str] = []
    for i, j in pairs:
        a, b = side_a[i], side_b[j]
        name = a if a.casefold() == b.casefold() else config.name_separator.join((a, b))
        if name not in candidates:
            candidates.append(name)
    return candidates


def _describe(group: _Group, projects: dict[str, Project], bundle: ConfigBundle, decimals: int) -> Zone:
    config = bundle.root.zones
    members = [projects[project_id] for project_id in sorted(group.project_ids)]
    relationships = sorted(group.relationships, key=relationship_key)
    top = relationships[0]
    dates = in_service_range(members)
    span_days = _timeline_span(dates)
    span_km = round(geographic_span_km(members), decimals)
    warnings = list(group.warnings)
    if span_km > config.max_geographic_span_km:
        warnings.append(f"Spans {span_km:g} km, beyond the {config.max_geographic_span_km:g} km guideline, because its projects are long")
    if span_days is not None and span_days > config.max_timeline_span_days:
        warnings.append(
            f"In-service dates span {span_days} days ({dates.start.isoformat()} to {dates.end.isoformat()}), "
            f"beyond the {config.max_timeline_span_days}-day guideline; coordinate in stages"
        )
    approximate = sum(relationship.approximate for relationship in relationships)
    if approximate:
        warnings.append(f"{approximate} of {len(relationships)} relationships use approximate geometry")

    tier_order = list(bundle.root.overlap.playbooks)
    themes: list[str] = []
    for tier in tier_order:
        for relationship in relationships:
            if relationship.spatial_tier == tier:
                themes += [theme for theme in relationship.coordination_playbook if theme not in themes]
    utility_order = [utility.code for utility in bundle.utilities]
    points = [point for member in members for point in _coordinates(member)]
    gaps = [relationship.timeline.gap_days for relationship in relationships if relationship.timeline.gap_days is not None]
    return Zone(
        # Provisional; build_zones renumbers zones in rank order.
        id=f"{config.id_prefix}-{top.id}",
        name=_name_candidates(top, projects, config)[0],
        project_ids=[member.id for member in members],
        relationship_ids=[relationship.id for relationship in relationships],
        top_relationship_id=top.id,
        utilities=sorted({member.utility for member in members}, key=utility_order.index),
        closest_distance_km=min(relationship.distance_km for relationship in relationships),
        best_gap_days=min(gaps) if gaps else None,
        in_service_range=dates,
        geographic_span_km=span_km,
        timeline_span_days=span_days,
        opportunity_priority=min((relationship.opportunity_priority for relationship in relationships), key=PRIORITY_ORDER.__getitem__),
        evidence_level=min((relationship.evidence.level for relationship in relationships), key=_EVIDENCE_ORDER.__getitem__),
        coordination_themes=themes,
        bounds=Bounds(
            west=min(point[0] for point in points),
            south=min(point[1] for point in points),
            east=max(point[0] for point in points),
            north=max(point[1] for point in points),
        ),
        warnings=warnings,
    )


def build_zones(graph: nx.Graph, projects: list[Project], bundle: ConfigBundle) -> list[Zone]:
    """Ranked zones from a graph whose relationships already carry opportunity priorities."""
    by_id = {project.id: project for project in projects}
    ranked_by_id = {data["relationship"].id: data["relationship"] for _, _, data in graph.edges(data=True)}
    if any(relationship.opportunity_priority is None for relationship in ranked_by_id.values()):
        raise ValueError("rank relationships before building zones")
    groups = group_relationships(graph, by_id, bundle.root.zones)
    zones = [_describe(group, by_id, bundle, bundle.root.overlap.distance_decimals) for group in groups]

    def zone_key(zone: Zone) -> tuple:
        top = ranked_by_id[zone.top_relationship_id]
        return (PRIORITY_ORDER[zone.opportunity_priority], relationship_key(top), -len(zone.relationship_ids), zone.top_relationship_id)

    ordered = sorted(zones, key=zone_key)
    prefix = bundle.root.zones.id_prefix
    ranked_zones: list[Zone] = []
    used: set[str] = set()
    for rank, zone in enumerate(ordered, start=1):
        zone_id = f"{prefix}-{rank:02d}"
        # Higher-ranked zones claim names first; a later zone takes its next distinct candidate.
        candidates = _name_candidates(ranked_by_id[zone.top_relationship_id], by_id, bundle.root.zones)
        name = next((candidate for candidate in candidates if candidate not in used), f"{candidates[0]} ({zone_id})")
        used.add(name)
        ranked_zones.append(zone.model_copy(update={"id": zone_id, "rank": rank, "name": name}))
    return ranked_zones
