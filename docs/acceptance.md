# V1 acceptance evidence

The handoff's §25 checklist, each item with the command, test or
screenshot that proves it. Test paths are under `backend/tests/`; the
browser checks ran against a production build (see the last section).

| # | Criterion | Evidence |
|---|---|---|
| 1 | At least two utilities are represented | `metrics.projectsByUtility`: DESC 44, GPC 138 · `integration/test_plan_ingestion.py::test_counts_match_configured_scope` |
| 2 | Public project records are normalized with provenance | `data/normalized/projects.json` (document, page, raw ID, raw fields on every record) · `gridlock inspect DESC-06367-D-G` · `integration/test_payload_invariants.py::test_i1_*` |
| 3 | Geo infrastructure is loaded from cached public data | `data/cache/osm_power.geojson` + `osm_power.meta.json` (query, count, SHA-256, ODbL) · `gridlock ingest osm --offline` · `unit/test_osm_cache.py::test_offline_mode_uses_only_cache` |
| 4 | At least one real project has verified or transparently approximated geometry | 120 of 182 located, each with its method and `isApproximation` · `integration/test_end_to_end.py::test_flagship_record_traces_from_filing_to_frontend_json` |
| 5 | Exact closest-distance logic works | `overlap/geometry.py` · `unit/test_overlap.py` (point↔point, point↔line, line↔line, crossing, shared endpoint, symmetry) · `test_i4_*` recomputes every stored distance |
| 6 | >40 km relationships are excluded | `unit/test_overlap.py::test_tier_boundaries` (40.000 → discarded) · `integration/test_overlap_pipeline.py::test_phase_5_invariants` |
| 7 | Spatial tiers work at required thresholds | `test_tier_boundaries` at 0 / 1.599 / 1.600 / 7.999 / 8.000 / 39.999 / 40.000 km · `test_i5_*` |
| 8 | Timeline is computed without inventing windows | `unit/test_overlap.py` timeline tests · `test_i6_*` · browser check: timeline bars only where a filed span exists (14 rows, 11 bars) |
| 9 | Evidence Quality is deterministic and explainable | `evidence/quality.py` from config weights · `test_i7_*` rescoring · breakdown and ✓/△ reasons in the evidence drawer (`docs/assets/evidence-drawer.png`) |
| 10 | Relationship graph exists | `graph/builder.py` · `unit/test_graph_zones.py` (isolated node, one edge, multi-edge component, same-utility edge rejected) |
| 11 | Coordination zones exist with anti-chain guards | `zones/builder.py` · `test_chain_beyond_the_span_guard_is_split_without_losing_relationships` · `test_timeline_guard_splits_only_in_split_mode` |
| 12 | Ranked planner-facing output exists | `data/output/gridlock.json` (zones and relationships ranked) · `test_savannah_leads_and_thurmond_stays_a_crossing` |
| 13 | Interactive map works | Browser check: selecting a zone updates the address, map connector and panel · `docs/assets/planner.png` |
| 14 | User can click a zone and understand why it was flagged | "Why GridLock flagged it" panel (backend reasons, tier, relevance, priority, themes) · `test_zone_headline_figures_all_come_from_the_top_relationship` |
| 15 | User can inspect provenance/evidence | Evidence drawer: page 23, raw ID `06367 D - G`, method, breakdown, warnings, OSM feature links (browser check) |
| 16 | Demo works without live Overpass/Nominatim | Fresh clone, all network blocked: 26/26 browser checks pass; bundled basemap in about 1.5 s · `docs/assets/planner-offline.png` |

## Phase 8 outcomes

- **Every §25 item is ticked** — the table above.
- **A fresh clone plus `.env` plus the documented commands brings up the
  demo with no network.** Verified by cloning the branch into an empty
  folder and running everything with proxies pointed at a dead port:
  `uv sync --offline`, `gridlock run --offline --skip-ingest` (reproduced
  every committed output, `git status` clean), `pnpm install --offline`,
  `pnpm build`, `gridlock serve`, `pnpm start`. The browser blocked every
  non-localhost request; all 26 checks passed.
- **The 3-minute demo is rehearsed against real output.** An automated
  walkthrough of `docs/demo-script.md` on the offline fresh clone found
  every quoted figure on screen at each of its 5 steps.

## Browser checks

26 checks against a production build: landing copy and call to action;
landing metrics equal the payload; featured zone is the payload's #1;
headline count equals `zones.length`; zones in backend order with
Jasper – McIntosh first; connector distance equals the JSON; panel figures
come from the top relationship; both utilities in the legend; approximate
geometry labelled; timeline bars only where a filed span or window exists,
labelled "as filed"; the filed-span flag never called a confirmed
overlap; coverage says "not assessed" means unknown; evidence drawer shows
page, raw ID, method, breakdown and warnings; Escape closes it; selecting
a zone updates map and panel; no runtime errors; offline basemap fallback
with geometry intact; no horizontal overflow at 390 and 900 px.
