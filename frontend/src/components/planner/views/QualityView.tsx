"use client";

import { Fragment } from "react";

import type { GridlockPayload } from "@/lib/contract";
import { formatNumber, label, utilityColor, utilityName } from "@/lib/format";

import styles from "./views.module.css";

interface Share {
  key: string;
  label: string;
  count: number;
  tone?: "muted";
}

/** One labelled count with a bar scaled to the total it belongs to. */
function Distribution({ rows, total }: { rows: Share[]; total: number }) {
  return (
    <dl className={styles.distribution}>
      {rows.map((row) => (
        <Fragment key={row.key}>
          <dt className={row.tone === "muted" ? "faint" : undefined}>{row.label}</dt>
          <dd>
            <span className={styles.bar} data-tone={row.tone}>
              <span style={{ width: `${total ? (row.count / total) * 100 : 0}%` }} />
            </span>
            <span className={styles.barCount}>
              {formatNumber(row.count)} <span className="faint">of {formatNumber(total)}</span>
            </span>
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}

/** Keep only categories the data actually contains, in the order the payload's labels list them. */
function present(counts: Record<string, number>, order: Record<string, string> | undefined): string[] {
  const keys = Object.keys(order ?? {}).filter((key) => (counts[key] ?? 0) > 0);
  return [...keys, ...Object.keys(counts).filter((key) => counts[key] > 0 && !keys.includes(key))];
}

/** What GridLock knows, how it knows it, and what it deliberately leaves unresolved. */
export function QualityView({ payload }: { payload: GridlockPayload }) {
  const { metadata, metrics, projects } = payload;
  if (!metrics) return <p className="mono pad">This payload has no metrics.</p>;
  const r = metrics.resolution;
  const notAssessed = r.notLocatedUnresolved + r.notLocatedNoNamedSite;
  const unresolvedMethod = "unresolved";

  const coverage: Share[] = [
    { key: "auto", label: "Located automatically from public geometry", count: r.locatedAutomatically },
    { key: "human", label: "Located only through a human-verified point", count: r.locatedHumanVerifiedOnly },
    { key: "unresolved", label: "Named sites not yet resolved", count: r.notLocatedUnresolved, tone: "muted" },
    { key: "no-site", label: "Title names no site", count: r.notLocatedNoNamedSite, tone: "muted" },
  ].filter((row) => row.count > 0) as Share[];

  const geometry: Share[] = present(metrics.geometryDistribution, metadata.labels.geometry_methods).map((key) => ({
    key,
    label: label(metadata, "geometry_methods", key),
    count: metrics.geometryDistribution[key],
    tone: key === unresolvedMethod ? "muted" : undefined,
  }));

  const evidence: Share[] = present(metrics.evidenceDistribution, metadata.labels.evidence_levels).map((key) => ({
    key,
    label: label(metadata, "evidence_levels", key),
    count: metrics.evidenceDistribution[key],
    tone: key === "UNRESOLVED" ? "muted" : undefined,
  }));

  const matches = projects.flatMap((project) => project.geometryResolution?.matches ?? []);
  const matchCounts: Record<string, number> = {};
  for (const match of matches) matchCounts[match.status] = (matchCounts[match.status] ?? 0) + 1;
  const endpointOutcomes: Share[] = present(matchCounts, metadata.labels.endpoint_match_status).map((key) => ({
    key,
    label: label(metadata, "endpoint_match_status", key),
    count: matchCounts[key],
  }));

  // Human-verified locations, grouped by the feature they place, with the reviewer's provenance note.
  const overrides = new Map<string, { endpoint: string; featureId: string | null; notes: string[]; projects: string[] }>();
  for (const project of projects) {
    for (const match of project.geometryResolution?.matches ?? []) {
      if (match.status !== "override") continue;
      const key = match.featureId ?? match.endpoint;
      const entry = overrides.get(key) ?? { endpoint: match.endpoint, featureId: match.featureId, notes: match.notes, projects: [] };
      entry.projects.push(project.projectName);
      overrides.set(key, entry);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader} data-gust="1">
        <p className="eyebrow">Data quality</p>
        <h2 className={`display ${styles.pageTitle}`}>GridLock preserves uncertainty instead of guessing.</h2>
        <p className={styles.pageLede}>
          Projects without verified public geometry remain unresolved and are excluded from spatial claims. Every figure on this page
          is read from the analysis output.
        </p>
      </header>

      <section className={styles.qualitySection} aria-labelledby="coverage-heading" data-gust="2">
        <div className={styles.qualityHead}>
          <h3 id="coverage-heading" className="eyebrow">
            Spatial coverage
          </h3>
          <p className={`display ${styles.coverageFigure}`}>
            {formatNumber(metrics.locatedProjects)}
            <span className="faint"> / {formatNumber(metrics.projects)}</span>
          </p>
          <p className="mono-plain">
            projects spatially assessed · {formatNumber(notAssessed)} not spatially assessed
          </p>
        </div>
        <div className={styles.qualityBody}>
          <Distribution rows={coverage} total={metrics.projects} />
          <table className={`${styles.table} ${styles.compactTable}`}>
            <thead>
              <tr>
                <th scope="col">Utility</th>
                <th scope="col">Projects</th>
                <th scope="col">Assessed</th>
                <th scope="col">Not assessed</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.resolutionByUtility).map(([code, breakdown]) => {
                const assessed = breakdown.locatedAutomatically + breakdown.locatedHumanVerifiedOnly;
                const missing = breakdown.notLocatedUnresolved + breakdown.notLocatedNoNamedSite;
                return (
                  <tr key={code}>
                    <td>
                      <span className={styles.utility}>
                        <span className={styles.swatch} style={{ background: utilityColor(metadata, code) }} />
                        {utilityName(metadata, code)}
                      </span>
                    </td>
                    <td>{formatNumber(metrics.projectsByUtility[code] ?? assessed + missing)}</td>
                    <td>
                      {formatNumber(assessed)}
                      {breakdown.locatedHumanVerifiedOnly > 0 && (
                        <span className="mono-plain faint"> incl. {formatNumber(breakdown.locatedHumanVerifiedOnly)} human-verified</span>
                      )}
                    </td>
                    <td className="faint">{formatNumber(missing)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.qualitySection} aria-labelledby="geometry-heading" data-gust="3">
        <div className={styles.qualityHead}>
          <h3 id="geometry-heading" className="eyebrow">
            Geometry method
          </h3>
          <p className="mono-plain">How each project’s location was established. Only methods that occur are listed.</p>
        </div>
        <div className={styles.qualityBody}>
          <Distribution rows={geometry} total={metrics.projects} />
        </div>
      </section>

      <section className={styles.qualitySection} aria-labelledby="evidence-heading" data-gust="4">
        <div className={styles.qualityHead}>
          <h3 id="evidence-heading" className="eyebrow">
            Evidence Quality
          </h3>
          <p className="mono-plain">How well each project’s location is supported. Kept separate from Opportunity Priority.</p>
        </div>
        <div className={styles.qualityBody}>
          <Distribution rows={evidence} total={metrics.projects} />
        </div>
      </section>

      <section className={styles.qualitySection} aria-labelledby="endpoints-heading" data-gust="5">
        <div className={styles.qualityHead}>
          <h3 id="endpoints-heading" className="eyebrow">
            Endpoint matching
          </h3>
          <p className="mono-plain">
            {formatNumber(matches.length)} endpoint lookups across {formatNumber(metrics.projectsWithNamedEndpoints)} projects that name a
            site.
          </p>
        </div>
        <div className={styles.qualityBody}>
          <Distribution rows={endpointOutcomes} total={matches.length} />
        </div>
      </section>

      <section className={styles.qualitySection} aria-labelledby="sources-heading" data-gust="6">
        <div className={styles.qualityHead}>
          <h3 id="sources-heading" className="eyebrow">
            Source provenance
          </h3>
          <p className="mono-plain">The public inputs this analysis was built from.</p>
        </div>
        <div className={styles.qualityBody}>
          <ul className={styles.sources}>
            {metadata.sources.map((source) => (
              <li key={`${source.kind}-${source.name}`}>
                <span className="mono">{source.kind.replaceAll("_", " ")}</span>
                <span>{source.name}</span>
                {(source.retrievedAt || source.sha256) && (
                  <span className="mono-plain faint">
                    {source.retrievedAt && <>retrieved {source.retrievedAt.slice(0, 10)}</>}
                    {source.retrievedAt && source.sha256 && " · "}
                    {source.sha256 && <>sha256 {source.sha256.slice(0, 12)}…</>}
                  </span>
                )}
              </li>
            ))}
            {[...overrides.values()].map((override) => (
              <li key={override.featureId ?? override.endpoint}>
                <span className="mono">human-verified location</span>
                <span>
                  {override.endpoint}
                  {override.featureId && <span className="mono-plain faint"> · {override.featureId}</span>}
                  <span className="mono-plain faint"> · used by {override.projects.length} {override.projects.length === 1 ? "project" : "projects"}</span>
                </span>
                {override.notes.map((note) => (
                  <span key={note} className={styles.sourceNote}>
                    {note}
                  </span>
                ))}
              </li>
            ))}
            {(metadata.impactAssumptions ?? []).map((item) => (
              <li key={item.id}>
                <span className="mono">impact assumption {item.id}</span>
                <span>
                  {item.value} {item.unit} · {item.label}
                </span>
                <span className={styles.sourceNote}>
                  {item.sourceUrl ? (
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                      {item.sourceTitle} ↗
                    </a>
                  ) : (
                    item.sourceTitle
                  )}{" "}
                  · {item.sourceLocator}. {item.caveat} Approved by {item.approvedBy}, {item.approvedOn}.
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
