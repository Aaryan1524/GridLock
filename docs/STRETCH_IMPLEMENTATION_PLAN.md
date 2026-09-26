# GridLock: final hackathon stretch implementation plan

Status: **proposal, awaiting approval.** No stretch code exists yet.

Baseline: `origin/main` at `4d01fcd`. This includes V1, the planner sections, both themes, the shared navbar, `/team` and the page entrance (PRs #13–#16).

Every figure below was read from the committed output (`data/output/gridlock.json`) or measured on this baseline, unless it is marked *proposed*.

---

## 1. Current-state architecture

```
config/gridlock.yaml + config/utilities/*.yaml + config/overrides/*.yaml
        │  (every threshold, rule, label, limit, path)
        ▼
backend/src/gridlock/pipeline/run.py :: run_pipeline(bundle, repository_root, offline, skip_ingest, log)
  1 ingest_plans     ingestion/documents/plans.py   raw PDFs → data/normalized/projects.json
                                                    (or the committed snapshot when --skip-ingest)
  2 ingest_osm       ingestion/osm/cache.py         data/cache/osm_power.geojson (offline: read only,
                                                    except it rewrites osm_operators.csv)
  3 resolve_projects georesolution/resolver.py      → data/normalized/projects_resolved.json, data/review/unresolved.csv
  4 run_overlap      overlap/engine.py              → data/output/relationships.json
  5 build_payload    pipeline/payload.py            rank → graph → zones → metrics → data/output/gridlock.json
        │
        ▼
api/app.py (FastAPI, read-only, GET only)   /api/health  /api/payload  /api/zones/{id}
        │   the payload JSON is re-read when the file changes
        ▼
frontend (Next.js 15)   lib/api.ts usePayload() → one GET /api/payload per page
  /            Landing
  /planner     Overview · Zones · Projects · Data quality (view and zone in the URL)
  /team
```

**Facts that shape the plan:**

- **One pipeline already exists.** The CLI `gridlock run` calls `run_pipeline`. The API does not run anything today.
- **Stage file locations all come from `bundle.root.paths`.** These are `raw_dir`, `cache_dir`, `normalized_dir`, `output_dir` and `review_dir`, each joined to `repository_root`. An absolute path overrides the join. So an isolated run can be a copy of the bundle whose `normalized_dir`, `output_dir` and `review_dir` point into `data/runs/RUN-…/`. No stage needs rewriting.
- **Three places break isolation and need small refactors:**
  1. `ingest_osm(offline=True)` still writes `osm_operators.csv` into the shared cache.
  2. `raw_dir()` prefers the process-wide `GRIDLOCK_RAW_DIR` environment variable, which concurrent runs can't safely share.
  3. `--skip-ingest` reads the committed `normalized/projects.json` from the run's own folder, so a run must be seeded with that snapshot first.
- **Runtime:** a full offline run takes about **4–9 s** on this machine (snapshot mode 8.7 s cold; with PDF ingestion 4.4 s warm). It reproduces the committed outputs byte-for-byte: `git status` stays clean after a run.
- **The engine rules are pure functions.** S3 can reuse them in memory:
  - `overlap/classify.py`: `timeline_relation`, `gap_relevance`
  - `ranking/priority.py`: `opportunity_priority`, `rank_relationships`
  - `pipeline/payload.py`: `assemble_payload(bundle, root, projects, relationships)`, which builds without writing
- **Upload validation already exists.** `check_source_file` checks for an in-folder path, the `.pdf` extension, the `%PDF-` signature and the 50 MB `limits.max_document_bytes`.
- **The parsers are tied to these documents' layouts.** The page ranges are in config: Dominion pp. 1–44; Georgia Power summary pp. 177–190 and detail pp. 214–425. Uploads can therefore only work for these editions, or for files with identical layout.
- **Dominion costs are real; Georgia Power costs are all redacted.** Zone 1 holds 3 Dominion projects with filed costs totalling $75,564,356, and 11 Georgia Power projects with none.
- **The priority rules already separate actionable pairs from background.** Zone 1 has 33 relationships:
  - 1 HIGH, 2 MEDIUM, 30 LOW.
  - The actionable ones are 06367 D-G × 20277 (4.89 km, 152 days, MEANINGFUL) and 06367 D-G × 20065 (4.89 km, 517 days, WEAK).
  - Also actionable: 6808-S × 20067 (25.656 km, 0 days, STRONG).

---

## 2. Phase A — S2: Coordination Impact Estimator

### A.1 Product goal
A planner looking at a zone asks: *"What might we actually gain by coordinating?"* S2 answers with ranges, and every number is traceable to either:
- an engine fact (which pairs, which projects, which filed costs), or
- a named, approved public assumption.

It never gives a savings figure without the arithmetic beside it.

### A.2 Existing components reused
- **Engine output:**
  - relationship `spatialTier`, `timeline.relevance`, `timeline.gapDays` and `opportunityPriority`
  - zone `relationshipIds` and `coordinationThemes`
  - project `estimatedCostUsd`, which is Dominion only
- **Config pattern:** a new `impact:` section in `config/gridlock.yaml`, validated by a pydantic model in `settings/models.py`, the same way `priority:` is.
- **Payload assembly:** `pipeline/payload.py :: assemble_payload` gets one more step after zones.
- **Frontend:**
  - `ZonePanel.tsx` gets a new section.
  - `lib/format.ts` provides the formatting.
  - The assumption citations appear in the Data quality "Source provenance" pattern.

### A.3 Architecture
```
zones + relationships + projects  ──►  impact/estimator.py :: estimate_zone_impact(zone, …, ImpactConfig)
                                         │ pure, deterministic, no I/O
                                         ▼
payload.impact = [ZoneImpact…]    (a new top-level list, keyed by zoneId)
payload.metadata.impactAssumptions = [the approved assumptions with sources]
                                         ▼
Zones panel → "Coordination impact"  (read-only rendering; the frontend does no arithmetic)
```

### A.4 Proposed calculation (every rule here needs your approval)

The calculation has four steps.

**Step 1: pick the coordinable pairs** (rule A-4). This is a policy choice with no external source, and it lives in config.
- **Shared staging** needs a pair whose tier is CROSSING, SHARED_CORRIDOR or SITE_LOGISTICS, *and* whose timeline relevance is OVERLAPPING, STRONG or MEANINGFUL.
- **Shared mobilization** needs a pair of any tier whose timeline relevance is OVERLAPPING, STRONG or MEANINGFUL.
- Pairs years apart are excluded. Coordinating those is sequencing, not sharing.

**Step 2: group the pairs into clusters.** Connected projects form one cluster. If a cluster has *k* projects, then between 1 and *k*−1 duplicates could potentially be avoided (rule A-5). The low end assumes only one cluster actually coordinates. The high end is Σ(*k*−1).

**Step 3: estimate the footprint.** Multiply the yards potentially shared by the acres per yard (assumption A-1).

**Step 4: estimate the Dominion budget in play.** This is not a savings figure. Add up `estimatedCostUsd` for the Dominion projects in mobilization clusters, and multiply by at most 5.5% (assumption A-2).
- This is an **upper bound** on the project-management and mobilization budget involved.
- Georgia Power's share is shown as "unknown: costs redacted", never estimated.
- Savings would be only a fraction of the bound. A savings figure would need assumption A-3, which has no public source.

**Illustrative result** under these proposed rules, for review only:

| Zone | Staging | Mobilization | Dominion budget in play |
|---|---|---|---|
| **Zone 1 · Jasper – McIntosh** | 1 cluster (06367 D-G × 20277), so 1 yard, so **2.8–13.0 acres** of temporary footprint | 2 clusters (06367 D-G × 20277; 6808-S × 20067), so **1–2 duplicate mobilizations** | ($23,787,423 + $40,660,000) × ≤5.5% = **up to $3,544,608** of Dominion project-management and mobilization budget |
| **Zone 2 · Thurmond** | No timely pairs | No timely pairs | None |
| **Zone 3** | No HIGH or MEDIUM pairs | — | None |
| **Zone 4** | No HIGH or MEDIUM pairs | — | None |

- Zone 2 reads "Coordination here is crossing structures and outage sequencing; the dates are 3,074 days apart, so there's no shared-mobilization estimate."
- Zones 3 and 4 read "No timely coordination opportunity, so no impact is estimated."

### A.5 Assumption register (Gate A0: your approval needed before any code)

| ID | Assumption | Proposed value | Public source (checked) | Caveat |
|---|---|---|---|---|
| A-1 | Temporary footprint of one staging / laydown yard | 2.8–13.0 acres (the final min–max will come from the full table) | Southern California Edison, *West of Devers Upgrade Project* PEA §3.2, Table 3.2-A "Potential Staging Yard Locations" and Table 3.2-G, which list yards of about 2.8, 4.5 and 13.0 acres. <https://ia.cpuc.ca.gov/environment/info/aspen/westofdevers/pea/3.0_project_description_part3.pdf> | This is a California 220 kV project. It gives a realistic *range* of yard sizes, not a Southeast-specific value. |
| A-2 | Mobilization is part of project management, which is at most this share of project cost | ≤ 5.5%, used **only as an upper bound** | MISO, *Transmission Cost Estimation Guide for MTEP19* (Apr 16, 2019), p. 31: "5.5% of project cost estimate: Project management (including mobilization and demobilization)". This copy was read: <https://nocapx2020.info/wp-content/uploads/2019/07/Transmission-Cost-Estimation-Guide-for-MTEP-2019337433.pdf>. The official current edition, MTEP25, is at cdn.misoenergy.org, which blocks automated download; please confirm it keeps the 5.5% line. | The 5.5% covers *all* project management, not just mobilization, so it is only a ceiling. MISO's 20% contingency and 7.5% AFUDC adders are **not** applied. |
| A-3 | The share of one mobilization that's avoided when two projects share it | **Not proposed.** No public source was found. | — | **Recommended:** show only the A-2 "budget in play" ceiling, labelled as such. Alternatively, you could approve an explicitly *unsourced* GridLock planning assumption (for example 25–50%), shown in the UI with that label. |
| A-4 | Which pairs count as coordinable | The tier and relevance sets in A.4 | GridLock policy. It reuses the engine's existing categories and adds no new thresholds. | This is a judgment call, and it will be recorded in `docs/data-decisions.md`. |
| A-5 | Counting duplicates avoided in a cluster of *k* | 1 to *k*−1 | GridLock policy | The same. |

I also checked the Dominion siting reports on SC PSC docket pages: Toolebeck–Aiken, Church Creek–Charleston, and a third report whose readable text is marked CEII. None of them states a laydown-yard size, so A-1 can't come from Dominion's own filings.

### A.6 Backend changes
- New module `backend/src/gridlock/impact/estimator.py`, pure: `estimate_zone_impact(...)` and `cluster_pairs(...)`.
- `settings/models.py` gets an `ImpactConfig` with the rules, and the assumptions as structured entries (value range, unit, source title, URL, page, caveat, approved_by, approved_on). The validator rejects an assumption with no source or no approval.
- `config/gridlock.yaml` gets a new `impact:` section, holding the approved values only.
- `pipeline/payload.py` has `assemble_payload` add `impact` and `metadata.impactAssumptions`.
- The CLI `gridlock run` summary gets one impact line per zone.
- **No change** to overlap, ranking, zones, evidence or any existing field.

### A.7 Frontend changes
- `ZonePanel.tsx` gets a new "Coordination impact" section. It shows:
  - the potential coordination themes
  - each range, with its formula in words
  - an "Assumptions" list (value, source link, caveat)
  - a fixed label: **"Illustrative planning estimate: not engineering-grade."**
- Zones without an estimate show the backend's reason text.
- Data quality gets an "Impact assumptions" block under Source provenance.
- The frontend does no arithmetic. It renders the backend's numbers and strings.

### A.8 Contract changes (additive only)
- `Payload.impact: list[ZoneImpact]` is new. `ZoneImpact` contains:
  - `zoneId`, `status` (`ESTIMATED` or `NOT_ESTIMATED`), `reason`
  - `stagingYards: Range`, `temporaryAcres: Range`, `mobilizations: Range`
  - `descBudgetInPlayUsd: Range | null`, `gpcCostKnown: false`
  - `clusters[]` (project IDs, the relationship IDs used), `formulaSteps[]`, `assumptionIds[]`
- `Metadata.impactAssumptions: list[ImpactAssumption]` is new.
- `gridlock contract export` regenerates the schema and `contract.ts`. A test asserts that every pre-existing key and value in the payload is unchanged.

### A.9 Data requirements
- **Existing:** tiers, relevance, priority, clusters, and Dominion costs (3 of 3 in zone 1; 5 of 5 in zone 2).
- **Missing:** Georgia Power costs (redacted; won't be estimated), Southeast-specific yard sizes, and any sourced "avoidable share" (A-3).

### A.10 Security and safety
- No new inputs, uploads or writes. The config is trusted and validated at load.
- The main risk is *misleading output*. Mitigations:
  - ranges only
  - the formula is shown
  - assumptions are cited
  - the fixed "illustrative" label
  - the `NOT_ESTIMATED` path

### A.11 Failure handling
- **No coordinable pairs:** `NOT_ESTIMATED` with a reason, never zero savings.
- **A cluster with no Dominion cost:** the budget shows "not available: no filed cost".
- **An assumption missing or unapproved:** config load fails loudly, the same as other config errors.

### A.12 Tests
- **Unit:**
  - clustering (1, 2 and 3-project clusters; disjoint clusters)
  - range arithmetic
  - the `NOT_ESTIMATED` paths
  - Georgia Power cost never used
  - config rejects an unsourced or unapproved assumption
- **Integration:** a full run produces the zone 1 figures in A.4 and zone 2–4 `NOT_ESTIMATED`. Two runs give identical output.
- **Contract:** schema regenerated; baseline keys unchanged; new fields validate.
- **Frontend:** `tsc`, the build, and new Playwright checks: panel figures equal the API, every assumption is shown with its link, the label is present, and zones 2–4 show their reason.
- **Existing suites:** 224 backend tests; 44, 32 and 20 browser checks, in both themes.

### A.13 Acceptance criteria
- [ ] Every value in A.5 was approved by you before implementation.
- [ ] The zone 1 panel shows 2.8–13.0 acres, 1–2 mobilizations and "up to $3,544,608 (Dominion only)", each with its formula and source. The final numbers follow the approved values.
- [ ] No Georgia Power cost appears anywhere.
- [ ] Zones 2–4 show their reason, not a zero.
- [ ] "Illustrative planning estimate: not engineering-grade" is shown.
- [ ] All existing payload fields are byte-identical to the baseline.
- [ ] All suites pass.

### A.14 Effort
**MEDIUM**, about 5–6 h after Gate A0:
- backend and config: 2–3 h
- UI: 1.5 h
- tests: 1.5 h

### A.15 Demo value
The sponsor bonus asks about potential impact and cost. This lets the presenter say:

> "Coordinating these two projects could avoid a staging yard, 2.8 to 13 acres, and up to two mobilizations. Here is every assumption and where it came from."

It's credible because it refuses to invent Georgia Power costs.

### A.16 Stop condition
Gate A0 (assumptions approved) and Gate A1 (acceptance criteria) must both pass, and you must approve the preview.

---

## 3. Phase B — S4: Coordination Brief

### B.1 Product goal
Turn the top zone into a one- to two-page handoff that a Dominion planner could send to Georgia Power, or the reverse. It uses only engine facts, in fixed template sentences.

### B.2 Existing components reused
- The payload: zone, headline, top relationship, member projects, evidence, source pages, warnings, and themes from metadata labels.
- `lib/presentation.ts` (`spatialLabel` for "Shared endpoint"), `lib/format.ts` and `Timeline.tsx`.
- Phase A's `impact` data, when present.
- The existing `usePayload`.

### B.3 Architecture
```
/brief/[zoneId]   (or /planner/brief?zone=ZONE-01)
  usePayload() → BriefView (template sections) → @media print stylesheet
  Map context: an SVG schematic drawn from the payload GeoJSON (the projected zone
               bounds, both utilities' geometry, the closest-point connector)
  "Print / Save as PDF" button → window.print()
Zones panel: "Open coordination brief →"
```

**Why the map is SVG:** a WebGL canvas often prints blank unless `preserveDrawingBuffer` is set. It also depends on online tiles. A deterministic SVG prints identically online, offline and to PDF.

### B.4 Backend changes
None.

### B.5 Frontend changes
- New route `app/brief/[zoneId]/page.tsx`, plus `components/brief/BriefView.tsx`, `BriefMap.tsx` (SVG) and `brief.module.css` (screen and print).
- A link from `ZonePanel.tsx`.
- The shared navbar is hidden in print.

### B.6 Contract changes
None. The brief reads the existing payload, plus the Phase A fields if they're merged.

### B.7 Data requirements
Everything is present in the payload. The source pages come from each project's `source.page` and `source.projectIdRaw`.

### B.8 Security and safety
- The brief is read-only, with no generated server files.
- It contains no AI text. The template sentences only interpolate engine values.
- A fixed footer reads: "Generated from GridLock analysis <payload hash / run ID>; public sources only; approximations flagged."

### B.9 Failure handling
- **Unknown zone ID:** a "Zone not found" message with a link back.
- **API down:** the existing StatusNotice.
- **No impact data** (Phase A not merged): the section is omitted.

### B.10 Tests
- **Playwright:**
  - The brief for ZONE-01 shows 4.89 km, 152 days, Site logistics, 14 projects, page 23 and raw ID `06367 D - G`.
  - ZONE-02 shows "Shared endpoint — Thurmond Substation".
  - The print-media emulation screenshot has no navbar and fits a set page count.
  - The PDF export via `page.pdf()` succeeds.
  - Offline, the SVG map still renders.
- `tsc` and the build.

### B.11 Acceptance criteria
- [ ] Every number in the brief equals the API.
- [ ] Every project lists its filing and page.
- [ ] Approximation warnings are present.
- [ ] Print and save-as-PDF produce a clean 1–2 page document in both themes. Print always uses light paper.
- [ ] It works offline.
- [ ] No new dependencies.

### B.12 Effort
**LOW–MEDIUM**, about 3–4 h.

### B.13 Demo value
The moment detection becomes a handoff:

> "This is what the planner sends to the neighboring utility."

It's a concrete deliverable a judge can picture being used.

### B.14 Stop condition
Gate B acceptance, and your approval of the printed PDF.

---

## 4. Phase C — Analysis Runner

### C.1 Product goal
Prove GridLock isn't a static dashboard. From the planner you start a new analysis, watch the **real** pipeline stages run, and open the result. You also get a reproducibility receipt: "This run reproduced the baseline exactly (sha256 …)".

### C.2 Existing components reused
- `run_pipeline`, which the CLI already uses, and all stage functions unchanged.
- `check_source_file` for upload validation.
- `contract/validate.py :: validate_payload` for the VALIDATING_OUTPUT stage.
- `osm_power.meta.json`'s sha256 for provenance.
- `api/app.py`'s `_PayloadFile` for serving a run's payload.
- The frontend's `usePayload` gets an optional run ID.

### C.3 Architecture
```
Planner "New analysis" ─POST /api/analyses {source:"snapshot"}──► API
   API: validate → create data/runs/RUN-<utc>-<6hex>/ (manifest.json, status.json: QUEUED)
        → spawn subprocess: python -m gridlock.cli run --run-dir data/runs/RUN-…   (one at a time)
   Subprocess (the same run_pipeline, now with on_stage and workspace parameters):
        READING_PLANS → LOADING_GEOGRAPHY → RESOLVING_GEOGRAPHY → COMPARING_PROJECTS
        → BUILDING_ZONES → VALIDATING_OUTPUT → COMPLETE | FAILED
        each stage writes status.json atomically (temp file + rename)
Planner polls GET /api/analyses/{id} (every 500 ms) → the stepper shows the real stage
"Open results" → /planner?run=RUN-… → usePayload fetches GET /api/analyses/{id}/payload
The baseline data/output stays the default analysis; runs never overwrite it.
```

**Stage honesty:** today `ingest_plans` parses *and* normalizes in one call. It will be reported as one stage, "Reading and normalizing plans", unless it is split. NORMALIZING_PROJECTS is never shown as a separate step if the code doesn't have one.

**Why a subprocess, not a thread:** it can be killed on timeout, a crash can't take down the API, and it keeps the CLI and API on literally the same entry point.

### C.4 Backend changes
- **`pipeline/run.py`:**
  - `run_pipeline(..., workspace: RunWorkspace | None = None, on_stage: Callable | None = None)`.
  - With no workspace, today's behavior is byte-identical, so the CLI and tests are unchanged.
  - With a workspace, it builds a bundle copy with `normalized_dir`, `output_dir` and `review_dir` pointing at the run folder.
- **`ingestion/osm/cache.py`:** `ingest_osm(..., operators_path=None)`, so a run writes its operator index into its own folder. The shared cache is read-only for runs.
- **`ingestion/documents/plans.py`:** `raw_dir(bundle, root, override=None)`. An explicit run source folder wins over the environment variable.
- **Snapshot mode:** it copies the committed `data/normalized/projects.json` into the run and records its hash. If the raw PDFs are available and the user chooses to, it ingests them instead.
- **New `runs/` module:**
  - `store.py`: create a run, validate its ID, read and write status and manifest atomically, list runs, prune them (retention in config).
  - `manifest.py`: provenance.
- **Provenance (`manifest.json`):**
  - run ID and creation time
  - source mode (snapshot or upload), each input's filename and sha256, the adapters used (DESC, GPC)
  - the OSM snapshot sha256 from `osm_power.meta.json`
  - a config hash (gridlock.yaml, utilities and overrides)
  - engine version (package version and git commit when available)
  - the output `gridlock.json` sha256, and `matchesBaseline: true|false`
- **`cli.py`:** `gridlock run --run-dir PATH` (used by the API) and `gridlock runs list`.
- **`api/app.py`:**
  - `POST /api/analyses`, `GET /api/analyses`, `GET /api/analyses/{id}`, `GET /api/analyses/{id}/payload`
  - CORS gains `POST`
  - `409` while a run is active, `404` for unknown IDs, `400` for invalid input
- **Config:** a new `runs:` section with `dir`, `timeout_seconds` (60), `max_retained` (10), `poll_interval_ms`, and `allow_uploads: false`.

### C.5 Frontend changes
- The Overview gets a "New analysis" button, which opens an analysis panel. It holds:
  - a source choice: "Current source snapshot (default)", or "Re-ingest from local PDFs" when the server reports them available
  - a real-stage stepper with per-stage durations
  - the result card: counts, output hash, "Reproduced baseline exactly ✓ / differs", and "Open results"
- A run list: ID, time, status and hash.
- `lib/api.ts`: `usePayload(runId?)` and a run-status polling hook.
- When `?run=` is present, a planner banner reads "Viewing analysis RUN-… · baseline ⟷ this run".
- The Overview, Zones, Projects and Data quality views are unchanged, because it's the same payload contract.

### C.6 Contract changes
- New models: `AnalysisRequest` (`source: "snapshot"`), `AnalysisStatus` (id, state, stage, stages[] with start and end times, error), and `AnalysisManifest`. They're added to the exported schema and `contract.ts`.
- **Existing endpoints and fields are unchanged.** `/api/payload` stays the baseline.

### C.7 Data requirements
- **Present:** the committed normalized snapshot, the OSM cache with its sha256, and the config.
- **Present only locally, not in git:** the raw PDFs in `data/raw/` or `GRIDLOCK_RAW_DIR`, which re-ingestion needs.
- **Uploads (C2):** they can only succeed for the *same editions* of the two filings, because the parser page ranges are fixed. **I recommend deferring uploads.** If they're built, they're labelled "supported documents: DESC 2024–2028 project descriptions; Georgia Power 2025 IRP Vol. 3".

### C.8 Security and safety
- **Filesystem:**
  - Run IDs are generated by the server and must match `^RUN-\d{8}T\d{6}Z-[0-9a-f]{6}$` before any path is built.
  - No client-supplied path is ever used.
  - Run folders are created under `runs.dir` only.
- **Uploads (C2 only):**
  - `check_source_file` rules: the extension allow-list, the `%PDF-` signature, and the 50 MB limit.
  - A streamed size cap during upload, stored under generated names, never executed.
  - Extracted text passes through the existing `untrusted_text`.
  - Needs the `python-multipart` dependency, which I'd flag for your approval.
- **Concurrency:** one active run, enforced by a lock file with a PID and stale-lock recovery. A second POST gets `409`.
- **Background jobs:** a subprocess with a timeout (kill then FAILED), and fixed arguments rather than a shell string.
- **API writes:** only `POST /api/analyses` writes, and only inside `runs.dir`. The API still binds to 127.0.0.1.
- **Disk:** retention prunes the oldest completed or failed runs past `max_retained`. The baseline is never pruned.
- **Generated files:** `data/runs/` is gitignored.

### C.9 Failure handling
- **A stage raises:** FAILED with the stage and message in status.json. Partial files stay in the run folder only. The baseline and other runs are untouched.
- **Timeout:** the subprocess is killed, the state is FAILED ("timed out after 60 s").
- **Malformed source, invalid upload, or parser mismatch:** FAILED at READING_PLANS, with the parser's error, which names the file and page.
- **Output fails contract validation:** FAILED at VALIDATING_OUTPUT. It is never offered as a result.
- **The frontend loses its connection:** polling backs off and shows "Connection lost; retrying". Since the run's state lives in status.json, reopening the panel resumes. The planner keeps showing the current analysis.
- **The API restarts mid-run:** an orphaned RUNNING state with a dead PID is marked FAILED ("interrupted") on the next read.

### C.10 Tests
- **Unit:** the run-ID regex rejects traversal; atomic status writes; the stage state machine; the lock and stale-lock handling; pruning never touches the baseline; manifest hashing.
- **Integration:**
  - A snapshot run in a temp workspace produces a `gridlock.json` byte-identical to the baseline (`matchesBaseline: true`).
  - A run leaves `data/output`, `data/normalized`, `data/review` and `data/cache` byte-identical (`git status` clean).
  - A forced failure mid-stage gives FAILED and leaves the baseline untouched.
  - The timeout kills and marks FAILED; a concurrent POST gets 409; the CLI `gridlock run` output is unchanged.
- **Contract:** the new models are exported; existing ones are unchanged.
- **API:** POST, then poll to COMPLETE, then the payload is served; errors return 400, 404 and 409.
- **Frontend and end-to-end:** Playwright starts a run, sees the stages advance in order (each backed by status.json), sees COMPLETE with "Reproduced baseline exactly", opens the results, and confirms all 44 planner checks pass on `?run=`. A failure is shown clearly, with an injectable failure in test mode only.

### C.11 Acceptance criteria
- [ ] The CLI and API both call `run_pipeline`. There's no second pipeline.
- [ ] Every displayed stage corresponds to a real status.json transition.
- [ ] A snapshot run reproduces the baseline hash.
- [ ] A failed run never changes the baseline or the active view.
- [ ] One run at a time; 409 otherwise.
- [ ] Run folders are isolated.
- [ ] Every run has a manifest with its input, OSM, config and output hashes.
- [ ] All suites pass.

### C.12 Effort
**HIGH.**
- C1 (snapshot runs, stages, provenance, UI): about 6–8 h.
- C2 (uploads): another 3 h plus the new dependency. I recommend skipping it.

### C.13 Demo value
> "This isn't a static dashboard."

A live 5-second run with real stages ends in "reproduced exactly: sha256 …", which directly backs the determinism claim. It's strong for technical credibility and moderate for sponsor value.

### C.14 Stop condition
Gate C1 acceptance. The baseline and CLI must be provably unchanged: `git status` clean, 224 tests, identical hash.

---

## 5. Phase D — S3: What-if Schedule Simulator

### D.1 Product goal
> "If Georgia Power moved McIntosh – Purrysburg six months later, would this still be a HIGH-priority coordination?"

The answer comes from the real engine rules, is shown as hypothetical, and is never saved.

### D.2 Existing components reused
- `overlap/classify.py :: timeline_relation`
- `ranking/priority.py :: rank_relationships` and `opportunity_priority`
- `pipeline/payload.py :: assemble_payload`, which builds zones, metrics and headlines in memory
- The Phase C run store, for `analysisId`. The baseline is the default, so D doesn't strictly depend on C.

### D.3 Architecture
```
Zones panel / evidence drawer: "What if…" → pick a project in the zone → new in-service date (or ±months)
POST /api/simulations/schedule {analysisId?: RUN-…|null, projectId, plannedInServiceDate, shiftFiledSpan?: bool}
  API → simulation/schedule.py:
     load the run's projects_resolved.json + relationships.json (read-only)
     copy the project with the new date (model_copy); optionally shift its filed start by the same delta
     for each relationship touching it: timeline = timeline_relation(a', b, gaps)
     payload' = assemble_payload(bundle, root, projects', relationships')   ← same ranking and zone code
     diff(payload, payload') → affected relationships (gap, relevance, priority, before → after),
                               zone before → after (priority, rank, headline, warnings)
  ← SimulationResult (hypothetical: true), never written to disk
UI: a "HYPOTHETICAL" card with before → after, "Reset" to discard
```

### D.4 Backend changes
- New `simulation/schedule.py` (pure, apart from loading), plus the endpoint `POST /api/simulations/schedule`.
- Config `simulation:` holds `max_shift_days` (for example ±3650) and `enabled`.
- **No change** to any engine function.

### D.5 Frontend changes
- `ZonePanel.tsx` gets a "What if…" control, or it goes on the timeline rows.
- A new `components/planner/SimulationCard.tsx`.
- Results show before → after with the backend labels. The frontend doesn't compute any gap or priority.

### D.6 Contract changes
New models `ScheduleSimulationRequest` and `ScheduleSimulationResult` (`hypothetical: true`, original and simulated relationship states, and the zone diff). They're additive.

### D.7 Data requirements
- **Present:** in-service dates for all projects in zones, and Georgia Power filed spans.
- **Limitation:** construction windows don't exist in the source data, so the simulator only moves in-service dates. It optionally shifts Georgia Power's filed span too, and says so.
- **Zones won't split on dates alone.** Relationships exist because of distance, and the timeline guard warns rather than splits. Zones are grown from the strongest relationship first, though, so a priority change *can* change how relationships are partitioned. The simulator reports whatever the real zone builder produces, including membership changes, and never assumes membership is fixed. Priority, rank, headline and warnings are the usual changes.

### D.8 Security and safety
- The endpoint is stateless and read-only.
- It validates the project ID exists and is located, parses the date, and caps the shift.
- It's rate-limited to one computation at a time, and each takes under 1 s.
- Results carry `hypothetical: true`. The API never writes, and the planner never mixes simulated values into the real views.

### D.9 Failure handling
- **Unknown project, or one not spatially assessed:** 400 with the reason ("not spatially assessed: no relationships to simulate").
- **A date outside the range:** 400.
- **An unknown run:** 404.
- **The frontend is offline:** the card shows an error, and the real data is unaffected.

### D.10 Tests
- **Unit:** a zero shift gives an identical payload; shifting 20277 by −150 days changes the gap from 152 to 2 days and the relevance and priority as the rules dictate; a large shift demotes HIGH to LOW; unknown or unlocated projects are rejected; nothing is written (the file mtimes don't change).
- **Contract and API:** request and response schemas; 400 and 404 paths.
- **End-to-end:** move a date and see HYPOTHETICAL before → after; Reset restores the original; the Overview and Zones figures are unchanged afterwards.

### D.11 Acceptance criteria
- [ ] The results match the engine rules. The frontend has no timeline or ranking logic.
- [ ] Nothing is persisted.
- [ ] Clearly labelled hypothetical.
- [ ] A zero shift is identical to the original.
- [ ] Reset works.
- [ ] All suites pass.

### D.12 Effort
**MEDIUM**, about 4–5 h.

### D.13 Demo value
Turns detection into planning:
> "Watch what happens if this date slips: the zone drops from HIGH to MEDIUM."

It's memorable, but optional in a three-minute demo.

### D.14 Stop condition
Gate D acceptance. Only after A–C are stable.

---

## 6. Branch strategy

```
origin/main @ 4d01fcd  (approved baseline)
   └─ stretch/s2-impact-estimator     → preview → Gate A1 → PR → you merge
         └─ (from the new main) stretch/s4-coordination-brief  → Gate B → PR → merge
               └─ stretch/analysis-runner                       → Gate C1 → PR → merge
                     └─ stretch/s3-schedule-simulator           → Gate D → PR → merge
```

- Each branch is created only when its phase is approved, from the latest merged `main`.
- It gets its own worktree, preview and tests, and it's never auto-merged.
- A rejected branch is deleted, and `main` is untouched.
- **Previews:** a single pair of ports, :3090 and :8090, reused for each phase in turn. The previous phase's preview is stopped when the next starts, so there are no extra servers.
- **Commits** have no AI attribution, per the standing rule.

## 7. Dependency graph

```
A (S2 impact) ──► B (S4 brief shows the impact section)
       │                │
       └──── independent of ────┐
                                ▼
                     C (analysis runner) ──► D (simulator accepts analysisId)
                                              (D also works on the baseline without C)
```
- B works without A: the section is omitted.
- C doesn't depend on A or B.
- D needs only the baseline, and uses C's run IDs if C exists.

## 8. Test strategy (all phases)

| Layer | Tool | Always run |
|---|---|---|
| Backend unit and integration | `uv run pytest` | The existing 224 tests, plus each phase's new tests (run with raw PDFs present) |
| Determinism | an integration test | two runs give an identical sha256; baseline payload keys unchanged |
| Contract | `gridlock contract export` and a diff test | additive changes only |
| Frontend | `pnpm exec tsc --noEmit`, `pnpm build` | every phase |
| End-to-end | Playwright (swiftshader) | the existing 44 planner, 32 Phase 7 and 20 theme checks, in dark and light, plus each phase's new checks |
| Offline | Playwright with non-localhost requests blocked | every phase with a map or brief |
| Fresh clone | `git clone`, `.env.example`, build | before each PR |

## 9. Demo progression (target: 3:00)

| Time | Screen | Line | Needs |
|---|---|---|---|
| 0:00 | Landing | "Plans stay disconnected across utilities." | baseline |
| 0:20 | Overview | "182 projects, 55 relationships, 4 zones: 13.75× less to look at." | baseline |
| 0:40 | Zone 1 map and timeline | "4.89 km apart, 152 days apart: site logistics." | baseline |
| 1:10 | Evidence drawer | "Page 23, project 06367 D - G, Evidence Quality 75/100." | baseline |
| 1:35 | **Coordination impact** | "One shared yard, 2.8–13 acres; up to 2 mobilizations; every assumption shown." | **A** |
| 2:00 | **Coordination brief** | "What the planner sends to the neighbouring utility." | **B** |
| 2:25 | **New analysis** | "Rerun live: real stages; reproduced exactly, sha256 …" | **C** |
| 2:50 | *(optional)* What-if | "Slip this date and the priority drops." | D |

## 10. Time and risk

| Phase | Effort | Build time | Technical risk | Sponsor value | Demo clarity | Main risk |
|---|---|---|---|---|---|---|
| A · S2 impact | MEDIUM | 5–6 h after approval | Low (pure, additive) | **Highest** (challenge bonus) | High | Over-claiming. Mitigated by ranges, sources, "not engineering-grade" and no Georgia Power costs. |
| B · S4 brief | LOW–MED | 3–4 h | Low | High | **Highest** | Print layout across browsers. Mitigated by the SVG map and print CSS. |
| C · runner (C1) | HIGH | 6–8 h (+3 h for uploads) | **Highest** (processes, filesystem, API writes, refactoring stage paths) | Medium | High | Breaking the CLI or baseline. Mitigated by byte-identical tests and the subprocess design. |
| D · S3 what-if | MEDIUM | 4–5 h | Medium | Medium | Medium | Implying zone splits it can't show. Mitigated by stating that membership is fixed. |

## 11. STOP / GO gates

| Gate | GO requires | Who |
|---|---|---|
| **G0: this plan** | You approve this document. | you |
| **A0: assumptions** | You approve or amend A-1 to A-5 (values, sources, A-3 choice). **No S2 code before this.** | you |
| **A1** | A.13 all ticked; preview reviewed. | me, then you |
| **B** | B.11 all ticked; printed PDF reviewed. | me, then you |
| **C1** | C.11 all ticked; baseline and CLI provably unchanged. | me, then you |
| **C2 (optional)** | You approve uploads and the `python-multipart` dependency. | you |
| **D** | D.11 all ticked. Starts only after A–C are merged and stable. | me, then you |

---

## Answers to the questions asked

**Does any phase change core GridLock behavior?**
No. Overlap, thresholds, tiers, timeline rules, graph, zones, ranking and Evidence Quality are untouched in every phase.
- **A** adds a new computation *after* zones, plus a config section. Existing fields stay byte-identical.
- **C** refactors *how stage folders are chosen* (workspace injection, an operator-index path, a raw-folder override). Tests prove the default path's output is byte-identical.
- **D** calls the existing rules on an in-memory copy and never writes.

**Are the existing API contracts sufficient?**
- **B** needs nothing new.
- **A** needs additive payload fields (`impact`, `metadata.impactAssumptions`).
- **C** needs new endpoints and models, and CORS must allow POST.
- **D** needs one new endpoint and its models.
- No existing field or endpoint changes.

**Which phase has the most technical risk?**
**C, the analysis runner.** It's the only phase with background processes, API writes, concurrency and filesystem layout. It also touches how the pipeline chooses its folders. Uploads (C2) would add more risk; I recommend skipping them.

**Which phase gives the most sponsor and demo value?**
- **Sponsor value: A (S2)**, because it directly targets the challenge bonus.
- **Demo clarity: B (S4)**, because it's a tangible deliverable.
- Together they complete the story.

**Minimum set before submission:**
**A + B**, plus **C1 if the time allows** (snapshot-only runs with the reproducibility receipt, no uploads). D is a bonus only if A–C are merged with time to spare.

---

## Roadmap (locked: not planned for implementation)

- **S5: Human review queue.** Inspect, accept or reject unresolved matches; acceptance writes an override with a public source.
- **S6: Plan diff engine.** Needs earlier editions of both filings.
- **S7: Third utility.** Needs another utility's public filing and a parser for its layout.

## Sources checked while writing this plan

- MISO, *Transmission Cost Estimation Guide for MTEP19* (Apr 16, 2019), pp. 6 and 31: <https://nocapx2020.info/wp-content/uploads/2019/07/Transmission-Cost-Estimation-Guide-for-MTEP-2019337433.pdf>. The current official edition, MTEP25: <https://cdn.misoenergy.org/MISO%20Transmission%20Cost%20Estimation%20Guide%20for%20MTEP25337433.pdf>. Automated download was blocked; please confirm it by hand.
- Southern California Edison, *West of Devers Upgrade Project* PEA §3.2, Tables 3.2-A and 3.2-G: <https://ia.cpuc.ca.gov/environment/info/aspen/westofdevers/pea/3.0_project_description_part3.pdf>
- SC PSC docket attachments for Dominion siting reports: <https://dms.psc.sc.gov/Attachments/Matter/685fb7a8-94ba-4b79-b203-08861775db8b>, <https://dms.psc.sc.gov/Attachments/Matter/bdb75d83-9d84-4b92-bb25-976f45670409> and <https://dms.psc.sc.gov/Attachments/Matter/c73dd56f-65b4-47bf-a2a1-679918163c76>. No laydown-yard size was found.
