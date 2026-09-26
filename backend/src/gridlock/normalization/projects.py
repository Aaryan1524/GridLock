"""Pure normalizers for project records extracted from public filings.

Every rule (formats, patterns, keyword lists) comes from the normalization config so the
same code can serve another utility's documents without edits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from gridlock.models.domain import Endpoint, EndpointRole, EndpointStatus, ProjectType
from gridlock.settings.models import EndpointRulesConfig, ProjectTypeConfig

_PARENTHETICAL = re.compile(r"\(([^()]*)\)")


def parse_filed_date(value: str | None, date_formats: tuple[str, ...]) -> date | None:
    """Parse a whole date string in one of the configured formats; anything else stays unknown."""
    if not value:
        return None
    for format_string in date_formats:
        try:
            return datetime.strptime(value.strip(), format_string).date()
        except ValueError:
            pass
    return None


def normalize_project_id(code: str, raw_id: str) -> str:
    """Build a stable ID from the utility code and the raw ID's alphanumeric tokens."""
    tokens = re.findall(r"[A-Za-z0-9]+", raw_id.upper())
    if not tokens:
        raise ValueError(f"project ID {raw_id!r} has no alphanumeric content")
    return f"{code}-" + "-".join(tokens)


def extract_voltage_kv(text: str, voltage_pattern: str) -> list[float]:
    """Return every voltage named in the text, including each level of a "230-115kV" chain."""
    values: set[float] = set()
    for match in re.finditer(voltage_pattern, text, re.I):
        values.update(float(number) for number in re.findall(r"\d+(?:\.\d+)?", match.group(1)))
    return sorted(values)


def _phrase_pattern(phrases: tuple[str, ...]) -> re.Pattern[str] | None:
    if not phrases:
        return None
    alternatives = "|".join(re.escape(phrase) for phrase in sorted(phrases, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])", re.I)


def strip_ignored_prefixes(title: str, rules: EndpointRulesConfig) -> str:
    text = title.strip()
    for pattern in rules.ignored_prefix_patterns:
        text = re.sub(pattern, "", text).strip()
    return text


@dataclass(frozen=True)
class EndpointExtraction:
    endpoints: list[Endpoint]
    status: EndpointStatus
    warnings: list[str] = field(default_factory=list)


def _clean_site(part: str, rules: EndpointRulesConfig) -> tuple[str, list[str]]:
    qualifiers = [" ".join(value.split()) for value in _PARENTHETICAL.findall(part) if value.strip()]
    name = _PARENTHETICAL.sub(" ", part)
    descriptors = _phrase_pattern(rules.descriptor_words)
    if descriptors:
        match = descriptors.search(name)
        if match:
            name = name[: match.start()]
    name = re.sub(rules.trailing_noise_pattern, "", " ".join(name.split()))
    return name.strip(), qualifiers


def extract_endpoints(title: str, rules: EndpointRulesConfig) -> EndpointExtraction:
    """Read named sites from a title; anything that is not a clean pair or site carries a warning."""
    warnings: list[str] = []
    if any(re.search(pattern, title.strip()) for pattern in rules.review_prefix_patterns):
        warnings.append("Customer-connection title; named sites may be customer facilities")

    text = strip_ignored_prefixes(title, rules)
    cut = len(text)
    for pattern in rules.section_end_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            cut = min(cut, match.start())
    section = text[:cut]

    without_voltages = text
    for pattern in rules.section_end_patterns:
        without_voltages = re.sub(pattern, " ", without_voltages, flags=re.I)
    if any(marker in without_voltages for marker in rules.multi_site_markers):
        warnings.append("Title may name more than one circuit or site; only the first is used")

    sites: list[tuple[str, list[str]]] = []
    for part in re.split(rules.separator_pattern, section):
        name, qualifiers = _clean_site(part, rules)
        if name:
            sites.append((name, qualifiers))

    if not sites:
        return EndpointExtraction([], EndpointStatus.NONE, warnings + ["No named site found in title"])
    malformed = [name for name, _ in sites if re.search(rules.residue_pattern, name, re.I)]
    if malformed:
        warnings.append(f"Site name may include title residue; source title may be malformed: {malformed}")
    if len(sites) == 1:
        name, qualifiers = sites[0]
        return EndpointExtraction(
            [Endpoint(name=name, role=EndpointRole.SINGLE, qualifiers=qualifiers)], EndpointStatus.SINGLE_SITE, warnings
        )
    roles = [EndpointRole.FROM] + [EndpointRole.VIA] * (len(sites) - 2) + [EndpointRole.TO]
    endpoints = [Endpoint(name=name, role=role, qualifiers=qualifiers) for (name, qualifiers), role in zip(sites, roles)]
    if len(sites) == 2:
        return EndpointExtraction(endpoints, EndpointStatus.EXPLICIT_PAIR, warnings)
    return EndpointExtraction(
        endpoints, EndpointStatus.CHAIN, warnings + [f"Title names {len(sites)} sites; intermediate sites marked as via"]
    )


def _first_rule_match(text: str, config: ProjectTypeConfig) -> str | None:
    for rule in config.rules:
        pattern = _phrase_pattern(rule.keywords)
        if pattern and pattern.search(text):
            return rule.type
    return None


def infer_project_type(
    title: str,
    description: str | None,
    endpoint_status: EndpointStatus,
    config: ProjectTypeConfig,
    endpoint_rules: EndpointRulesConfig,
) -> ProjectType:
    """Classify from the title's lead section, then the whole title, then endpoints, then the description."""
    title_body = strip_ignored_prefixes(title, endpoint_rules)
    lead_section = title_body.split(":", maxsplit=1)[0]
    matched = _first_rule_match(lead_section, config) or _first_rule_match(title_body, config)
    if matched is None and endpoint_status in {EndpointStatus.EXPLICIT_PAIR, EndpointStatus.CHAIN}:
        matched = config.endpoint_pair_type
    if matched is None and description:
        matched = _first_rule_match(description, config)
    return ProjectType(matched or config.default_type)
