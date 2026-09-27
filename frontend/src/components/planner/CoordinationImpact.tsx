"use client";

import type { GridlockPayload, ImpactAssumption, ImpactRange, Project, ZoneImpact } from "@/lib/contract";
import { label, utilityName } from "@/lib/format";

import styles from "./panel.module.css";

// Display only: every number, range and sentence comes from payload.impact (backend/src/gridlock/impact).
function range(value: ImpactRange | null | undefined, format: (n: number) => string = (n) => n.toLocaleString("en-US")): string {
  if (!value) return "—";
  if (value.low === null || value.low === undefined) return `up to ${format(value.high)}`;
  return value.low === value.high ? format(value.high) : `${format(value.low)}–${format(value.high)}`;
}

/** $1,772,304 → "$1.77M": a shorter reading of the same backend figure (the exact value is in the method). */
function shortUsd(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000).toLocaleString("en-US")}K`;
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

const upperFirst = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

interface Props {
  payload: GridlockPayload;
  impact: ZoneImpact;
  projects: Map<string, Project>;
}

/** S2 result first: four figures, one sentence, compact uncertainty flags; the calculation chain on request. */
export function CoordinationImpact({ payload, impact, projects }: Props) {
  const { metadata } = payload;
  const costedUtilities = [
    ...new Set(impact.clusters.flatMap((cluster) => cluster.costedProjectIds).map((id) => projects.get(id)?.utility).filter(Boolean)),
  ] as string[];
  const basis =
    costedUtilities.length > 0
      ? `with published ${costedUtilities.map((code) => utilityName(metadata, code)).join(" and ")} project costs`
      : "none with a published project cost";

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
          <dl className={styles.impactFigures}>
            {impact.stagingYards && (
              <div>
                <dd className="display">{range(impact.stagingYards)}</dd>
                <dt>potential shared staging {impact.stagingYards.high === 1 ? "yard" : "yards"}</dt>
              </div>
            )}
            {impact.temporaryAcres && (
              <div>
                <dd className="display">{range(impact.temporaryAcres)} acres</dd>
                <dt>temporary footprint potentially consolidated</dt>
              </div>
            )}
            {impact.mobilizations && (
              <div>
                <dd className="display">{range(impact.mobilizations)}</dd>
                <dt>duplicate mobilizations potentially avoided</dt>
              </div>
            )}
            {impact.expectedSavingUsd && (
              <div>
                <dd className="display" title={range(impact.expectedSavingUsd, (n) => `$${Math.round(n).toLocaleString("en-US")}`)}>
                  {upperFirst(range(impact.expectedSavingUsd, shortUsd))}
                </dd>
                <dt>illustrative estimated savings ceiling</dt>
              </div>
            )}
          </dl>

          <p className={styles.impactBasis}>
            Based on {impact.timelyCount} timely coordination {impact.timelyCount === 1 ? "relationship" : "relationships"} {basis}.
          </p>

          {impact.indicators.length > 0 && (
            <div className={styles.indicators}>
              {impact.indicators.map((indicator) => (
                <details key={indicator.summary} className={styles.indicator}>
                  <summary>△ {indicator.summary}</summary>
                  <p>{indicator.detail}</p>
                </details>
              ))}
            </div>
          )}

          {impact.chain.length > 0 && (
            <details className={styles.method}>
              <summary className="mono">
                How this was calculated <span aria-hidden>↓</span>
              </summary>
              <ol className={styles.chain}>
                {impact.chain.map((step) => (
                  <li key={step.label}>
                    <span className="mono">{step.label}</span>
                    <span className={styles.chainValue}>{step.value}</span>
                    {(step.detail || step.assumptionIds.length > 0) && (
                      <span className="mono-plain faint">
                        {step.detail}
                        {step.assumptionIds.length > 0 && ` · ${step.assumptionIds.join(", ")}`}
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
    </section>
  );
}

function assumptionKind(item: ImpactAssumption, used: Set<string>): string {
  if (item.basis === "derived") return "GridLock scenario assumption, approved; not an external empirical fact.";
  if (!used.has(item.id)) return "Reference only · not used in GridLock arithmetic.";
  return "External planning reference.";
}

/** Every impact assumption, compact, with full provenance: collapsed at the bottom of the expanded drawer. */
export function ImpactMethodology({ payload }: { payload: GridlockPayload }) {
  const assumptions = payload.metadata.impactAssumptions ?? [];
  if (assumptions.length === 0) return null;
  // Used by any zone's calculation; an assumption no zone uses is a reference (the cross-check).
  const used = new Set((payload.impact ?? []).flatMap((item) => item.chain.flatMap((step) => step.assumptionIds)));
  return (
    <section className={styles.section} aria-labelledby="methodology-heading">
      <details className={styles.methodology}>
        <summary>
          <span id="methodology-heading" className="eyebrow">
            Methodology &amp; assumptions
          </span>
        </summary>
        <p className={styles.impactReason}>
          The coordination impact counts only relationships GridLock already ranks as higher priority with timely dates, and uses only
          published project costs. Each value below was approved before use.
        </p>
        <ul className={styles.assumptions}>
          {assumptions.map((item) => (
            <li key={item.id}>
              <p className={styles.assumptionHead}>
                <span className="mono">{item.id}</span> · {item.title}
              </p>
              <p className={`display ${styles.assumptionValue}`}>
                {item.value} <span className="mono-plain">{item.unit}</span>
              </p>
              <p className="mono-plain">{assumptionKind(item, used)}</p>
              <p className={styles.assumptionSource}>
                <span className="faint">Source:</span> {item.sourceTitle}
                <span className="mono-plain faint"> · {item.sourceLocator}</span>
              </p>
              <p className={styles.assumptionSource}>
                <span className="faint">Context:</span> {item.caveat}
              </p>
              <p className="mono-plain faint">
                Approved by {item.approvedBy}, {item.approvedOn}
                {item.sourceUrl && (
                  <>
                    {" · "}
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                      View source ↗
                    </a>
                  </>
                )}
              </p>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
