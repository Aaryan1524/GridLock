"use client";

import type { GridlockPayload } from "@/lib/contract";
import { formatNumber } from "@/lib/format";
import type { PlannerView } from "@/lib/plannerState";

import styles from "./planner.module.css";

const ITEMS: { view: PlannerView; label: string; count: (payload: GridlockPayload) => number | null }[] = [
  { view: "overview", label: "Overview", count: () => null },
  { view: "zones", label: "Zones", count: (payload) => payload.zones.length },
  { view: "projects", label: "Projects", count: (payload) => payload.projects.length },
  { view: "quality", label: "Data quality", count: () => null },
];

export function PlannerNav({ payload, view, onChange }: { payload: GridlockPayload; view: PlannerView; onChange: (view: PlannerView) => void }) {
  return (
    <nav className={styles.plannerNav} aria-label="Planner sections" data-gust="0">
      <ol>
        {ITEMS.map((item, index) => {
          const count = item.count(payload);
          return (
            <li key={item.view}>
              <button type="button" data-active={view === item.view} aria-current={view === item.view ? "page" : undefined} onClick={() => onChange(item.view)}>
                <span className="mono-plain">{String(index + 1).padStart(2, "0")}</span>
                <span className={styles.navLabel}>{item.label}</span>
                {count !== null && <span className="mono-plain">{formatNumber(count)}</span>}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
