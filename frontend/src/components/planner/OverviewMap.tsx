"use client";

import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { GridlockPayload } from "@/lib/contract";
import { utilityColor, utilityName } from "@/lib/format";
import { type Basemap, createBaseMap, token } from "@/lib/mapBase";
import { projectFeatures } from "@/lib/mapData";

import styles from "./map.module.css";

type MapLibre = typeof import("maplibre-gl");

const PROJECTS = "ov-projects";
const ZONES = "ov-zones";
const CHIP_GAP = 4;
// Room above the zones for the basemap badge and for zone labels stacked on shared edges.
const BADGE_ROOM = 56;
const CHIP_ROOM = 30;
// Priority tones reuse the design tokens that style the priority tags.
const PRIORITY_TOKEN: Record<string, string> = { HIGH: "--accent", MEDIUM: "--amber", LOW: "--neutral" };

function zoneFeatures(payload: GridlockPayload, selectedId: string | null) {
  return {
    type: "FeatureCollection" as const,
    features: payload.zones.map((zone) => {
      const { west, south, east, north } = zone.bounds;
      return {
        type: "Feature" as const,
        properties: { id: zone.id, priority: zone.opportunityPriority, selected: zone.id === selectedId },
        geometry: {
          type: "Polygon" as const,
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
      };
    }),
  };
}

/** Projects in any zone are emphasized; everything else located is faint background. */
function overviewProjects(payload: GridlockPayload) {
  const inZones = new Set(payload.zones.flatMap((zone) => zone.projectIds));
  const collection = projectFeatures(payload, null);
  for (const feature of collection.features) {
    feature.properties.role = inZones.has(String(feature.properties.id)) ? "zone" : "background";
  }
  return collection;
}

function addLayers(map: MapLibreMap) {
  if (map.getSource(PROJECTS)) return;
  const empty = { type: "FeatureCollection" as const, features: [] };
  map.addSource(PROJECTS, { type: "geojson", data: empty, attribution: "Project geometry © OpenStreetMap contributors (ODbL)" });
  map.addSource(ZONES, { type: "geojson", data: empty });
  const tone: ExpressionSpecification = [
    "match",
    ["get", "priority"],
    ...Object.entries(PRIORITY_TOKEN).flatMap(([priority, name]) => [priority, token(name)]),
    token("--neutral"),
  ] as unknown as ExpressionSpecification;
  const zoneRole: ExpressionSpecification = ["==", ["get", "role"], "zone"];

  map.addLayer({ id: "ov-zone-fill", type: "fill", source: ZONES, paint: { "fill-color": tone, "fill-opacity": ["case", ["get", "selected"], 0.16, 0.07] } });
  map.addLayer({
    id: "ov-zone-outline",
    type: "line",
    source: ZONES,
    paint: { "line-color": tone, "line-width": ["case", ["get", "selected"], 2, 1], "line-opacity": ["case", ["get", "selected"], 1, 0.6], "line-dasharray": [3, 2] },
  });
  map.addLayer({
    id: "ov-project-lines",
    type: "line",
    source: PROJECTS,
    filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": ["get", "color"], "line-width": ["case", zoneRole, 1.8, 1], "line-opacity": ["case", zoneRole, 0.85, 0.25] },
  });
  map.addLayer({
    id: "ov-project-points",
    type: "circle",
    source: PROJECTS,
    filter: ["==", ["geometry-type"], "Point"],
    paint: {
      "circle-radius": ["case", zoneRole, 3.5, 2.2],
      "circle-color": ["get", "color"],
      "circle-opacity": ["case", zoneRole, 0.9, 0.3],
      "circle-stroke-width": 0,
    },
  });
}

interface Props {
  payload: GridlockPayload;
  selectedId: string | null;
  onSelect: (zoneId: string) => void;
}

export function OverviewMap({ payload, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const libRef = useRef<MapLibre | null>(null);
  const markers = useRef<Marker[]>([]);
  const latest = useRef({ payload, selectedId, onSelect });
  latest.current = { payload, selectedId, onSelect };
  const [basemap, setBasemap] = useState<Basemap>("loading");
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  function sync() {
    const map = mapRef.current;
    const lib = libRef.current;
    if (!map || !lib || !map.getSource(ZONES)) return;
    const { payload: data, selectedId: selected } = latest.current;
    (map.getSource(ZONES) as GeoJSONSource).setData(zoneFeatures(data, selected) as never);
    (map.getSource(PROJECTS) as GeoJSONSource).setData(overviewProjects(data) as never);
    markers.current.forEach((marker) => marker.remove());
    markers.current = data.zones.map((zone) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = styles.zoneChip;
      element.dataset.priority = zone.opportunityPriority;
      element.dataset.selected = String(zone.id === selected);
      element.textContent = `${String(zone.rank ?? "").padStart(2, "0")}  ${zone.name}`;
      element.setAttribute("aria-label", `Select zone ${zone.rank}: ${zone.name}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        latest.current.onSelect(zone.id);
      });
      const { west, east, north } = zone.bounds;
      return new lib.Marker({ element, anchor: "bottom" }).setLngLat([(west + east) / 2, north]).addTo(map);
    });
    layoutChips();
  }

  /** Zones can share an edge, so their labels can land on top of each other; stack later ranks upward. */
  function layoutChips() {
    const map = mapRef.current;
    if (!map) return;
    const placed: { left: number; right: number; top: number; bottom: number }[] = [];
    for (const marker of markers.current) {
      const element = marker.getElement();
      const anchor = map.project(marker.getLngLat());
      const width = element.offsetWidth;
      const height = element.offsetHeight;
      let lift = 0;
      const box = () => ({ left: anchor.x - width / 2, right: anchor.x + width / 2, top: anchor.y - height - lift, bottom: anchor.y - lift });
      let rect = box();
      while (placed.some((other) => rect.left < other.right && rect.right > other.left && rect.top < other.bottom && rect.bottom > other.top)) {
        lift += height + CHIP_GAP;
        rect = box();
      }
      marker.setOffset([0, -lift]);
      placed.push(rect);
    }
  }

  function frameAllZones(map: MapLibreMap) {
    const zones = latest.current.payload.zones;
    if (!zones.length) return;
    map.fitBounds(
      [
        [Math.min(...zones.map((zone) => zone.bounds.west)), Math.min(...zones.map((zone) => zone.bounds.south))],
        [Math.max(...zones.map((zone) => zone.bounds.east)), Math.max(...zones.map((zone) => zone.bounds.north))],
      ],
      {
        padding: { top: Math.min(BADGE_ROOM + zones.length * CHIP_ROOM, map.getContainer().clientHeight * 0.4), bottom: 60, left: 60, right: 60 },
        duration: 0,
        maxZoom: 9,
      },
    );
  }

  useEffect(() => {
    let cancelled = false;
    let disposeBase = () => {};
    (async () => {
      const lib: MapLibre = await import("maplibre-gl");
      if (cancelled || !container.current) return;
      libRef.current = lib;
      const base = createBaseMap(lib, container.current, setBasemap);
      const map = base.map;
      disposeBase = base.dispose;
      mapRef.current = map;
      const observer = new ResizeObserver(() => {
        map.resize();
        frameAllZones(map);
      });
      observer.observe(container.current);
      map.once("remove", () => observer.disconnect());
      map.on("style.load", () => {
        addLayers(map);
        sync();
        frameAllZones(map);
        setReady(true);
      });
      map.on("click", "ov-zone-fill", (event: MapLayerMouseEvent) => {
        const id = event.features?.[0]?.properties?.id;
        if (typeof id === "string") latest.current.onSelect(id);
      });
      map.on("zoom", layoutChips);
      map.on("mouseenter", "ov-zone-fill", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "ov-zone-fill", () => (map.getCanvas().style.cursor = ""));
    })().catch((error: unknown) => {
      if (!cancelled) setFailure(error instanceof Error ? error.message : String(error));
    });
    return () => {
      cancelled = true;
      disposeBase();
      markers.current.forEach((marker) => marker.remove());
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(sync, [payload, selectedId]);

  const { metadata } = payload;
  return (
    <div className={styles.frame}>
      <div ref={container} className={styles.map} role="region" aria-label="Map of all coordination zones" />
      {failure ? (
        <div className={styles.loading} role="alert">
          <p className="mono" style={{ color: "var(--accent)", margin: 0 }}>
            Map unavailable in this browser
          </p>
          <p className="mono-plain" style={{ margin: "6px 0 0", maxWidth: "46ch" }}>
            {failure}. The zone list and figures beside the map still work.
          </p>
        </div>
      ) : (
        !ready && <div className={`mono ${styles.loading}`}>Loading map…</div>
      )}
      <div className={styles.topBar}>
        <span className={`mono ${styles.badge}`} data-basemap={basemap}>
          {basemap === "online" ? "Online basemap" : basemap === "bundled" ? "Bundled basemap · offline-safe" : "Basemap…"}
        </span>
      </div>
      <div className={styles.legend}>
        {Object.keys(metadata.utilityColors).map((code) => (
          <span key={code} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: utilityColor(metadata, code) }} />
            {utilityName(metadata, code)}
          </span>
        ))}
        <span className={styles.legendItem}>
          <span className={styles.zoneKey} /> Coordination zone extent (select to inspect)
        </span>
      </div>
    </div>
  );
}
