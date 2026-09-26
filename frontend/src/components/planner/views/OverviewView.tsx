"use client";

import { useState } from "react";

import type { GridlockPayload, Zone } from "@/lib/contract";
import { countOf, formatDays, formatDistance, formatNumber, label, projectIndex, utilityName } from "@/lib/format";
import { topRelationship } from "@/lib/mapData";
import { priorityCounts, spatialLabel } from "@/lib/presentation";

import { OverviewMap } from "../OverviewMap";
import { PanelToggle } from "../PanelToggle";
import styles from "./views.module.css";

interface Props {
  payload: GridlockPayload;
  selectedZoneId: string | null;
  onSelectZone: (zoneId: string) => void;
  onInvestigate: (zoneId: string) => void;
}

function ZoneSummary({
  payload,
  zone,
  eyebrow,
  role,
  onInvestigate,
}: {
  payload: GridlockPayload;
  zone: Zone;
  eyebrow: string;
  role: "selected" | "top";
  onInvestigate: (id: string) => void;
}) {
  const { metadata } = payload;
  const top = topRelationship(payload, zone);
  const projects = projectIndex(payload);
  const spatial = top ? spatialLabel(metadata, top, projects) : null;
  return (
    <div className={styles.zoneSummary} data-summary={role}>
      <p className="eyebrow">{eyebrow}</p>
      <h3 className={`display ${styles.summaryName}`}>{zone.name}</h3>
      <div className={styles.summaryMeta}>
        <span className="tag" data-priority={zone.opportunityPriority}>
          {label(metadata, "priority", zone.opportunityPriority)} priority
        </span>
        <span className="mono-plain">
          {countOf(zone.projectIds.length, "project")} · {countOf(zone.relationshipIds.length, "relationship")}
        </span>
      </div>
      {top && (
        <dl className={styles.summaryFigures}>
          <div>
            <dt className="mono">Closest approach</dt>
            <dd>{formatDistance(top.distanceKm, metadata)}</dd>
          </div>
          <div>
            <dt className="mono">{label(metadata, "timeline_types", top.timeline.type)}</dt>
            <dd>{formatDays(top.timeline.gapDays)}</dd>
          </div>
          <div>
            <dt className="mono">Spatial relationship</dt>
            <dd title={spatial?.long}>{spatial?.short}</dd>
          </div>
        </dl>
      )}
      <button type="button" className="button small" onClick={() => onInvestigate(zone.id)}>
        Investigate zone <span aria-hidden>→</span>
      </button>
    </div>
  );
}

