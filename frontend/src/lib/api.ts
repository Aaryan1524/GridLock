"use client";

import { useEffect, useState } from "react";

import { missingConfig, runtimeConfig } from "./config";
import type { GridlockPayload } from "./contract";

export type PayloadState =
  | { status: "loading" }
  | { status: "error"; message: string; detail?: string }
  | { status: "ready"; payload: GridlockPayload };

interface Health {
  service?: string;
  status?: string;
  payloadAvailable?: boolean;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Confirms the API is the GridLock service (not another local server) before trusting its data. */
async function loadPayload(): Promise<GridlockPayload> {
  const missing = missingConfig();
  if (missing.length) {
    throw new Error(`Missing frontend settings: ${missing.join(", ")}. Copy .env.example to .env.`);
  }
  const health = await getJson<Health>("/api/health");
  if (health.service !== runtimeConfig.apiService) {
    throw new Error(
      `The server at ${runtimeConfig.apiBaseUrl} identifies as "${health.service ?? "unknown"}", not "${runtimeConfig.apiService}".`,
    );
  }
  if (!health.payloadAvailable) {
    throw new Error("The GridLock API is running but has no payload yet. Run `uv run gridlock run --offline`.");
  }
  return getJson<GridlockPayload>("/api/payload");
}

// One request per page load, shared by every component that needs the payload.
let pending: Promise<GridlockPayload> | null = null;

export function usePayload(): PayloadState {
  const [state, setState] = useState<PayloadState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    pending ??= loadPayload();
    pending.then(
      (payload) => active && setState({ status: "ready", payload }),
      (error: unknown) => {
        pending = null;
        if (!active) return;
        const message = error instanceof Error ? error.message : String(error);
        setState({
          status: "error",
          message: "GridLock data is unavailable.",
          detail: message.includes("Failed to fetch")
            ? `Could not reach a GridLock API at ${runtimeConfig.apiBaseUrl} (not running, or a different server that blocks this origin). Start it with \`uv run gridlock serve\`.`
            : message,
        });
      },
    );
    return () => {
      active = false;
    };
  }, []);

  return state;
}
