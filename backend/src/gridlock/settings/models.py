"""Pydantic models for the configuration surface used by every pipeline stage."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from gridlock.models.domain import GeometryMethod, ProjectType, SpatialTier


class PathsConfig(BaseModel):
    raw_dir: str
    cache_dir: str
    normalized_dir: str
    output_dir: str
    review_dir: str


class ThresholdsConfig(BaseModel):
    near: float = Field(gt=0)
    local: float = Field(gt=0)
    maximum: float = Field(gt=0)

    @model_validator(mode="after")
    def tiers_are_ordered(self) -> "ThresholdsConfig":
        if not self.near < self.local < self.maximum:
            raise ValueError("thresholds_km must satisfy near < local < maximum")
        return self


class TimelineGapConfig(BaseModel):
    near: int = Field(ge=0)
    moderate: int = Field(ge=0)
    distant: int = Field(ge=0)

    @model_validator(mode="after")
    def buckets_are_ordered(self) -> "TimelineGapConfig":
        if not self.near < self.moderate < self.distant:
            raise ValueError("timeline_gap_days must satisfy near < moderate < distant")
        return self


class DisplayConfig(BaseModel):
    distance_unit: str
    timezone: str

    @model_validator(mode="after")
    def has_supported_distance_unit(self) -> "DisplayConfig":
        if self.distance_unit not in {"km", "mi"}:
            raise ValueError("display.distance_unit must be km or mi")
        return self


class GeometryConfig(BaseModel):
    projected_crs: str
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def bbox_is_west_south_east_north(self) -> "GeometryConfig":
        west, south, east, north = self.bbox
        if west >= east or south >= north:
            raise ValueError("geometry.bbox must be ordered west, south, east, north")
        return self


class OsmConfig(BaseModel):
    overpass_url: str
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    max_response_bytes: int = Field(gt=0)
    # Wait before retry n is backoff_seconds * 2**n; Overpass asks clients not to retry tightly.
    backoff_seconds: float = Field(gt=0)
    user_agent: str = Field(min_length=1)
    feature_types: tuple[str, ...] = Field(min_length=1)
    query_version: str = Field(min_length=1)


class AiConfig(BaseModel):
    enabled: bool = False


def _compiles(patterns: tuple[str, ...]) -> tuple[str, ...]:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"invalid regular expression {pattern!r}: {error}") from error
    return patterns


class EndpointRulesConfig(BaseModel):
    """Rules for reading named sites out of a project title."""

    ignored_prefix_patterns: tuple[str, ...] = ()
    review_prefix_patterns: tuple[str, ...] = ()
    separator_pattern: str
    section_end_patterns: tuple[str, ...] = Field(min_length=1)
    multi_site_markers: tuple[str, ...] = ()
    descriptor_words: tuple[str, ...] = ()
    trailing_noise_pattern: str
    # Text that should never survive into a site name; a match means the title is malformed.
    residue_pattern: str

    @field_validator("ignored_prefix_patterns", "review_prefix_patterns", "section_end_patterns")
    @classmethod
    def patterns_compile(cls, patterns: tuple[str, ...]) -> tuple[str, ...]:
        return _compiles(patterns)

    @field_validator("separator_pattern", "trailing_noise_pattern", "residue_pattern")
    @classmethod
    def pattern_compiles(cls, pattern: str) -> str:
        _compiles((pattern,))
        return pattern


def _known_project_type(value: str) -> str:
    known = {item.value for item in ProjectType}
    if value not in known:
        raise ValueError(f"unknown project type {value!r}; expected one of {sorted(known)}")
    return value


class ProjectTypeRule(BaseModel):
    type: str = Field(min_length=1)
    keywords: tuple[str, ...] = Field(min_length=1)

    _type_is_known = field_validator("type")(_known_project_type)


class ProjectTypeConfig(BaseModel):
    """Ordered keyword rules; the first rule with a matching keyword decides the type."""

    rules: tuple[ProjectTypeRule, ...] = Field(min_length=1)
    endpoint_pair_type: str
    default_type: str

    _types_are_known = field_validator("endpoint_pair_type", "default_type")(_known_project_type)


class NormalizationConfig(BaseModel):
    date_formats: tuple[str, ...] = Field(min_length=1)
    voltage_pattern: str
    endpoints: EndpointRulesConfig
    project_types: ProjectTypeConfig

    @field_validator("voltage_pattern")
    @classmethod
    def voltage_pattern_compiles(cls, pattern: str) -> str:
        _compiles((pattern,))
        return pattern


class ResolutionConfig(BaseModel):
    """Rules for linking a project's named endpoints to public OSM features."""

    candidate_power_types: tuple[str, ...] = Field(min_length=1)
    name_match_threshold: float = Field(gt=0, le=100)
    # Words dropped from both names before comparing ("Substation", "Primary", ...).
    name_noise_words: tuple[str, ...] = ()
    # Abbreviations expanded on both sides before comparing ("n" -> "north").
    name_abbreviations: dict[str, str] = Field(default_factory=dict)
    # Expanded only as a name's first word: "St George" is Saint George, "Williams St" is a street.
    name_leading_abbreviations: dict[str, str] = Field(default_factory=dict)
    # Spelling variants applied to word endings on both sides ("queensborough" -> "queensboro").
    name_suffix_equivalents: dict[str, str] = Field(default_factory=dict)
    # Tokens that must agree exactly when present in either name ("east" never matches "west").
    distinguishing_tokens: tuple[str, ...] = ()
    # Equal-score candidates this close together are treated as one site (separate voltage yards).
    same_site_radius_km: float = Field(gt=0)
    # Endpoints of one project resolved further apart than this are treated as a mismatch.
    max_endpoint_separation_km: float = Field(gt=0)
    # How many name candidates per endpoint are tried when choosing a plausible combination.
    max_candidates_per_endpoint: int = Field(ge=1)
    # Words in a project title or description that mark it as a tie with a neighbouring system.
    tie_keywords: tuple[str, ...] = ()
    # Phrases removed before looking for tie keywords, because they name equipment ("bus tie breaker").
    tie_exclusion_phrases: tuple[str, ...] = ()
    overrides_file: str


