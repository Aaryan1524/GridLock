# Configuration reference

Nothing that shapes a result is hardcoded. Tunables live in
`config/gridlock.yaml`, one file per utility in `config/utilities/`,
human-verified locations in `config/overrides/geometry_overrides.yaml`,
and deployment settings in the repository-root `.env`. Config is
validated on load: a bad value stops the run with a message naming it.

## `config/gridlock.yaml`

| Section | What it controls |
|---|---|
| `paths` | Folders for raw documents, the OSM cache, normalized records, review files and outputs |
| `utilities`, `utility_files` | Which utilities run, and their config files |
| `thresholds_km` | Spatial tiers: `near` (1.6), `local` (8), `maximum` (40); strict upper bounds |
| `timeline_gap_days` | Timeline relevance buckets: `near` (90), `moderate` (180), `distant` (365) |
| `display` | Distance unit shown in the UI (`km` or `mi`) and time zone |
| `geometry` | Projected CRS for closest-point search and the OSM bounding box |
| `osm` | Overpass URL, timeout, retries, backoff, byte limit, User-Agent, feature types, query version |
| `ai` | Must stay `enabled: false`; V1 has no AI path |
| `limits` | Allowed document and oracle file types and sizes, project ceiling per utility, stored text length |
| `logging` | Default log level (`--log-level` overrides) |
| `normalization` | Date formats, voltage pattern, endpoint rules, project-type keyword rules |
| `resolution` | Name matching (threshold, noise words, abbreviations, suffix spellings, distinguishing words), same-site radius, endpoint separation limit, tie keywords, overrides file |
| `evidence` | Handoff §10 point weights (must total 100) and HIGH/MEDIUM cutoffs |
| `overlap` | Prefilter slack, output precision, coordination playbooks and their labels |
| `zones` | Geographic and timeline guards, `timeline_guard: warn \| split`, project cap, ID prefix, naming |
| `priority` | Ordered Opportunity Priority rules (tiers, relevance, `max_gap_days`) and default |
| `labels` | Every display label the frontend shows, by vocabulary |
| `api` | Service name returned by `/api/health`, host, port, CORS origins, payload file |
| `oracle` | The sponsor workbook, its sheets, and the mapping from its IDs to ours |

## `config/utilities/<utility>.yaml`

One file per utility; adding a utility means adding a file (and a parser
if its documents have a new layout).

| Key | Meaning |
|---|---|
| `id`, `code` | Config ID and the upper-case code used on records and IDs (`DESC`, `GPC`) |
| `display_name`, `color` | Shown in the UI |
| `operator_aliases` | OSM operator spellings that mean this utility |
| `interconnections` | Neighbouring systems: operator spellings, qualifiers that mark a tie, `always_allowed` for co-owners |
| `service_area_bbox`, `sponsor_service_areas` | Where this utility's endpoints may be; narrower boxes per sponsor |
| `included_sponsors` | Which sponsors count as this utility |
| `sources` | Each document: file, parser, page ranges, field labels, boilerplate to strip, date precedence |

## `config/overrides/geometry_overrides.yaml`

Human-verified endpoint locations for sites OSM lacks or leaves unnamed.
Each entry needs `utility`, `endpoint`, `lat`, `lon`, a public `source`,
the `reviewer` who confirmed it and a `note`; `feature_id` is optional.
Never use the sponsor spreadsheet as a source.

## Environment (`.env`, from `.env.example`)

| Variable | Used by | Meaning |
|---|---|---|
| `GRIDLOCK_CONFIG` | backend | Alternate root config file |
| `GRIDLOCK_RAW_DIR` | backend | Alternate folder holding the raw documents |
| `GRIDLOCK_API_HOST`, `GRIDLOCK_API_PORT` | `gridlock serve` | Override `api.host` / `api.port` |
| `GRIDLOCK_API_CORS_ORIGINS` | `gridlock serve` | Comma-separated browser origins; overrides `api.cors_origins` |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Where the API is |
| `NEXT_PUBLIC_API_SERVICE` | frontend | Must equal `api.service_name`; any other server is refused |
| `NEXT_PUBLIC_MAP_STYLE_URL` | frontend | Online basemap style; empty means always use the bundled map |
| `NEXT_PUBLIC_MAP_STYLE_TIMEOUT_MS` | frontend | Wait before switching to the bundled map |
| `NEXT_DIST_DIR` | frontend (process only) | Separate build folder, for running a second server beside a dev server |

The frontend reads the root `.env` itself (`frontend/next.config.ts`) and
passes only `NEXT_PUBLIC_*` values to the browser. Real environment
variables win over the file.
