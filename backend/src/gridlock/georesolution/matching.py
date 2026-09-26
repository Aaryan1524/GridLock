"""Link a project's named endpoints to public OSM features, with deterministic vetoes.

AI never takes part here. A match needs a close name and must survive the operator, region
and voltage vetoes; a project's endpoints must also sit plausibly close together. Anything
uncertain stays unresolved and goes to the review queue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations, product
from typing import Any

from pyproj import Geod
from shapely.geometry import shape

from gridlock.models.domain import Endpoint, EndpointMatch, EndpointMatchStatus, Point, Project
from gridlock.settings.models import GeometryOverride, Interconnection, ResolutionConfig, UtilityConfig

from .names import NormalizedName, name_score, normalize_name, tie_break_score

GEOD = Geod(ellps="WGS84")
COORDINATE_DECIMALS = 7

OWN = "own"
INTERCONNECTION = "interconnection"
UNTAGGED = "untagged"
FOREIGN = "foreign"
_RELATION_ORDER = {OWN: 0, INTERCONNECTION: 1, UNTAGGED: 2}


def distance_km(a: Point, b: Point) -> float:
    """Geodesic distance on the WGS84 ellipsoid."""
    _, _, metres = GEOD.inv(a.lon, a.lat, b.lon, b.lat)
    return metres / 1000


def _canonical(value: str) -> str:
    return " ".join(value.casefold().split())


def parse_voltage_kv(tag: Any) -> list[float]:
    """OSM voltage tags are volts, possibly several separated by ';' ("230000;115000")."""
    values = set()
    for part in str(tag or "").split(";"):
        if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", part):
            values.add(round(float(part) / 1000, 3))
    return sorted(values)


@dataclass(frozen=True)
class IndexedFeature:
    feature_id: str
    name: str
    normalized: NormalizedName
    operators: tuple[str, ...]
    voltage_kv: tuple[float, ...]
    point: Point


def build_index(features: list[dict[str, Any]], rules: ResolutionConfig) -> list[IndexedFeature]:
    """Named candidate features with a representative point, in stable ID order."""
    allowed = set(rules.candidate_power_types)
    indexed: list[IndexedFeature] = []
    for feature in features:
        properties = feature.get("properties", {})
        name = properties.get("name")
        if properties.get("power") not in allowed or not isinstance(name, str) or not name.strip():
            continue
        centroid = shape(feature["geometry"]).centroid
        if centroid.is_empty:
            continue
        indexed.append(
            IndexedFeature(
                feature_id=feature["id"],
                name=name,
                normalized=normalize_name(name, rules),
                operators=tuple(part.strip() for part in str(properties.get("operator") or "").split(";") if part.strip()),
                voltage_kv=tuple(parse_voltage_kv(properties.get("voltage"))),
                point=Point(lat=round(centroid.y, COORDINATE_DECIMALS), lon=round(centroid.x, COORDINATE_DECIMALS)),
            )
        )
    return sorted(indexed, key=lambda item: item.feature_id)


def in_area(point: Point, bbox: tuple[float, float, float, float]) -> bool:
    west, south, east, north = bbox
    return west <= point.lon <= east and south <= point.lat <= north


def voltages_compatible(project_kv: list[float], feature_kv: tuple[float, ...]) -> bool:
    """A substation cannot carry a project voltage above its highest known voltage.

    OSM often tags only a substation's highest voltage, so a lower project voltage is never a
    conflict, and a missing tag on either side never vetoes.
    """
    return not project_kv or not feature_kv or max(project_kv) <= max(feature_kv)


@dataclass(frozen=True)
class MatchContext:
    """Everything about one project that decides which features may serve as its endpoints."""

    utility: UtilityConfig
    area: tuple[float, float, float, float]
    project_kv: list[float]
    is_tie: bool
    rules: ResolutionConfig

    @classmethod
    def for_project(cls, project: Project, utility: UtilityConfig, rules: ResolutionConfig) -> "MatchContext":
        text = f"{project.project_name} {project.description or ''}"
        for phrase in rules.tie_exclusion_phrases:
            text = re.sub(re.escape(phrase), " ", text, flags=re.I)
        is_tie = any(re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text, re.I) for word in rules.tie_keywords)
        area = utility.sponsor_service_areas.get(project.sponsor or "", utility.service_area_bbox)
        return cls(utility=utility, area=area, project_kv=list(project.voltage_kv), is_tie=is_tie, rules=rules)


def _interconnection(operators: tuple[str, ...], utility: UtilityConfig) -> Interconnection | None:
    names = {_canonical(operator) for operator in operators}
    for group in utility.interconnections:
        if names & {_canonical(alias) for alias in group.operators}:
            return group
    return None


def operator_relation(operators: tuple[str, ...], utility: UtilityConfig) -> str:
    if not operators:
        return UNTAGGED
    if {_canonical(operator) for operator in operators} & {_canonical(alias) for alias in utility.operator_aliases}:
        return OWN
    return INTERCONNECTION if _interconnection(operators, utility) else FOREIGN


def _veto_reason(feature: IndexedFeature, endpoint: Endpoint, context: MatchContext) -> str | None:
    relation = operator_relation(feature.operators, context.utility)
    operators = "; ".join(feature.operators)
    if relation == FOREIGN:
        return f"operated by {operators}"
    if relation == INTERCONNECTION:
        group = _interconnection(feature.operators, context.utility)
        qualifiers = {_canonical(value) for value in endpoint.qualifiers}
        marked = qualifiers & {_canonical(value) for value in group.qualifiers}
        if not (group.always_allowed or marked or context.is_tie):
            return f"operated by neighbouring system {operators}, but the filing does not mark this end as a tie"
    if not in_area(feature.point, context.area):
        return f"outside the project's service area at ({feature.point.lat}, {feature.point.lon})"
    if not voltages_compatible(context.project_kv, feature.voltage_kv):
        return f"highest voltage {max(feature.voltage_kv):g} kV is below the project's {max(context.project_kv):g} kV"
    return None


@dataclass(frozen=True)
class Option:
    """One candidate site for an endpoint; several same-named yards within the site radius collapse into one."""

    feature: IndexedFeature
    score: float
    tie_break: float
    voltage_confirmed: bool
    site_size: int

    @property
    def key(self) -> tuple[float, float, bool]:
        return (self.score, self.tie_break, self.voltage_confirmed)


@dataclass(frozen=True)
class EndpointCandidates:
    endpoint: Endpoint
    options: list[Option]
    # The record to report when no option is chosen (no candidate, vetoed, or an override).
    fallback: EndpointMatch


def _match(endpoint: Endpoint, status: EndpointMatchStatus, **fields: Any) -> EndpointMatch:
    return EndpointMatch(endpoint=endpoint.name, role=endpoint.role, status=status, **fields)


def _feature_match(endpoint: Endpoint, option: Option, context: MatchContext, notes: list[str]) -> EndpointMatch:
    feature = option.feature
    if option.site_size > 1:
        notes = [f"{option.site_size} same-named features within {context.rules.same_site_radius_km:g} km treated as one site", *notes]
    return _match(
        endpoint,
        EndpointMatchStatus.MATCHED,
        feature_id=feature.feature_id,
        feature_name=feature.name,
        operator="; ".join(feature.operators) or None,
        operator_relation=operator_relation(feature.operators, context.utility),
        voltage_kv=list(feature.voltage_kv),
        name_score=option.score,
        point=feature.point,
        notes=notes,
    )


def _override_for(endpoint: Endpoint, utility: UtilityConfig, overrides: tuple[GeometryOverride, ...]) -> GeometryOverride | None:
    for override in overrides:
        if override.utility == utility.code and _canonical(override.endpoint) == _canonical(endpoint.name):
            return override
    return None


def _sites(ranked: list[Option], radius_km: float) -> list[Option]:
    """Group equally ranked features that sit within the radius of the group's first member."""
    options: list[Option] = []
    for candidate in ranked:
        for index, option in enumerate(options):
            if option.key == candidate.key and distance_km(option.feature.point, candidate.feature.point) <= radius_km:
                options[index] = Option(option.feature, option.score, option.tie_break, option.voltage_confirmed, option.site_size + 1)
                break
        else:
            options.append(candidate)
    return options