class EvidenceLevelsConfig(BaseModel):
    high: int = Field(ge=0, le=100)
    medium: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def high_above_medium(self) -> "EvidenceLevelsConfig":
        if not self.medium < self.high:
            raise ValueError("evidence.levels must satisfy medium < high")
        return self


class EvidenceConfig(BaseModel):
    """Handoff section 10 point weights; the four part maxima must add up to 100."""

    source: dict[Literal["official_with_id", "official_weak_id", "secondary", "none"], int]
    identity: dict[Literal["name", "operator", "voltage", "region"], int]
    geometry: dict[str, int]
    timeline: dict[Literal["construction_window", "start_and_in_service", "in_service_date", "unknown"], int]
    levels: EvidenceLevelsConfig

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> "EvidenceConfig":
        missing = {method.value for method in GeometryMethod} - set(self.geometry)
        if missing:
            raise ValueError(f"evidence.geometry is missing weights for {sorted(missing)}")
        total = max(self.source.values()) + sum(self.identity.values()) + max(self.geometry.values()) + max(self.timeline.values())
        if total != 100:
            raise ValueError(f"evidence weights must total 100 at their maxima, found {total}")
        return self


class OverlapConfig(BaseModel):
    """Overlap-engine settings; spatial and timeline cutoffs live in thresholds_km and timeline_gap_days."""

    # A pair is measured exactly only if its projected bounding boxes are within maximum km * (1 + slack).
    prefilter_slack_ratio: float = Field(ge=0)
    distance_decimals: int = Field(ge=0)
    coordinate_decimals: int = Field(ge=0)
    # Handoff section 11: likely coordination themes per spatial tier.
    playbooks: dict[SpatialTier, tuple[str, ...]]
    playbook_labels: dict[str, str]

    @model_validator(mode="after")
    def playbooks_cover_every_tier(self) -> "OverlapConfig":
        missing = set(SpatialTier) - set(self.playbooks)
        if missing:
            raise ValueError(f"overlap.playbooks is missing tiers {sorted(missing)}")
        unlabeled = {key for keys in self.playbooks.values() for key in keys} - set(self.playbook_labels)
        if unlabeled:
            raise ValueError(f"overlap.playbook_labels is missing {sorted(unlabeled)}")
        return self


