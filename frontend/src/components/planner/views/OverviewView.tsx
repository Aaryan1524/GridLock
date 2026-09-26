"use client";

import type { GridlockPayload, Zone } from "@/lib/contract";
import { countOf, formatDays, formatDistance, formatNumber, label, projectIndex, utilityName } from "@/lib/format";
import { priorityCounts, spatialLabel, topRelationshipOf } from "@/lib/presentation";

import { OverviewMap } from "../OverviewMap";
import styles from "./views.module.css";

interface Props {
  payload: GridlockPayload;
  selectedZoneId: string | null;
  onSelectZone: (zoneId: string) => void;
  onInvestigate: (zoneId: string) => void;
}

function ZoneSummary({ payload, zone, eyebrow, onInvestigate }: { payload: GridlockPayload; zone: Zone; eyebrow: string; onInvestigate: (id: string) => void }) {
  const { metadata } = payload;
  const top = topRelationshipOf(payload, zone);
  const projects = projectIndex(payload);
  const spatial = top ? spatialLabel(metadata, top, projects) : null;
  return (
    <div className={styles.zoneSummary}>
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
  if (!metrics) return <p className="mono pad">This payload has no metrics.</p>;
  const r = metrics.resolution;
  const notAssessed = r.notLocatedUnresolved + r.notLocatedNoNamedSite;
  const top = zones[0];
  const selected = zones.find((zone) => zone.id === selectedZoneId) ?? null;
  const utilities = Object.keys(metrics.projectsByUtility);

  const stats: { value: string; caption: string; note?: string }[] = [
    { value: formatNumber(metrics.projects), caption: "Projects analyzed" },
    { value: formatNumber(metrics.locatedProjects), caption: "Spatially assessed" },
    { value: formatNumber(notAssessed), caption: "Not spatially assessed", note: "Location unresolved" },
    { value: formatNumber(metrics.relationships), caption: "Cross-utility relationships" },
    { value: formatNumber(metrics.zones), caption: "Coordination zones" },
    { value: metrics.attentionCompressionRatio != null ? `${metrics.attentionCompressionRatio}×` : "—", caption: "Attention compression" },
  ];

  return (
    <div className={styles.overview}>
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

      <div className={styles.overviewBody}>
        <section className={styles.overviewMap} aria-label="Where the coordination situations are">
          <OverviewMap payload={payload} selectedId={selected?.id ?? null} onSelect={onSelectZone} />
          {selected && (
            <div className={styles.mapCard}>
              <ZoneSummary payload={payload} zone={selected} eyebrow={`Selected · zone ${selected.rank} of ${zones.length}`} onInvestigate={onInvestigate} />
            </div>
          )}
        </section>

        <aside className={styles.overviewSide}>
          {top && (
            <section className={styles.sideSection}>
              <ZoneSummary payload={payload} zone={top} eyebrow="Top opportunity · backend rank 1" onInvestigate={onInvestigate} />
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
                      <button key={zone.id} type="button" onClick={() => onSelectZone(zone.id)}>
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
    </div>
  );
}