def endpoint_candidates(
    endpoint: Endpoint, context: MatchContext, index: list[IndexedFeature], overrides: tuple[GeometryOverride, ...]
) -> EndpointCandidates:
    """Rank the plausible sites for one endpoint; a human override replaces the OSM search."""
    override = _override_for(endpoint, context.utility, overrides)
    if override is not None:
        point = Point(lat=override.lat, lon=override.lon)
        if not in_area(point, context.area):
            return EndpointCandidates(endpoint, [], _match(endpoint, EndpointMatchStatus.VETOED, notes=["Override point is outside the project's service area"]))
        note = f"Human-verified by {override.reviewer}: {override.note} (source: {override.source})"
        fallback = _match(endpoint, EndpointMatchStatus.OVERRIDE, feature_id=override.feature_id, point=point, notes=[note])
        return EndpointCandidates(endpoint, [], fallback)

    target = normalize_name(endpoint.name, context.rules)
    named = [(name_score(target, feature.normalized), feature) for feature in index]
    named = [(score, feature) for score, feature in named if score >= context.rules.name_match_threshold]
    if not named:
        return EndpointCandidates(endpoint, [], _match(endpoint, EndpointMatchStatus.NO_CANDIDATE, notes=["No public OSM feature with a matching name"]))

    survivors: list[Option] = []
    vetoed: list[tuple[float, IndexedFeature, str]] = []
    for score, feature in named:
        reason = _veto_reason(feature, endpoint, context)
        if reason is None:
            tie_break = tie_break_score(target, feature.normalized)
            # When the endpoint carries a number ("#2"), a feature with the same number ranks first.
            if target.numbers and feature.normalized.numbers == target.numbers:
                tie_break += 0.01
            confirmed = bool(set(context.project_kv) & set(feature.voltage_kv))
            survivors.append(Option(feature, score, tie_break, confirmed, 1))
        else:
            vetoed.append((score, feature, reason))
    vetoed.sort(key=lambda item: (-item[0], item[1].feature_id))
    veto_notes = [f"{feature.name} ({feature.feature_id}): {why}" for _, feature, why in vetoed]
    if not survivors:
        score, feature, _ = vetoed[0]
        # A vetoed feature is named for review but never given a point that could be used as geometry.
        fallback = _match(
            endpoint, EndpointMatchStatus.VETOED, feature_id=feature.feature_id, feature_name=feature.name, name_score=score, notes=veto_notes
        )
        return EndpointCandidates(endpoint, [], fallback)

    survivors.sort(
        key=lambda option: (
            -option.score,
            -option.tie_break,
            not option.voltage_confirmed,
            _RELATION_ORDER[operator_relation(option.feature.operators, context.utility)],
            option.feature.feature_id,
        )
    )
    options = _sites(survivors, context.rules.same_site_radius_km)[: context.rules.max_candidates_per_endpoint]
    return EndpointCandidates(endpoint, options, _match(endpoint, EndpointMatchStatus.NO_CANDIDATE, notes=veto_notes))


