# Architecture

GridLock is a deterministic pipeline that writes versioned files, a
read-only API over its final payload, and a Next.js planner that renders
that payload without any domain logic of its own.

```
public filings ──► ingest plans ──► data/normalized/projects.json
OSM (Overpass) ──► ingest osm   ──► data/cache/osm_power.geojson
                        │
                        ▼
                     resolve    ──► data/normalized/projects_resolved.json
                        │           data/review/unresolved.csv
                        ▼
                     overlap    ──► data/output/relationships.json
                        │
                        ▼
      graph → rank → zones → metrics → impact ──► data/output/gridlock.json
                                         data/output/metrics.json
                        │
                        ▼
              FastAPI (/api/*)  ──►  Next.js planner (/, /planner)
```

Each stage reads only the previous stage's files and `config/`, so any
stage can be rerun alone (`gridlock <stage>`), and a full run reproduces
every committed output byte-for-byte.

## Stages

| Stage | Command | Module | What it decides |
|---|---|---|---|
| Plans | `gridlock ingest plans` | `ingestion/documents`, `normalization` | Fields, dates, voltages, endpoints, provenance |
| OSM | `gridlock ingest osm [--offline]` | `ingestion/osm` | The cached public power-feature snapshot |
| Resolve | `gridlock resolve` | `georesolution`, `evidence` | Endpoint matches, geometry ladder, Evidence Quality |
| Overlap | `gridlock overlap` | `overlap` | Closest points, distance, tier, timeline, playbook |
| Payload | `gridlock payload` | `graph`, `ranking`, `zones`, `metrics`, `impact`, `pipeline` | Priority, rank, zones, metrics, coordination impact (S2, computed after zones from their output), final payload |
| All | `gridlock run --offline [--skip-ingest]` | `pipeline` | Every stage in order |
| Serve | `gridlock serve` | `api` | Nothing; read-only HTTP over the payload |

## The contract

`backend/src/gridlock/models/domain.py` is the single source of truth.
`gridlock contract export` writes `contract/gridlock.schema.json` (the
serialization schema: what the API emits) and generates
`frontend/src/lib/contract.ts` from it. Python uses snake_case; the wire
uses camelCase through a Pydantic alias generator.

## Where each invariant is enforced

| Invariant (handoff §21) | Enforced in | Tested in |
|---|---|---|
| I-1 Provenance | `SourceRef` is required on every project | `test_payload_invariants::test_i1_*` |
| I-2 No fabricated fields | Unknowns stay `null` with raw text kept | `test_i2_*`, `test_plan_ingestion` |
| I-3 No AI geometry truth | Geometry only from matched or overridden points; AI disabled | `test_i3_*`, `test_hardening` |
| I-4 Distance reproducibility | `overlap/geometry.py` (deterministic contact point) | `test_i4_*`, `test_overlap` |
| I-5 One threshold source | `thresholds_km` in config, shipped in metadata | `test_i5_*` |
| I-6 Timeline semantics | `overlap/classify.py`; filed spans never windows | `test_i6_*` |
| I-7 Evidence reproducibility | `evidence/quality.py` from config weights | `test_i7_*` |
| I-8 Cross-utility edges | `graph/builder.py` rejects same-utility edges | `test_i8_*`, `test_graph_zones` |
| I-9 Evidence never hides a crossing | Priority rules ignore evidence | `test_i9_*` |
| I-10 Approximation disclosure | `isApproximation` on projects and relationships | `test_i10_*` |

## Frontend

- `src/lib/api.ts` checks `/api/health` names the expected service, then
  fetches `/api/payload` once per page.
- `src/lib/format.ts` formats numbers and looks up every label in
  `payload.metadata.labels`.
- `src/lib/mapData.ts` turns the payload into GeoJSON; it only decides
  emphasis (top pair, zone, background), never analysis.
- `src/components/planner/` holds the planner: a section nav and four
  views (Overview, Zones, Projects, Data quality) under
  `components/planner/views/`, plus the zone rail, both MapLibre maps,
  zone panel, timeline and evidence drawer. The view and selected zone
  live in the URL (`?view=zones&zone=ZONE-01`, `src/lib/plannerState.ts`).
- `src/lib/presentation.ts` re-expresses backend results for display
  (location status, "Shared endpoint" when both projects end at the same
  matched feature, priority counts); it never classifies or ranks.
- `src/lib/mapBase.ts` creates both maps: the online style for the
  current theme, the bundled fallback, and restyling on a theme change.
- Light and dark themes share one set of CSS tokens in
  `src/app/globals.css`; `[data-theme="light"]` only changes values.
  `src/lib/themeScript.ts` applies the stored choice before first paint,
  and `components/shared/SiteNav.tsx` is the one header on every page.
