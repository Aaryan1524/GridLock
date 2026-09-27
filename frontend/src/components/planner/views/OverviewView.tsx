"use client";

import { useRef, useState } from "react";

import type { GridlockPayload, Zone } from "@/lib/contract";
import { countOf, formatDays, formatDistance, formatNumber, label, projectIndex, utilityName } from "@/lib/format";
import { topRelationship } from "@/lib/mapData";
import { priorityCounts, spatialLabel } from "@/lib/presentation";

import { OverviewMap } from "../OverviewMap";
import { PanelToggle } from "../PanelToggle";
import styles from "./overview.module.css";

interface Props {
  payload: GridlockPayload;
  selectedZoneId: string | null;
  onSelectZone: (zoneId: string) => void;
  onInvestigate: (zoneId: string) => void;
  onOpenQuality: () => void;
}

// Display arithmetic only (shares of a total for bar widths); every count comes from the payload.
const share = (value: number, total: number) => (total ? (value / total) * 100 : 0);

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
  const spatial = top ? spatialLabel(metadata, top, projectIndex(payload)) : null;
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

/** Counts per code, in the order the payload's label vocabulary lists them; zero counts are left out. */
function ordered(counts: Record<string, number>, vocabulary: Record<string, string> | undefined): [string, number][] {
  const order = Object.keys(vocabulary ?? {});
  const rank = (code: string) => (order.includes(code) ? order.indexOf(code) : order.length);
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => rank(a) - rank(b));
}

