# GridLock — V1 Build Plan

## Context

`GRIDLOCK_BUILD_HANDOFF.md` specifies GridLock, a ShellHacks 2026 / Sperry Tech entry.

**What it does:**
- It reads public construction plans from two utilities: Dominion Energy SC (DESC) and Georgia Power (GPC).
- It resolves each project to public OSM geometry.
- It finds cross-utility spatial and timeline overlaps using deterministic rules.
- It compresses the pairwise overlaps into a few **coordination zones**.
- It shows them in a planner UI, with Evidence Quality kept separate from Opportunity Priority.

**Repo state:** the repo is empty (LICENSE, a one-line README, the handoff doc). The source files are in `~/Downloads/Sperry-Tech-Challenge/`.

**Goal:** reach the §25 V1 acceptance criteria in verifiable phases, following these rules:
- Nothing is hardcoded.
- The layout is ready to extend (for example, a third utility).
- You approve every step.

## Locked decisions

| Topic | Decision |
|---|---|
| GPC scope | Sponsors **GPC + SAV only** (122 + 16 = **138**). `sponsor` is kept as a field. Which sponsors count is set in the utility config. |
| AI | **Regex parsers are primary.** Every DESC and GPC field is labeled, so regex is clearly easier. **OpenAI** (`OPENAI_API_KEY`) is used only as a fallback for endpoint extraction when regex is ambiguous, and optionally for explanations built from verified facts. AI output passes a schema gate, is tagged `ai_suggested`, and never decides geometry, distance, tiers, edges, zones, or evidence. |
| Raw files | Copied to `data/raw/` and **gitignored**. Normalized JSON and the OSM cache **are committed**, so a fresh clone can run the demo offline. |
| Thresholds | Canonical km values from the handoff: `<1.6`, `<8`, `<40` (discard at ≥40). Crossing means distance == 0 or intersects. The display unit (km or mi) is set in config. |
| Stack | **Backend:** Python (uv), pydantic v2, shapely 2, pyproj, networkx, rapidfuzz, pypdf, httpx, FastAPI, pytest. **Frontend:** Next.js + TypeScript + MapLibre GL (no map token), pnpm. |
| Wire format | snake_case in Python and camelCase JSON on the wire, via a pydantic alias generator. JSON Schema is generated from the models, and TS types are generated from that schema, so the contract is defined once. |

## Working agreement (approval gates)

I stop and ask before each of the following:
1. Starting each phase.
2. Any dependency install (`uv add`, `pnpm add`).
3. Any network call to Overpass, Nominatim, or OpenAI.
4. Copying files into `data/raw/`.
5. Any git branch or commit. The first step proposed is creating a `build/v1` branch off `main`.

At each **Phase-end outcome**, I show the evidence (command output and file paths) and wait for your sign-off.

**Stretch goals S1–S7 stay locked until you explicitly unlock them.**

## Facts found in the source data (these drive the design)

**DESC PDF (44 pages):**
- One project per page, with labeled fields: title, `Project ID`, `Project Description`, `Project Status`, `Planned In-Service Date` (in both `12/31/23` and `12/31/2024` formats), and a cost table ending in `Total*`.
- Raw IDs are messy: `06367 D - G`, `0139 M,N`, `0167C-D`.
- There is **no start date**, so DESC has in-service dates only.

**GPC IRP (668 pages):**
- Ten-Year Plan summary table on pp. 177–190: Zone / Year / TEAMS # / Name / Need Date / Sponsor.
- One detail page per project on pp. 214–425. Each has `Teams #`, **`Need Date` + `Start Date`**, and a description.
- All costs are `REDACTED`.
- Pages after 474 are unrelated.
- Every page carries a CEII banner, but the document is the *PUBLIC DISCLOSURE* version.

**Sponsor `Projects_Overlaps.xlsx`:**
- 10 projects and 6 overlaps, computed **center-to-center with haversine, in miles**.
- It is used **only as a test oracle**. Its lat/lons never become geometry, because it is a secondary source (I-1/I-3), it lists McIntosh with two different longitudes, and it has no coordinates for Hooks Sub.

