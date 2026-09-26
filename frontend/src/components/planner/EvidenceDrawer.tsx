"use client";

import { useEffect, useRef } from "react";

import type { GridlockPayload } from "@/lib/contract";
import { formatDate, label, utilityColor, utilityName } from "@/lib/format";

import styles from "./panel.module.css";

function osmLink(featureId: string): string | null {
  const [kind, id] = featureId.split("/");
  return ["node", "way", "relation"].includes(kind) && /^\d+$/.test(id ?? "") ? `https://www.openstreetmap.org/${kind}/${id}` : null;
}

interface Props {
  payload: GridlockPayload;
  projectId: string;
  onClose: () => void;
}

/** Full provenance for one project: source record, geometry method, matched features, evidence. */
export function EvidenceDrawer({ payload, projectId, onClose }: Props) {
  const { metadata } = payload;
  const project = payload.projects.find((item) => item.id === projectId);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!project) return null;
  const resolution = project.geometryResolution;
  const evidence = project.evidence;
  const warnings = [...(evidence?.warnings ?? []), ...project.warnings];
  const rawFields = Object.entries(project.source.rawFields);

  return (
    <div className={styles.drawerBackdrop} onClick={onClose}>
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.drawerHead}>
          <div>
            <p className="eyebrow">Evidence · {project.id}</p>
            <h2 id="evidence-title" className={`display ${styles.drawerTitle}`}>
              {project.projectName}
            </h2>
          </div>
          <button ref={closeRef} type="button" className="button ghost small" onClick={onClose} aria-label="Close evidence">
            Close
          </button>
        </header>

        <section className={styles.drawerSection}>
          <p className="eyebrow">Evidence quality</p>
          <p className={`display ${styles.evidenceScore}`}>
            {label(metadata, "evidence_levels", evidence?.level)} · {evidence?.score ?? "—"}/100
          </p>
          {evidence && Object.keys(evidence.breakdown).length > 0 && (
            <dl className={styles.breakdown}>
              {Object.entries(evidence.breakdown).map(([part, points]) => (
                <div key={part}>
                  <dt className="mono">{part}</dt>
                  <dd>{points}</dd>
                </div>
              ))}
            </dl>
          )}
          <ul className={styles.reasons}>
            {(evidence?.reasons ?? []).map((reason) => (
              <li key={reason} data-partial={reason.startsWith("△")}>
                {reason}
              </li>
            ))}
          </ul>
          {warnings.length > 0 && (
            <ul className={styles.caveats}>
              {warnings.map((warning) => (
                <li key={warning}>△ {warning.replace(/^△\s*/, "")}</li>
              ))}
            </ul>
          )}
        </section>

        <section className={styles.drawerSection}>
          <p className="eyebrow">Source record</p>
          <dl className={styles.facts}>
            <div>
              <dt>Utility</dt>
              <dd>
                <span className={styles.dot} style={{ background: utilityColor(metadata, project.utility) }} />
                {utilityName(metadata, project.utility)}
                {project.sponsor ? ` · sponsor ${project.sponsor}` : ""}
              </dd>
            </div>
            <div>
              <dt>Document</dt>
              <dd>{project.source.document}</dd>
            </div>
            <div>
              <dt>Page</dt>
              <dd>{project.source.page}</dd>
            </div>
            <div>
              <dt>Raw project ID</dt>
              <dd className="mono-plain">{project.source.projectIdRaw}</dd>
            </div>
            <div>
              <dt>In-service date</dt>
              <dd>{formatDate(project.plannedInServiceDate)}</dd>
            </div>
            {project.filedStartDate && (
              <div>
                <dt>Project start (as filed)</dt>
                <dd>{formatDate(project.filedStartDate)}</dd>
              </div>
            )}
            {project.voltageKv.length > 0 && (
              <div>
                <dt>Voltage</dt>
                <dd>{project.voltageKv.join(" / ")} kV</dd>
              </div>
            )}
            {rawFields.map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")} (raw)</dt>
                <dd className="mono-plain">{value}</dd>
              </div>
            ))}
          </dl>
          {project.description && <p className={styles.description}>{project.description}</p>}
        </section>

        <section className={styles.drawerSection}>
          <p className="eyebrow">Geometry</p>
          <p>
            {label(metadata, "geometry_methods", resolution?.method)}
            {resolution?.isApproximation ? <span className={styles.approx}> · approximate — not a surveyed route</span> : ""}
          </p>
          {!project.geometry && (
            <p className="muted">Location unresolved: this project is not spatially assessed. That means unknown, not “no overlap”.</p>
          )}
          <ul className={styles.matches}>
            {(resolution?.matches ?? []).map((match) => {
              const link = match.featureId ? osmLink(match.featureId) : null;
              return (
                <li key={`${match.endpoint}-${match.role}`}>
                  <span className={styles.matchHead}>
                    <span>{match.endpoint}</span>
                    <span className="mono-plain">{label(metadata, "endpoint_match_status", match.status)}</span>
                  </span>
                  {match.featureId && (
                    <span className="mono-plain">
                      {match.featureName ?? "Feature"} ·{" "}
                      {link ? (
                        <a href={link} target="_blank" rel="noreferrer">
                          {match.featureId}
                        </a>
                      ) : (
                        match.featureId
                      )}
                      {match.operator ? ` · ${match.operator}` : ""}
                      {match.voltageKv.length ? ` · ${match.voltageKv.join("/")} kV` : ""}
                    </span>
                  )}
                  {match.notes.map((note) => (
                    <span key={note} className="mono-plain faint">
                      {note}
                    </span>
                  ))}
                </li>
              );
            })}
          </ul>
        </section>
      </aside>
    </div>
  );
}
