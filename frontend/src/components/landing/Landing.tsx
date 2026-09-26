"use client";

import Link from "next/link";

import { usePayload } from "@/lib/api";
import type { GridlockPayload, Zone } from "@/lib/contract";
import { formatDays, formatDistance, formatNumber, label, projectIndex, utilityName } from "@/lib/format";

import { Coverage } from "../shared/Coverage";
import { SiteNav } from "../shared/SiteNav";
import { StatusNotice } from "../shared/StatusNotice";
import styles from "./landing.module.css";

const OLD_WAY = ["Utility A plan", "Utility B plan", "Separate PDFs", "Separate timelines", "Manual comparison", "Dozens of possible project pairs"];
const WITH_GRIDLOCK = ["Verified geometry", "Exact closest approach", "Timeline relevance", "Evidence provenance", "Coordination zones", "Ranked attention"];
const FLOW = ["Public plans", "Verified geography", "Overlap engine", "Coordination graph", "Actionable zones"];

function Stat({ value, caption }: { value: string; caption: string }) {
  return (
    <div className={styles.stat}>
      <div className={`display ${styles.statValue}`}>{value}</div>
      <div className="eyebrow">{caption}</div>
    </div>
  );
}

function FeaturedZone({ payload, zone }: { payload: GridlockPayload; zone: Zone }) {
  const { metadata } = payload;
  const headline = zone.headline;
  const projects = projectIndex(payload);
  const pair = headline ? [projects.get(headline.projectA), projects.get(headline.projectB)] : [];
  return (
    <section className={`frame rule-top ${styles.featured}`} aria-labelledby="featured-zone">
      <div className={styles.featuredIntro}>
        <p className="eyebrow">Real finding · rank {zone.rank} of {payload.zones.length}</p>
        <h2 id="featured-zone" className={`display ${styles.featuredName}`}>
          {zone.name}
        </h2>
        <span className="tag" data-priority={zone.opportunityPriority}>
          {label(metadata, "priority", zone.opportunityPriority)} priority
        </span>
        <p className={styles.featuredCopy}>
          Instead of asking planners to inspect {formatNumber(zone.relationshipIds.length)} individual project pairs, GridLock groups
          the activity into a single regional coordination situation.
        </p>
        <Link className="button ghost" href={`/planner?zone=${encodeURIComponent(zone.id)}`}>
          Explore this zone <span aria-hidden>→</span>
        </Link>
      </div>
      <div className={styles.featuredFacts}>
        <div className={styles.factRow}>
          <Stat value={formatNumber(zone.projectIds.length)} caption="Projects" />
          <Stat value={formatNumber(zone.relationshipIds.length)} caption="Relationships" />
        </div>
        {headline && (
          <div className={styles.topPair}>
            <p className="eyebrow">Top relationship</p>
            <p className={styles.pairNames}>
              {pair.map((project, index) => (
                <span key={project?.id ?? index}>
                  <span className="mono-plain">{project ? utilityName(metadata, project.utility) : ""}</span>
                  <span className={styles.pairName}>{project?.projectName ?? "Unknown project"}</span>
                </span>
              ))}
            </p>
            <div className={styles.factRow}>
              <Stat value={formatDistance(headline.distanceKm, metadata)} caption="Closest approach" />
              <Stat value={formatDays(headline.gapDays)} caption={label(metadata, "timeline_types", headline.timelineType)} />
              <Stat value={label(metadata, "spatial_tiers", headline.spatialTier)} caption="Spatial tier" />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

export function Landing() {
  const state = usePayload();
  const payload = state.status === "ready" ? state.payload : null;
  const metrics = payload?.metrics;
  const dash = "—";

  return (
    <main className={styles.page}>
      <SiteNav />

      <section className={`frame guides ${styles.hero}`}>
        <p className="eyebrow">Cross-utility transmission intelligence</p>
        <h1 className={`display ${styles.heroTitle}`}>
          Infrastructure plans,
          <br />
          <em>finally seen together.</em>
        </h1>
        <p className={styles.heroCopy}>
          Utilities plan transmission projects years in advance, often across separate planning systems. GridLock compares those
          public plans, verifies where projects actually sit, and surfaces the coordination opportunities worth acting on.
        </p>
        <Link className="button" href="/planner">
          Open coordination planner <span aria-hidden>→</span>
        </Link>
      </section>

      {state.status !== "ready" && (
        <div className="frame rule-top pad">
          <StatusNotice state={state} />
        </div>
      )}

      <section className={`frame rule-top ${styles.strip}`} aria-label="What GridLock found">
        <Stat value={metrics ? formatNumber(metrics.projects) : dash} caption="Public projects analyzed" />
        <Stat value={metrics ? formatNumber(metrics.relationships) : dash} caption="Cross-utility relationships" />
        <Stat value={metrics ? formatNumber(metrics.zones) : dash} caption="Coordination zones" />
        <Stat
          value={metrics?.attentionCompressionRatio != null ? `${metrics.attentionCompressionRatio}×` : dash}
          caption="Attention compression"
        />
      </section>
      {metrics && (
        <p className={`frame ${styles.stripNote}`}>
          {formatNumber(metrics.relationships)} individual pairwise alerts, compressed into {formatNumber(metrics.zones)} situations a
          planner actually needs to investigate.
        </p>
      )}

      <section className={`frame rule-top ${styles.split}`}>
        <div className={styles.splitColumn}>
          <p className="eyebrow">The old way</p>
          <ul className={styles.list}>
            {OLD_WAY.map((item) => (
              <li key={item} className="faint">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className={styles.splitColumn}>
          <p className="eyebrow">With GridLock</p>
          <ul className={styles.list}>
            {WITH_GRIDLOCK.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <blockquote className={`display ${styles.pullQuote}`}>
          <span>
            GridLock doesn’t give planners more data.
            <br />
            It tells them where to look.
          </span>
        </blockquote>
      </section>

      <section className={`frame rule-top ${styles.flowSection}`} aria-label="How it works">
        <p className="eyebrow">How it works</p>
        <ol className={styles.flow}>
          {FLOW.map((step, index) => (
            <li key={step}>
              <span className="mono-plain">{String(index + 1).padStart(2, "0")}</span>
              <span className={styles.flowStep}>{step}</span>
            </li>
          ))}
        </ol>
        <p className={`${styles.flowCaption} muted`}>
          AI may assist with interpreting messy documents. It never decides distance, overlap, evidence, ranking or zone
          membership — every result is deterministic and reproducible.
        </p>
      </section>

      {payload && payload.zones[0] && <FeaturedZone payload={payload} zone={payload.zones[0]} />}

      <section className={`frame guides rule-top ${styles.final}`}>
        <h2 className={`display ${styles.finalTitle}`}>
          {metrics ? formatNumber(metrics.relationships) : dash} relationships.
          <br />
          <em>{metrics ? formatNumber(metrics.zones) : dash} conversations worth starting.</em>
        </h2>
        <Link className="button" href="/planner">
          Open the planner <span aria-hidden>→</span>
        </Link>
      </section>

      <footer className={`frame rule-top ${styles.footer}`}>
        {payload?.metrics ? <Coverage metadata={payload.metadata} metrics={payload.metrics} /> : <span className="faint mono-plain">GridLock</span>}
      </footer>
    </main>
  );
}
