"""Handoff section 24: one real DESC <-> GPC path, source record to frontend JSON, reproduced from scratch."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from gridlock.ingestion.documents.plans import raw_dir
from gridlock.models.domain import Payload
from gridlock.pipeline import run_pipeline
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml")
PATHS = BUNDLE.root.paths
RAW = raw_dir(BUNDLE, REPOSITORY_ROOT)
SOURCES = [RAW / source.path for utility in BUNDLE.utilities for source in utility.sources]
COMMITTED_OUTPUTS = [
    f"{PATHS.normalized_dir}/projects.json",
    f"{PATHS.normalized_dir}/projects_resolved.json",
    f"{PATHS.review_dir}/unresolved.csv",
    f"{PATHS.output_dir}/relationships.json",
    f"{PATHS.output_dir}/{BUNDLE.root.api.payload_file}",
    f"{PATHS.output_dir}/metrics.json",
]

pytestmark = pytest.mark.skipif(not all(path.is_file() for path in SOURCES), reason="raw planning documents are not available")


@pytest.fixture(scope="module")
def fresh_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty workspace with only the public inputs: the raw filings and the cached OSM snapshot."""
    root = tmp_path_factory.mktemp("fresh")
    (root / PATHS.raw_dir).parent.mkdir(parents=True, exist_ok=True)
    (root / PATHS.raw_dir).symlink_to(RAW, target_is_directory=True)
    shutil.copytree(REPOSITORY_ROOT / PATHS.cache_dir, root / PATHS.cache_dir)
    run_pipeline(BUNDLE, root, offline=True, skip_ingest=False, log=lambda _message: None)
    return root


@pytest.mark.parametrize("relative", COMMITTED_OUTPUTS)
def test_a_fresh_run_reproduces_every_committed_output(fresh_root: Path, relative: str) -> None:
    assert (fresh_root / relative).read_bytes() == (REPOSITORY_ROOT / relative).read_bytes()


def test_flagship_record_traces_from_filing_to_frontend_json(fresh_root: Path) -> None:
    projects = {p["id"]: p for p in json.loads((fresh_root / PATHS.normalized_dir / "projects.json").read_text(encoding="utf-8"))}
    resolved = {p["id"]: p for p in json.loads((fresh_root / PATHS.normalized_dir / "projects_resolved.json").read_text(encoding="utf-8"))}
    relationships = {r["id"]: r for r in json.loads((fresh_root / PATHS.output_dir / "relationships.json").read_text(encoding="utf-8"))}
    payload = Payload.model_validate_json((fresh_root / PATHS.output_dir / BUNDLE.root.api.payload_file).read_text(encoding="utf-8"))

    # 1. Source record: the DESC filing, page 23.
    source = projects["DESC-06367-D-G"]["source"]
    assert (source["document"], source["page"], source["projectIdRaw"]) == ("2024-2028-2million-and-above-project-descriptions.pdf", 23, "06367 D - G")
    # 2. Normalized project.
    assert [e["name"] for e in projects["DESC-06367-D-G"]["endpoints"]] == ["Jasper", "Okatie"]
    assert projects["DESC-06367-D-G"]["plannedInServiceDate"] == "2025-12-31"
    # 3. Geometry: Jasper from OSM, Okatie from the reviewed override; a disclosed approximation.
    matches = {m["endpoint"]: m for m in resolved["DESC-06367-D-G"]["geometryResolution"]["matches"]}
    assert matches["Jasper"]["status"] == "matched" and matches["Okatie"]["status"] == "override"
    assert resolved["DESC-06367-D-G"]["geometryResolution"]["isApproximation"] is True
    # 4. Relationship with the GPC McIntosh - Purrysburg project.
    relationship = relationships["REL-DESC-06367-D-G-GPC-20277"]
    assert (relationship["distanceKm"], relationship["spatialTier"]) == (4.89, "SITE_LOGISTICS")
    assert (relationship["timeline"]["type"], relationship["timeline"]["gapDays"]) == ("IN_SERVICE_GAP", 152)
    # 5. Zone: it heads the top-ranked zone.
    zone = payload.zones[0]
    assert zone.top_relationship_id == relationship["id"] and zone.rank == 1
    # 6. Frontend JSON carries the same figures in the zone headline.
    assert (zone.headline.distance_km, zone.headline.gap_days) == (4.89, 152)
