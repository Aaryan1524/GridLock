import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

import { runtimeConfig } from "./config";
import { currentTheme, onThemeChange, type Theme } from "./theme";

type MapLibre = typeof import("maplibre-gl");
export type Basemap = "loading" | "online" | "bundled";

// Served from public/ by scripts/copy-maplibre-worker.mjs (bundlers cannot rewrite the worker's imports).
export const WORKER_URL = "/vendor/maplibre/maplibre-gl-worker.mjs";

/** True only when the online style itself failed to download (not tile or layer errors). */
export function isStyleFetchFailure(error: unknown, styleUrl: string): boolean {
  const detail = error as { name?: string; url?: string } | undefined;
  return detail?.url === styleUrl || detail?.name === "AJAXError" || error instanceof TypeError;
}

// Longest a map stays hidden waiting for its first complete draw (slow tiles still show up).
const FIRST_DRAW_WAIT_MS = 1500;

/** Calls back once, when the map has first drawn everything it can (or after FIRST_DRAW_WAIT_MS). Returns a cancel. */
export function whenFirstDrawn(map: MapLibreMap, callback: () => void): () => void {
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    callback();
  };
  const timer = setTimeout(finish, FIRST_DRAW_WAIT_MS);
  map.once("idle", finish);
  return () => {
    done = true;
    clearTimeout(timer);
  };
}

export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** The bundled offline basemap: state outlines from the U.S. Census Bureau (see public/data/README.md), in the current theme. */
export function bundledStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      states: { type: "geojson", data: "/data/states-southeast.geojson", attribution: "U.S. Census Bureau" },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": token("--map-bg") } },
      { id: "states-fill", type: "fill", source: "states", paint: { "fill-color": token("--map-land") } },
      { id: "states-line", type: "line", source: "states", paint: { "line-color": token("--map-outline"), "line-width": 0.8 } },
    ],
  };
}

/** The online style for a theme (NEXT_PUBLIC_MAP_STYLE_URL / _LIGHT); empty means use the bundled map. */
export function onlineStyleUrl(theme: Theme): string {
  return theme === "light" ? runtimeConfig.mapStyleUrlLight : runtimeConfig.mapStyleUrl;
}

// Online basemap layers that take the theme's paper and water tints when the theme defines them.
const TINTS: [layer: string, property: "background-color" | "fill-color", tokenName: string][] = [
  ["background", "background-color", "--map-tint-land"],
  ["water", "fill-color", "--map-tint-water"],
];

function tintOnlineStyle(map: MapLibreMap) {
  for (const [layer, property, name] of TINTS) {
    const value = token(name);
    if (value && map.getLayer(layer)) map.setPaintProperty(layer, property, value);
  }
}

/**
 * A map on the theme's online style that falls back to the bundled state outlines when the style
 * cannot be downloaded or exceeds NEXT_PUBLIC_MAP_STYLE_TIMEOUT_MS. Once it has fallen back it stays
 * on the bundled map. A theme change swaps the style; callers add their own layers on every
 * "style.load", which fires for each style.
 */
export function createBaseMap(
  lib: MapLibre,
  container: HTMLElement,
  onBasemap: (basemap: Basemap) => void,
): { map: MapLibreMap; dispose: () => void } {
  lib.setWorkerUrl(WORKER_URL);
  let online = onlineStyleUrl(currentTheme());
  let fellBack = false;
  let settled = true;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const map = new lib.Map({
    container,
    style: online || bundledStyle(),
    attributionControl: { compact: true },
    dragRotate: false,
  });
  map.touchZoomRotate.disableRotation();

  const useBundled = () => {
    if (settled) return;
    settled = true;
    fellBack = true;
    clearTimeout(timer);
    onBasemap("bundled");
    map.setStyle(bundledStyle(), { diff: false });
  };
  const awaitOnline = () => {
    settled = false;
    if (runtimeConfig.mapStyleTimeoutMs) timer = setTimeout(useBundled, runtimeConfig.mapStyleTimeoutMs);
  };

  map.on("error", (event) => {
    if (!settled && online && isStyleFetchFailure(event.error, online)) useBundled();
  });
  // Registered before any caller's handler, so tints apply before GridLock layers are added.
  map.on("style.load", () => {
    if (settled && !online) return;
    if (!fellBack) tintOnlineStyle(map);
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    onBasemap("online");
  });

  if (online) awaitOnline();
  else onBasemap("bundled");

  const stopWatchingTheme = onThemeChange(() => {
    clearTimeout(timer);
    settled = true;
    online = fellBack ? "" : onlineStyleUrl(currentTheme());
    if (online) {
      onBasemap("loading");
      awaitOnline();
      map.setStyle(online, { diff: false });
    } else {
      onBasemap("bundled");
      map.setStyle(bundledStyle(), { diff: false });
    }
  });

  return {
    map,
    dispose: () => {
      clearTimeout(timer);
      stopWatchingTheme();
    },
  };
}
