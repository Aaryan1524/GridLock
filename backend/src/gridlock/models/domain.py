"""Pydantic domain contract for GridLock's deterministic pipeline."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _camel_case(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ContractModel(BaseModel):
    """Base model that keeps Python snake_case and API camelCase aligned."""

    # Defaults always serialize, so the emitted (serialization) schema marks those fields required.
    model_config = ConfigDict(
        alias_generator=_camel_case, populate_by_name=True, json_schema_serialization_defaults_required=True
    )


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


class ImpactAssumption(ContractModel):
    """An approved estimating assumption, shown beside every impact figure that uses it."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    low: float | None = None
    high: float
    unit: str = Field(min_length=1)
    # The value as shown to the planner, e.g. "3–20" or "≤5.5%".
    value: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_url: str | None = None
    source_locator: str = Field(min_length=1)
    caveat: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_on: date


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
    impact_assumptions: list[ImpactAssumption] = Field(default_factory=list)


class ResolutionBreakdown(ContractModel):
    """Where every project ended up; the four buckets always add up to the project count."""

    located_automatically: int = Field(ge=0)
    # Located only through human-verified override points, with no automatic OSM match.
    located_human_verified_only: int = Field(ge=0)
    # The title names sites, but none could be linked to public geometry.
    not_located_unresolved: int = Field(ge=0)
    # The title names no site at all ("SMART VALVE INSTALLATION"), so there is nothing to locate.
    not_located_no_named_site: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.located + self.not_located

    @property
    def located(self) -> int:
        return self.located_automatically + self.located_human_verified_only

    @property
    def not_located(self) -> int:
        return self.not_located_unresolved + self.not_located_no_named_site


class Metrics(ContractModel):
    """Handoff section 28 metrics, computed from the real run; nothing here is estimated.

    Denominators are stated per field: "of all projects" or "of projects that name a site".
    """

    projects: int = Field(ge=0)
    projects_by_utility: dict[str, int]
    # Of all projects.
    located_projects: int = Field(ge=0)
    # Of all projects: not located, so not assessed for overlap ("unknown", not "no overlap").
    not_assessed_by_utility: dict[str, int]
    resolution: ResolutionBreakdown
    resolution_by_utility: dict[str, ResolutionBreakdown]
    # Projects whose title names at least one site; the denominator of automatic_resolution_rate.
    projects_with_named_endpoints: int = Field(ge=0)
    # located_automatically / projects_with_named_endpoints; human-verified points are excluded.
    automatic_resolution_rate: float = Field(ge=0, le=1)
    human_verified_endpoints: int = Field(ge=0)
    relationships: int = Field(ge=0)
    relationships_by_tier: dict[str, int]
    zones: int = Field(ge=0)
    attention_compression_ratio: float | None = None
    evidence_distribution: dict[str, int]
    geometry_distribution: dict[str, int]

    @model_validator(mode="after")
    def counts_reconcile(self) -> "Metrics":
        breakdown = self.resolution
        problems = []
        if breakdown.total != self.projects:
            problems.append(f"resolution buckets add up to {breakdown.total}, not {self.projects} projects")
        if breakdown.located != self.located_projects:
            problems.append(f"located buckets add up to {breakdown.located}, not {self.located_projects}")
        if breakdown.not_located != sum(self.not_assessed_by_utility.values()):
            problems.append("not-located buckets disagree with not_assessed_by_utility")
        if self.projects - breakdown.not_located_no_named_site != self.projects_with_named_endpoints:
            problems.append("projects_with_named_endpoints disagrees with the no-named-site bucket")
        expected_rate = round(breakdown.located_automatically / self.projects_with_named_endpoints, 3) if self.projects_with_named_endpoints else 0.0
        if self.automatic_resolution_rate != expected_rate:
            problems.append(f"automatic_resolution_rate should be {expected_rate}")
        for code, part in self.resolution_by_utility.items():
            if part.total != self.projects_by_utility.get(code) or part.not_located != self.not_assessed_by_utility.get(code):
                problems.append(f"{code} breakdown does not reconcile")
        if problems:
            raise ValueError("metrics do not reconcile: " + "; ".join(problems))
        return self


class ImpactStatus(StrEnum):
    ESTIMATED = "ESTIMATED"
    NOT_ESTIMATED = "NOT_ESTIMATED"


class ImpactRange(ContractModel):
    """A low–high range; a missing low means "up to" the high value."""

    low: float | None = Field(default=None, ge=0)
    high: float = Field(ge=0)


class ImpactCluster(ContractModel):
    """Projects linked by coordinable relationships that could share staging or a mobilization."""

    kind: str = Field(min_length=1)
    project_ids: list[str] = Field(min_length=2)
    relationship_ids: list[str] = Field(min_length=1)
    # Projects with a published cost, and the sum of those costs; the rest have none (e.g. redacted).
    costed_project_ids: list[str] = Field(default_factory=list)
    uncosted_project_ids: list[str] = Field(default_factory=list)
    published_cost_usd: float = Field(default=0, ge=0)
    avoidable_share: float = Field(ge=0, le=1)


class ImpactStep(ContractModel):
    """One line of the working: what was multiplied by what, citing the assumptions used."""

    label: str = Field(min_length=1)
    working: str = Field(min_length=1)
    assumption_ids: list[str] = Field(default_factory=list)


class ZoneImpact(ContractModel):
    """S2: what coordinating a zone's timely pairs might avoid. Ranges and ceilings, never engineering figures."""

    zone_id: str = Field(min_length=1)
    status: ImpactStatus
    label: str = Field(min_length=1)
    # Why nothing was estimated (NOT_ESTIMATED only).
    reason: str | None = None
    themes: list[str] = Field(default_factory=list)
    staging_yards: ImpactRange | None = None
    temporary_acres: ImpactRange | None = None
    mobilizations: ImpactRange | None = None
    budget_in_play_usd: ImpactRange | None = None
    expected_saving_usd: ImpactRange | None = None
    clusters: list[ImpactCluster] = Field(default_factory=list)
    steps: list[ImpactStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Payload(ContractModel):
    metadata: Metadata
    metrics: Metrics | None = None
    projects: list[Project] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    impact: list[ZoneImpact] = Field(default_factory=list)
