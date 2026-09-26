import type { GridlockPayload, Metadata, Project } from "./contract";

const KM_PER_MILE = 1.609344;

/** Format a distance in the payload's display unit; the stored value is always kilometres. */
export function formatDistance(km: number, metadata: Metadata): string {
  const unit = metadata.distanceUnit ?? "km";
  const value = unit === "mi" ? km / KM_PER_MILE : km;
  const digits = value === 0 ? 0 : value < 10 ? 2 : 1;
  return `${value.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 })} ${unit}`;
}

export function formatDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return "—";
  return `${days.toLocaleString("en-US")} ${days === 1 ? "day" : "days"}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Unknown";
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

export function countOf(value: number, singular: string, plural = `${singular}s`): string {
  return `${formatNumber(value)} ${value === 1 ? singular : plural}`;
}

/** A display label from payload metadata, falling back to the raw code (never invented text). */
export function label(metadata: Metadata, vocabulary: string, code: string | null | undefined): string {
  if (!code) return "—";
  return metadata.labels?.[vocabulary]?.[code] ?? code;
}

export function utilityName(metadata: Metadata, code: string): string {
  return metadata.utilityNames?.[code] ?? code;
}

export function utilityColor(metadata: Metadata, code: string): string {
  return metadata.utilityColors[code] ?? "var(--muted)";
}

export function projectIndex(payload: GridlockPayload): Map<string, Project> {
  return new Map(payload.projects.map((project) => [project.id, project]));
}
