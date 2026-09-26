"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { usePayload } from "@/lib/api";
import type { GridlockPayload } from "@/lib/contract";
import { formatNumber, utilityName } from "@/lib/format";
import { usePlannerState } from "@/lib/plannerState";

import { StatusNotice } from "../shared/StatusNotice";
import { ThemeToggle } from "../shared/ThemeToggle";
import { EvidenceDrawer } from "./EvidenceDrawer";
import styles from "./planner.module.css";
import { PlannerNav } from "./PlannerNav";
import { OverviewView } from "./views/OverviewView";
import { ProjectsView } from "./views/ProjectsView";
import { QualityView } from "./views/QualityView";
import { ZonesView } from "./views/ZonesView";

function Workspace({ payload }: { payload: GridlockPayload }) {
  const { view, zoneId, navigate } = usePlannerState();
  const zone = useMemo(() => payload.zones.find((item) => item.id === zoneId) ?? payload.zones[0] ?? null, [payload.zones, zoneId]);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const closeEvidence = useCallback(() => setInspecting(null), []);

  return (
    <div className={styles.shell}>
      <PlannerNav payload={payload} view={view} onChange={(next) => navigate({ view: next })} />
      <div className={styles.viewport}>
        {view === "zones" && (
          <ZonesView payload={payload} zone={zone} onSelectZone={(id) => navigate({ view: "zones", zone: id })} onInspect={setInspecting} />
        )}
        {view === "overview" && (
          <OverviewView
            payload={payload}
            selectedZoneId={zoneId}
            onSelectZone={(id) => navigate({ view: "overview", zone: id })}
            onInvestigate={(id) => navigate({ view: "zones", zone: id })}
          />
        )}
        {view === "projects" && (
          <ProjectsView payload={payload} onInspect={setInspecting} onOpenZone={(id) => navigate({ view: "zones", zone: id })} />
        )}
        {view === "quality" && <QualityView payload={payload} />}
      </div>
      {inspecting && <EvidenceDrawer payload={payload} projectId={inspecting} onClose={closeEvidence} />}
    </div>
  );
}

export function Planner() {
  const state = usePayload();
  const payload = state.status === "ready" ? state.payload : null;
  const metrics = payload?.metrics;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <Link href="/" className={styles.wordmark}>
            GridLock
          </Link>
          <span className="muted">Cross-utility coordination planner</span>
        </div>
        <div className={styles.headerActions}>
          {payload && metrics && (
            <dl className={styles.headerStats}>
              <div>
                <dt className="mono">Zones</dt>
                <dd>{formatNumber(metrics.zones)}</dd>
              </div>
              <div>
                <dt className="mono">Relationships</dt>
                <dd>{formatNumber(metrics.relationships)}</dd>
              </div>
              <div>
                <dt className="mono">Compression</dt>
                <dd>{metrics.attentionCompressionRatio != null ? `${metrics.attentionCompressionRatio}×` : "—"}</dd>
              </div>
              <div className={styles.headerSource}>
                <dt className="mono">Sources</dt>
                <dd className="mono-plain">
                  {Object.keys(metrics.projectsByUtility)
                    .map((code) => utilityName(payload.metadata, code))
                    .join(" + ")}{" "}
                  · public planning data
                </dd>
              </div>
            </dl>
          )}
          <ThemeToggle />
        </div>
      </header>
      {state.status === "ready" ? (
        <Workspace payload={state.payload} />
      ) : (
        <div className={styles.status}>
          <StatusNotice state={state} />
        </div>
      )}
    </main>
  );
}
