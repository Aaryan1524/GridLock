"""Pydantic domain contract for GridLock's deterministic pipeline."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


def _camel_case(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ContractModel(BaseModel):
    """Base model that keeps Python snake_case and API camelCase aligned."""

    model_config = ConfigDict(alias_generator=_camel_case, populate_by_name=True)


# Utility codes come from config/utilities/*.yaml, so a new utility needs no model change.
UtilityCode = Annotated[str, Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")]


class ProjectType(StrEnum):
    TRANSMISSION_LINE = "transmission_line"
    SUBSTATION = "substation"
    REACTOR = "reactor"
    OTHER = "other"


class EndpointRole(StrEnum):
    FROM = "from"
    TO = "to"
    VIA = "via"
    SINGLE = "single"
    UNKNOWN = "unknown"


class EndpointStatus(StrEnum):
    """How endpoints were read from a project title; anything but a clean pair/site needs review."""

    EXPLICIT_PAIR = "explicit_pair"
    CHAIN = "chain"
    SINGLE_SITE = "single_site"
    NONE = "none"


class GeometryMethod(StrEnum):
    VERIFIED_FULL_LINE = "verified_full_line"
    VERIFIED_ENDPOINTS_STRAIGHT_LINE = "verified_endpoints_straight_line"
    VERIFIED_ENDPOINT_ROUTE = "verified_endpoint_route"
    VERIFIED_SINGLE_ENDPOINT = "verified_single_endpoint"
    APPROXIMATE_AREA_CENTROID = "approximate_area_centroid"
    HUMAN_VERIFIED_OVERRIDE = "human_verified_override"
    UNRESOLVED = "unresolved"


class EvidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNRESOLVED = "UNRESOLVED"


class SpatialTier(StrEnum):
    CROSSING = "CROSSING"
    SHARED_CORRIDOR = "SHARED_CORRIDOR"
    SITE_LOGISTICS = "SITE_LOGISTICS"
    CREWS_EQUIPMENT = "CREWS_EQUIPMENT"


class TimelineType(StrEnum):
    IN_SERVICE_GAP = "IN_SERVICE_GAP"
    WINDOW_OVERLAP = "WINDOW_OVERLAP"
    WINDOW_GAP = "WINDOW_GAP"
    UNRESOLVED = "UNRESOLVED"


class TimelineRelevance(StrEnum):
    """Window overlap, then one bucket per configured timeline_gap_days cutoff, then beyond them."""

    OVERLAPPING = "OVERLAPPING"
    STRONG = "STRONG"
    MEANINGFUL = "MEANINGFUL"
    POSSIBLE = "POSSIBLE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Endpoint(ContractModel):
    name: str = Field(min_length=1)
    role: EndpointRole = EndpointRole.UNKNOWN
    # Parenthetical title qualifiers such as owner or circuit markers: "(APC)", "(USA)", "(WHITE)".
    qualifiers: list[str] = Field(default_factory=list)


class ConstructionWindow(ContractModel):
    start_date: date
    end_date: date


class SourceRef(ContractModel):
    document: str = Field(min_length=1)
    project_id_raw: str = Field(min_length=1)
    page: int = Field(ge=1)
    raw_text: str | None = None
    # Source strings kept verbatim, e.g. an unparseable date or a REDACTED cost.
    raw_fields: dict[str, str] = Field(default_factory=dict)


class Point(ContractModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class EndpointMatchStatus(StrEnum):
    MATCHED = "matched"
    OVERRIDE = "override"
    NO_CANDIDATE = "no_candidate"
    AMBIGUOUS = "ambiguous"
    VETOED = "vetoed"
    SEPARATION_REJECTED = "separation_rejected"


class EndpointMatch(ContractModel):
    """How one named endpoint was (or was not) linked to public infrastructure."""

    endpoint: str = Field(min_length=1)
    role: EndpointRole
    status: EndpointMatchStatus
    feature_id: str | None = None
    feature_name: str | None = None
    operator: str | None = None
    operator_relation: str | None = None
    voltage_kv: list[float] = Field(default_factory=list)
    name_score: float | None = None
    point: Point | None = None
    notes: list[str] = Field(default_factory=list)


class GeometryResolution(ContractModel):
    method: GeometryMethod
    is_approximation: bool
    feature_ids: list[str] = Field(default_factory=list)
    matches: list[EndpointMatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Evidence(ContractModel):
    level: EvidenceLevel
    score: int = Field(ge=0, le=100)
    # Points per handoff section 10 part: source, identity, geometry, timeline.
    breakdown: dict[str, int] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Project(ContractModel):
    id: str = Field(min_length=1)
    utility: UtilityCode
    project_name: str = Field(min_length=1)
    project_type: ProjectType
    sponsor: str | None = None
    description: str | None = None
    voltage_kv: list[float] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    endpoint_status: EndpointStatus = EndpointStatus.NONE
    status: str | None = None
    planned_in_service_date: date | None = None
    # A project start date as filed by the utility; never treated as a construction window.
    filed_start_date: date | None = None
    construction_window: ConstructionWindow | None = None
    estimated_cost_usd: int | None = Field(default=None, ge=0)
    source: SourceRef
    geometry: dict[str, Any] | None = None
    geometry_resolution: GeometryResolution | None = None
    evidence: Evidence | None = None
    warnings: list[str] = Field(default_factory=list)


class Timeline(ContractModel):
    """How two projects relate in time; an in-service gap is never presented as a window overlap (I-6)."""

    type: TimelineType
    # Days between in-service dates (IN_SERVICE_GAP) or between windows that do not overlap.
    gap_days: int | None = Field(default=None, ge=0)
    # Days two explicit construction windows share; only set for WINDOW_OVERLAP.
    overlap_days: int | None = Field(default=None, ge=0)
    relevance: TimelineRelevance
    # One project's in-service date falls inside the other's filed start-to-need span (not a construction overlap).
    isd_within_filed_span: bool = False


class Relationship(ContractModel):
    id: str = Field(min_length=1)
    project_a: str = Field(min_length=1)
    project_b: str = Field(min_length=1)
    distance_km: float = Field(ge=0)
    closest_points: tuple[Point, Point]
    spatial_tier: SpatialTier
    # Geometry method of project A and project B, so approximations stay visible (I-10).
    geometry_methods: tuple[GeometryMethod, GeometryMethod]
    approximate: bool
    timeline: Timeline
    # Set by ranking (Phase 6); absent on raw overlap-engine output.
    opportunity_priority: Priority | None = None
    rank: int | None = Field(default=None, ge=1)
    coordination_playbook: list[str] = Field(default_factory=list)
    evidence: Evidence


class Bounds(ContractModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)


class DateRange(ContractModel):
    start: date | None = None
    end: date | None = None


class ZoneHeadline(ContractModel):
    """Card figures, all from the zone's single top relationship so they describe one real pair."""

    relationship_id: str = Field(min_length=1)
    project_a: str = Field(min_length=1)
    project_b: str = Field(min_length=1)
    distance_km: float = Field(ge=0)
    spatial_tier: SpatialTier
    timeline_type: TimelineType
    gap_days: int | None = Field(default=None, ge=0)
    timeline_relevance: TimelineRelevance
    opportunity_priority: Priority


