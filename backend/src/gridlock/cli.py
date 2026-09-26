"""The GridLock command-line interface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from .contract import export_contract, validate_payload
from .georesolution import resolve_projects
from .georesolution.oracle import HEADER, OVERLAP_HEADER, oracle_check, overlap_oracle_check
from .overlap import run_overlap
from .ingestion.documents import IngestionError, ingest_plans
from .ingestion.osm import ingest_osm
from .ingestion.osm.cache import OsmIngestionError
from .settings.loader import ConfigBundle, ConfigError, load_settings


def _default_config_path() -> Path:
    configured = os.environ.get("GRIDLOCK_CONFIG")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "config" / "gridlock.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gridlock")
    parser.add_argument("--config", type=Path, default=_default_config_path())
    commands = parser.add_subparsers(dest="command", required=True)
    config_parser = commands.add_parser("config", help="inspect resolved configuration")
    config_parser.add_argument("action", choices=["show"])
    contract_parser = commands.add_parser("contract", help="export or validate the API contract")
    contract_parser.add_argument("action", choices=["export", "validate"])
    contract_parser.add_argument("payload", type=Path, nargs="?")
    ingest_parser = commands.add_parser("ingest", help="ingest configured public sources")
    ingest_parser.add_argument("source", choices=["plans", "osm"])
    ingest_parser.add_argument("--offline", action="store_true")
    commands.add_parser("resolve", help="resolve projects to public OSM geometry")
    commands.add_parser("oracle", help="compare resolved endpoints with the sponsor's worked example")
    commands.add_parser("overlap", help="measure and classify cross-utility project relationships")
    inspect_parser = commands.add_parser("inspect", help="print one normalized project record")
    inspect_parser.add_argument("project_id")
    inspect_parser.add_argument("--resolved", action="store_true", help="read the geometry-resolved output instead")
    inspect_parser.add_argument("--raw-text", action="store_true", help="include the stored source page text")
    return parser


def _print_table(header: list[str], rows: list[list[object]], widths: list[int]) -> None:
    print("  ".join(title.ljust(width) for title, width in zip(header, widths)))
    for row in rows:
        print("  ".join(str(value)[:width].ljust(width) for value, width in zip(row, widths)))


def _inspect(bundle: ConfigBundle, project_id: str, resolved: bool, include_raw_text: bool) -> int:
    file_name = "projects_resolved.json" if resolved else "projects.json"
    path = Path(__file__).resolve().parents[3] / bundle.root.paths.normalized_dir / file_name
    try:
        projects = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        print(f"Cannot read {path}: {error}")
        return 2
    match = next((project for project in projects if project["id"] == project_id), None)
    if match is None:
        print(f"No project {project_id!r} in {path}")
        return 1
    if not include_raw_text:
        match["source"].pop("rawText", None)
    print(json.dumps(match, indent=2, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "config" and args.action == "show":
        try:
            bundle = load_settings(args.config)
        except ConfigError as error:
            print(f"Configuration error: {error}")
            return 2
        print(json.dumps(bundle.summary(), indent=2, sort_keys=True))
        return 0
    if args.command == "contract" and args.action == "export":
        repository_root = Path(__file__).resolve().parents[3]
        schema_path, types_path = export_contract(repository_root)
        print(f"Wrote {schema_path}")
        print(f"Wrote {types_path}")
        return 0
    if args.command == "contract" and args.action == "validate":
        if args.payload is None:
            print("contract validate requires a payload path")
            return 2
        try:
            validate_payload(args.payload)
        except (OSError, ValueError) as error:
            print(f"Contract validation error: {error}")
            return 2
        print(f"Valid: {args.payload}")
        return 0
    if args.command == "ingest" and args.source == "plans":
        try:
            bundle = load_settings(args.config)
            report = ingest_plans(bundle, Path(__file__).resolve().parents[3])
        except (ConfigError, IngestionError) as error:
            print(f"Ingestion error: {error}")
            return 2
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "ingest" and args.source == "osm":
        try:
            bundle = load_settings(args.config)
            report = ingest_osm(bundle, Path(__file__).resolve().parents[3], offline=args.offline)
        except (ConfigError, OsmIngestionError) as error:
            print(f"OSM ingestion error: {error}")
            return 2
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "inspect":
        try:
            bundle = load_settings(args.config)
        except ConfigError as error:
            print(f"Configuration error: {error}")
            return 2
        return _inspect(bundle, args.project_id, args.resolved, args.raw_text)
    if args.command == "oracle":
        try:
            bundle = load_settings(args.config)
            rows = oracle_check(bundle, Path(__file__).resolve().parents[3])
        except (ConfigError, OSError, ValueError, KeyError) as error:
            print(f"Oracle check error: {error}")
            return 2
        _print_table(HEADER, [row.as_list() for row in rows], [10, 16, 20, 20, 20, 44, 11])
        relationships = Path(__file__).resolve().parents[3] / bundle.root.paths.output_dir / "relationships.json"
        if relationships.is_file():
            overlaps = overlap_oracle_check(bundle, Path(__file__).resolve().parents[3], relationships)
            print()
            _print_table(OVERLAP_HEADER, [row.as_list() for row in overlaps], [10, 30, 9, 14, 16, 8, 12, 16])
        return 0
    if args.command == "overlap":
        try:
            bundle = load_settings(args.config)
            report = run_overlap(bundle, Path(__file__).resolve().parents[3])
        except (ConfigError, OSError, ValueError) as error:
            print(f"Overlap error: {error}")
            return 2
        print(json.dumps(report.as_dict(), indent=2))
        return 0
    if args.command == "resolve":
        try:
            bundle = load_settings(args.config)
            report = resolve_projects(bundle, Path(__file__).resolve().parents[3])
        except (ConfigError, OSError, ValueError) as error:
            print(f"Resolution error: {error}")
            return 2
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
