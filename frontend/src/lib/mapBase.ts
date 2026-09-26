import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

import { runtimeConfig } from "./config";

type MapLibre = typeof import("maplibre-gl");
export type Basemap = "loading" | "online" | "bundled";

// Served from public/ by scripts/copy-maplibre-worker.mjs (bundlers cannot rewrite the worker's imports).
export const WORKER_URL = "/vendor/maplibre/maplibre-gl-worker.mjs";

/** True only when the online style itself failed to download (not tile or layer errors). */
export function isStyleFetchFailure(error: unknown, styleUrl: string): boolean {
  const detail = error as { name?: string; url?: string } | undefined;
  return detail?.url === styleUrl || detail?.name === "AJAXError" || error instanceof TypeError;
}

export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** The bundled offline basemap: state outlines from the U.S. Census Bureau (see public/data/README.md). */
export function bundledStyle(): StyleSpecification {
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

/**
 * A map on the online style from NEXT_PUBLIC_MAP_STYLE_URL that falls back to the bundled state
 * outlines when the style cannot be downloaded or exceeds NEXT_PUBLIC_MAP_STYLE_TIMEOUT_MS.
 * Callers add their own layers on every "style.load" (the fallback replaces the style).
 */
export function createBaseMap(
  lib: MapLibre,
  container: HTMLElement,
  onBasemap: (basemap: Basemap) => void,
): { map: MapLibreMap; dispose: () => void } {
  lib.setWorkerUrl(WORKER_URL);
  const online = runtimeConfig.mapStyleUrl;
  const map = new lib.Map({
    container,
    style: online || bundledStyle(),
    attributionControl: { compact: true },
    dragRotate: false,
  });
  map.touchZoomRotate.disableRotation();

  let timer: ReturnType<typeof setTimeout> | undefined;
  let settled = !online;
  const useBundled = () => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    onBasemap("bundled");
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
      onBasemap("online");
    });
  } else {
    onBasemap("bundled");
  }
  return { map, dispose: () => clearTimeout(timer) };
}
