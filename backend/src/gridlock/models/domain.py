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


class GeometryResolution(ContractModel):
    method: GeometryMethod
    is_approximation: bool
    feature_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Evidence(ContractModel):
    level: EvidenceLevel
    score: int = Field(ge=0, le=100)
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
    type: TimelineType
    gap_days: int | None = Field(default=None, ge=0)
    relevance: TimelineRelevance
    isd_within_filed_span: bool = False


class Relationship(ContractModel):
    id: str = Field(min_length=1)
    project_a: str = Field(min_length=1)
    project_b: str = Field(min_length=1)
    distance_km: float = Field(ge=0)
    closest_points: tuple[Point, Point]
    spatial_tier: SpatialTier
    timeline: Timeline
    opportunity_priority: Priority
    coordination_playbook: list[str] = Field(default_factory=list)
    evidence: Evidence


class Bounds(ContractModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)


class Zone(ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    utilities: list[UtilityCode] = Field(default_factory=list)
    closest_distance_km: float = Field(ge=0)
    opportunity_priority: Priority
    evidence_level: EvidenceLevel
    coordination_themes: list[str] = Field(default_factory=list)
    bounds: Bounds


class Metadata(ContractModel):
    schema_version: str = "1.0"
    fixture: bool = False
    distance_unit: str = "km"
    thresholds_km: dict[str, float]
    utility_colors: dict[str, str]


class Payload(ContractModel):
    metadata: Metadata
    projects: list[Project] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