/** Broad system state: what was analyzed, where the coordination situations are, and how much is unknown. */
export function OverviewView({ payload, selectedZoneId, onSelectZone, onInvestigate }: Props) {
  const { metadata, metrics, zones } = payload;
  const [detailsOpen, setDetailsOpen] = useState(false);
  if (!metrics) return <p className="mono pad">This payload has no metrics.</p>;
  const r = metrics.resolution;
  const notAssessed = r.notLocatedUnresolved + r.notLocatedNoNamedSite;
  const top = zones[0];
  const selected = zones.find((zone) => zone.id === selectedZoneId) ?? null;
  const utilities = Object.keys(metrics.projectsByUtility);
  // The map leads; the details column slides out when a zone is chosen and can be retracted again.
  const selectZone = (zoneId: string) => {
    onSelectZone(zoneId);
    setDetailsOpen(true);
  };

  const stats: { value: string; caption: string; note?: string }[] = [
    { value: formatNumber(metrics.projects), caption: "Projects analyzed" },
    { value: formatNumber(metrics.locatedProjects), caption: "Spatially assessed" },
    { value: formatNumber(notAssessed), caption: "Not spatially assessed", note: "Location unresolved" },
    { value: formatNumber(metrics.relationships), caption: "Cross-utility relationships" },
    { value: formatNumber(metrics.zones), caption: "Coordination zones" },
    { value: metrics.attentionCompressionRatio != null ? `${metrics.attentionCompressionRatio}×` : "—", caption: "Attention compression" },
  ];

  const statsStrip = (
    <>
      <section className={styles.stats} aria-label="Analysis summary">
        {stats.map((stat) => (
          <div key={stat.caption} className={styles.stat}>
            <span className={`display ${styles.statValue}`}>{stat.value}</span>
            <span className="eyebrow">{stat.caption}</span>
            {stat.note && <span className="mono-plain faint">{stat.note}</span>}
          </div>
        ))}
      </section>
      <p className={styles.coverageLine}>
        Of all {formatNumber(metrics.projects)} projects, {formatNumber(metrics.locatedProjects)} are spatially assessed and{" "}
        {formatNumber(notAssessed)} have an unresolved location ({formatNumber(r.notLocatedUnresolved)} with named sites not yet
        resolved, {formatNumber(r.notLocatedNoNamedSite)} whose titles name no site). Unresolved means unknown — never “no overlap”.
      </p>
    </>
  );

  return (
    <div className={styles.overview}>
      <div className={styles.overviewBody} data-details={detailsOpen ? "open" : "closed"}>
        <section className={styles.overviewMap} aria-label="Where the coordination situations are">
          <OverviewMap payload={payload} selectedId={selected?.id ?? null} onSelect={selectZone} />
          <PanelToggle open={detailsOpen} controls="overview-details" onToggle={() => setDetailsOpen((open) => !open)} />
        </section>

        <aside id="overview-details" className={styles.overviewSide} aria-label="Overview details">
          {selected && (
            <section className={styles.sideSection}>
              <ZoneSummary
                payload={payload}
                zone={selected}
                role="selected"
                eyebrow={selected.id === top?.id ? `Selected · top opportunity · backend rank ${selected.rank}` : `Selected · zone ${selected.rank} of ${zones.length}`}
                onInvestigate={onInvestigate}
              />
            </section>
          )}
          {top && top.id !== selected?.id && (
            <section className={styles.sideSection}>
              <ZoneSummary payload={payload} zone={top} role="top" eyebrow={`Top opportunity · backend rank ${top.rank}`} onInvestigate={onInvestigate} />
            </section>
          )}

          <section className={styles.sideSection}>
            <p className="eyebrow">Coordination priority</p>
            <ul className={styles.priorityList}>
              {priorityCounts(zones).map(({ priority, zones: group }) => (
                <li key={priority}>
                  <span className={`display ${styles.priorityCount}`}>{group.length}</span>
                  <span className="tag" data-priority={priority}>
                    {label(metadata, "priority", priority)}
                  </span>
                  <span className={styles.priorityZones}>
                    {group.map((zone) => (
                      <button key={zone.id} type="button" onClick={() => selectZone(zone.id)}>
                        {zone.name}
                      </button>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className={styles.sideSection}>
            <p className="eyebrow">Analysis snapshot</p>
            <dl className={styles.snapshot}>
              <div>
                <dt>Utilities</dt>
                <dd>
                  {utilities.length} · {utilities.map((code) => utilityName(metadata, code)).join(", ")}
                </dd>
              </div>
              <div>
                <dt>Projects analyzed</dt>
                <dd>{formatNumber(metrics.projects)}</dd>
              </div>
              <div>
                <dt>Spatially assessed</dt>
                <dd>{formatNumber(metrics.locatedProjects)}</dd>
              </div>
              <div>
                <dt>Not spatially assessed</dt>
                <dd>{formatNumber(notAssessed)}</dd>
              </div>
              <div>
                <dt>Relationships</dt>
                <dd>{formatNumber(metrics.relationships)}</dd>
              </div>
              <div>
                <dt>Zones</dt>
                <dd>{formatNumber(metrics.zones)}</dd>
              </div>
              <div>
                <dt>Engine</dt>
                <dd>Deterministic — same inputs, same output</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
      {statsStrip}
    </div>
  );
}
