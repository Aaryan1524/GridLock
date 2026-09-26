"""Opportunity Priority (handoff section 15): spatial tier first, then timeline; evidence stays separate (I-9)."""

from __future__ import annotations

from gridlock.models.domain import Priority, Relationship, SpatialTier, TimelineRelevance
from gridlock.settings.models import PriorityConfig

# Enum declaration order is the ranking order: CROSSING before SHARED_CORRIDOR, OVERLAPPING before STRONG.
TIER_ORDER = {tier: rank for rank, tier in enumerate(SpatialTier)}
RELEVANCE_ORDER = {relevance: rank for rank, relevance in enumerate(TimelineRelevance)}
PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def opportunity_priority(relationship: Relationship, config: PriorityConfig) -> Priority:
    for rule in config.rules:
        if relationship.spatial_tier in rule.tiers and (not rule.relevance or relationship.timeline.relevance in rule.relevance):
            return rule.priority
    return config.default


def relationship_key(relationship: Relationship) -> tuple:
    """Strongest first: tier, then timeline relevance, then smaller date gap, then closer, then ID."""
    gap = relationship.timeline.gap_days
    return (
        TIER_ORDER[relationship.spatial_tier],
        RELEVANCE_ORDER[relationship.timeline.relevance],
        gap is None,
        gap if gap is not None else 0,
        relationship.distance_km,
        relationship.id,
    )


def rank_relationships(relationships: list[Relationship], config: PriorityConfig) -> list[Relationship]:
    ranked = sorted(relationships, key=relationship_key)
    return [
        relationship.model_copy(update={"opportunity_priority": opportunity_priority(relationship, config), "rank": rank})
        for rank, relationship in enumerate(ranked, start=1)
    ]
