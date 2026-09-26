"""Opportunity Priority (handoff section 15): spatial tier first, then timeline; evidence stays separate (I-9)."""

from __future__ import annotations

from gridlock.models.domain import Priority, Relationship, SpatialTier, TimelineRelevance
from gridlock.settings.models import PriorityConfig

# Enum declaration order is the ranking order: CROSSING before SHARED_CORRIDOR, OVERLAPPING before STRONG.
TIER_ORDER = {tier: rank for rank, tier in enumerate(SpatialTier)}
RELEVANCE_ORDER = {relevance: rank for rank, relevance in enumerate(TimelineRelevance)}
PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def opportunity_priority(relationship: Relationship, config: PriorityConfig) -> Priority:
    gap = relationship.timeline.gap_days
    for rule in config.rules:
        if relationship.spatial_tier not in rule.tiers:
            continue
        if rule.relevance and relationship.timeline.relevance not in rule.relevance:
            continue
        if rule.max_gap_days is not None and gap is not None and gap > rule.max_gap_days:
            continue
        return rule.priority
    return config.default


def relationship_key(relationship: Relationship) -> tuple:
    """Spatial strength: tier, then timeline relevance, then smaller date gap, then closer, then ID.

    Zone grouping walks relationships in this order, so zone membership is geography-first.
    """
    gap = relationship.timeline.gap_days
    return (
        TIER_ORDER[relationship.spatial_tier],
        RELEVANCE_ORDER[relationship.timeline.relevance],
        gap is None,
        gap if gap is not None else 0,
        relationship.distance_km,
        relationship.id,
    )


def priority_key(relationship: Relationship) -> tuple:
    """Presentation order: Opportunity Priority first, then spatial strength."""
    if relationship.opportunity_priority is None:
        raise ValueError(f"{relationship.id} has no opportunity priority yet")
    return (PRIORITY_ORDER[relationship.opportunity_priority], *relationship_key(relationship))


def rank_relationships(relationships: list[Relationship], config: PriorityConfig) -> list[Relationship]:
    prioritized = [
        relationship.model_copy(update={"opportunity_priority": opportunity_priority(relationship, config)})
        for relationship in relationships
    ]
    return [relationship.model_copy(update={"rank": rank}) for rank, relationship in enumerate(sorted(prioritized, key=priority_key), start=1)]
