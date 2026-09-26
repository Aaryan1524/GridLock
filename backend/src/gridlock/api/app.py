"""Read-only HTTP API over the built payload; it never recomputes domain logic."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from gridlock.envfile import load_root_env, repository_path
from gridlock.settings.loader import ConfigBundle, load_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONFIG_ENV = "GRIDLOCK_CONFIG"
CORS_ENV = "GRIDLOCK_API_CORS_ORIGINS"


def cors_origins(configured: tuple[str, ...]) -> list[str]:
    """Allowed browser origins: a comma-separated GRIDLOCK_API_CORS_ORIGINS overrides the config."""
    override = os.environ.get(CORS_ENV, "")
    origins = [origin.strip() for origin in override.split(",") if origin.strip()]
    return origins or list(configured)


class _PayloadFile:
    """Reads the payload JSON, re-reading only when the file changes on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stamp: tuple[int, int] | None = None
        self._data: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        try:
            stat = self.path.stat()
        except FileNotFoundError as error:
            raise HTTPException(status_code=503, detail="payload not built yet; run `gridlock run --offline`") from error
        stamp = (stat.st_mtime_ns, stat.st_size)
        if stamp != self._stamp:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            self._stamp = stamp
        return self._data


def create_app(bundle: ConfigBundle, repository_root: Path = REPOSITORY_ROOT) -> FastAPI:
    api = bundle.root.api
    payload = _PayloadFile(repository_root / bundle.root.paths.output_dir / api.payload_file)
    app = FastAPI(title="GridLock", description="Evidence-backed cross-utility coordination zones (read-only).")
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(api.cors_origins), allow_methods=["GET"], allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"service": api.service_name, "status": "ok", "payloadAvailable": payload.path.is_file()}

    @app.get("/api/payload")
    def full_payload() -> dict[str, Any]:
        return payload.load()

    @app.get("/api/zones/{zone_id}")
    def zone_detail(zone_id: str) -> dict[str, Any]:
        data = payload.load()
        zone = next((item for item in data["zones"] if item["id"] == zone_id), None)
        if zone is None:
            raise HTTPException(status_code=404, detail=f"no zone {zone_id!r}")
        project_ids, relationship_ids = set(zone["projectIds"]), set(zone["relationshipIds"])
        return {
            "zone": zone,
            "projects": [project for project in data["projects"] if project["id"] in project_ids],
            "relationships": [item for item in data["relationships"] if item["id"] in relationship_ids],
            "metadata": data["metadata"],
        }

    return app


def _default_bundle() -> ConfigBundle:
    load_root_env(REPOSITORY_ROOT)  # also when started directly with uvicorn
    configured = os.environ.get(CONFIG_ENV)
    return load_settings(repository_path(configured, REPOSITORY_ROOT) if configured else REPOSITORY_ROOT / "config" / "gridlock.yaml")


app = create_app(_default_bundle())
