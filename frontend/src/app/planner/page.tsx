import type { Metadata } from "next";
import { Suspense } from "react";

import { Planner } from "@/components/planner/Planner";

export const metadata: Metadata = {
  title: "GridLock — coordination planner",
};

export default function PlannerPage() {
  // useSearchParams (zone deep links) needs a Suspense boundary.
  return (
    <Suspense fallback={null}>
      <Planner />
    </Suspense>
  );
}
