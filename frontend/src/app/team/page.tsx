import type { Metadata } from "next";

import { Team } from "@/components/team/Team";

export const metadata: Metadata = {
  title: "Team — GridLock",
  description: "The people who built GridLock.",
};

export default function TeamPage() {
  return <Team />;
}
