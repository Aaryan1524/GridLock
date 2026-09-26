"""Config-driven parsers for the DESC and GPC public planning documents."""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pypdf import PdfReader

from gridlock.models.domain import EndpointStatus, Project, SourceRef
from gridlock.normalization import (
    extract_endpoints,
    extract_voltage_kv,
    infer_project_type,
    normalize_project_id,
    parse_filed_date,
)
from gridlock.settings.loader import ConfigBundle
from gridlock.settings.models import NormalizationConfig, SourceConfig, UtilityConfig

RAW_DIR_ENV = "GRIDLOCK_RAW_DIR"


class IngestionError(ValueError):
    """Raised when a configured source does not satisfy its known public layout."""


@dataclass(frozen=True)
class IngestionReport:
    projects_by_utility: dict[str, int]
    null_counts: dict[str, int]
    endpoint_status: dict[str, int]
    projects_with_warnings: int
    output_path: Path
    review_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "projects_by_utility": self.projects_by_utility,
            "total_projects": sum(self.projects_by_utility.values()),
            "null_counts": self.null_counts,
            "endpoint_status": self.endpoint_status,
            "projects_with_warnings": self.projects_with_warnings,
            "output_path": str(self.output_path),
            "review_path": str(self.review_path),
        }


@dataclass(frozen=True)
class ParseContext:
    source_path: Path
    source: SourceConfig
    utility: UtilityConfig
    normalization: NormalizationConfig

    def label(self, key: str) -> str:
        try:
            return self.source.labels[key]
        except KeyError as error:
            raise IngestionError(f"source {self.source.id!r} is missing the {key!r} label in its config") from error


Parser = Callable[[ParseContext], list[Project]]


def _field(text: str, label: str, next_label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*\n?(.*?)(?=\n\s*{re.escape(next_label)}\b)", text, re.S | re.I)
    return " ".join(match.group(1).split()) if match else None


def _clean_source_text(text: str, source: SourceConfig) -> str:
    """Drop configured boilerplate (e.g. a CEII notice) so records keep only the project's own text."""
    for block in source.strip_blocks:
        start = r"\s+".join(map(re.escape, block.start.split()))
        end = r"\s+".join(map(re.escape, block.end.split()))
        text = re.sub(rf"{start}.*?{end}", "", text, flags=re.S)
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if not any(re.match(pattern, line.strip()) for pattern in source.ignored_line_patterns)]
    return "\n".join(lines).strip()


def _project(
    context: ParseContext,
    *,
    raw_id: str,
    title: str,
    description: str | None,
    page: int,
    text: str,
    raw_fields: dict[str, str],
    warnings: list[str],
    **fields: object,
) -> Project:
    rules = context.normalization
    extraction = extract_endpoints(title, rules.endpoints)
    return Project(
        id=normalize_project_id(context.utility.code, raw_id),
        utility=context.utility.code,
        project_name=title,
        project_type=infer_project_type(title, description, extraction.status, rules.project_types, rules.endpoints),
        description=description,
        voltage_kv=extract_voltage_kv(title, rules.voltage_pattern) or extract_voltage_kv(description or "", rules.voltage_pattern),
        endpoints=extraction.endpoints,
        endpoint_status=extraction.status,
        source=SourceRef(
            document=context.source.path,
            project_id_raw=raw_id,
            page=page,
            raw_text=_clean_source_text(text, context.source),
            raw_fields=raw_fields,
        ),
        warnings=warnings + extraction.warnings,
        **fields,
    )


def _desc_title(text: str, title_after: str, before: str) -> str | None:
    before_marker = text.split(before, maxsplit=1)[0]
    try:
        after_header = before_marker.split(title_after, maxsplit=1)[1]
    except IndexError:
        return None
    lines = [line.strip() for line in after_header.splitlines() if line.strip()]
    return " ".join(lines) or None


def _desc_total_cost(text: str, cost_label: str) -> tuple[int | None, str | None]:
    amounts = re.findall(r"\$([\d,]+)", text.split(cost_label, maxsplit=1)[-1])
    if not amounts:
        return None, None
    return int(amounts[-1].replace(",", "")), f"${amounts[-1]}"


