"use client";

import type { GridlockPayload } from "@/lib/contract";
import { countOf, formatDays, formatDistance, formatNumber, label, projectIndex } from "@/lib/format";
import { topRelationship } from "@/lib/mapData";
import { spatialLabel } from "@/lib/presentation";

import styles from "./planner.module.css";

interface Props {
  payload: GridlockPayload;
  selectedId: string | null;
  onSelect: (zoneId: string) => void;
}

/** Zones in backend rank order; each row shows its headline pair's own figures. */
export function ZoneRail({ payload, selectedId, onSelect }: Props) {
  const { metadata, zones } = payload;
  const projects = projectIndex(payload);
  return (
    <nav className={styles.rail} aria-label="Coordination zones">
      <div className={styles.railHead}>
        <p className="eyebrow">Ranked by opportunity priority</p>
        <h2 className={`display ${styles.railTitle}`}>
          {formatNumber(zones.length)} coordination {zones.length === 1 ? "zone needs" : "zones need"} review
        </h2>
      </div>
      <ol className={styles.zoneList}>
        {zones.map((zone) => {
          const headline = zone.headline;
          const selected = zone.id === selectedId;
          const top = topRelationship(payload, zone);
          const spatial = top ? spatialLabel(metadata, top, projects) : null;
          return (
            <li key={zone.id}>
              <button
                type="button"
                className={styles.zoneRow}
                data-selected={selected}
                aria-pressed={selected}
                onClick={() => onSelect(zone.id)}
              >
                <span className={styles.zoneRowTop}>
                  <span className="mono-plain">{String(zone.rank ?? "").padStart(2, "0")}</span>
                  <span className="tag" data-priority={zone.opportunityPriority}>
                    {label(metadata, "priority", zone.opportunityPriority)}
                  </span>
                </span>
                <span className={styles.zoneName}>{zone.name}</span>
                {headline && (
                  <span className={styles.zoneFigures}>
                    <span>
                      {formatDistance(headline.distanceKm, metadata)}
                      <span className="faint" title={spatial?.long}>
                        {" "}
                        · {spatial?.short ?? label(metadata, "spatial_tiers", headline.spatialTier)}
                      </span>
                    </span>
                    <span>
                      {formatDays(headline.gapDays)}
                      <span className="faint"> · {label(metadata, "timeline_types", headline.timelineType)}</span>
                    </span>
                  </span>
                )}
                <span className="mono-plain">
                  {countOf(zone.projectIds.length, "project")} · {countOf(zone.relationshipIds.length, "relationship")}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
