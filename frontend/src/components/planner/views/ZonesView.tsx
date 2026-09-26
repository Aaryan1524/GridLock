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
  const [detailsOpen, setDetailsOpen] = useState(true);
  useEffect(() => setShowAll(false), [zone?.id]);

  return (
    <div className={styles.workspace} data-details={detailsOpen ? "open" : "closed"}>
      <ZoneRail payload={payload} selectedId={zone?.id ?? null} onSelect={onSelectZone} />
      <section className={styles.mapRegion} aria-label="Map" data-gust="2" data-gust-plain>
        <MapView payload={payload} zone={zone} showAll={showAll} onShowAllChange={setShowAll} onProjectClick={onInspect} />
        <PanelToggle open={detailsOpen} controls="zone-details" onToggle={() => setDetailsOpen((open) => !open)} />
      </section>
      <aside id="zone-details" className={styles.panel} aria-label="Selected zone" data-gust="3">
        {zone ? <ZonePanel payload={payload} zone={zone} onInspect={onInspect} /> : <p className="muted pad">No coordination zones in this payload.</p>}
      </aside>
    </div>
  );
}
