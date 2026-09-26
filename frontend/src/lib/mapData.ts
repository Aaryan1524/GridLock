import type { GridlockPayload, Relationship, Zone } from "./contract";
import { utilityColor } from "./format";

// Minimal GeoJSON typing, enough for MapLibre sources.
export interface Feature {
  type: "Feature";
  id?: number;
  properties: Record<string, string | number | boolean>;
  geometry: { type: string; coordinates: unknown };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: Feature[];
}

/** How a located project relates to the selected zone; drives emphasis only, never analysis. */
export type ProjectRole = "top" | "zone" | "background";

export function projectFeatures(payload: GridlockPayload, zone: Zone | null): FeatureCollection {
  const inZone = new Set(zone?.projectIds ?? []);
  const topPair = new Set(zone?.headline ? [zone.headline.projectA, zone.headline.projectB] : []);
  const features: Feature[] = [];
  payload.projects.forEach((project, index) => {
    if (!project.geometry) return; // unlocated projects make no spatial claims and are not drawn
    const role: ProjectRole = topPair.has(project.id) ? "top" : inZone.has(project.id) ? "zone" : "background";
    features.push({
      type: "Feature",
      id: index,
      properties: {
        id: project.id,
        utility: project.utility,
        color: utilityColor(payload.metadata, project.utility),
        approximate: project.geometryResolution?.isApproximation ?? false,
        role,
      },
      geometry: project.geometry as Feature["geometry"],
    });
  });
  return { type: "FeatureCollection", features };
}

function connector(relationship: Relationship, top: boolean): Feature {
  const [a, b] = relationship.closestPoints;
  return {
    type: "Feature",
    properties: { id: relationship.id, top },
    geometry: { type: "LineString", coordinates: [[a.lon, a.lat], [b.lon, b.lat]] },
  };
}

/** Closest-point connectors: the top relationship always; the rest of the zone only on request. */
export function connectorFeatures(payload: GridlockPayload, zone: Zone | null, showAll: boolean): FeatureCollection {
  if (!zone) return { type: "FeatureCollection", features: [] };
  const topId = zone.topRelationshipId;
  const members = new Set(zone.relationshipIds);
  const features = payload.relationships
    .filter((relationship) => members.has(relationship.id) && (showAll || relationship.id === topId))
    .map((relationship) => connector(relationship, relationship.id === topId));
  return { type: "FeatureCollection", features };
}

export function closestPointFeatures(payload: GridlockPayload, zone: Zone | null): FeatureCollection {
  const top = zone ? payload.relationships.find((relationship) => relationship.id === zone.topRelationshipId) : undefined;
  if (!top) return { type: "FeatureCollection", features: [] };
  return {
    type: "FeatureCollection",
    features: top.closestPoints.map((point, index) => ({
      type: "Feature",
      properties: { end: index },
      geometry: { type: "Point", coordinates: [point.lon, point.lat] },
    })),
  };
}

export function topRelationship(payload: GridlockPayload, zone: Zone | null): Relationship | undefined {
  return zone ? payload.relationships.find((relationship) => relationship.id === zone.topRelationshipId) : undefined;
}
