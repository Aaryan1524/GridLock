"use client";

import type { Metadata, Project, Relationship } from "@/lib/contract";
import { formatDate, formatDays, label, utilityColor } from "@/lib/format";

import styles from "./panel.module.css";

const DAY = 86_400_000;
const ROW = 30;
const LEFT = 132;
const RIGHT = 18;
const WIDTH = 400;

function time(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** What the filing actually gives for a project's timing; nothing is invented (I-6). */
function span(project: Project): { start: string; end: string; kind: "window" | "filed" } | null {
  if (project.constructionWindow) {
    return { start: project.constructionWindow.startDate, end: project.constructionWindow.endDate, kind: "window" };
  }
  if (project.filedStartDate && project.plannedInServiceDate) {
    return { start: project.filedStartDate, end: project.plannedInServiceDate, kind: "filed" };
  }
  return null;
}

interface Props {
  metadata: Metadata;
  projects: Project[];
  top: Relationship | undefined;
  onInspect: (projectId: string) => void;
}

/**
 * In-service dates are markers; a bar appears only where the filing gives a start date (labelled
 * "as filed") or an explicit construction window. The top pair's in-service gap is bracketed.
 */
export function Timeline({ metadata, projects, top, onInspect }: Props) {
  const topIds = new Set(top ? [top.projectA, top.projectB] : []);
  const rows = [...projects].sort((a, b) => {
    const pinned = Number(topIds.has(b.id)) - Number(topIds.has(a.id));
    return pinned || (a.plannedInServiceDate ?? "9999").localeCompare(b.plannedInServiceDate ?? "9999") || a.id.localeCompare(b.id);
  });
  const dates = rows.flatMap((project) => [project.plannedInServiceDate, span(project)?.start].filter((value): value is string => !!value));
  if (!dates.length) {
    return <p className="mono-plain">No dates are published for these projects.</p>;
  }
  const min = Math.min(...dates.map(time));
  const max = Math.max(...dates.map(time));
  const first = new Date(min).getUTCFullYear();
  const last = new Date(max).getUTCFullYear() + 1;
  const from = Date.UTC(first, 0, 1);
  const to = Date.UTC(last, 0, 1);
  const x = (iso: string) => LEFT + ((time(iso) - from) / (to - from)) * (WIDTH - LEFT - RIGHT);
  const years = Array.from({ length: last - first + 1 }, (_, index) => first + index);
  const step = Math.max(1, Math.ceil(years.length / 6));
  const height = rows.length * ROW + 34;
  const pair = top ? rows.filter((project) => topIds.has(project.id)) : [];

  return (
    <figure className={styles.timeline}>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label="Project dates for the selected zone">
        {years.map((year, index) =>
          index % step === 0 ? (
            <g key={year}>
              <line x1={x(`${year}-01-01`)} x2={x(`${year}-01-01`)} y1={0} y2={height - 20} className={styles.gridLine} />
              <text x={x(`${year}-01-01`)} y={height - 6} className={styles.axisLabel} textAnchor="middle">
                {year}
              </text>
            </g>
          ) : null,
        )}
        {rows.map((project, index) => {
          const y = index * ROW + 16;
          const color = utilityColor(metadata, project.utility);
          const range = span(project);
          const emphasis = topIds.has(project.id);
          return (
            <g key={project.id} className={styles.timelineRow} data-top={emphasis} onClick={() => onInspect(project.id)}>
              <title>
                {`${project.projectName}\nIn-service: ${formatDate(project.plannedInServiceDate)}` +
                  (range ? `\n${range.kind === "filed" ? "Project span (as filed)" : "Construction window"}: ${formatDate(range.start)} – ${formatDate(range.end)}` : "")}
              </title>
              <text x={0} y={y + 4} className={styles.rowLabel} data-top={emphasis}>
                {project.id}
              </text>
              {range && (
                <rect
                  x={x(range.start)}
                  y={y - 5}
                  width={Math.max(2, x(range.end) - x(range.start))}
                  height={10}
                  fill={color}
                  fillOpacity={range.kind === "filed" ? 0.18 : 0.5}
                  stroke={color}
                  strokeOpacity={0.6}
                  strokeDasharray={range.kind === "filed" ? "3 2" : undefined}
                />
              )}
              {project.plannedInServiceDate ? (
                <path
                  d={`M ${x(project.plannedInServiceDate)} ${y - 6} l 6 6 l -6 6 l -6 -6 z`}
                  fill={color}
                  stroke="var(--bg)"
                  strokeWidth={1}
                />
              ) : (
                <text x={LEFT} y={y + 4} className={styles.axisLabel}>
                  in-service date unknown
                </text>
              )}
            </g>
          );
        })}
        {pair.length === 2 && pair[0].plannedInServiceDate && pair[1].plannedInServiceDate && top?.timeline.gapDays != null && (
          <g className={styles.gapBracket}>
            <line x1={x(pair[0].plannedInServiceDate)} x2={x(pair[0].plannedInServiceDate)} y1={16} y2={ROW + 16} />
            <line x1={x(pair[1].plannedInServiceDate)} x2={x(pair[1].plannedInServiceDate)} y1={16} y2={ROW + 16} />
          </g>
        )}
      </svg>
      <figcaption className={styles.timelineKey}>
        <span>
          <span className={styles.keyDiamond} /> In-service / need date
        </span>
        <span>
          <span className={styles.keyFiled} /> Project span — as filed
        </span>
        {top && (
          <span>
            Top pair: {formatDays(top.timeline.gapDays)} · {label(metadata, "timeline_types", top.timeline.type)}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
