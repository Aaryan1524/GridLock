// Presentation-only views of payload data. Nothing here classifies, scores or ranks: every value
// is read from, or directly re-expresses, what the backend already decided.

import type { GridlockPayload, Metadata, Project, Relationship, Zone } from "./contract";
import { label } from "./format";

const RESOLVED = new Set(["matched", "override"]);
// Coordinates are stored to 7 decimals; the contact point is recomputed through a projection, so
// compare within about a centimetre rather than exactly.
const SAME_POINT_DEGREES = 1e-6;

/**
 * When a 0 km relationship touches at an endpoint both projects matched to the same public
 * feature (e.g. both end at Thurmond Substation), return that feature's name; otherwise null.
 */
export function sharedEndpointName(relationship: Relationship, projects: Map<string, Project>): string | null {
  if (relationship.distanceKm !== 0) return null;
  const [contact] = relationship.closestPoints;
  const at = (projectId: string) =>
    (projects.get(projectId)?.geometryResolution?.matches ?? []).filter(
      (match) =>
        RESOLVED.has(match.status) &&
        match.featureId &&
        match.point &&
        Math.abs(match.point.lat - contact.lat) < SAME_POINT_DEGREES &&
        Math.abs(match.point.lon - contact.lon) < SAME_POINT_DEGREES,
    );
  const b = at(relationship.projectB);
  const shared = at(relationship.projectA).find((match) => b.some((other) => other.featureId === match.featureId));
  return shared ? (shared.featureName ?? shared.endpoint) : null;
}

/** "Shared endpoint" when the evidence shows one; otherwise the backend's spatial tier label. */
export function spatialLabel(metadata: Metadata, relationship: Relationship, projects: Map<string, Project>): { short: string; long: string } {
  const shared = sharedEndpointName(relationship, projects);
  if (shared) return { short: "Shared endpoint", long: `Shared endpoint — ${shared}` };
  const tier = label(metadata, "spatial_tiers", relationship.spatialTier);
  return { short: tier, long: tier };
}

export function topRelationshipOf(payload: GridlockPayload, zone: Zone): Relationship | undefined {
  return payload.relationships.find((relationship) => relationship.id === zone.topRelationshipId);
}

export type LocationStatus = "resolved" | "approximate" | "human_verified" | "unresolved";

export const LOCATION_STATUS_LABELS: Record<LocationStatus, string> = {
  resolved: "Resolved",
  approximate: "Approximate",
  human_verified: "Human-verified",
  unresolved: "Not spatially assessed",
};

/** How a project is located, read from its geometry resolution. Unlocated means unknown, not "no overlap". */
export function locationStatus(project: Project): LocationStatus {
  const resolution = project.geometryResolution;
  if (!project.geometry || !resolution) return "unresolved";
  if (resolution.matches.some((match) => match.status === "override")) return "human_verified";
  return resolution.isApproximation ? "approximate" : "resolved";
}

export type CoordinationStatus = "in_zone" | "no_relationship" | "not_assessed";

export const COORDINATION_STATUS_LABELS: Record<CoordinationStatus, string> = {
  in_zone: "In a coordination zone",
  no_relationship: "No detected relationship",
  not_assessed: "Not spatially assessed",
};

export interface ProjectRow {
  project: Project;
  location: LocationStatus;
  coordination: CoordinationStatus;
  zones: Zone[];
  relationships: number;
}

export function projectRows(payload: GridlockPayload): ProjectRow[] {
  const counts = new Map<string, number>();
  for (const relationship of payload.relationships) {
    for (const id of [relationship.projectA, relationship.projectB]) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return payload.projects.map((project) => {
    const location = locationStatus(project);
    const zones = payload.zones.filter((zone) => zone.projectIds.includes(project.id));
    const coordination: CoordinationStatus = location === "unresolved" ? "not_assessed" : zones.length ? "in_zone" : "no_relationship";
    return { project, location, coordination, zones, relationships: counts.get(project.id) ?? 0 };
  });
}

export function priorityCounts(zones: Zone[]): { priority: string; zones: Zone[] }[] {
  const order: string[] = [];
  const groups = new Map<string, Zone[]>();
  for (const zone of zones) {
    if (!groups.has(zone.opportunityPriority)) {
      groups.set(zone.opportunityPriority, []);
      order.push(zone.opportunityPriority);
    }
    groups.get(zone.opportunityPriority)!.push(zone);
  }
  return order.map((priority) => ({ priority, zones: groups.get(priority)! }));
}
