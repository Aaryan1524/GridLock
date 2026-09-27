"""S2 coordination impact: what coordinating a zone's timely pairs might avoid.

Pure and deterministic. It reads the engine's existing output (priority, tier, timeline relevance,
published costs) and the approved assumptions in `impact:`; it never changes a relationship, zone
or priority. Every figure is a range or a ceiling, and every step of the working is returned so
the planner can see how it was produced.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridlock.models.domain import (
    ImpactAssumption,
    ImpactChainStep,
    ImpactCluster,
    ImpactIndicator,
    ImpactRange,
    ImpactStatus,
    ImpactStep,
    Project,
    Relationship,
    Zone,
    ZoneImpact,
)
from gridlock.settings.models import ImpactAssumptionConfig, ImpactConfig

STAGING = "staging"
MOBILIZATION = "mobilization"


def assumption_records(config: ImpactConfig) -> list[ImpactAssumption]:
    """The approved assumptions, as they are shown to the planner (shares as percentages)."""
    roles = config.assumptions
    shares = {roles.mobilization_share.id, roles.avoidable_share.id, roles.cross_check.id}

    def value(item: ImpactAssumptionConfig) -> str:
        scale, suffix = (100, "%") if item.id in shares else (1, "")
        high = _number(round(item.high * scale, 4))
        if item.low is None:
            return f"≤{high}{suffix}"
        return f"{_number(round(item.low * scale, 4))}–{high}{suffix}"

    return [
        ImpactAssumption.model_validate({**item.model_dump(), "value": value(item)})
        for item in (roles.yard_acres, roles.mobilization_share, roles.avoidable_share, roles.cross_check)
    ]


def cluster_pairs(relationships: Iterable[Relationship]) -> list[tuple[list[str], list[str]]]:
    """Connected groups of projects (sorted project ids, sorted relationship ids), in a stable order."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    edges = sorted(relationships, key=lambda item: item.id)
    for relationship in edges:
        for node in (relationship.project_a, relationship.project_b):
            parent.setdefault(node, node)
        root_a, root_b = find(relationship.project_a), find(relationship.project_b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)
    groups: dict[str, tuple[set[str], list[str]]] = {}
    for relationship in edges:
        members, ids = groups.setdefault(find(relationship.project_a), (set(), []))
        members.update((relationship.project_a, relationship.project_b))
        ids.append(relationship.id)
    return sorted(((sorted(members), sorted(ids)) for members, ids in groups.values()), key=lambda group: group[0])


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _number(value: float) -> str:
    return f"{value:g}"


def _span(low: float | None, high: float, unit: str = "") -> str:
    text = f"up to {_number(high)}" if low is None else (_number(high) if low == high else f"{_number(low)}–{_number(high)}")
    return f"{text}{unit}"


def _count(value: float, singular: str, plural: str | None = None) -> str:
    return singular if value == 1 else (plural or f"{singular}s")


def _or_list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} or {items[-1]}"


def _label(labels: dict[str, dict[str, str]], vocabulary: str, code: str) -> str:
    return labels.get(vocabulary, {}).get(code, code)


def _cluster(kind: str, members: list[str], relationship_ids: list[str], projects: dict[str, Project], cap: float) -> ImpactCluster:
    costed = [pid for pid in members if projects[pid].estimated_cost_usd is not None]
    return ImpactCluster(
        kind=kind,
        project_ids=members,
        relationship_ids=relationship_ids,
        costed_project_ids=costed,
        uncosted_project_ids=[pid for pid in members if pid not in costed],
        published_cost_usd=float(sum(projects[pid].estimated_cost_usd or 0 for pid in costed)),
        # k projects sharing one mobilization avoid (k-1)/k of it, never more than the approved cap.
        avoidable_share=min((len(members) - 1) / len(members), cap),
    )