class OracleConfig(BaseModel):
    """The sponsor's worked example, used only to sanity-check our output, never as input."""

    file: str
    sheet: str
    overlaps_sheet: str
    project_ids: dict[str, str]


class GridlockConfig(BaseModel):
    paths: PathsConfig
    utilities: tuple[str, ...]
    utility_files: tuple[str, ...]
    thresholds_km: ThresholdsConfig
    timeline_gap_days: TimelineGapConfig
    display: DisplayConfig
    geometry: GeometryConfig
    osm: OsmConfig
    ai: AiConfig
    normalization: NormalizationConfig
    resolution: ResolutionConfig
    evidence: EvidenceConfig
    overlap: OverlapConfig
    oracle: OracleConfig | None = None

    @model_validator(mode="after")
    def utility_file_count_matches_scope(self) -> "GridlockConfig":
        if len(set(self.utilities)) != len(self.utilities):
            raise ValueError("utilities must not contain duplicates")
        if not self.utilities:
            raise ValueError("at least one utility must be configured")
        if len(self.utility_files) != len(self.utilities):
            raise ValueError("utility_files must provide exactly one file per utility")
        return self


class StripBlock(BaseModel):
    """A boilerplate block removed from stored source text, matched from start to end marker."""

    start: str = Field(min_length=1)
    end: str = Field(min_length=1)


class SourceConfig(BaseModel):
    id: str
    parser: str
    path: str
    # Field labels printed in the source document, keyed by the name each parser asks for.
    labels: dict[str, str] = Field(default_factory=dict)
    strip_blocks: tuple[StripBlock, ...] = ()
    ignored_line_patterns: tuple[str, ...] = ()
    # Which record wins when a summary table and a detail page disagree on a date.
    date_precedence: Literal["detail", "summary"] | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    summary_page_start: int | None = Field(default=None, ge=1)
    summary_page_end: int | None = Field(default=None, ge=1)
    detail_page_start: int | None = Field(default=None, ge=1)
    detail_page_end: int | None = Field(default=None, ge=1)


class Interconnection(BaseModel):
    """A neighbouring system. Its substations are accepted as endpoints only when the filing says so:
    a matching qualifier on the endpoint ("WEBB (APC)"), a tie keyword, or always for co-owners."""

    operators: tuple[str, ...] = Field(min_length=1)
    qualifiers: tuple[str, ...] = ()
    always_allowed: bool = False


class UtilityConfig(BaseModel):
    id: str
    # Upper-case code used on project records and as the project ID prefix, e.g. DESC.
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    display_name: str
    color: str
    states: tuple[str, ...]
    operator_aliases: tuple[str, ...] = ()
    # Neighbouring or co-owning systems whose substations can be the far end of this utility's lines.
    interconnections: tuple[Interconnection, ...] = ()
    # West, south, east, north box that endpoints must fall inside, including tie-line neighbours.
    service_area_bbox: tuple[float, float, float, float]
    # Narrower boxes for sponsors with their own territory (e.g. GPC's Savannah zone).
    sponsor_service_areas: dict[str, tuple[float, float, float, float]] = Field(default_factory=dict)
    included_sponsors: tuple[str, ...] = ()
    sources: tuple[SourceConfig, ...]

    @model_validator(mode="after")
    def service_area_is_ordered(self) -> "UtilityConfig":
        west, south, east, north = self.service_area_bbox
        if west >= east or south >= north:
            raise ValueError("service_area_bbox must be ordered west, south, east, north")
        return self


class GeometryOverride(BaseModel):
    """A human-verified endpoint location from a public source, used when OSM has no usable match."""

    utility: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    endpoint: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    # The public feature the reviewer identified, when one exists (e.g. an unnamed OSM way).
    feature_id: str | None = None
    source: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    note: str = Field(min_length=1)


class GeometryOverrides(BaseModel):
    overrides: tuple[GeometryOverride, ...] = ()