def parse_desc(context: ParseContext) -> list[Project]:
    label = context.label
    reader = PdfReader(context.source_path)
    page_start = context.source.page_start or 1
    page_end = context.source.page_end or len(reader.pages)
    date_formats = context.normalization.date_formats
    projects: list[Project] = []
    for page_number in range(page_start, page_end + 1):
        text = reader.pages[page_number - 1].extract_text() or ""
        raw_id = _field(text, label("project_id"), label("description"))
        title = _desc_title(text, label("title_after"), label("project_id"))
        if not raw_id or not title:
            raise IngestionError(f"{context.source.id} page {page_number} is missing a project ID or title")
        in_service_raw = _field(text, label("in_service_date"), label("cost"))
        in_service = parse_filed_date(in_service_raw, date_formats)
        cost, cost_raw = _desc_total_cost(text, label("cost"))
        raw_fields = {key: value for key, value in (("in_service_date", in_service_raw), ("estimated_cost_total", cost_raw)) if value}
        warnings = []
        if in_service_raw and in_service is None:
            warnings.append(f"Planned in-service date is not a single parseable date: {in_service_raw!r}")
        projects.append(
            _project(
                context,
                raw_id=raw_id,
                title=title,
                description=_field(text, label("description"), label("need")),
                page=page_number,
                text=text,
                raw_fields=raw_fields,
                warnings=warnings,
                status=_field(text, label("status"), label("in_service_date")),
                planned_in_service_date=in_service,
                estimated_cost_usd=cost,
            )
        )
    return projects


# One summary-table row; the redacted-cost token that ends it comes from the source labels.
_SUMMARY_ROW = (
    r"(?P<zone>\d{3})\s+(?P<year>20\d{2})\s+(?P<team>\d{4,6})\s+"
    r"(?P<name>.*?)\s+(?P<need>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<sponsor>[A-Z]{2,5})\s+"
)


def _summary_rows(reader: PdfReader, context: ParseContext) -> dict[str, dict[str, str]]:
    source = context.source
    if source.summary_page_start is None or source.summary_page_end is None:
        raise IngestionError(f"{source.id} requires summary page bounds")
    text = "\n".join(
        reader.pages[index - 1].extract_text() or ""
        for index in range(source.summary_page_start, source.summary_page_end + 1)
    )
    row_pattern = re.compile(_SUMMARY_ROW + re.escape(context.label("redacted")), re.S)
    rows = {
        match.group("team"): {
            "zone": match.group("zone"),
            "year": match.group("year"),
            "name": " ".join(match.group("name").split()),
            "need": match.group("need"),
            "sponsor": match.group("sponsor"),
        }
        for match in row_pattern.finditer(text)
    }
    if not rows:
        raise IngestionError(f"{source.id} summary table did not yield any project rows")
    return rows


def _gpc_description(text: str, after: str, redacted: str) -> str | None:
    """The description block follows the cost footnote and ends at the redacted supporting statement."""
    _, found, tail = text.partition(after)
    if not found:
        return None
    lines: list[str] = []
    for line in tail.splitlines():
        if line.strip() == redacted:
            break
        if line.strip():
            lines.append(line.strip())
    return " ".join(lines) or None


def parse_gpc(context: ParseContext) -> list[Project]:
    label = context.label
    source = context.source
    reader = PdfReader(context.source_path)
    summary = _summary_rows(reader, context)
    included_sponsors = set(context.utility.included_sponsors)
    date_formats = context.normalization.date_formats
    number_pattern = re.compile(rf"{re.escape(label('project_number'))}\s*(?P<team>\d+)", re.I)
    dates_pattern = re.compile(
        rf"{re.escape(label('need_date'))}\s+(?P<need>\d{{1,2}}/\d{{1,2}}/\d{{4}})\s+"
        rf"{re.escape(label('start_date'))}\s+(?P<start>\d{{1,2}}/\d{{1,2}}/\d{{4}})",
        re.I,
    )
    page_start = source.detail_page_start or 1
    page_end = source.detail_page_end or len(reader.pages)
    details: dict[str, tuple[int, str]] = {}
    for page_number in range(page_start, page_end + 1):
        text = _clean_source_text(reader.pages[page_number - 1].extract_text() or "", source)
        match = number_pattern.search(text)
        if match:
            details[match.group("team")] = (page_number, text)

    projects: list[Project] = []
    for team, row in sorted(summary.items(), key=lambda item: int(item[0])):
        if row["sponsor"] not in included_sponsors:
            continue
        detail = details.get(team)
        if detail is None:
            raise IngestionError(f"{source.id} summary project {team} has no detail page")
        page_number, text = detail
        number_match = number_pattern.search(text)
        assert number_match is not None
        title_lines = [line.strip() for line in text[: number_match.start()].splitlines() if line.strip()]
        title = " ".join(title_lines) or row["name"]

        dates = dates_pattern.search(text)
        raw_fields = {
            "summary_name": row["name"],
            "summary_zone": row["zone"],
            "summary_year": row["year"],
            "summary_need_date": row["need"],
            "estimated_cost": label("redacted"),
        }
        warnings: list[str] = []
        summary_need = parse_filed_date(row["need"], date_formats)
        detail_need = parse_filed_date(dates.group("need"), date_formats) if dates else None
        start = parse_filed_date(dates.group("start"), date_formats) if dates else None
        if dates:
            raw_fields["detail_need_date"] = dates.group("need")
            raw_fields["detail_start_date"] = dates.group("start")
        else:
            warnings.append("Detail page has no need/start dates; summary need date used")
        need = detail_need or summary_need
        if detail_need and summary_need and detail_need != summary_need:
            if source.date_precedence is None:
                raise IngestionError(f"{source.id} project {team} has conflicting need dates and no date_precedence")
            need = summary_need if source.date_precedence == "summary" else detail_need
            warnings.append(
                f"Summary table need date {summary_need.isoformat()} differs from detail page need date "
                f"{detail_need.isoformat()}; {source.date_precedence} value used per configured precedence"
            )
        projects.append(
            _project(
                context,
                raw_id=team,
                title=title,
                description=_gpc_description(text, label("description_after"), label("redacted")),
                page=page_number,
                text=text,
                raw_fields=raw_fields,
                warnings=warnings,
                sponsor=row["sponsor"],
                planned_in_service_date=need,
                filed_start_date=start,
            )
        )
    return projects


