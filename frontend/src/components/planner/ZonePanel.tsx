"use client";

import type { CSSProperties } from "react";

import type { GridlockPayload, Project, Zone } from "@/lib/contract";
import { countOf, formatDays, formatDistance, label, utilityColor, utilityName } from "@/lib/format";
import { topRelationship } from "@/lib/mapData";
import { spatialLabel } from "@/lib/presentation";

import { CoordinationImpact, ImpactMethodology } from "./CoordinationImpact";
import styles from "./panel.module.css";
import { Timeline } from "./Timeline";

interface Props {
  payload: GridlockPayload;
  zone: Zone;
  onInspect: (projectId: string) => void;
  // Compact: where and why. Expanded (about half the workspace): impact, timeline, evidence, methodology.
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
}

function ProjectLine({ project, payload, onInspect }: { project: Project; payload: GridlockPayload; onInspect: (id: string) => void }) {
  const { metadata } = payload;
  const resolution = project.geometryResolution;
  return (
    <li className={styles.projectLine}>
      <span className={styles.utilityBar} style={{ background: utilityColor(metadata, project.utility) }} />
      <span className={styles.projectText}>
        <span className="mono-plain">
          {project.id} · {utilityName(metadata, project.utility)}
        </span>
        <span>{project.projectName}</span>
        <span className="mono-plain">
          {label(metadata, "geometry_methods", resolution?.method)}
          {resolution?.isApproximation ? " · approximate" : ""} · evidence {label(metadata, "evidence_levels", project.evidence?.level)}
          {project.evidence ? ` ${project.evidence.score}/100` : ""}
        </span>
        <span className="mono-plain faint">
          Source: {project.source.document}, p. {project.source.page} · {project.source.projectIdRaw}
        </span>
      </span>
      <button type="button" className="button ghost small" onClick={() => onInspect(project.id)}>
        Evidence
      </button>
    </li>
  );
}

export function ZonePanel({ payload, zone, onInspect, expanded, onExpandedChange }: Props) {
  const { metadata } = payload;
  const projects = new Map(payload.projects.map((project) => [project.id, project]));
  const top = topRelationship(payload, zone);
  const a = top ? projects.get(top.projectA) : undefined;
  const b = top ? projects.get(top.projectB) : undefined;
  const spatial = top ? spatialLabel(metadata, top, projects) : null;
  const tier = top ? label(metadata, "spatial_tiers", top.spatialTier) : "";
  const impact = (payload.impact ?? []).find((item) => item.zoneId === zone.id);
  const members = zone.projectIds.map((id) => projects.get(id)).filter((project): project is Project => !!project);

  return (
    <div className={styles.panel} data-expanded={expanded}>
      <section className={styles.section}>
        <div className={styles.headerRow}>
          <p className="eyebrow">
            Zone {zone.rank} of {payload.zones.length} · {zone.utilities.map((code) => utilityName(metadata, code)).join(" × ")}
          </p>
          <button type="button" className={styles.expandButton} aria-expanded={expanded} onClick={() => onExpandedChange(!expanded)}>
            {expanded ? "Collapse ⤡" : "Details ⤢"}
          </button>
        </div>
        <h2 className={`display ${styles.zoneTitle}`}>{zone.name}</h2>
        <div className={styles.titleMeta}>
          <span className="tag" data-priority={zone.opportunityPriority}>
            {label(metadata, "priority", zone.opportunityPriority)} priority
          </span>
          <span className="mono-plain">
            {countOf(zone.projectIds.length, "project")} · {countOf(zone.relationshipIds.length, "relationship")}
          </span>
        </div>
      </section>

      {top && a && b && (
        <section className={styles.section}>
          <p className="eyebrow">Top coordination opportunity</p>
          <div className={styles.pair}>
            {[a, b].map((project, index) => (
              <button key={project.id} type="button" className={styles.pairProject} onClick={() => onInspect(project.id)}>
                <span className="mono-plain utility-ink" style={{ "--utility": utilityColor(metadata, project.utility) } as CSSProperties}>
                  {utilityName(metadata, project.utility)}
                </span>
                <span>{project.projectName}</span>
                {index === 0 && <span className={styles.times} aria-hidden>×</span>}
              </button>
            ))}
          </div>
          <dl className={styles.figures}>
            <div>
              <dt className="mono">Closest approach</dt>
              <dd className="display">{formatDistance(top.distanceKm, metadata)}</dd>
            </div>
            <div>
              <dt className="mono">{label(metadata, "timeline_types", top.timeline.type)}</dt>
              <dd className="display">{formatDays(top.timeline.gapDays)}</dd>
            </div>
            <div>
              <dt className="mono">Spatial relationship</dt>
              <dd className="display" title={spatial?.long}>
                {spatial?.short}
              </dd>
            </div>
          </dl>
        </section>
      )}

      {top && (
        <section className={styles.section}>
          <p className="eyebrow">Why GridLock flagged it</p>
          <ul className={styles.reasons}>
            {top.evidence.reasons.filter((reason) => reason.startsWith("✓")).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
            <li>
              {spatial && spatial.long !== tier ? `${spatial.long} · ${tier.toLowerCase()} tier` : `${tier} tier`} ·{" "}
              {label(metadata, "timeline_relevance", top.timeline.relevance).toLowerCase()} timeline relevance ·{" "}
              {label(metadata, "priority", top.opportunityPriority ?? undefined).toLowerCase()} opportunity priority
            </li>
            {top.timeline.isdWithinFiledSpan && (
              <li className="muted">
                Secondary context: one project’s in-service date falls inside the other’s filed project span. This is not a confirmed
                construction overlap.
              </li>
            )}
          </ul>
          <p className="eyebrow" style={{ marginTop: 20 }}>
            Likely coordination themes
          </p>
          <ul className={styles.themes}>
            {zone.coordinationThemes.map((theme) => (
              <li key={theme}>{label(metadata, "playbook", theme)}</li>
            ))}
          </ul>
        </section>
      )}

      {!expanded && (
        <section className={`${styles.section} ${styles.moreCta}`}>
          <p className="mono-plain">Coordination impact · timeline · evidence and sources · methodology</p>
          <button type="button" className="button ghost small" onClick={() => onExpandedChange(true)}>
            Open full analysis <span aria-hidden>→</span>
          </button>
        </section>
      )}

      {expanded && impact && <CoordinationImpact payload={payload} impact={impact} projects={projects} />}

      {expanded && (
        <>
          <section className={styles.section}>
            <p className="eyebrow">Timeline</p>
            <Timeline metadata={metadata} projects={members} top={top} onInspect={onInspect} />
          </section>

          {zone.warnings.length > 0 && (
            <section className={styles.section}>
              <p className="eyebrow">Caveats</p>
              <ul className={styles.caveats}>
                {zone.warnings.map((warning) => (
                  <li key={warning}>△ {warning}</li>
                ))}
              </ul>
            </section>
          )}

          <section className={styles.section}>
            <p className="eyebrow">Projects in this zone</p>
            <ul className={styles.projectList}>
              {members.map((project) => (
                <ProjectLine key={project.id} project={project} payload={payload} onInspect={onInspect} />
              ))}
            </ul>
          </section>

          <ImpactMethodology payload={payload} />
        </>
      )}
    </div>
  );
}
