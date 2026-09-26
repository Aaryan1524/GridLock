"use client";

import { useMemo, useState } from "react";

import type { GridlockPayload } from "@/lib/contract";
import { formatNumber, label, utilityColor, utilityName } from "@/lib/format";
import {
  COORDINATION_STATUS_LABELS,
  type CoordinationStatus,
  LOCATION_STATUS_LABELS,
  type LocationStatus,
  projectRows,
} from "@/lib/presentation";

import styles from "./views.module.css";

interface Props {
  payload: GridlockPayload;
  onInspect: (projectId: string) => void;
  onOpenZone: (zoneId: string) => void;
}

const ALL = "";

/** Every analyzed project, including the ones GridLock could not place on the map. */
export function ProjectsView({ payload, onInspect, onOpenZone }: Props) {
  const { metadata } = payload;
  const rows = useMemo(() => projectRows(payload), [payload]);
  const [query, setQuery] = useState("");
  const [utility, setUtility] = useState(ALL);
  const [location, setLocation] = useState(ALL);
  const [evidence, setEvidence] = useState(ALL);
  const [coordination, setCoordination] = useState(ALL);

  // Filter options list only values present in the data, in the order the payload labels them.
  const present = <T extends string>(values: T[], order: string[]) => order.filter((value) => values.includes(value as T)) as T[];
  const utilities = present(rows.map((row) => row.project.utility), Object.keys(metadata.utilityNames));
  const locations = present(rows.map((row) => row.location), Object.keys(LOCATION_STATUS_LABELS));
  const evidenceLevels = present(rows.map((row) => row.project.evidence?.level ?? ""), Object.keys(metadata.labels.evidence_levels ?? {}));
  const coordinations = present(rows.map((row) => row.coordination), Object.keys(COORDINATION_STATUS_LABELS));

  const needle = query.trim().toLowerCase();
  const visible = rows.filter(({ project, location: loc, coordination: coord }) => {
    if (utility && project.utility !== utility) return false;
    if (location === "assessed" ? loc === "unresolved" : location && loc !== location) return false;
    if (evidence && project.evidence?.level !== evidence) return false;
    if (coordination && coord !== coordination) return false;
    if (!needle) return true;
    return [project.projectName, project.id, project.source.projectIdRaw, project.sponsor ?? ""].some((text) => text.toLowerCase().includes(needle));
  });
  const filtered = Boolean(needle || utility || location || evidence || coordination);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <p className="eyebrow">Projects</p>
        <h2 className={`display ${styles.pageTitle}`}>Every project analyzed</h2>
        <p className={styles.pageLede}>
          Projects GridLock could not place on the map stay in the list as <strong>not spatially assessed</strong>. That is an
          unknown, not a finding of no overlap.
        </p>
      </header>

      <div className={styles.filters} role="search">
        <input
          type="search"
          className={styles.search}
          placeholder="Search name, project ID or sponsor"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search projects"
        />
        <select value={utility} onChange={(event) => setUtility(event.target.value)} aria-label="Utility">
          <option value={ALL}>All utilities</option>
          {utilities.map((code) => (
            <option key={code} value={code}>
              {utilityName(metadata, code)}
            </option>
          ))}
        </select>
        <select value={location} onChange={(event) => setLocation(event.target.value)} aria-label="Location status">
          <option value={ALL}>Any location status</option>
          <option value="assessed">Spatially assessed</option>
          {locations.map((status) => (
            <option key={status} value={status}>
              {LOCATION_STATUS_LABELS[status as LocationStatus]}
            </option>
          ))}
        </select>
        <select value={evidence} onChange={(event) => setEvidence(event.target.value)} aria-label="Evidence Quality">
          <option value={ALL}>Any Evidence Quality</option>
          {evidenceLevels.map((level) => (
            <option key={level} value={level}>
              {label(metadata, "evidence_levels", level)}
            </option>
          ))}
        </select>
        <select value={coordination} onChange={(event) => setCoordination(event.target.value)} aria-label="Coordination status">
          <option value={ALL}>Any coordination status</option>
          {coordinations.map((status) => (
            <option key={status} value={status}>
              {COORDINATION_STATUS_LABELS[status as CoordinationStatus]}
            </option>
          ))}
        </select>
        <span className={`mono ${styles.resultCount}`} aria-live="polite">
          {formatNumber(visible.length)} of {formatNumber(rows.length)}
        </span>
        {filtered && (
          <button
            type="button"
            className="button ghost small"
            onClick={() => {
              setQuery("");
              setUtility(ALL);
              setLocation(ALL);
              setEvidence(ALL);
              setCoordination(ALL);
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Project</th>
              <th scope="col">Utility</th>
              <th scope="col">Location status</th>
              <th scope="col">Geometry method</th>
              <th scope="col">Evidence Quality</th>
              <th scope="col">Coordination status</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(({ project, location: loc, coordination: coord, zones, relationships }) => (
              <tr
                key={project.id}
                tabIndex={0}
                data-location={loc}
                onClick={() => onInspect(project.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onInspect(project.id);
                  }
                }}
                aria-label={`Open evidence for ${project.projectName}`}
              >
                <td>
                  <span className={styles.projectName}>{project.projectName}</span>
                  <span className="mono-plain faint">
                    {project.source.projectIdRaw} · p. {project.source.page}
                  </span>
                </td>
                <td>
                  <span className={styles.utility}>
                    <span className={styles.swatch} style={{ background: utilityColor(metadata, project.utility) }} />
                    {utilityName(metadata, project.utility)}
                  </span>
                </td>
                <td>
                  <span className={styles.status} data-status={loc}>
                    {LOCATION_STATUS_LABELS[loc]}
                  </span>
                </td>
                <td className={loc === "unresolved" ? "faint" : undefined}>
                  {label(metadata, "geometry_methods", project.geometryResolution?.method ?? "unresolved")}
                </td>
                <td>
                  {project.evidence ? (
                    <span className={loc === "unresolved" ? "faint" : undefined}>
                      {label(metadata, "evidence_levels", project.evidence.level)}
                      {loc !== "unresolved" && <span className="mono-plain faint"> {project.evidence.score}</span>}
                    </span>
                  ) : (
                    <span className="faint">—</span>
                  )}
                </td>
                <td>
                  <span className={styles.status} data-status={coord}>
                    {COORDINATION_STATUS_LABELS[coord]}
                  </span>
                  {zones.length > 0 && (
                    <span className={styles.zoneLinks}>
                      {zones.map((zone) => (
                        <button
                          key={zone.id}
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onOpenZone(zone.id);
                          }}
                        >
                          {zone.name}
                        </button>
                      ))}
                      <span className="mono-plain faint">
                        · {relationships} {relationships === 1 ? "relationship" : "relationships"}
                      </span>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 && <p className="mono pad">No projects match these filters.</p>}
      </div>
    </div>
  );
}
