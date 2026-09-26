from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gridlock.models.domain import EndpointRole, EndpointStatus, ProjectType
from gridlock.normalization import (
    extract_endpoints,
    extract_voltage_kv,
    infer_project_type,
    normalize_project_id,
    parse_filed_date,
)
from gridlock.settings.loader import load_settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RULES = load_settings(REPOSITORY_ROOT / "config" / "gridlock.yaml").root.normalization


def _names(title: str) -> list[str]:
    return [endpoint.name for endpoint in extract_endpoints(title, RULES.endpoints).endpoints]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12/31/23", date(2023, 12, 31)),
        ("12/31/2024", date(2024, 12, 31)),
        ("06/01/2026", date(2026, 6, 1)),
        ("10/1/2025 (phase 1) and 10/1/2026 (phase 2)", None),
        ("TBD", None),
        ("", None),
        (None, None),
    ],
)
def test_dates_parse_only_when_the_whole_value_is_one_date(raw: str | None, expected: date | None) -> None:
    assert parse_filed_date(raw, RULES.date_formats) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Jasper – Okatie 230 kV #2: Construct", [230]),
        ("Okatie 230-115kV Substation", [115, 230]),
        ("BOWEN #10 500/230KV AUTOBANK REPLACEMENT", [230, 500]),
        ("Union Pier 115-13.8 kV Sub: Tap", [13.8, 115]),
        ("Stevens Creek - Hooks 115kV/LR Plumb Branch 46kV", [46, 115]),
        ("Edenwood Sub: #1 & #2 230-115kV Autobanks", [115, 230]),
        ("THOMASTON 230 NEW BUILD SUB", []),
    ],
)
def test_every_voltage_in_a_chain_is_kept(text: str, expected: list[float]) -> None:
    assert extract_voltage_kv(text, RULES.voltage_pattern) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("06367 D - G", "DESC-06367-D-G"),
        ("0139 M,N", "DESC-0139-M-N"),
        ("0167C-D", "DESC-0167C-D"),
        ("06076A", "DESC-06076A"),
    ],
)
def test_project_ids_normalize_to_code_and_tokens(raw: str, expected: str) -> None:
    assert normalize_project_id("DESC", raw) == expected


def test_project_id_without_content_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_project_id("DESC", " - ")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Jasper – Okatie 230 kV #2: Construct", ["Jasper", "Okatie"]),
        ("Okatie-Bluffton 115kV: Rebuild", ["Okatie", "Bluffton"]),
        ("Hooks - Thurmond 115kV Tie: Rebuild", ["Hooks", "Thurmond"]),
        ("Stevens Creek - Hooks 115kV/LR Plumb Branch 46kV Rebuilds", ["Stevens Creek", "Hooks"]),
        ("SAV: MCINTOSH - PURRYSBURG 230KV REACTORS", ["MCINTOSH", "PURRYSBURG"]),
        ("SAV: GOSHEN (SAV) - MCINTOSH 115KV LINE REBUILD", ["GOSHEN", "MCINTOSH"]),
        ("EVANS PRIMARY - THURMOND DAM (USA) #5 115KV REBUILD", ["EVANS PRIMARY", "THURMOND DAM #5"]),
        ("GRID - ARKWRIGHT - LLOYD SHOALS 115KV", ["ARKWRIGHT", "LLOYD SHOALS"]),
        ("Canadys-Ritter 115KV-Rebld SPDC 230/115KV 1272 (Approx 18 Miles)", ["Canadys", "Ritter"]),
        ("Union Pier 115-13.8 kV Sub: Tap", ["Union Pier"]),
        ("Riverport Tap: Construct Tap", ["Riverport"]),
        ("THOMASTON 230 NEW BUILD SUB", ["THOMASTON"]),
        ("SAV: CC - BIG OGEECHEE 500/230KV (CC NETWORK IMPROVEMENTS)", ["BIG OGEECHEE"]),
    ],
)
def test_endpoints_are_site_names_only(title: str, expected: list[str]) -> None:
    assert _names(title) == expected


def test_pair_roles_and_parenthetical_qualifiers() -> None:
    extraction = extract_endpoints("LOWER RIVER - WEBB (APC) 115KV RECONDUCTOR", RULES.endpoints)

    assert extraction.status is EndpointStatus.EXPLICIT_PAIR
    assert [endpoint.role for endpoint in extraction.endpoints] == [EndpointRole.FROM, EndpointRole.TO]
    assert extraction.endpoints[1].qualifiers == ["APC"]
    assert extraction.warnings == []


def test_three_site_title_is_a_chain_with_via_role() -> None:
    extraction = extract_endpoints("Cameron Jct – Cameron – St Matthews 46 kV Rebuild", RULES.endpoints)

    assert extraction.status is EndpointStatus.CHAIN
    assert [endpoint.role for endpoint in extraction.endpoints] == [EndpointRole.FROM, EndpointRole.VIA, EndpointRole.TO]
    assert extraction.warnings


def test_single_site_title() -> None:
    extraction = extract_endpoints("Summerville: Replace and Spare 230-115kV 336MVA Auto Bank", RULES.endpoints)

    assert extraction.status is EndpointStatus.SINGLE_SITE
    assert extraction.endpoints[0].role is EndpointRole.SINGLE


def test_title_without_a_site_yields_no_endpoints() -> None:
    extraction = extract_endpoints("SMART VALVE INSTALLATION", RULES.endpoints)

    assert extraction.status is EndpointStatus.NONE
    assert extraction.endpoints == []


def test_multi_circuit_and_customer_titles_are_flagged() -> None:
    multi = extract_endpoints("Queensboro - Ft Johnson 115 kV & Queensboro-Bayfront 115kV", RULES.endpoints)
    customer = extract_endpoints("CC - MICROSOFT - SHUGART (CCO06)", RULES.endpoints)

    assert any("more than one circuit" in warning for warning in multi.warnings)
    assert any("Customer-connection" in warning for warning in customer.warnings)


def _type(title: str, description: str | None = None) -> ProjectType:
    status = extract_endpoints(title, RULES.endpoints).status
    return infer_project_type(title, description, status, RULES.project_types, RULES.endpoints)


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        # A named pair is a line even when the description mentions a substation.
        ("Jasper – Okatie 230 kV #2: Construct", "Construct a 230 kV line ... to Okatie 230/115kV Substation.", ProjectType.TRANSMISSION_LINE),
        # "PRIMARY" is part of a substation name, not a substation-type keyword.
        ("EVANS PRIMARY - THURMOND DAM (USA) #5 115KV REBUILD", None, ProjectType.TRANSMISSION_LINE),
        ("St George - Sumter 230kV Tie: Rebuild Line from Santee Substation", None, ProjectType.TRANSMISSION_LINE),
        ("SAV: MCINTOSH - PURRYSBURG 230KV REACTORS", None, ProjectType.REACTOR),
        ("BOWEN #10 500/230KV AUTOBANK REPLACEMENT", None, ProjectType.SUBSTATION),
        ("SAV: LITTLE OGEECHEE 230-115KV: RELAY MODERNIZATION", None, ProjectType.SUBSTATION),
        ("KATHLEEN AREA IMPROVEMENTS", None, ProjectType.OTHER),
    ],
)
def test_project_type_rules(title: str, description: str | None, expected: ProjectType) -> None:
    assert _type(title, description) is expected
