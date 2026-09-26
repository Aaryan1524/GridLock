"""Resolve projects to public OSM geometry; every unresolved endpoint is kept and queued for review."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from gridlock.evidence import score_evidence
from gridlock.models.domain import (
    EndpointMatch,
    EndpointMatchStatus,
    EndpointStatus,
    GeometryMethod,
    GeometryResolution,
    Project,
)
from gridlock.settings.loader import ConfigBundle
from gridlock.settings.models import GeometryOverride, ResolutionConfig, UtilityConfig

from .matching import IndexedFeature, build_index, distance_km, match_project_endpoints

RESOLVED = {EndpointMatchStatus.MATCHED, EndpointMatchStatus.OVERRIDE}


def _geometry(
    project: Project, matches: list[EndpointMatch], rules: ResolutionConfig
) -> tuple[dict | None, GeometryResolution]:
    """Apply the handoff section 9 ladder to the resolved endpoints, in title order."""
    resolved = [match for match in matches if match.status in RESOLVED]
    warnings: list[str] = []
    if len(resolved) >= 2:
        spread = max(distance_km(a.point, b.point) for a, b in combinations(resolved, 2))
        if spread > rules.max_endpoint_separation_km:
            warnings.append(
                f"Resolved endpoints are {spread:.1f} km apart, beyond the {rules.max_endpoint_separation_km:g} km limit; "
                "geometry withheld"
            )
            matches = [
                match.model_copy(update={"status": EndpointMatchStatus.SEPARATION_REJECTED, "point": None})
                if match.status in RESOLVED
                else match
                for match in matches
            ]
            resolved = []

    feature_ids = [match.feature_id or f"override/{project.utility}/{match.endpoint}" for match in resolved]
    only_overrides = bool(resolved) and all(match.status is EndpointMatchStatus.OVERRIDE for match in resolved)
    if len(resolved) >= 2:
        method = GeometryMethod.HUMAN_VERIFIED_OVERRIDE if only_overrides else GeometryMethod.VERIFIED_ENDPOINTS_STRAIGHT_LINE
        geometry = {"type": "LineString", "coordinates": [[match.point.lon, match.point.lat] for match in resolved]}
        is_approximation = True
        if len(resolved) < len(matches):
            warnings.append("Line drawn through the resolved endpoints only")
    elif len(resolved) == 1:
        method = GeometryMethod.HUMAN_VERIFIED_OVERRIDE if only_overrides else GeometryMethod.VERIFIED_SINGLE_ENDPOINT
        geometry = {"type": "Point", "coordinates": [resolved[0].point.lon, resolved[0].point.lat]}
        # A single-site project is fully located by its site; a line located by one end is not.
        is_approximation = project.endpoint_status is not EndpointStatus.SINGLE_SITE
    else:
        method, geometry, is_approximation = GeometryMethod.UNRESOLVED, None, False
    return geometry, GeometryResolution(
        method=method, is_approximation=is_approximation, feature_ids=feature_ids, matches=matches, warnings=warnings
    )


def resolve_project(
    project: Project,
    utility: UtilityConfig,
    index: list[IndexedFeature],
    bundle: ConfigBundle,
    overrides: tuple[GeometryOverride, ...] = (),
) -> Project:
    rules = bundle.root.resolution
    matches = match_project_endpoints(project, utility, index, rules, overrides)
    geometry, resolution = _geometry(project, matches, rules)
    return project.model_copy(
        update={
            "geometry": geometry,
            "geometry_resolution": resolution,
            "evidence": score_evidence(project, resolution, bundle.root.evidence),
        }
    )


@dataclass(frozen=True)
class ResolutionReport:
    output_path: Path
    review_path: Path
    projects: int
    projects_with_endpoints: int
    projects_with_geometry: int
    endpoint_status: dict[str, int]
    geometry_methods: dict[str, int]
    evidence_levels: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        rate = self.projects_with_geometry / self.projects_with_endpoints if self.projects_with_endpoints else 0.0
        return {
            "projects": self.projects,
            "projects_with_named_endpoints": self.projects_with_endpoints,
            "projects_with_geometry": self.projects_with_geometry,
            "automatic_resolution_rate": round(rate, 3),
            "endpoint_status": self.endpoint_status,
            "geometry_methods": self.geometry_methods,
            "evidence_levels": self.evidence_levels,
            "output_path": str(self.output_path),
            "review_path": str(self.review_path),
        }


def resolve_projects(
    bundle: ConfigBundle,
    repository_root: Path,
    output_path: Path | None = None,
    review_path: Path | None = None,
) -> ResolutionReport:
    paths = bundle.root.paths
    normalized_path = repository_root / paths.normalized_dir / "projects.json"
    cache_path = repository_root / paths.cache_dir / "osm_power.geojson"
    projects = [Project.model_validate(item) for item in json.loads(normalized_path.read_text(encoding="utf-8"))]
    index = build_index(json.loads(cache_path.read_text(encoding="utf-8"))["features"], bundle.root.resolution)
    resolved = [
        resolve_project(project, bundle.utility(project.utility), index, bundle, bundle.overrides) for project in projects
    ]

    output_path = output_path or repository_root / paths.normalized_dir / "projects_resolved.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([project.model_dump(mode="json", by_alias=True) for project in resolved], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    review_path = review_path or repository_root / paths.review_dir / "unresolved.csv"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["project_id", "project_name", "endpoint", "status", "best_candidate", "notes"])
        for project in resolved:
            if not project.endpoints:
                writer.writerow([project.id, project.project_name, "", "no_named_endpoint", "", " | ".join(project.warnings)])
            for match in project.geometry_resolution.matches:
                if match.status not in RESOLVED:
                    candidate = f"{match.feature_name} ({match.feature_id})" if match.feature_id else ""
                    writer.writerow([project.id, project.project_name, match.endpoint, match.status.value, candidate, " | ".join(match.notes)])

    all_matches = [match for project in resolved for match in project.geometry_resolution.matches]
    return ResolutionReport(
        output_path=output_path,
        review_path=review_path,
        projects=len(resolved),
        projects_with_endpoints=sum(bool(project.endpoints) for project in resolved),
        projects_with_geometry=sum(project.geometry is not None for project in resolved),
        endpoint_status=dict(sorted(Counter(match.status.value for match in all_matches).items())),
        geometry_methods=dict(sorted(Counter(p.geometry_resolution.method.value for p in resolved).items())),
        evidence_levels=dict(sorted(Counter(p.evidence.level.value for p in resolved).items())),
    )