PARSERS: dict[str, Parser] = {
    "desc_project_descriptions": parse_desc,
    "gpc_irp_ten_year": parse_gpc,
}


def raw_dir(bundle: ConfigBundle, repository_root: Path) -> Path:
    """The raw source folder: GRIDLOCK_RAW_DIR if set, otherwise the configured path."""
    configured = Path(os.environ.get(RAW_DIR_ENV) or bundle.root.paths.raw_dir)
    return configured if configured.is_absolute() else repository_root / configured


def parse_plans(bundle: ConfigBundle, repository_root: Path) -> list[Project]:
    """Parse every configured planning source into normalized, provenance-rich projects."""
    projects: list[Project] = []
    source_dir = raw_dir(bundle, repository_root)
    for utility in bundle.utilities:
        for source in utility.sources:
            source_path = source_dir / source.path
            if not source_path.is_file():
                raise IngestionError(f"configured source file is missing: {source_path}")
            parser = PARSERS.get(source.parser)
            if parser is None:
                raise IngestionError(f"unsupported parser {source.parser!r}; known parsers: {sorted(PARSERS)}")
            projects.extend(parser(ParseContext(source_path, source, utility, bundle.root.normalization)))
    ids = [project.id for project in projects]
    if len(ids) != len(set(ids)):
        duplicate_ids = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
        raise IngestionError(f"normalized project IDs are not unique: {duplicate_ids}")
    return projects


def _needs_review(project: Project) -> bool:
    return bool(project.warnings) or project.endpoint_status in {EndpointStatus.NONE, EndpointStatus.CHAIN}


def ingest_plans(
    bundle: ConfigBundle,
    repository_root: Path,
    output_path: Path | None = None,
    review_path: Path | None = None,
) -> IngestionReport:
    """Parse configured sources, write projects.json, and list records a person should check."""
    projects = parse_plans(bundle, repository_root)
    output_path = output_path or repository_root / bundle.root.paths.normalized_dir / "projects.json"
    review_path = review_path or repository_root / bundle.root.paths.review_dir / "endpoint_review.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([project.model_dump(mode="json", by_alias=True) for project in projects], indent=2) + "\n",
        encoding="utf-8",
    )
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", newline="", encoding="utf-8") as review_file:
        writer = csv.writer(review_file)
        writer.writerow(["project_id", "project_name", "endpoint_status", "endpoints", "warnings"])
        for project in projects:
            if _needs_review(project):
                endpoints = " | ".join(f"{endpoint.role.value}:{endpoint.name}" for endpoint in project.endpoints)
                writer.writerow(
                    [project.id, project.project_name, project.endpoint_status.value, endpoints, " | ".join(project.warnings)]
                )
    nullable_fields = ("description", "status", "planned_in_service_date", "filed_start_date", "estimated_cost_usd")
    return IngestionReport(
        projects_by_utility=dict(sorted(Counter(project.utility for project in projects).items())),
        null_counts={field: sum(getattr(project, field) is None for project in projects) for field in nullable_fields},
        endpoint_status=dict(sorted(Counter(project.endpoint_status.value for project in projects).items())),
        projects_with_warnings=sum(bool(project.warnings) for project in projects),
        output_path=output_path,
        review_path=review_path,
    )
