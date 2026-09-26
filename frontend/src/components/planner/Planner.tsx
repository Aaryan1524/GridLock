"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { usePayload } from "@/lib/api";
import type { GridlockPayload } from "@/lib/contract";
import { formatNumber, utilityName } from "@/lib/format";

import { StatusNotice } from "../shared/StatusNotice";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { MapView } from "./MapView";
import styles from "./planner.module.css";
import { ZonePanel } from "./ZonePanel";
import { ZoneRail } from "./ZoneRail";

function Workspace({ payload }: { payload: GridlockPayload }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("zone");
  const zones = payload.zones;
  const selected = useMemo(() => zones.find((zone) => zone.id === requested) ?? zones[0] ?? null, [zones, requested]);
  const [showAll, setShowAll] = useState(false);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const closeEvidence = useCallback(() => setInspecting(null), []);

  const select = useCallback(
    (zoneId: string) => {
      setShowAll(false);
      router.replace(`${pathname}?zone=${encodeURIComponent(zoneId)}`, { scroll: false });
    },
    [pathname, router],
  );

  return (
    <div className={styles.workspace}>
      <ZoneRail zones={zones} metadata={payload.metadata} selectedId={selected?.id ?? null} onSelect={select} />
      <section className={styles.mapRegion} aria-label="Map">
        <MapView payload={payload} zone={selected} showAll={showAll} onShowAllChange={setShowAll} onProjectClick={setInspecting} />
      </section>
      <aside className={styles.panel} aria-label="Selected zone">
        {selected ? (
          <ZonePanel payload={payload} zone={selected} onInspect={setInspecting} />
        ) : (
          <p className="muted pad">No coordination zones in this payload.</p>
        )}
      </aside>
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
