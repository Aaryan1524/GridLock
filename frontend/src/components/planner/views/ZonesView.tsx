"use client";

import { useEffect, useState } from "react";

import type { GridlockPayload, Zone } from "@/lib/contract";

import { MapView } from "../MapView";
import { PanelToggle } from "../PanelToggle";
import styles from "../planner.module.css";
import { ZonePanel } from "../ZonePanel";
import { ZoneRail } from "../ZoneRail";

interface Props {
  payload: GridlockPayload;
  zone: Zone | null;
  onSelectZone: (zoneId: string) => void;
  onInspect: (projectId: string) => void;
}

/** The V1 coordination-zone investigation (rail, map, panel), unchanged apart from its host. */
export function ZonesView({ payload, zone, onSelectZone, onInspect }: Props) {
  const [showAll, setShowAll] = useState(false);
  // closed (map only) · compact (where and why) · expanded (about half the workspace: impact, evidence, method).
  const [drawer, setDrawer] = useState<"closed" | "compact" | "expanded">("compact");
  const detailsOpen = drawer !== "closed";
  // Choosing another zone shows its compact summary first; the deep view is always the planner's choice.
  useEffect(() => {
    setShowAll(false);
    setDrawer((current) => (current === "expanded" ? "compact" : current));
  }, [zone?.id]);

  return (
    <div className={styles.workspace} data-details={drawer}>
      <ZoneRail payload={payload} selectedId={zone?.id ?? null} onSelect={onSelectZone} />
      <section className={styles.mapRegion} aria-label="Map" data-gust="2" data-gust-plain>
        <MapView payload={payload} zone={zone} showAll={showAll} onShowAllChange={setShowAll} onProjectClick={onInspect} />
        <PanelToggle open={detailsOpen} controls="zone-details" onToggle={() => setDrawer(detailsOpen ? "closed" : "compact")} />
      </section>
      <aside id="zone-details" className={styles.panel} aria-label="Selected zone" data-gust="3">
        {zone ? <ZonePanel
            payload={payload}
            zone={zone}
            onInspect={onInspect}
            expanded={drawer === "expanded"}
            onExpandedChange={(expand) => setDrawer(expand ? "expanded" : "compact")}
          /> : <p className="muted pad">No coordination zones in this payload.</p>}
      </aside>
    </div>
  );
}
