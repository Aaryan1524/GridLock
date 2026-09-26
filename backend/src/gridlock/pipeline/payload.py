"""Assemble the frontend payload: projects, ranked relationships, zones, metrics and metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gridlock.graph import build_graph
from gridlock.metrics import compute_metrics
from gridlock.models.domain import Metadata, Payload, Project, Relationship, SourceSnapshot
from gridlock.ranking import rank_relationships
from gridlock.settings.loader import ConfigBundle
from gridlock.zones import build_zones


def _metadata(bundle: ConfigBundle, repository_root: Path) -> Metadata:
    root = bundle.root
    sources = [
        SourceSnapshot(kind="planning_document", name=source.path)
        for utility in bundle.utilities
        for source in utility.sources
    ]
    osm_meta_path = repository_root / root.paths.cache_dir / "osm_power.meta.json"
    if osm_meta_path.is_file():
        osm = json.loads(osm_meta_path.read_text(encoding="utf-8"))
        sources.append(SourceSnapshot(kind="osm_snapshot", name=osm["source"], retrieved_at=osm.get("retrieved_at"), sha256=osm.get("sha256")))
    labels = {**root.labels, "playbook": dict(root.overlap.playbook_labels)}
    return Metadata(
        distance_unit=root.display.distance_unit,
        thresholds_km=root.thresholds_km.model_dump(),
        timeline_gap_days=root.timeline_gap_days.model_dump(),
        zone_guards=root.zones.model_dump(include={"max_geographic_span_km", "max_timeline_span_days", "timeline_guard", "max_projects"}),
        utility_colors={utility.code: utility.color for utility in bundle.utilities},
        utility_names={utility.code: utility.display_name for utility in bundle.utilities},
        labels=labels,
        sources=sources,
    )


def assemble_payload(bundle: ConfigBundle, repository_root: Path, projects: list[Project], relationships: list[Relationship]) -> Payload:
    ranked = rank_relationships(relationships, bundle.root.priority)
    graph = build_graph(projects, ranked)
    zones = build_zones(graph, projects, bundle)
    utility_order = [utility.code for utility in bundle.utilities]
    return Payload(
        metadata=_metadata(bundle, repository_root),
        metrics=compute_metrics(projects, ranked, zones, utility_order),
        projects=sorted(projects, key=lambda project: project.id),
        relationships=ranked,
        zones=zones,
    )


@dataclass(frozen=True)
class PayloadResult:
    payload: Payload
    output_path: Path


def build_payload(bundle: ConfigBundle, repository_root: Path, output_path: Path | None = None) -> PayloadResult:
    paths = bundle.root.paths
    projects = [
        Project.model_validate(item)
        for item in json.loads((repository_root / paths.normalized_dir / "projects_resolved.json").read_text(encoding="utf-8"))
    ]
    relationships = [
        Relationship.model_validate(item)
        for item in json.loads((repository_root / paths.output_dir / "relationships.json").read_text(encoding="utf-8"))
    ]
    payload = assemble_payload(bundle, repository_root, projects, relationships)
    output_path = output_path or repository_root / paths.output_dir / bundle.root.api.payload_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return PayloadResult(payload, output_path)
