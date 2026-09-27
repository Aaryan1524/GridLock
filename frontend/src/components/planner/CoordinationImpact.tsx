"use client";

import type { GridlockPayload, ImpactRange, Project, ZoneImpact } from "@/lib/contract";
import { label, utilityName } from "@/lib/format";

import styles from "./panel.module.css";

// Display only: every number, range and sentence here comes from payload.impact (see backend/src/gridlock/impact).
function range(value: ImpactRange | null | undefined, format: (n: number) => string = (n) => n.toLocaleString("en-US")): string {
  if (!value) return "—";
  if (value.low === null || value.low === undefined) return `up to ${format(value.high)}`;
  return value.low === value.high ? format(value.high) : `${format(value.low)}–${format(value.high)}`;
}

const usd = (value: number) => `$${Math.round(value).toLocaleString("en-US")}`;

function names(ids: string[], projects: Map<string, Project>): string {
  return ids.map((id) => projects.get(id)?.projectName ?? id).join(" × ");
}

interface Props {
  payload: GridlockPayload;
  impact: ZoneImpact;
  projects: Map<string, Project>;
}

/** S2: what coordinating this zone's timely pairs might avoid, with the working and the approved assumptions. */
export function CoordinationImpact({ payload, impact, projects }: Props) {
  const { metadata } = payload;
  const assumptions = metadata.impactAssumptions ?? [];
  const cited = new Set(impact.steps.flatMap((step) => step.assumptionIds));
  const costedUtilities = [
    ...new Set(impact.clusters.flatMap((cluster) => cluster.costedProjectIds).map((id) => projects.get(id)?.utility).filter(Boolean)),
  ] as string[];
  const pairs = impact.clusters.filter((cluster, index, all) => all.findIndex((other) => other.projectIds.join() === cluster.projectIds.join()) === index);

  return (
    <section className={styles.section} aria-labelledby="impact-heading">
      <p id="impact-heading" className="eyebrow">
        Coordination impact
      </p>
      <p className={styles.impactLabel}>{impact.label}</p>

      {impact.status === "NOT_ESTIMATED" ? (
        <>
          <p className={styles.impactReason}>{impact.reason}</p>
          {impact.themes.length > 0 && (
            <p className="mono-plain">Coordination themes: {impact.themes.map((theme) => label(metadata, "playbook", theme)).join(" · ")}</p>
          )}
        </>
      ) : (
        <>
          <p className="mono-plain">
            Potential coordination: {impact.themes.map((theme) => label(metadata, "playbook", theme)).join(" · ")}
          </p>

          <dl className={styles.impactFigures}>
            {impact.stagingYards && (
              <div>
                <dt className="mono">Shared staging</dt>
                <dd className="display">{range(impact.temporaryAcres)} acres</dd>
                <dd className="mono-plain">
                  {range(impact.stagingYards)} {impact.stagingYards.high === 1 ? "yard" : "yards"} of temporary footprint potentially avoided
                </dd>
              </div>
            )}
            {impact.mobilizations && (
              <div>
                <dt className="mono">Duplicate mobilizations</dt>
                <dd className="display">{range(impact.mobilizations)}</dd>
                <dd className="mono-plain">potentially avoided</dd>
              </div>
            )}
            {impact.expectedSavingUsd && (
              <div>
                <dt className="mono">Expected saving</dt>
                <dd className="display">{range(impact.expectedSavingUsd, usd)}</dd>
                <dd className="mono-plain">
                  of {range(impact.budgetInPlayUsd, usd)} budget in play
                  {costedUtilities.length > 0 && <> · {costedUtilities.map((code) => utilityName(metadata, code)).join(", ")} published costs</>}
                </dd>
              </div>
            )}
          </dl>

          <ul className={styles.impactPairs}>
            {pairs.map((cluster) => (
              <li key={cluster.projectIds.join()}>{names(cluster.projectIds, projects)}</li>
            ))}
          </ul>

          <details className={styles.impactWorking}>
            <summary className="mono">How this was worked out</summary>
            <ol>
              {impact.steps.map((step) => (
                <li key={step.label}>
                  <span className={styles.impactStepLabel}>{step.label}</span>
                  <span>{step.working}</span>
                  {step.assumptionIds.length > 0 && <span className="mono-plain faint"> [{step.assumptionIds.join(", ")}]</span>}
                </li>
              ))}
            </ol>
          </details>

          {impact.notes.length > 0 && (
            <ul className={styles.caveats}>
              {impact.notes.map((note) => (
                <li key={note}>△ {note}</li>
              ))}
            </ul>
          )}

          <p className="eyebrow" style={{ marginTop: 20 }}>
            Assumptions
          </p>
          <ul className={styles.impactAssumptions}>
            {assumptions
              .filter((item) => cited.has(item.id))
              .map((item) => (
                <li key={item.id}>
                  <span className="mono">{item.id}</span>
                  <span>
                    <strong>{item.value}</strong> {item.unit} · {item.label}
                  </span>
                  <span className="mono-plain">
                    {item.sourceUrl ? (
                      <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                        {item.sourceTitle} ↗
                      </a>
                    ) : (
                      item.sourceTitle
                    )}{" "}
                    · {item.sourceLocator}
                  </span>
                  <span className="mono-plain faint">
                    {item.caveat} Approved by {item.approvedBy}, {item.approvedOn}.
                  </span>
                </li>
              ))}
          </ul>
        </>
      )}
    </section>
  );
}
