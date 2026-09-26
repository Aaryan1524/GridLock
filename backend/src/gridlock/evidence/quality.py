"""Deterministic Evidence Quality (handoff section 10): same inputs, same score and reasons."""

from __future__ import annotations

from gridlock.models.domain import (
    EndpointMatch,
    EndpointMatchStatus,
    Evidence,
    EvidenceLevel,
    GeometryMethod,
    GeometryResolution,
    Project,
)
from gridlock.settings.models import EvidenceConfig

CHECK = "✓"
PARTIAL = "△"


def _source(project: Project, config: EvidenceConfig) -> tuple[int, str]:
    source = project.source
    if source.document and source.project_id_raw:
        return config.source["official_with_id"], f"{CHECK} Official {project.utility} filing, project {source.project_id_raw} (page {source.page})"
    if source.document:
        return config.source["official_weak_id"], f"{PARTIAL} Official {project.utility} filing without a project identifier"
    return config.source["none"], f"{PARTIAL} No traceable source"


def _identity(project: Project, matches: list[EndpointMatch], config: EvidenceConfig) -> tuple[int, list[str]]:
    resolved = [match for match in matches if match.status in {EndpointMatchStatus.MATCHED, EndpointMatchStatus.OVERRIDE}]
    if not resolved:
        return 0, []
    osm = [match for match in resolved if match.status is EndpointMatchStatus.MATCHED]
    reasons: list[str] = []
    points = config.identity["name"]
    for match in osm:
        reasons.append(f"{CHECK} {match.endpoint} matched OSM “{match.feature_name}” ({match.feature_id})")
    for match in resolved:
        if match.status is EndpointMatchStatus.OVERRIDE:
            reasons.append(f"{CHECK} {match.endpoint} location human-verified")

    if resolved == osm and all(match.operator_relation == "own" for match in osm):
        points += config.identity["operator"]
        reasons.append(f"{CHECK} Operator matched {project.utility}")
    for match in osm:
        if match.operator_relation == "interconnection":
            reasons.append(f"{PARTIAL} {match.endpoint} is operated by {match.operator} (interconnection)")
        elif match.operator_relation == "untagged":
            reasons.append(f"{PARTIAL} {match.endpoint} has no operator tag in OSM")

    project_kv = set(project.voltage_kv)
    if project_kv and resolved == osm and all(project_kv & set(match.voltage_kv) for match in osm):
        points += config.identity["voltage"]
        reasons.append(f"{CHECK} Voltage matched ({'/'.join(f'{kv:g}' for kv in sorted(project_kv))} kV)")
    else:
        reasons.append(f"{PARTIAL} Voltage not confirmed at every resolved endpoint")

    # Every accepted match passed the service-area veto, so region always holds for resolved endpoints.
    points += config.identity["region"]
    reasons.append(f"{CHECK} Within the {project.utility} service area")
    return points, reasons


def _timeline(project: Project, config: EvidenceConfig) -> tuple[int, str]:
    if project.construction_window:
        return config.timeline["construction_window"], f"{CHECK} Explicit construction window"
    if project.filed_start_date and project.planned_in_service_date:
        return (
            config.timeline["start_and_in_service"],
            f"{CHECK} Filed start {project.filed_start_date.isoformat()} and in-service {project.planned_in_service_date.isoformat()}",
        )
    if project.planned_in_service_date:
        return config.timeline["in_service_date"], f"{CHECK} In-service date {project.planned_in_service_date.isoformat()}"
    return config.timeline["unknown"], f"{PARTIAL} In-service date unknown"


def _geometry_reasons(resolution: GeometryResolution) -> list[str]:
    reasons = []
    for match in resolution.matches:
        if match.status not in {EndpointMatchStatus.MATCHED, EndpointMatchStatus.OVERRIDE}:
            reasons.append(f"{PARTIAL} {match.endpoint} not resolved ({match.status.value.replace('_', ' ')})")
    if resolution.method is GeometryMethod.VERIFIED_ENDPOINTS_STRAIGHT_LINE:
        reasons.append(f"{PARTIAL} Full planned route geometry unavailable; straight line between verified endpoints")
    return reasons


def score_evidence(project: Project, resolution: GeometryResolution, config: EvidenceConfig) -> Evidence:
    source_points, source_reason = _source(project, config)
    identity_points, identity_reasons = _identity(project, resolution.matches, config)
    geometry_points = config.geometry[resolution.method.value]
    timeline_points, timeline_reason = _timeline(project, config)
    breakdown = {"source": source_points, "identity": identity_points, "geometry": geometry_points, "timeline": timeline_points}
    score = sum(breakdown.values())
    if resolution.method is GeometryMethod.UNRESOLVED:
        level = EvidenceLevel.UNRESOLVED
    elif score >= config.levels.high:
        level = EvidenceLevel.HIGH
    elif score >= config.levels.medium:
        level = EvidenceLevel.MEDIUM
    else:
        level = EvidenceLevel.LOW
    reasons = [source_reason, *identity_reasons, timeline_reason, *_geometry_reasons(resolution)]
    return Evidence(level=level, score=score, breakdown=breakdown, reasons=reasons, warnings=list(resolution.warnings))