**Mixed timeline case (the handoff doesn't cover it):**
- Almost every DESC×GPC pair compares a DESC in-service date against a GPC start→need span.
- Rule: the primary metric is the **in-service/need-date gap** (`IN_SERVICE_GAP`).
- A separate flag, `ISD_WITHIN_FILED_SPAN`, is set when the DESC ISD falls inside the GPC filed span. It is **never** labeled a construction overlap (I-6).
- GPC `Start Date` is shown as "project start (as filed)".
- `WINDOW_OVERLAP` is used only when both sides have explicit windows.

**Other data notes:**
- DESC was formerly SCE&G, so OSM operator tags may use legacy names. The alias lists are seeded from the operators actually found in the cache, not from memory.
- GPC costs are redacted, so any cost/impact estimate (challenge bonus / S2) can only use DESC figures. That is your decision to make later.

## Repository layout (built to be extended)

```text
GridLock/
├── config/
│   ├── gridlock.yaml              # ALL tunables: paths, thresholds, timeline buckets, evidence weights,
│   │                              # zone guards, ranking order, playbooks, bbox, CRS, Overpass/Nominatim/AI
│   │                              # settings, resource limits, UI labels/units
│   ├── utilities/                 # one file per utility → a 3rd utility = add a file + a parser
│   │   ├── desc.yaml              # id, display name, color, states, operator aliases, sources
│   │   │                          #   (file, parser id, page ranges, field labels)
│   │   └── gpc.yaml               # + included sponsors [GPC, SAV]
│   └── overrides/
│       └── geometry_overrides.yaml  # human-verified matches, each with provenance + reviewer note
├── backend/
│   ├── pyproject.toml             # uv project, pinned Python, `gridlock` CLI entry point
│   ├── src/gridlock/
│   │   ├── settings/              # config loader + pydantic config models (fails fast on bad config)
│   │   ├── models/                # Project, Endpoint, SourceRef, GeometryResolution, Evidence,
│   │   │                          #   Relationship, Timeline, Zone, Payload, Metadata
│   │   ├── ingestion/
│   │   │   ├── documents/         # Parser protocol + registry; desc_project_descriptions.py; gpc_irp_ten_year.py
│   │   │   └── osm/               # Overpass client (backoff/timeout), query builder, GeoJSON cache
│   │   ├── extraction/            # AI adapter interface + openai_provider.py (off unless enabled + key)
│   │   ├── normalization/         # dates, voltage, IDs, endpoint parsing, name normalization
│   │   ├── georesolution/         # candidate gen, vetoes, scoring, geometry ladder, overrides
│   │   ├── evidence/              # deterministic Evidence Quality from config weights
│   │   ├── overlap/               # distance, spatial tiers, timeline relation, playbooks
│   │   ├── graph/                 # networkx project graph
│   │   ├── zones/                 # components + span guards + deterministic split + naming
│   │   ├── ranking/               # Opportunity Priority
│   │   ├── metrics/               # compression ratio, resolution rate, distributions
│   │   ├── contract/              # JSON Schema export + payload validation
│   │   ├── pipeline/              # stage orchestration + CLI (`gridlock <stage>`)
│   │   └── api/                   # FastAPI read-only: /api/payload, /api/health
│   └── tests/{unit,integration,fixtures}/
├── contract/gridlock.schema.json  # generated; the frontend's TS types are generated from it
├── frontend/                      # Next.js app router
│   └── src/{app,components/{map,zones,timeline,evidence},lib/{api,contract}}/
├── data/
│   ├── raw/        (gitignored)   # source PDFs/docx/xlsx
│   ├── fixtures/                  # hand-built demo payload (clearly labeled FIXTURE)
│   ├── cache/                     # osm_power.geojson + .meta.json, AI/Nominatim response caches
│   ├── normalized/                # projects.json, projects_resolved.json
│   ├── review/                    # unresolved.csv (review queue input)
│   └── output/                    # gridlock.json (final payload), metrics.json
├── docs/                          # architecture, config reference, data-decisions log
├── .env.example                   # OPENAI_API_KEY, GRIDLOCK_CONFIG, GRIDLOCK_RAW_DIR,
│                                  #   NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_MAP_STYLE_URL
└── .gitignore                     # .env*, !.env.example, data/raw/, node_modules, .venv
```

**How "no hardcoding" is enforced:**
- Every number, label, path, URL, model name, page range, and field label comes from `config/` or `.env`.
- Parsing *logic* lives in code, but the labels it searches for come from config.
- The frontend contains **no domain logic**. Thresholds, tier labels, utility colors, and unit settings all arrive in `payload.metadata`.
- A unit test fails if the thresholds used by the engine don't come from the loaded config.

---

## Phase 0 — Foundation & configuration

**Tasks:**
- Create the `build/v1` branch.
- Create the folder skeleton, `.gitignore`, and `.env.example`.
- Set up the uv project with a pinned Python (3.13, after verifying shapely/pyproj wheels exist; falls back to 3.12).
- Write the config loader, with pydantic validation of `gridlock.yaml` and `utilities/*.yaml`.
- Add the CLI skeleton with `gridlock config show` and a pytest harness.
- Copy the source files into `data/raw/`.
- Scaffold the empty Next.js app, which reads its API base URL from env.

**Phase-end outcome:**
- [ ] `uv run gridlock config show` prints the resolved config: thresholds 1.6/8/40 km, utilities DESC and GPC, GPC sponsors [GPC, SAV].
- [ ] An invalid config (e.g., tier thresholds out of order, or an unknown utility) is rejected with a clear error. This is covered by a test.
- [ ] `uv run pytest` is green.
- [ ] `pnpm dev` serves a blank GridLock shell.
- [ ] `git status` shows nothing from `data/raw/`, and `.env` is ignored.

## Phase 1 — Domain contract & fixture (the "freeze truth model" step)

**Tasks:**
- Write the pydantic models for every object in handoff §7 and §16.
- Enums: SpatialTier, TimelineType (`IN_SERVICE_GAP`, `WINDOW_OVERLAP`, `UNRESOLVED`) plus the `isdWithinFiledSpan` flag, GeometryMethod (the §9 ladder plus `human_verified_override`), EvidenceLevel, Priority.
- `gridlock contract export`: models → `contract/gridlock.schema.json` → `frontend/src/lib/contract.ts`.
- Hand-build `data/fixtures/demo_payload.json`, labeled as a fixture.

**Phase-end outcome:**
- [ ] `uv run gridlock contract export` generates both the schema and the TS types, and the generated files are identical on re-run.
- [ ] `uv run gridlock contract validate data/fixtures/demo_payload.json` passes.
- [ ] Changing a tier value to `"FOO"` in a copy makes validation fail.
- [ ] The camelCase wire keys match handoff §16 (`distanceKm`, `closestPoints`, `spatialTier`, …).

## Phase 2 — Planning data ingestion & normalization

**Tasks:**
- Parser registry keyed by the utility config.
- **DESC parser:** one page = one record. The field labels come from config.
- **GPC parser:** parse the summary table and the detail pages, then join on TEAMS #. Use the detail-page name, because summary names wrap across lines. Filter to the configured sponsors.
- **Normalization:**
  - 2-digit and 4-digit years → ISO dates.
  - A dates that won't parse stays `null`, and its raw text is kept.
  - Voltage → a numeric kV list.
  - One tested ID-normalization rule, plus a uniqueness check.
  - `REDACTED` cost → `null`, with the raw string kept.
  - Endpoints are pulled from the name with regex patterns set in config.
- Every record carries `source` (document, page, raw ID, raw text).
- **AI decision point:** print the records whose endpoints regex couldn't confidently extract. If any exist, I ask you before enabling the OpenAI fallback on just those records.

**Phase-end outcome:**
- [ ] `uv run gridlock ingest plans` writes `data/normalized/projects.json`.
- [ ] The report shows **DESC = 44, GPC = 138** (GPC 122 + SAV 16), with 0 duplicate IDs.
- [ ] The report includes per-field null counts.
- Spot checks, printed by `gridlock inspect project <id>`:
  - [ ] DESC `06367 D - G` → "Jasper – Okatie 230 kV #2: Construct", 230 kV, endpoints Jasper/Okatie, ISD **2025-12-31**, cost **$23,787,423**, page **23**.
  - [ ] GPC TEAMS **20277** → "SAV: MCINTOSH - PURRYSBURG 230KV REACTORS", sponsor SAV, start **2024-01-01**, need **2026-06-01**, page **227**, cost `null` (raw `REDACTED`).
  - [ ] GPC TEAMS **20793** (Evans Primary – Thurmond Dam #5) → need 2033-06-01.
- [ ] The list of ambiguous-endpoint records has been reviewed, and you have made the AI fallback call.
- [ ] Unit tests cover dates, voltage, IDs, and null preservation.

## Phase 3 — OSM geo ingestion & cache

**Tasks:**
- Overpass client. The endpoint, timeout, backoff, max retries, and bbox (GA+SC corridor) all come from config.
- The query covers the power feature types listed in config (substation, line, and others).
- Convert the response to GeoJSON and write the cache plus a metadata file (`source`, `retrieved_at`, `bbox`, `query_version`).
- An `--offline` flag reads only from the cache.
- I will **ask before the network call.**

**Phase-end outcome:**
- [ ] `data/cache/osm_power.geojson` and `osm_power.meta.json` exist.
- [ ] Feature counts are printed by power type.
- [ ] `data/cache/osm_operators.csv` lists each distinct `operator` value with its count. You review it, and the DESC/GPC operator aliases in `config/utilities/*.yaml` are seeded from it.
- [ ] `uv run gridlock ingest osm --offline` succeeds with networking disabled.
- [ ] The response size is bounded by the configured bbox and limits.

## Phase 4 — Project ↔ infrastructure resolution, geometry & Evidence Quality

**Tasks:**
- Name normalization (e.g., "Sub" / "Primary" / "(SAV)" / "(USA)" stripped via config lists) plus rapidfuzz similarity.
- Candidates are generated using type, voltage, operator (aliases), and region.
- **Deterministic vetoes:** wrong explicit operator, wrong state/region, incompatible voltage, incompatible type, corrupt geometry.
- The §9 geometry ladder, with `is_approximation` set explicitly.
- `geometry_overrides.yaml` holds human-verified matches, each with provenance and its own evidence rule.
- Nominatim is a gated, throttled, cached fallback, used only for unresolved records (asked first).
- Evidence Quality is computed from the §10 weights in config, with reasons, warnings, and a level.
- Unresolved projects stay in the dataset but get no geometry.

**Phase-end outcome:**
- [ ] `uv run gridlock resolve` writes `projects_resolved.json` and `data/review/unresolved.csv`.
- [ ] The printed report includes:
  - the **auto-resolution rate**
  - the **geometry-method distribution** (full / endpoints / single / approx / unresolved)
  - the **evidence distribution** (High / Medium / Low)
- [ ] Jasper and Okatie resolve to specific OSM feature IDs, and DESC `06367 D-G` shows a full evidence breakdown (✓ / △ lines, as in §10).
- [ ] **Oracle sanity check:** a table shows our resolved endpoints against the sponsor xlsx coordinates, with the distance between them. Large mismatches are listed for your review.
- [ ] Tests cover exact match, abbreviated operator, missing operator, wrong-region rejection, voltage-conflict veto, and geometry downgrade.
- [ ] Re-running `resolve` produces byte-identical output (I-7).

## Phase 5 — Overlap engine

**Tasks:**
- Cross-utility pairs only, with a cheap bbox prefilter.
- Nearest points are found in the projected CRS set in config (chosen to cover GA+SC; the zone-edge limitation is documented). The reported distance is the **geodesic** distance between those points (`pyproj.Geod`), and intersecting geometries → 0 / CROSSING.
- Tier classification comes from config. Timeline relation uses the mixed-case rule above, with the buckets 90/180/365 from config. Playbooks come from config.
- Projects without geometry are excluded from spatial claims.

**Phase-end outcome:**
- [ ] `uv run gridlock overlap` writes `data/output/relationships.json` and prints counts per tier.
- [ ] Assertions: 0 pairs ≥ 40 km, 0 same-utility pairs, and every relationship has closest points and a geometry method.
- [ ] **Oracle check:** all 6 sponsor overlap pairs are detected (a superset check), shown next to our closest-point km. Differences from their center-to-center miles are expected and explained.
- [ ] Boundary tests at 0 / 1.599 / 1.600 / 7.999 / 8.000 / 39.999 / 40.000 km pass.
- [ ] Timeline tests (same day, 90, 180, 365, missing, true window overlap, mixed ISD-within-span flag) pass.
- [ ] Geometry tests (point↔point, point↔line, line↔line, crossing = 0, endpoint fallback) pass.
- [ ] The same inputs give identical distance and points (I-4).

## Phase 6 — Graph, zones, ranking, final payload & API

**Tasks:**
- networkx graph: nodes are projects, edges are valid relationships (I-8).
- Connected components are checked against guards (`max_zone_geographic_span_km`, `max_zone_timeline_span_days`, `max_zone_projects` from config). Any component that breaks a guard is split deterministically.
- Zones are named deterministically from their member endpoints.
- Opportunity Priority: spatial tier first, then timeline relevance, then density. Evidence stays separate (I-9).
- Metrics: compression ratio, resolution rate, evidence and geometry distributions.
- The payload is assembled with metadata (thresholds, labels, units, utility colors, source snapshot info).
- FastAPI serves the payload read-only.
- `gridlock run` runs the full pipeline.

**Phase-end outcome:**
- [ ] `uv run gridlock run --offline` writes `data/output/gridlock.json`, which passes contract validation.
- [ ] The printed summary includes: the **number of zones**, the **attention compression ratio** (relationships / zones), and the top zone with its projects, closest km, date gap, and themes. All numbers are real, none invented.
- [ ] Two consecutive runs produce identical SHA-256 hashes.
- [ ] Graph tests pass: isolated node, one edge, multi-edge component, and a chain that needs splitting.
- [ ] Invariant tests I-1 through I-10 pass. Example: a low-evidence crossing still ranks as a crossing, with a warning.
- [ ] `curl $API/api/payload` returns the payload.

## Phase 7 — Planner frontend

**Tasks:**
- Build against the fixture first, then point to the API via env.
- **Landing:** "N Coordination Zones Found" plus ranked zone cards.
- **Zone detail:**
  - A MapLibre map showing both utilities, the highlighted zone, and a **closest-point connector**.
  - A timeline. In-service-only projects render as markers, never as bars.
  - A "Why GridLock flagged it" panel.
- **Evidence drawer:** source record, geometry method, matched OSM feature, score breakdown, and warnings.
- **Offline basemap fallback:** a bundled state-boundary GeoJSON is used when `NEXT_PUBLIC_MAP_STYLE_URL` is unreachable.
- Loading and error states.

**Phase-end outcome (visual checklist you run):**
- [ ] The landing headline count equals `zones.length` from the API.
- [ ] Clicking a zone flies the map to it, shows both utilities' geometries, and draws the connector. The distance label matches the JSON.
- [ ] The timeline never shows a bar for a DESC in-service-only date. GPC's start→need span is labeled "as filed".
- [ ] The evidence drawer shows the page number and raw ID for the selected project.
- [ ] Approximated geometry is visibly styled and labeled (I-10).
- [ ] With Wi-Fi off, the page still renders zones and geometries over the fallback basemap.
- [ ] `grep` shows no tier thresholds or utility names hardcoded in `frontend/src`.

## Phase 8 — Integration, hardening & demo freeze

**Tasks:**
- End-to-end integration test: the real DESC↔GPC path from source record to normalized project, geometry, relationship, zone, and frontend JSON.
- Tests for malformed and missing geometry.
- A full no-internet demo run.
- Input hardening: file-type allowlist, size limits, and AI output treated as untrusted and schema-gated.
- Logging of stage, project ID, match status, and evidence, with no secrets logged.
- README (quick-start, known gaps) and `docs/` (architecture, config reference, data-decisions log).
- The final real metrics are written to `data/output/metrics.json`.

**Phase-end outcome:**
- [ ] Every item in the §25 V1 acceptance checklist is ticked, each with a pointer to the command, test, or screenshot that proves it.
- [ ] A fresh clone plus `.env` plus the documented commands brings up the demo with no network.
- [ ] A 3-minute demo path (§27) is rehearsed against real output.

**Stop at the V1 boundary.**
- S1–S7 stay locked.
- S2 (the cost/impact bonus) can only use DESC costs, because GPC costs are redacted. Whether to unlock it is your call after V1.

---

## Verification (end-to-end)

```bash
cd backend && uv run pytest                        # unit + integration + invariants
uv run gridlock run --offline                      # full pipeline from caches
uv run gridlock contract validate ../data/output/gridlock.json
uv run uvicorn gridlock.api.app:app                # API (host/port from env)
cd ../frontend && pnpm dev                         # UI (API URL + map style from .env)
```

Every phase-end outcome above is a subset of this flow, checked with the specific numbers listed in that phase.
