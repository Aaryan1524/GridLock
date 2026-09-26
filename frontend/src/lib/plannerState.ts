"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export const PLANNER_VIEWS = ["overview", "zones", "projects", "quality"] as const;
export type PlannerView = (typeof PLANNER_VIEWS)[number];

/**
 * Planner navigation lives in the URL so every screen is reproducible and shareable:
 * `?view=overview`, `?view=zones&zone=ZONE-01`, `?view=projects`, `?view=quality`.
 * A bare `?zone=` (the landing page's deep link) opens the Zones view.
 */
export function usePlannerState() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requestedView = params.get("view");
  const zoneId = params.get("zone");
  const view: PlannerView = PLANNER_VIEWS.includes(requestedView as PlannerView)
    ? (requestedView as PlannerView)
    : zoneId
      ? "zones"
      : "overview";

  const navigate = useCallback(
    (next: { view?: PlannerView; zone?: string | null }) => {
      const query = new URLSearchParams();
      query.set("view", next.view ?? view);
      const zone = next.zone === undefined ? zoneId : next.zone;
      if (zone) query.set("zone", zone);
      router.replace(`${pathname}?${query.toString()}`, { scroll: false });
    },
    [pathname, router, view, zoneId],
  );

  return { view, zoneId, navigate };
}
