"""Deterministic spatial tier, timeline relation and coordination playbook for one project pair."""

from __future__ import annotations

from datetime import date

from gridlock.models.domain import Project, SpatialTier, Timeline, TimelineRelevance, TimelineType
from gridlock.settings.models import OverlapConfig, ThresholdsConfig, TimelineGapConfig


def spatial_tier(distance_km: float, touching: bool, thresholds: ThresholdsConfig) -> SpatialTier | None:
    """Handoff section 11 with strict upper bounds: < near, < local, < maximum; maximum and beyond is discarded."""
    if touching or distance_km == 0:
        return SpatialTier.CROSSING
    if distance_km < thresholds.near:
        return SpatialTier.SHARED_CORRIDOR
    if distance_km < thresholds.local:
        return SpatialTier.SITE_LOGISTICS
    if distance_km < thresholds.maximum:
        return SpatialTier.CREWS_EQUIPMENT
    return None


def gap_relevance(gap_days: int, gaps: TimelineGapConfig) -> TimelineRelevance:
    """Inclusive cutoffs: a gap of exactly `near` days is still STRONG."""
    if gap_days <= gaps.near:
        return TimelineRelevance.STRONG
    if gap_days <= gaps.moderate:
        return TimelineRelevance.MEANINGFUL
    if gap_days <= gaps.distant:
        return TimelineRelevance.POSSIBLE
    return TimelineRelevance.WEAK


def _in_filed_span(in_service: date | None, other: Project) -> bool:
    start, end = other.filed_start_date, other.planned_in_service_date
    return bool(in_service and start and end and start <= in_service <= end)


def timeline_relation(a: Project, b: Project, gaps: TimelineGapConfig) -> Timeline:
    """Compare explicit windows when both have them, else in-service dates; never invent a window (I-6)."""
    if a.construction_window and b.construction_window:
        start = max(a.construction_window.start_date, b.construction_window.start_date)
        end = min(a.construction_window.end_date, b.construction_window.end_date)
        shared = (end - start).days
        if shared >= 0:
            return Timeline(type=TimelineType.WINDOW_OVERLAP, overlap_days=shared, relevance=TimelineRelevance.OVERLAPPING)
        return Timeline(type=TimelineType.WINDOW_GAP, gap_days=-shared, relevance=gap_relevance(-shared, gaps))
    if a.planned_in_service_date and b.planned_in_service_date:
        gap = abs((a.planned_in_service_date - b.planned_in_service_date).days)
        return Timeline(
            type=TimelineType.IN_SERVICE_GAP,
            gap_days=gap,
            relevance=gap_relevance(gap, gaps),
            isd_within_filed_span=_in_filed_span(a.planned_in_service_date, b) or _in_filed_span(b.planned_in_service_date, a),
        )
    return Timeline(type=TimelineType.UNRESOLVED, relevance=TimelineRelevance.UNKNOWN)


def playbook(tier: SpatialTier, config: OverlapConfig) -> list[str]:
    return list(config.playbooks[tier])
