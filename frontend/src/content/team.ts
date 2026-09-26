// The people who built GridLock, in the order they should appear on /team.
// Add one entry per person; links are optional (e.g. GitHub, LinkedIn, personal site).
//
// {
//   name: "Full Name",
//   role: "What they built",
//   links: [{ label: "GitHub", href: "https://github.com/username" }],
// },

export interface TeamMember {
  name: string;
  role: string;
  links?: { label: string; href: string }[];
}

export const TEAM: TeamMember[] = [];