def _not_estimated(zone: Zone, config: ImpactConfig, reason: str, counts: tuple[int, int, int], themes: list[str] | None = None) -> ZoneImpact:
    total, candidates, timely = counts
    return ZoneImpact(
        zone_id=zone.id,
        status=ImpactStatus.NOT_ESTIMATED,
        label=config.label,
        reason=reason,
        themes=themes or [],
        relationship_count=total,
        candidate_count=candidates,
        timely_count=timely,
    )


def _cost_withheld(project: Project) -> bool:
    """True when the filing shows the cost field but withholds it (e.g. "REDACTED")."""
    return any("cost" in key.lower() and value.strip().upper() == "REDACTED" for key, value in project.source.raw_fields.items())


def estimate_zone_impact(
    zone: Zone,
    relationships: dict[str, Relationship],
    projects: dict[str, Project],
    config: ImpactConfig,
    labels: dict[str, dict[str, str]],
    utility_names: dict[str, str] | None = None,
) -> ZoneImpact:
    """The impact estimate for one zone, or the reason there is none."""
    names = utility_names or {}
    roles = config.assumptions
    zone_relationships = [relationships[rid] for rid in zone.relationship_ids]
    priority_names = " or ".join(_label(labels, "priority", priority.value).upper() for priority in config.candidate_priorities)
    candidates = [item for item in zone_relationships if item.opportunity_priority in config.candidate_priorities]
    if not candidates:
        return _not_estimated(
            zone, config, f"No relationship in this zone ranks {priority_names}, so no coordination impact is estimated.", (len(zone_relationships), 0, 0)
        )

    timely = [item for item in candidates if item.timeline.relevance in config.timely_relevance]
    if not timely:
        gaps = sorted({item.timeline.gap_days for item in candidates if item.timeline.gap_days is not None})
        dates = f"in-service dates {', '.join(f'{gap:,}' for gap in gaps)} days apart" if gaps else "unknown dates"
        themes = list(dict.fromkeys(theme for item in candidates for theme in item.coordination_playbook))
        plural = "s" if len(candidates) != 1 else ""
        return _not_estimated(
            zone,
            config,
            f"Its {len(candidates)} {priority_names} relationship{plural} have {dates}, too far apart "
            "to share staging or a mobilization; coordination here is about sequencing.",
            (len(zone_relationships), len(candidates), 0),
            themes,
        )

    cap = roles.avoidable_share.high
    staging = [item for item in timely if item.spatial_tier in config.staging_tiers]
    staging_clusters = [_cluster(STAGING, members, ids, projects, cap) for members, ids in cluster_pairs(staging)]
    mobilization_clusters = [_cluster(MOBILIZATION, members, ids, projects, cap) for members, ids in cluster_pairs(timely)]

    relevance_names = _or_list([_label(labels, "timeline_relevance", value.value).lower() for value in config.timely_relevance])
    steps = [
        ImpactStep(
            label="Coordinable pairs",
            working=f"{len(candidates)} of {len(zone_relationships)} relationships rank {priority_names}; "
            f"{len(timely)} of those have {relevance_names} timeline relevance.",
        )
    ]
    notes: list[str] = []

    yards = acres = None
    if staging_clusters:
        yards = ImpactRange(low=1, high=sum(len(cluster.project_ids) - 1 for cluster in staging_clusters))
        acres = ImpactRange(low=yards.low * _low(roles.yard_acres), high=yards.high * roles.yard_acres.high)
        steps.append(ImpactStep(
            label="Shared staging yards",
            working=f"{len(staging_clusters)} {_count(len(staging_clusters), 'cluster')} at {_tier_names(config, labels)}: "
            + "; ".join(" × ".join(cluster.project_ids) for cluster in staging_clusters)
            + f" → {_span(yards.low, yards.high)} {_count(yards.high, 'yard')} potentially shared.",
        ))
        steps.append(ImpactStep(
            label="Temporary footprint",
            working=f"{_span(yards.low, yards.high)} {_count(yards.high, 'yard')} × {_span(roles.yard_acres.low, roles.yard_acres.high)} "
            f"acres per yard = {_span(acres.low, acres.high)} acres.",
            assumption_ids=[roles.yard_acres.id],
        ))
    else:
        notes.append(f"No timely pair is at {_tier_names(config, labels)}, so no shared staging yard is estimated.")

    mobilizations = ImpactRange(low=1, high=sum(len(cluster.project_ids) - 1 for cluster in mobilization_clusters))
    steps.append(ImpactStep(
        label="Duplicate mobilizations",
        working=f"{len(mobilization_clusters)} {_count(len(mobilization_clusters), 'cluster')} with timely dates: "
        + "; ".join(" × ".join(cluster.project_ids) for cluster in mobilization_clusters)
        + f" → {_span(mobilizations.low, mobilizations.high)} {_count(mobilizations.high, 'mobilization')} potentially avoided.",
    ))

    share = roles.mobilization_share.high
    costed = sorted({pid for cluster in mobilization_clusters for pid in cluster.costed_project_ids})
    uncosted = sorted({pid for cluster in mobilization_clusters for pid in cluster.uncosted_project_ids})
    budget = saving = None
    if costed:
        cost = float(sum(projects[pid].estimated_cost_usd or 0 for pid in costed))
        budget = ImpactRange(high=round(cost * share))
        saving = ImpactRange(high=round(sum(cluster.published_cost_usd * share * cluster.avoidable_share for cluster in mobilization_clusters)))
        steps.append(ImpactStep(
            label="Budget in play (a ceiling, not a saving)",
            working=f"{_money(cost)} published cost ({', '.join(costed)}) × ≤{share:.1%} = up to {_money(budget.high)}.",
            assumption_ids=[roles.mobilization_share.id],
        ))
        per_cluster = "; ".join(
            f"{' × '.join(cluster.project_ids)}: {_money(cluster.published_cost_usd)} × ≤{share:.1%} × ≤{cluster.avoidable_share:.0%}"
            for cluster in mobilization_clusters
            if cluster.costed_project_ids
        )
        steps.append(ImpactStep(
            label="Expected saving",
            working=f"{per_cluster} = up to {_money(saving.high)} (≤{saving.high / cost:.2%} of published cost).",
            assumption_ids=[roles.mobilization_share.id, roles.avoidable_share.id],
        ))
        cross = roles.cross_check
        steps.append(ImpactStep(
            label="Cross-check",
            working=f"{cross.label}: {_span(cross.low * 100 if cross.low is not None else None, cross.high * 100)}% "
            "(one bundling pilot, cited only for comparison). This estimate stays below even its low end, because separate "
            "utilities coordinating share logistics only, not one contract.",
            assumption_ids=[cross.id],
        ))
    else:
        notes.append("No project in these clusters has a published cost, so no dollar figure is estimated.")
    if uncosted:
        notes.append(f"{', '.join(uncosted)}: no published cost (for example, redacted in the filing); not estimated.")
    approximate = [item for item in timely if item.approximate]
    if approximate:
        notes.append(
            f"{len(approximate)} of {len(timely)} counted {_count(len(timely), 'pair')} use approximate geometry (one endpoint or a "
            "straight line between endpoints), so their distances are to that geometry, not a surveyed route."
        )

    # Presentation: the same figures as a chain, and the notes as compact flags with their full text.
    priority_words = "/".join(_label(labels, "priority", priority.value) for priority in config.candidate_priorities)
    chain = [
        ImpactChainStep(label="Coordinable relationships", value=f"{len(candidates)} {priority_words}",
                        detail=f"of {len(zone_relationships)} in this zone"),
        ImpactChainStep(label="Timely relationships", value=str(len(timely)), detail=f"{relevance_names} timeline relevance"),
    ]
    if yards and acres:
        chain += [
            ImpactChainStep(label="Shared staging opportunities", value=_span(yards.low, yards.high), detail=f"at {_tier_names(config, labels)}"),
            ImpactChainStep(label="Reference footprint", value=f"{_span(acres.low, acres.high)} acres",
                            detail=f"{_span(roles.yard_acres.low, roles.yard_acres.high)} acres per yard", assumption_ids=[roles.yard_acres.id]),
        ]
    chain.append(ImpactChainStep(label="Duplicate mobilizations", value=_span(mobilizations.low, mobilizations.high)))
    if budget and saving:
        cost_utilities = sorted({projects[pid].utility for pid in costed})
        chain += [
            ImpactChainStep(label="Published project cost", value=_money(cost),
                            detail=f"{', '.join(names.get(code, code) for code in cost_utilities)} · {len(costed)} {_count(len(costed), 'project')}"),
            ImpactChainStep(label="Budget in play", value=f"≤ {_money(budget.high)}", detail=f"≤{share:.1%} of published cost",
                            assumption_ids=[roles.mobilization_share.id]),
            ImpactChainStep(label="Illustrative savings ceiling", value=f"≤ {_money(saving.high)}",
                            detail=f"≤{cap:.0%} of a shared mobilization", assumption_ids=[roles.mobilization_share.id, roles.avoidable_share.id]),
        ]
    indicators = []
    if approximate:
        indicators.append(ImpactIndicator(
            summary=f"{len(approximate)} {_count(len(approximate), 'relationship')} {'uses' if len(approximate) == 1 else 'use'} approximate geometry",
            detail=notes[-1],
        ))
    if uncosted:
        by_utility: dict[str, list[str]] = {}
        for pid in uncosted:
            by_utility.setdefault(projects[pid].utility, []).append(pid)
        for code, ids in sorted(by_utility.items()):
            withheld = all(_cost_withheld(projects[pid]) for pid in ids)
            indicators.append(ImpactIndicator(
                summary=f"{names.get(code, code)} project costs {'are redacted' if withheld else 'are not published'}",
                detail=f"{', '.join(ids)}: {'the filing shows the cost as REDACTED' if withheld else 'no cost is published'}, so "
                "these projects add nothing to the dollar figures.",
            ))

    return ZoneImpact(
        zone_id=zone.id,
        status=ImpactStatus.ESTIMATED,
        label=config.label,
        themes=list(dict.fromkeys(theme for item in timely for theme in item.coordination_playbook)),
        staging_yards=yards,
        temporary_acres=acres,
        mobilizations=mobilizations,
        budget_in_play_usd=budget,
        expected_saving_usd=saving,
        clusters=staging_clusters + mobilization_clusters,
        steps=steps,
        notes=notes,
        relationship_count=len(zone_relationships),
        candidate_count=len(candidates),
        timely_count=len(timely),
        chain=chain,
        indicators=indicators,
    )


def _low(assumption: ImpactAssumptionConfig) -> float:
    return assumption.low if assumption.low is not None else 0.0


def _tier_names(config: ImpactConfig, labels: dict[str, dict[str, str]]) -> str:
    """The widest staging tier, e.g. "site logistics distance or closer" (tiers are listed nearest first)."""
    widest = config.staging_tiers[-1]
    return f"{_label(labels, 'spatial_tiers', widest.value).lower()} distance" + (" or closer" if len(config.staging_tiers) > 1 else "")


def estimate_impact(
    zones: list[Zone],
    relationships: list[Relationship],
    projects: list[Project],
    config: ImpactConfig,
    labels: dict[str, dict[str, str]],
    utility_names: dict[str, str] | None = None,
) -> list[ZoneImpact]:
    """One estimate (or reason) per zone, in zone order."""
    by_relationship = {item.id: item for item in relationships}
    by_project = {item.id: item for item in projects}
    return [estimate_zone_impact(zone, by_relationship, by_project, config, labels, utility_names) for zone in zones]
