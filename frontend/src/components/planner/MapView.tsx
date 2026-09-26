"use client";

import type {
  ExpressionSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  MapLayerMouseEvent,
  Marker,
  StyleSpecification,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { runtimeConfig } from "@/lib/config";
import type { GridlockPayload, Zone } from "@/lib/contract";
import { countOf, formatDistance, label, utilityColor, utilityName } from "@/lib/format";
import { closestPointFeatures, connectorFeatures, projectFeatures, topRelationship } from "@/lib/mapData";

import styles from "./map.module.css";

type MapLibre = typeof import("maplibre-gl");
type Basemap = "loading" | "online" | "bundled";

const PROJECTS = "gl-projects";
const CONNECTORS = "gl-connectors";
const CLOSEST = "gl-closest";
const CLICKABLE = ["gl-project-points", "gl-project-lines", "gl-project-lines-approx"];
// Served from public/ by scripts/copy-maplibre-worker.mjs (bundlers cannot rewrite the worker's imports).
const WORKER_URL = "/vendor/maplibre/maplibre-gl-worker.mjs";

/** True only when the online style itself failed to download (not tile or layer errors). */
function isStyleFetchFailure(error: unknown, styleUrl: string): boolean {
  const detail = error as { name?: string; url?: string } | undefined;
  return detail?.url === styleUrl || detail?.name === "AJAXError" || error instanceof TypeError;
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** The bundled offline basemap: state outlines from the U.S. Census Bureau (see public/data/README.md). */
function bundledStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      states: { type: "geojson", data: "/data/states-southeast.geojson", attribution: "U.S. Census Bureau" },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": token("--bg-sunken") } },
      { id: "states-fill", type: "fill", source: "states", paint: { "fill-color": token("--bg-raised") } },
      { id: "states-line", type: "line", source: "states", paint: { "line-color": token("--line-strong"), "line-width": 0.8 } },
    ],
  };
}

function addLayers(map: MapLibreMap) {
  if (map.getSource(PROJECTS)) return;
  const empty = { type: "FeatureCollection" as const, features: [] };
  map.addSource(PROJECTS, { type: "geojson", data: empty, attribution: "Project geometry © OpenStreetMap contributors (ODbL)" });
  map.addSource(CONNECTORS, { type: "geojson", data: empty });
  map.addSource(CLOSEST, { type: "geojson", data: empty });

  const background: ExpressionSpecification = ["==", ["get", "role"], "background"];
  const line: ExpressionSpecification = ["==", ["geometry-type"], "LineString"];
  const point: ExpressionSpecification = ["==", ["geometry-type"], "Point"];
  const width: ExpressionSpecification = ["match", ["get", "role"], "top", 4, "zone", 2.2, 1];
  const opacity: ExpressionSpecification = ["match", ["get", "role"], "top", 1, "zone", 0.8, 0.28];

  map.addLayer({
    id: "gl-project-lines",
    type: "line",
    source: PROJECTS,
    filter: ["all", line, ["!", ["get", "approximate"]]],
    layout: { "line-cap": "round" },
    paint: { "line-color": ["get", "color"], "line-width": width, "line-opacity": opacity },
  });
  map.addLayer({
    id: "gl-project-lines-approx",
    type: "line",
    source: PROJECTS,
    filter: ["all", line, ["get", "approximate"]],
    paint: {
      "line-color": ["get", "color"],
      "line-width": width,
      "line-opacity": opacity,
      "line-dasharray": [2, 1.6],
    },
  });
  map.addLayer({
    id: "gl-connectors-all",
    type: "line",
    source: CONNECTORS,
    filter: ["!", ["get", "top"]],
    paint: { "line-color": token("--text"), "line-width": 1, "line-opacity": 0.45, "line-dasharray": [1, 2] },
  });
  map.addLayer({
    id: "gl-connectors-top",
    type: "line",
    source: CONNECTORS,
    filter: ["get", "top"],
    paint: { "line-color": token("--accent"), "line-width": 2.5 },
  });
  map.addLayer({
    id: "gl-project-points",
    type: "circle",
    source: PROJECTS,
    filter: point,
    paint: {
      "circle-radius": ["match", ["get", "role"], "top", 7, "zone", 5, 2.5],
      // Hollow = located by one endpoint of a longer project (approximate); solid = the site itself.
      "circle-color": ["case", ["get", "approximate"], token("--bg-sunken"), ["get", "color"]],
      "circle-stroke-color": ["get", "color"],
      "circle-stroke-width": ["case", ["==", ["get", "role"], "background"], 1, 2],
      "circle-opacity": ["case", background, 0.35, 1],
      "circle-stroke-opacity": ["case", background, 0.35, 1],
    },
  });
  map.addLayer({
    id: "gl-closest-points",
    type: "circle",
    source: CLOSEST,
    paint: { "circle-radius": 4, "circle-color": token("--accent"), "circle-stroke-color": token("--text"), "circle-stroke-width": 1.5 },
  });
}

interface Props {
  payload: GridlockPayload;
  zone: Zone | null;
  showAll: boolean;
  onShowAllChange: (value: boolean) => void;
  onProjectClick: (projectId: string) => void;
}

