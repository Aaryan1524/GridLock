"""Run every pipeline stage in order and summarize the result."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from gridlock.georesolution import resolve_projects
from gridlock.ingestion.documents import ingest_plans
from gridlock.ingestion.documents.plans import raw_dir
from gridlock.ingestion.osm import ingest_osm
from gridlock.models.domain import Payload
from gridlock.overlap import run_overlap
from gridlock.settings.loader import ConfigBundle

from .payload import PayloadResult, build_payload


class PipelineError(RuntimeError):
    """Raised when a stage cannot run with the available inputs."""


def run_pipeline(
    bundle: ConfigBundle,
    repository_root: Path,
    *,
    offline: bool,
    skip_ingest: bool,
    log: Callable[[str], None] = print,
) -> PayloadResult:
    """Ingest → OSM → resolve → overlap → graph/zones/ranking/payload."""
    if skip_ingest:
        log("1/5 plans: using committed data/normalized/projects.json")
    else:
        missing = [
            source.path
            for utility in bundle.utilities
            for source in utility.sources
            if not (raw_dir(bundle, repository_root) / source.path).is_file()
        ]
        if missing:
            raise PipelineError(f"raw planning documents are missing ({', '.join(missing)}); rerun with --skip-ingest")
        report = ingest_plans(bundle, repository_root)
        log(f"1/5 plans: {report.as_dict()['total_projects']} projects")
    osm = ingest_osm(bundle, repository_root, offline=offline)
    log(f"2/5 osm: {sum(osm.feature_counts.values())} features ({'cache' if offline else 'refreshed from Overpass'})")
    resolution = resolve_projects(bundle, repository_root).as_dict()
    log(f"3/5 resolve: {resolution['projects_with_geometry']} projects located")
    overlap = run_overlap(bundle, repository_root).as_dict()
    log(f"4/5 overlap: {overlap['relationships']} relationships")
    result = build_payload(bundle, repository_root)
    log(f"5/5 zones: {len(result.payload.zones)} zones → {result.output_path}")
    return result


def summarize(payload: Payload) -> list[str]:
    """Plain-language summary of the payload; every number comes from the payload itself."""
    metrics, labels = payload.metrics, payload.metadata.labels
    projects = {project.id: project for project in payload.projects}
    lines = [
        f"{metrics.zones} coordination zones from {metrics.relationships} cross-utility relationships "
        f"(attention compression {metrics.attention_compression_ratio}x)",
        f"{metrics.located_projects} of {metrics.projects} projects located; not assessed: "
        + ", ".join(f"{code} {count}" for code, count in metrics.not_assessed_by_utility.items()),
    ]
    for zone in payload.zones:
        themes = ", ".join(labels.get("playbook", {}).get(theme, theme) for theme in zone.coordination_themes)
        top = zone.headline
        gap = f"{top.gap_days}-day {labels.get('timeline_types', {}).get(top.timeline_type.value, top.timeline_type.value).lower()}" if top.gap_days is not None else "dates unknown"
        tier = labels.get("spatial_tiers", {}).get(top.spatial_tier.value, top.spatial_tier.value).lower()
        lines.append(
            f"#{zone.rank} {zone.name} [{zone.opportunity_priority.value} priority, {zone.evidence_level.value} evidence]: "
            f"{len(zone.project_ids)} projects, {len(zone.relationship_ids)} relationships"
        )
        lines.append(f"     top pair {top.project_a} × {top.project_b}: {top.distance_km:g} km ({tier}), {gap}")
        lines.append(f"     themes: {themes}")
        lines.append("     projects: " + "; ".join(f"{pid} {projects[pid].project_name}" for pid in zone.project_ids[:6])
                     + (f"; +{len(zone.project_ids) - 6} more" if len(zone.project_ids) > 6 else ""))
        lines += [f"     △ {warning}" for warning in zone.warnings]
    return lines