def _ambiguous(candidates: EndpointCandidates, options: list[Option], reason: str) -> EndpointMatch:
    notes = [reason] + [f"{option.feature.name} ({option.feature.feature_id}) at ({option.feature.point.lat}, {option.feature.point.lon})" for option in options]
    return _match(candidates.endpoint, EndpointMatchStatus.AMBIGUOUS, name_score=options[0].score, notes=notes)


def choose_matches(all_candidates: list[EndpointCandidates], context: MatchContext) -> list[EndpointMatch]:
    """Pick the best-scoring site per endpoint such that a project's endpoints sit plausibly together."""
    searchable = [index for index, candidates in enumerate(all_candidates) if candidates.options]
    results = [candidates.fallback for candidates in all_candidates]
    if not searchable:
        return results

    limit = context.rules.max_endpoint_separation_km
    fixed = [candidates.fallback.point for candidates in all_candidates if candidates.fallback.status is EndpointMatchStatus.OVERRIDE]

    def feasible(choice: tuple[Option, ...]) -> bool:
        points = [option.feature.point for option in choice] + fixed
        return all(distance_km(a, b) <= limit for a, b in combinations(points, 2))

    combos = list(product(*(all_candidates[index].options for index in searchable)))
    valid = [choice for choice in combos if feasible(choice)]
    if not valid:
        for index in searchable:
            results[index] = _match(
                all_candidates[index].endpoint,
                EndpointMatchStatus.SEPARATION_REJECTED,
                notes=[f"No combination of candidate sites puts the endpoints within {limit:g} km of each other"],
            )
        return results

    def total(choice: tuple[Option, ...]) -> tuple[float, float, int]:
        return (
            sum(option.score for option in choice),
            sum(option.tie_break for option in choice),
            sum(option.voltage_confirmed for option in choice),
        )

    best_total = max(total(choice) for choice in valid)
    best = [choice for choice in valid if total(choice) == best_total]
    top_choice = best[0]
    for position, index in enumerate(searchable):
        candidates = all_candidates[index]
        picked = {choice[position].feature.feature_id: choice[position] for choice in best}
        if len(picked) > 1:
            results[index] = _ambiguous(candidates, sorted(picked.values(), key=lambda option: option.feature.feature_id), "Equally good candidate sites")
            continue
        option = top_choice[position]
        notes = []
        if option is not candidates.options[0]:
            notes.append("Chosen over a higher-ranked namesake so the project's endpoints sit plausibly together")
        results[index] = _feature_match(candidates.endpoint, option, context, notes)
    return results


def match_project_endpoints(
    project: Project,
    utility: UtilityConfig,
    index: list[IndexedFeature],
    rules: ResolutionConfig,
    overrides: tuple[GeometryOverride, ...] = (),
) -> list[EndpointMatch]:
    context = MatchContext.for_project(project, utility, rules)
    candidates = [endpoint_candidates(endpoint, context, index, overrides) for endpoint in project.endpoints]
    return choose_matches(candidates, context)