class Zone(ContractModel):
    """A regional coordination situation: a guarded group of related cross-utility relationships."""

    id: str = Field(min_length=1)
    rank: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1)
    project_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    # The relationship the zone is ranked by; its closest points name the zone.
    top_relationship_id: str | None = None
    headline: ZoneHeadline | None = None
    utilities: list[UtilityCode] = Field(default_factory=list)
    # Closest approach across all of the zone's relationships (not necessarily the headline pair).
    closest_distance_km: float = Field(ge=0)
    in_service_range: DateRange = Field(default_factory=DateRange)
    geographic_span_km: float | None = Field(default=None, ge=0)
    timeline_span_days: int | None = Field(default=None, ge=0)
    opportunity_priority: Priority
    # The weakest evidence among the zone's relationships.
    evidence_level: EvidenceLevel
    coordination_themes: list[str] = Field(default_factory=list)
    bounds: Bounds
    warnings: list[str] = Field(default_factory=list)


class SourceSnapshot(ContractModel):
    """A public input the payload was built from."""

    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    retrieved_at: str | None = None
    sha256: str | None = None


class Metadata(ContractModel):
    schema_version: str = "1.0"
    fixture: bool = False
    distance_unit: str = "km"
    thresholds_km: dict[str, float]
    timeline_gap_days: dict[str, int] = Field(default_factory=dict)
    zone_guards: dict[str, Any] = Field(default_factory=dict)
    utility_colors: dict[str, str]
    utility_names: dict[str, str] = Field(default_factory=dict)
    # Display labels by vocabulary (tiers, relevance, playbook, ...); the UI never hardcodes them.
    labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    sources: list[SourceSnapshot] = Field(default_factory=list)


class Metrics(ContractModel):
    """Handoff section 28 metrics, computed from the real run; nothing here is estimated."""

    projects: int = Field(ge=0)
    projects_by_utility: dict[str, int]
    located_projects: int = Field(ge=0)
    # Projects without geometry were not assessed for overlap; that is not the same as "no overlap".
    not_assessed_by_utility: dict[str, int]
    projects_with_named_endpoints: int = Field(ge=0)
    automatic_resolution_rate: float = Field(ge=0, le=1)
    human_verified_endpoints: int = Field(ge=0)
    relationships: int = Field(ge=0)
    relationships_by_tier: dict[str, int]
    zones: int = Field(ge=0)
    attention_compression_ratio: float | None = None
    evidence_distribution: dict[str, int]
    geometry_distribution: dict[str, int]


class Payload(ContractModel):
    metadata: Metadata
    metrics: Metrics | None = None
    projects: list[Project] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