/** Overview = understand: the map of every zone first, then the network's shape as it scrolls up over the map. */
export function OverviewView({ payload, selectedZoneId, onSelectZone, onInvestigate, onOpenQuality }: Props) {
  const { metadata, metrics, zones, relationships } = payload;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const analysis = useRef<HTMLElement>(null);
  const dashboard = useRef<HTMLDivElement>(null);
  if (!metrics) return <p className="mono pad">This payload has no metrics.</p>;

  const top = zones[0];
  const selected = zones.find((zone) => zone.id === selectedZoneId) ?? null;
  const selectZone = (zoneId: string) => {
    onSelectZone(zoneId);
    setDetailsOpen(true);
  };
  // From the analysis below the map: back up to the map, with that zone selected.
  const showZone = (zoneId: string) => {
    selectZone(zoneId);
    scroller.current?.scrollTo({ top: 0 });
  };

  const totalRelationships = metrics.relationships;
  const busiest = [...zones].sort((a, b) => b.relationshipIds.length - a.relationshipIds.length)[0];
  const r = metrics.resolution;
  const assessed = r.locatedAutomatically + r.locatedHumanVerifiedOnly;
  const unresolved = r.notLocatedUnresolved + r.notLocatedNoNamedSite;
  const tiers = ordered(metrics.relationshipsByTier, metadata.labels.spatial_tiers);
  const relevanceCounts: Record<string, number> = {};
  for (const relationship of relationships) {
    relevanceCounts[relationship.timeline.relevance] = (relevanceCounts[relationship.timeline.relevance] ?? 0) + 1;
  }
  const relevance = ordered(relevanceCounts, metadata.labels.timeline_relevance);
  const utilities = Object.keys(metrics.projectsByUtility).map((code) => utilityName(metadata, code));
  const priorities = priorityCounts(zones);

  return (
    <div className={styles.overview} ref={scroller}>
      <div className={styles.stage}>
        <header className={styles.stageHead} data-gust="1">
          <h2 className={`display ${styles.headline}`}>
            {formatNumber(metrics.zones)} coordination zones <em>from {formatNumber(totalRelationships)} cross-utility relationships</em>
          </h2>
          <div className={styles.headMeta}>
            {metrics.attentionCompressionRatio != null && (
              <span>
                <span className={styles.compression}>{metrics.attentionCompressionRatio}×</span>{" "}
                <span className="mono">attention compression</span>
              </span>
            )}
            <button type="button" className={styles.scrollCue} onClick={() => analysis.current?.scrollIntoView()}>
              Network analysis <span aria-hidden>↓</span>
            </button>
          </div>
        </header>

        <div className={styles.body} data-details={detailsOpen ? "open" : "closed"}>
          <section className={styles.map} aria-label="Where the coordination situations are" data-gust="2" data-gust-plain>
            <OverviewMap payload={payload} selectedId={selected?.id ?? null} onSelect={selectZone} />
            <PanelToggle open={detailsOpen} controls="overview-details" onToggle={() => setDetailsOpen((open) => !open)} />
          </section>

          <aside id="overview-details" className={styles.side} aria-label="Overview details">
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
          </aside>
        </div>
      </div>

      <section ref={analysis} className={styles.analysis} aria-labelledby="analysis-heading">
        <div className={styles.analysisHead}>
          <p className="eyebrow">Network analysis</p>
          <h2 id="analysis-heading" className={`display ${styles.analysisTitle}`}>
            What is happening across the network
          </h2>
          <p className={styles.analysisLede}>
            The current state of the analysis of {utilities.join(" and ")} public plans, from a deterministic engine: the same inputs give
            the same output. Every figure is read from that output; there is no analysis history yet, so nothing here is a trend.
          </p>
          <button type="button" className={styles.moreArrow} aria-label="Scroll to the network dashboard" onClick={() => dashboard.current?.scrollIntoView()}>
            <svg viewBox="0 0 16 16" aria-hidden>
              <path d="M8 2.5v10M3.5 8.5 8 13l4.5-4.5" />
            </svg>
          </button>
        </div>

        <div className={styles.grid} ref={dashboard}>
          <section className={`${styles.panel} ${styles.panelWide}`} aria-label="Where the relationships concentrate">
            <p className="eyebrow">Opportunity concentration</p>
            <h3 className={`display ${styles.panelTitle}`}>
              {busiest.name} holds {formatNumber(busiest.relationshipIds.length)} of the {formatNumber(totalRelationships)} relationships
            </h3>
            <ul className={styles.rows}>
              {zones.map((zone) => (
                <li key={zone.id} className={styles.row}>
                  <span className={styles.rowLabel}>
                    <span className="tag" data-priority={zone.opportunityPriority}>
                      {label(metadata, "priority", zone.opportunityPriority)}
                    </span>
                    <button type="button" onClick={() => showZone(zone.id)} title="Show on the map">
                      {zone.name}
                    </button>
                  </span>
                  <span className={styles.track}>
                    <span
                      className={styles.fill}
                      data-priority={zone.opportunityPriority}
                      style={{ width: `${share(zone.relationshipIds.length, totalRelationships)}%` }}
                    />
                  </span>
                  <span className={styles.count}>
                    {formatNumber(zone.relationshipIds.length)} · {Math.round(share(zone.relationshipIds.length, totalRelationships))}%
                    <span className="faint"> · {countOf(zone.projectIds.length, "project")}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className={styles.panel} aria-label="Coordination priority">
            <p className="eyebrow">Coordination priority</p>
            <div className={styles.segments} role="img" aria-label={priorities.map(({ priority, zones: group }) => `${group.length} ${priority}`).join(", ")}>
              {zones.map((zone) => (
                <span key={zone.id} className={styles.segment} data-priority={zone.opportunityPriority} style={{ flex: 1 }} title={zone.name} />
              ))}
            </div>
            <ul className={styles.legend}>
              {priorities.map(({ priority, zones: group }) => (
                <li key={priority}>
                  <span className={styles.legendValue}>{group.length}</span>
                  <span className="tag" data-priority={priority}>
                    {label(metadata, "priority", priority)}
                  </span>
                </li>
              ))}
            </ul>
            <p className={styles.panelNote}>One segment per zone, in rank order.</p>
          </section>

          <section className={styles.panel} aria-label="Spatial coverage">
            <p className="eyebrow">Spatial coverage</p>
            <div className={styles.segments} role="img" aria-label={`${assessed} spatially assessed, ${unresolved} location unresolved`}>
              <span className={styles.segment} style={{ flex: assessed }} />
              <span className={styles.segment} data-tone="faint" style={{ flex: unresolved }} />
            </div>
            <ul className={styles.legend}>
              <li>
                <span className={styles.legendValue}>{formatNumber(assessed)}</span>
                <span className="mono">spatially assessed</span>
              </li>
              <li>
                <span className={styles.legendValue}>{formatNumber(unresolved)}</span>
                <span className="mono">location unresolved</span>
              </li>
            </ul>
            <p className={styles.panelNote}>Of {formatNumber(metrics.projects)} projects. Unresolved means unknown, never “no overlap”.</p>
            <button type="button" className={styles.link} onClick={onOpenQuality}>
              Data quality <span aria-hidden>→</span>
            </button>
          </section>

          <section className={styles.panel} aria-label="How close the relationships are">
            <p className="eyebrow">How close</p>
            <ul className={styles.rows}>
              {tiers.map(([tier, count]) => (
                <li key={tier} className={styles.row}>
                  <span className={styles.rowLabel}>{label(metadata, "spatial_tiers", tier)}</span>
                  <span className={styles.track}>
                    <span className={styles.fill} style={{ width: `${share(count, totalRelationships)}%` }} />
                  </span>
                  <span className={styles.count}>{formatNumber(count)}</span>
                </li>
              ))}
            </ul>
            <p className={styles.panelNote}>Relationships by spatial tier, closest first.</p>
          </section>

          <section className={styles.panel} aria-label="How timely the relationships are">
            <p className="eyebrow">How timely</p>
            <ul className={styles.rows}>
              {relevance.map(([code, count]) => (
                <li key={code} className={styles.row}>
                  <span className={styles.rowLabel}>{label(metadata, "timeline_relevance", code)}</span>
                  <span className={styles.track}>
                    <span className={styles.fill} data-tone="muted" style={{ width: `${share(count, totalRelationships)}%` }} />
                  </span>
                  <span className={styles.count}>{formatNumber(count)}</span>
                </li>
              ))}
            </ul>
            <p className={styles.panelNote}>Relationships by the engine’s timeline relevance for their in-service date gap.</p>
          </section>
        </div>
      </section>
    </div>
  );
}
