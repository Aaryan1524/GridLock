"use client";

import { useCallback, useMemo, useState } from "react";

import { usePayload } from "@/lib/api";
import type { GridlockPayload } from "@/lib/contract";
import { usePlannerState } from "@/lib/plannerState";

import { SiteNav } from "../shared/SiteNav";
import { StatusNotice } from "../shared/StatusNotice";
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
            onOpenQuality={() => navigate({ view: "quality" })}
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

  return (
    <main className={styles.page}>
      <SiteNav />
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
