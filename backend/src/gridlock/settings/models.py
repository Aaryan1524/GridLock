"""Pydantic models for the configuration surface used by every pipeline stage."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from gridlock.models.domain import ProjectType


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


class UtilityConfig(BaseModel):
    id: str
    # Upper-case code used on project records and as the project ID prefix, e.g. DESC.
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    display_name: str
    color: str
    states: tuple[str, ...]
    operator_aliases: tuple[str, ...] = ()
    included_sponsors: tuple[str, ...] = ()
    sources: tuple[SourceConfig, ...]
