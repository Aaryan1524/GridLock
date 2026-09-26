"""OpenStreetMap ingestion through a bounded, reproducible Overpass cache."""

from .cache import ingest_osm

__all__ = ["ingest_osm"]

