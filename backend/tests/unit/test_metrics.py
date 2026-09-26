from __future__ import annotations

import pytest

from gridlock.models.domain import Metrics, ResolutionBreakdown


def _metrics(**overrides) -> dict:
    breakdown = ResolutionBreakdown(located_automatically=119, located_human_verified_only=1, not_located_unresolved=59, not_located_no_named_site=3)
    desc = ResolutionBreakdown(located_automatically=28, located_human_verified_only=1, not_located_unresolved=15, not_located_no_named_site=0)
    gpc = ResolutionBreakdown(located_automatically=91, located_human_verified_only=0, not_located_unresolved=44, not_located_no_named_site=3)
    values = dict(
        projects=182,
        projects_by_utility={"DESC": 44, "GPC": 138},
        located_projects=120,
        not_assessed_by_utility={"DESC": 15, "GPC": 47},
        resolution=breakdown,
        resolution_by_utility={"DESC": desc, "GPC": gpc},
        projects_with_named_endpoints=179,
        automatic_resolution_rate=0.665,
        human_verified_endpoints=3,
        relationships=55,
        relationships_by_tier={},
        zones=4,
        attention_compression_ratio=13.75,
        evidence_distribution={},
        geometry_distribution={},
    )
    values.update(overrides)
    return values


def test_reconciled_metrics_validate() -> None:
    metrics = Metrics(**_metrics())

    assert metrics.resolution.total == 182
    assert metrics.resolution.located == 120
    assert metrics.resolution.not_located == 62


@pytest.mark.parametrize(
    "overrides",
    [
        {"located_projects": 121},
        {"projects_with_named_endpoints": 182},  # ignores the three titles that name no site
        {"automatic_resolution_rate": 0.67},  # 120/179 counts the human-verified project as automatic
        {"not_assessed_by_utility": {"DESC": 15, "GPC": 44}},
    ],
)
def test_metrics_that_do_not_reconcile_are_rejected(overrides: dict) -> None:
    with pytest.raises(ValueError, match="do not reconcile"):
        Metrics(**_metrics(**overrides))