export function MapView({ payload, zone, showAll, onShowAllChange, onProjectClick }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const libRef = useRef<MapLibre | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const fittedZone = useRef<string | null>(null);
  const latest = useRef({ payload, zone, showAll, onProjectClick });
  latest.current = { payload, zone, showAll, onProjectClick };
  const [basemap, setBasemap] = useState<Basemap>("loading");
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  /** Push the current selection into the map's sources, fly to the zone, and place the distance label. */
  function sync() {
    const map = mapRef.current;
    const lib = libRef.current;
    if (!map || !lib || !map.getSource(PROJECTS)) return;
    const { payload: data, zone: selected, showAll: all } = latest.current;
    (map.getSource(PROJECTS) as GeoJSONSource).setData(projectFeatures(data, selected) as never);
    (map.getSource(CONNECTORS) as GeoJSONSource).setData(connectorFeatures(data, selected, all) as never);
    (map.getSource(CLOSEST) as GeoJSONSource).setData(closestPointFeatures(data, selected) as never);

    markerRef.current?.remove();
    markerRef.current = null;
    const top = topRelationship(data, selected);
    if (top) {
      const [a, b] = top.closestPoints;
      const element = document.createElement("div");
      element.className = styles.distanceLabel;
      element.textContent = formatDistance(top.distanceKm, data.metadata);
      markerRef.current = new lib.Marker({ element, anchor: "bottom", offset: [0, -10] })
        .setLngLat([(a.lon + b.lon) / 2, (a.lat + b.lat) / 2])
        .addTo(map);
    }

    if (selected && fittedZone.current !== selected.id) {
      fittedZone.current = selected.id;
      const { west, south, east, north } = selected.bounds;
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: 72, maxZoom: 11.5, duration: 900 },
      );
    }
  }

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    (async () => {
      const lib: MapLibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      libRef.current = lib;
      lib.setWorkerUrl(WORKER_URL);
      const online = runtimeConfig.mapStyleUrl;
      const map = new lib.Map({
        container: container.current,
        style: online || bundledStyle(),
        attributionControl: { compact: true },
        dragRotate: false,
      });
      mapRef.current = map;
      map.touchZoomRotate.disableRotation();
      // Keep the canvas matched to its region (layout changes, narrow screens) and re-frame the zone.
      const observer = new ResizeObserver(() => {
        map.resize();
        fittedZone.current = null;
        sync();
      });
      observer.observe(container.current);
      map.once("remove", () => observer.disconnect());

      let settled = !online;
      const useBundled = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        setBasemap("bundled");
        map.setStyle(bundledStyle());
      };
      if (online) {
        if (runtimeConfig.mapStyleTimeoutMs) timer = setTimeout(useBundled, runtimeConfig.mapStyleTimeoutMs);
        map.on("error", (event) => {
          if (isStyleFetchFailure(event.error, online)) useBundled();
        });
        map.once("style.load", () => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          setBasemap("online");
        });
      } else {
        setBasemap("bundled");
      }

      // Every style (online or bundled) gets the GridLock layers re-added on load.
      map.on("style.load", () => {
        fittedZone.current = null;
        addLayers(map);
        sync();
        setReady(true);
      });
      for (const layer of CLICKABLE) {
        map.on("click", layer, (event: MapLayerMouseEvent) => {
          const id = event.features?.[0]?.properties?.id;
          if (typeof id === "string") latest.current.onProjectClick(id);
        });
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }
    })().catch((error: unknown) => {
      // Most often WebGL is disabled; the rest of the planner keeps working without the map.
      if (!cancelled) setFailure(error instanceof Error ? error.message : String(error));
    });

    return () => {
      cancelled = true;
      clearTimeout(timer);
      markerRef.current?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(sync, [payload, zone, showAll]);

  const metadata = payload.metadata;
  const relationshipCount = zone?.relationshipIds.length ?? 0;
  const top = topRelationship(payload, zone);
  return (
    <div className={styles.frame}>
      <div ref={container} className={styles.map} aria-label="Map of the selected coordination zone" role="region" />
      {failure ? (
        <div className={styles.loading} role="alert">
          <p className="mono" style={{ color: "var(--accent)", margin: 0 }}>
            Map unavailable in this browser
          </p>
          <p className="mono-plain" style={{ margin: "6px 0 0", maxWidth: "46ch" }}>
            {failure}. Zone details, timeline and evidence still work; the distance shown is from the analysis, not the map.
          </p>
        </div>
      ) : (
        !ready && <div className={`mono ${styles.loading}`}>Loading map…</div>
      )}

      <div className={styles.topBar}>
        <span className={`mono ${styles.badge}`} data-basemap={basemap}>
          {basemap === "online" ? "Online basemap" : basemap === "bundled" ? "Bundled basemap · offline-safe" : "Basemap…"}
        </span>
        {relationshipCount > 1 && (
          <label className={`mono ${styles.toggle}`}>
            <input type="checkbox" checked={showAll} onChange={(event) => onShowAllChange(event.target.checked)} />
            Show all {countOf(relationshipCount, "relationship")}
          </label>
        )}
      </div>

      <div className={styles.legend}>
        {Object.keys(metadata.utilityColors).map((code) => (
          <span key={code} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: utilityColor(metadata, code) }} />
            {utilityName(metadata, code)}
          </span>
        ))}
        <span className={styles.legendItem}>
          <span className={styles.dashed} /> Approximate line ({label(metadata, "geometry_methods", "verified_endpoints_straight_line").toLowerCase()})
        </span>
        <span className={styles.legendItem}>
          <span className={styles.hollow} /> Located by one endpoint only
        </span>
        {top && (
          <span className={styles.legendItem}>
            <span className={styles.connector} /> Closest approach, top relationship
          </span>
        )}
      </div>
    </div>
  );
}
