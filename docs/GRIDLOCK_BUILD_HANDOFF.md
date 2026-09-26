# GridLock — ShellHacks 2026 Build Handoff

> **Mission:** Turn disconnected public utility construction plans into a small number of **evidence-backed cross-utility coordination decisions**.
>
> **Hackathon constraint:** 24 hours. Build the deterministic engine first, lock the data contract early, then stitch on a clear planner-facing frontend. Do **not** chase breadth. Reliability, explainability, and a strong demo path matter more than feature count.

---

## 0. The One-Sentence Product

**GridLock automatically reconciles public utility planning records with public geospatial infrastructure data, detects true spatial + temporal overlaps, compresses pairwise conflicts into actionable coordination zones, and shows planners exactly where cross-utility coordination deserves attention.**

This is **not** a power-flow simulator, grid-design tool, NERC compliance engine, or transmission planning replacement.

Utilities already decide **what** they need to build. GridLock answers:

> **Given what neighboring utilities already plan to build, where should they coordinate?**

---

# 1. Challenge Context

The supplied ShellHacks/Sperry Tech challenge asks teams to compare future public construction plans from at least two electric utilities (working example: Dominion Energy South Carolina / DESC and Georgia Power / GPC) and identify where planned transmission work overlaps.

The required signals are:

- **Geographic overlap — primary signal**
  - touching/crossing
  - under **1.6 km**
  - under **8 km**
  - under **40 km (25 miles)**
  - farther than 40 km → ignore
- **Timeline overlap — strong secondary signal**
- **Interactive UI** showing both utilities and overlaps
- **Ranked coordination opportunities**
- **Bonus:** rough cost/impact estimate for at least one opportunity

Important challenge reality:

- Most projects should **not** overlap.
- Public planning data is messy.
- Public location data is incomplete.
- CEII/private/sensitive infrastructure information is explicitly out of scope.
- The winning implementation should therefore be good at **filtering, proving, and compressing**, not just plotting.

### Supplied source set

Use the supplied files as the authoritative hackathon working set:

- `ShellHacks_Challenge_Gridlock.docx`
- `2025 IRP Volume 3 PUBLIC DISCLOSURE.pdf`
- `2024-2028-2million-and-above-project-descriptions.pdf`
- `Finding_Real_Locations_Guide.docx`
- `Projects_Overlaps.xlsx`

---

# 2. Product Thesis

Most teams can build:

```text
Utility PDFs
   ↓
Projects
   ↓
Pins/lines on a map
   ↓
distance < 25 miles?
   ↓
ranked overlap table
```

GridLock should instead build:

```text
PUBLIC PLANS
   ↓
VERIFIED PROJECT GEOMETRY
   ↓
SPACE + TIME RELATIONSHIPS
   ↓
PROJECT GRAPH
   ↓
COORDINATION ZONES
   ↓
"These people should talk, during this window,
 about these specific shared resources."
```

### The core innovation is compression

```text
100+ planned projects
      ↓
valid cross-utility relationships
      ↓
related relationships clustered
      ↓
3–5 coordination zones
      ↓
planner investigates only what matters
```

Do **not** optimize for feature count. Optimize for **decision compression**.

---

# 3. Frozen V1 Flow

This is the canonical system flow. Do not casually change it during the hackathon.

```text
1. PUBLIC UTILITY PLANS
   DESC PDFs + Georgia Power IRP
   ↓

2. PROJECT EXTRACTION
   AI parses messy text into candidate structured fields:
   project name, endpoints, voltage, date, cost, status, description
   ↓

3. DETERMINISTIC NORMALIZATION
   Validate schema, types, utility, project ID, voltage, date formats
   ↓

4. GEO DATA INGESTION
   Bulk-pull relevant substations + transmission lines
   from OSM through Overpass API
   ↓
   cache locally as GeoJSON
   ↓

5. PROJECT ↔ INFRASTRUCTURE MATCHING
   Resolve candidates using deterministic evidence:
   name + operator + voltage + region + topology
   ↓
   unresolved cases → fallback discovery / AI suggestion / human review
   ↓

6. VERIFIED PROJECT GEOMETRY
   Each project has:
   geometry + provenance + Evidence Quality
   ↓

7. OVERLAP ENGINE
   For every cross-utility candidate:
   • closest geometry distance
   • crossing/intersection detection
   • timeline relationship
   ↓

8. CLASSIFICATION
   Crossing
   <1.6 km
   <8 km
   <40 km
   >40 km → discard
   ↓

9. GRAPH
   Project = node
   valid cross-utility coordination relationship = edge
   ↓

10. COORDINATION ZONES
    Combine related pairwise overlaps into meaningful regional situations
    with geographic/time guards
    ↓

11. RANK
    Opportunity Priority (space + time)
    Evidence Quality kept separate
    ↓

12. PLANNER UI

    "3 coordination zones need attention"

    instead of

    "Here are 100 projects on a map."
```

Equivalent compact architecture:

```text
OFFICIAL UTILITY PLANS
        ↓
AI-assisted structured extraction
        ↓
schema + source validation
        ↓
bulk OSM / Overpass geo cache
        ↓
deterministic project ↔ infrastructure resolution
        ↓
verified geometry + provenance
        ↓
closest-point / fallback geometry engine
        ↓
distance + timeline calculations
        ↓
deterministic overlap classification
        ↓
project relationship graph
        ↓
guarded coordination-zone clustering
        ↓
Opportunity Priority + Evidence Quality
        ↓
interactive planner UI
        ↓
optional AI explanation from verified facts
```

---

# 4. Engineering Philosophy: AI at the Edges

## Rule

> **AI proposes. Deterministic code verifies and decides.**

GridLock is infrastructure decision support. The decision path must be reproducible.

### AI is allowed to help with

- parsing messy public PDFs into candidate structured fields
- identifying likely endpoints from project descriptions
- normalizing messy language into candidate search terms
- ranking candidate names for further deterministic validation
- generating concise human-readable explanations **from already-verified facts**
- suggesting what unresolved record a human should inspect next

### AI must NOT decide

- actual project distance
- geometry intersection
- whether an overlap exists
- spatial severity tier
- timeline gap
- Evidence Quality score
- graph edges
- coordination-zone membership
- ranking formula
- whether a public-source conflict should be silently overridden

### Required AI boundary

```text
MESSY WORLD
    ↓
AI helps structure candidate facts
    ↓
DETERMINISTIC VALIDATION GATE
    ↓
DETERMINISTIC GRIDLOCK ENGINE
    ↓
verified opportunities
    ↓
AI may explain verified output
```

If an AI-extracted fact cannot be verified, it remains **unresolved** or **low evidence**. Never silently promote it to truth.

---

# 5. Data Strategy

There are two fundamentally different datasets.

## A. Planning dataset — “What will be built?”

Source examples:

- DESC public project descriptions / planning filings
- Georgia Power IRP / transmission expansion plan
- SCRTP / PSC / other public planning documents

Typical fields:

- utility
- project ID
- project name
- description
- project type
- voltage
- named endpoints
- status
- planned in-service date
- explicit construction window if available
- estimated cost if available
- source document / page / record

## B. Physical infrastructure dataset — “Where is it?”

Primary hackathon path:

- OpenStreetMap data via **Overpass API**

Useful fields:

- OSM feature ID/type
- geometry
- name
- operator
- voltage
- power feature type
- ref
- region / bounds

Fallback/QA tools:

- Nominatim — fallback discovery only
- OpenInfraMap — human sanity-check / debugging only
- direct OSM browser — human QA
- optional public GIS/HIFLD if useful and public

### Important simplification

Do **not** manually hop between Overpass Turbo, Nominatim, OpenInfraMap, spreadsheets, and PDFs for every project.

Use:

```text
one/few regional Overpass bulk pulls
          ↓
local GeoJSON cache
          ↓
all project matching runs locally
```

This makes the pipeline faster, reproducible, and demo-safe.

---

# 6. Geo Ingestion Design

## Primary strategy

Bulk retrieve relevant public OSM power infrastructure for the target region.

Prefer a controlled geographic bounding area around Georgia / South Carolina target corridors rather than relying exclusively on `operator` filters.

### Why not operator-only?

OSM tags may be incomplete or inconsistent.

A useful feature may contain:

```text
power=substation
name=Okatie
voltage=230000;115000
```

but have a missing, abbreviated, or differently formatted operator tag.

Therefore:

```text
Broad regional retrieval
       ↓
local deterministic filtering
```

is safer than:

```text
operator="Dominion Energy South Carolina"
       ↓
hope nothing is missing
```

## Cache requirements

Persist a reproducible snapshot, e.g.:

```text
data/cache/osm_power.geojson
```

Record metadata:

```json
{
  "source": "OpenStreetMap via Overpass",
  "retrieved_at": "...",
  "bbox": [...],
  "query_version": "v1"
}
```

Never make the live demo depend on a public Overpass request completing successfully.

---

# 7. Project Schema

Freeze this early so backend and frontend can work independently.

Recommended conceptual schema:

```json
{
  "id": "DESC-06367-D-G",
  "utility": "DESC",
  "project_name": "Jasper – Okatie 230 kV #2: Construct",
  "project_type": "transmission_line",
  "description": "...",
  "voltage_kv": [230],
  "endpoints": [
    { "name": "Jasper", "role": "from" },
    { "name": "Okatie", "role": "to" }
  ],
  "status": "In Progress",
  "planned_in_service_date": "2025-12-31",
  "construction_window": null,
  "estimated_cost_usd": 23787423,
  "source": {
    "document": "2024-2028-2million-and-above-project-descriptions.pdf",
    "project_id_raw": "06367 D - G",
    "page": 23
  },
  "geometry": null,
  "geometry_resolution": null,
  "evidence": null
}
```

## Hard normalization rules

- Utility must be from an allowlist in v1: `DESC`, `GPC`.
- Dates must parse to ISO format or remain unresolved.
- Never invent start dates from an in-service date.
- Voltage stored numerically in kV.
- Preserve raw project ID and raw source text where possible.
- Preserve source document/page information.
- Unknown values stay `null`; they are not guessed.

---

# 8. Project ↔ Infrastructure Resolution

Treat this as a **record-linkage problem**, not a geocoding problem.

## Candidate generation

Given a normalized project:

```text
Project:
Jasper – Okatie 230 kV #2
Utility: DESC
Voltage: 230 kV
Region: SC/GA border area
```

retrieve candidate public infrastructure features from the local OSM cache using:

- normalized endpoint name similarity
- power feature type
- operator match if present
- voltage compatibility if present
- plausible geographic region
- topology / nearby named endpoint relationships if available

## Deterministic vetoes

Reject or heavily penalize candidates with clear conflicts:

- wrong known utility/operator when operator is explicit
- clearly wrong state/region
- incompatible known voltage
- incompatible power feature type
- impossible geometry / corrupted record

AI cannot override a deterministic veto.

## Unresolved path

If deterministic matching does not produce a trustworthy candidate:

```text
unresolved
   ↓
Nominatim / additional public-source discovery
   ↓
AI may suggest likely candidates
   ↓
human or deterministic evidence check
   ↓
accept / reject / remain unresolved
```

Never fabricate geometry merely to make every project appear on the map.

---

# 9. Geometry Resolution Ladder

Future projects may not have exact geometry in OSM. The engine must degrade gracefully.

Use this ladder:

1. **Verified full line geometry**
2. **Verified named endpoints** → approximate project as endpoint-to-endpoint line
3. **One verified endpoint + credible route/corridor evidence**
4. **One verified endpoint only**
5. **Approximate place/area centroid**
6. **Unresolved**

Each lower level reduces Evidence Quality.

### Non-negotiable rule

Do not represent an endpoint-to-endpoint approximation as surveyed/official route geometry.

Store geometry method explicitly:

```json
{
  "method": "verified_endpoints_straight_line",
  "is_approximation": true
}
```

---

# 10. Evidence Quality — Deterministic, Not Hallucinated

Prefer the name **Evidence Quality** or **Evidence Score**, not “AI confidence.”

It must be fully reproducible from fixed rules.

## Suggested 100-point framework

### A. Source provenance — 20

```text
Official utility filing + project identifier    20
Official filing but weak identifier             15
Public secondary source only                     5
No traceable source                              0
```

### B. Feature identity — 30

Example:

```text
normalized name match      10
operator match             10
voltage match               5
region match                5
```

Use explicit vetoes for serious conflicts.

### C. Geometry completeness — 35

```text
Verified actual line geometry        35
Both project endpoints verified      30
One endpoint + credible route        22
One verified endpoint only           15
Approximate place/centroid            5
Unknown                                0
```

### D. Timeline completeness — 15

```text
Explicit construction window          15
Explicit start + in-service dates      15
Explicit in-service date               10
Year only                                6
AI/inferred date                         0–2 maximum, never ranking truth
Unknown                                  0
```

## Example

```text
Official project filing       20/20
Name/operator/voltage         30/30
Both endpoints verified       30/35
Exact in-service date         10/15
                              ─────
                              90/100
```

The UI should expose **why**:

```text
✓ Official DESC filing
✓ Project ID matched
✓ Operator matched
✓ Voltage matched
✓ Jasper verified
✓ Okatie verified
✓ In-service date verified
△ Full planned route geometry unavailable
```

### Important separation

Do **not** fold Evidence Quality directly into Opportunity Priority such that an important low-evidence pair disappears.

Show both:

```text
Opportunity Priority: HIGH
Evidence Quality: MEDIUM
```

---

# 11. Overlap Engine

## Cross-utility only

For v1, compare only projects belonging to different utilities.

```text
DESC project × GPC project
```

No same-utility edges unless explicitly needed later.

## Distance logic

Use the **closest points between project geometries**, not center-to-center distance, whenever geometry supports it.

Supported conceptual cases:

```text
Point ↔ Point
Point ↔ Line
Line ↔ Line
Line intersects Line → distance = 0
```

If only fallback point/endpoint geometry is available, calculate with that representation and expose the geometry method in evidence.

## Spatial classification

```text
if geometries intersect / distance == 0:
    CROSSING
elif distance_km < 1.6:
    SHARED_CORRIDOR
elif distance_km < 8:
    SITE_LOGISTICS
elif distance_km < 40:
    CREWS_EQUIPMENT
else:
    DISCARD
```

## Deterministic coordination playbook

Attach likely coordination themes using challenge-defined distance logic:

```text
CROSSING
→ crossing structures
→ outage timing / sequencing

<1.6 km
→ right-of-way
→ access roads
→ permitting / corridor coordination

<8 km
→ staging / laydown yards
→ deliveries
→ site logistics

<40 km
→ crews
→ contractors
→ heavy equipment / mobilization
```

This is deterministic guidance, not AI speculation.

---

# 12. Timeline Logic

Do not invent construction windows.

## Preferred information hierarchy

1. explicit construction start/end window
2. explicit start + in-service dates
3. exact in-service dates only
4. year-only dates
5. unresolved

## If only in-service dates are available

Calculate:

```text
timeline_gap_days = abs(date_a - date_b)
```

Label it correctly as **in-service date gap**, not construction overlap.

## If explicit construction windows exist

Then calculate true interval overlap:

```text
overlap_days
```

and/or interval separation.

## Suggested relevance buckets for v1

These are product heuristics, not sponsor-mandated thresholds. Keep them transparent and configurable.

```text
actual window overlap          strongest
≤ 90-day date gap              strong
≤ 180 days                     meaningful
≤ 365 days                     possible
> 365 days                     weak
```

Do not hide the raw number.

---

# 13. Project Graph

The graph improves GridLock because individual overlap pairs may actually represent one regional coordination situation.

## Nodes

Every planned project is a node.

```text
Node = Utility Project
```

Node attributes may include:

- project ID
- utility
- geometry
- date/window
- voltage
- evidence
- source

## Edges

Create an edge only when a valid **cross-utility spatial overlap** exists (<40 km / crossing).

Each edge carries deterministic metadata:

```json
{
  "project_a": "DESC-23",
  "project_b": "GPC-104",
  "distance_km": 4.7,
  "closest_points": [...],
  "spatial_tier": "SITE_LOGISTICS",
  "timeline_gap_days": 152,
  "timeline_relation": "MEANINGFUL",
  "coordination_playbook": ["staging", "deliveries", "site_logistics"]
}
```

## Why graph instead of table only?

A basic overlap table may produce:

```text
DESC-A ↔ GPC-X
DESC-A ↔ GPC-Y
DESC-B ↔ GPC-X
DESC-B ↔ GPC-Z
```

The graph can reveal that all of these belong to one meaningful regional situation.

---

# 14. Coordination Zones

## Goal

Compress many pairwise relationships into a smaller number of planner-facing situations.

Example:

```text
SAVANNAH COORDINATION ZONE

5 projects
2 utilities
4 cross-utility relationships
closest approach: 1.7 km
active/in-service period: 2025–2027
```

## V1 clustering approach

Start with connected components in the relationship graph, then guard against accidental giant chains.

Problem case:

```text
A — B — C — D
```

A may not actually belong to the same practical situation as D.

### Required guards

After finding a candidate component, evaluate:

- geographic spread / bounding box diameter
- timeline spread
- optional max number of projects

If the component exceeds configured limits, split it.

Keep the split logic simple and deterministic in v1.

### Suggested configurable guards

Start conservatively and inspect the real dataset:

```text
max_zone_geographic_span_km: 40–60
max_zone_timeline_span_days: 730
```

These are implementation heuristics, not challenge rules. Put them in config, not magic constants scattered through code.

---

# 15. Opportunity Priority

Do not produce a fake “AI opportunity score.”

Prefer an explainable category/ranking based on deterministic facts.

## Inputs

- spatial tier — primary
- timeline relevance — secondary
- optional zone-level relationship density

## Keep evidence separate

```text
Opportunity Priority = how worthwhile coordination appears
Evidence Quality      = how trustworthy the underlying inputs are
```

Example UI:

```text
HIGH OPPORTUNITY
MEDIUM EVIDENCE

1.4 km closest approach
120-day in-service gap
geometry based on verified endpoints
```

### Recommended ranking order

1. crossings/intersections
2. <1.6 km
3. <8 km
4. <40 km

Within a spatial tier, prioritize smaller timeline gap / stronger true window overlap.

Do not let a low Evidence Score silently hide a physically critical crossing. Surface it with a warning instead.

---

# 16. Backend ↔ Frontend Contract

Freeze this in the first hours.

Frontend should consume normalized JSON and **not reimplement domain logic**.

Recommended top-level payload:

```json
{
  "metadata": {},
  "projects": [],
  "relationships": [],
  "zones": []
}
```

## Relationship object

```json
{
  "id": "REL-DESC23-GPC104",
  "projectA": "DESC-23",
  "projectB": "GPC-104",
  "distanceKm": 4.7,
  "closestPoints": [
    {"lat": 0, "lon": 0},
    {"lat": 0, "lon": 0}
  ],
  "spatialTier": "SITE_LOGISTICS",
  "timeline": {
    "type": "IN_SERVICE_GAP",
    "gapDays": 152,
    "relevance": "MEANINGFUL"
  },
  "opportunityPriority": "HIGH",
  "coordinationPlaybook": [
    "staging_yards",
    "deliveries",
    "site_logistics"
  ],
  "evidence": {
    "level": "HIGH",
    "score": 90,
    "reasons": []
  }
}
```

## Zone object

```json
{
  "id": "ZONE-SAVANNAH-01",
  "name": "Lower Savannah Corridor",
  "projectIds": [],
  "relationshipIds": [],
  "utilities": ["DESC", "GPC"],
  "closestDistanceKm": 1.3,
  "opportunityPriority": "HIGH",
  "evidenceLevel": "HIGH",
  "coordinationThemes": [
    "right_of_way",
    "site_logistics",
    "crews_equipment"
  ],
  "bounds": {}
}
```

---

# 17. Frontend Product Experience

The map is required, but the map is **not the product**.

## Landing view

Lead with:

```text
GRIDLOCK

3 Coordination Zones Found
```

Then ranked zone cards.

Example:

```text
#1 LOWER SAVANNAH CORRIDOR

5 projects • 2 utilities
Closest: 1.3 km
Date relationship: 214 days
Opportunity: ROW + staging + contractor coordination
Evidence: High

[View Zone]
```

## Zone detail

Show three things immediately:

### A. Map

- both utilities
- project lines/points
- highlight active zone
- draw **closest-point connector** between the selected relationship geometries

### B. Timeline

Show project dates/windows clearly.

Do not imply a full construction window where only in-service dates are known.

### C. Why GridLock flagged it

```text
1.3 km closest approach
214-day date gap
3 linked projects

Likely coordination:
• right-of-way/access planning
• site logistics
• contractor/equipment coordination
```

## Evidence drawer

A user should be able to inspect:

- source project record
- geometry method
- matched infrastructure feature
- Evidence Score breakdown
- warnings / approximations

This is a major differentiator.

---

# 18. Backend-First Work Split

Backend is the differentiated product. Frontend is the delivery surface.

However, do not wait until the backend is 100% complete before touching frontend.

## Execution pattern

```text
Hour 0–2
Freeze schema + frontend/backend contract
Create fixture JSON

Backend team
→ ingestion
→ matching
→ geometry
→ overlap engine
→ graph/zones

Frontend team
→ UI shell using fixture JSON
→ map
→ zone cards
→ detail view

Later
→ swap fixture JSON for real engine output
```

This prevents backend/frontend integration failure late in the hackathon.

---

# 19. Suggested Stack

Keep the stack boring and fast.

## Backend / analysis

Recommended:

- Python
- `pydantic` — schemas/validation
- `requests` or `httpx` — public data ingestion
- `shapely` — geometry + closest-distance logic
- `geopandas` — GeoJSON/data handling if useful
- `networkx` — graph + connected components
- `pandas` — source tables / debugging

Optional:

- `rapidfuzz` — deterministic name similarity

## Frontend

Recommended:

- Next.js / React
- TypeScript
- Mapbox GL **or** MapLibre GL
- simple component library if already familiar

Avoid learning a complex new framework during the hackathon.

## Storage

V1 does not need a production database.

Use versioned local artifacts:

```text
data/raw/
data/cache/
data/normalized/
data/output/
```

JSON / GeoJSON / Parquet/CSV is enough.

---

# 20. Repository Layout

Suggested:

```text
gridlock/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── ingestion/
│   │   ├── normalization/
│   │   ├── georesolution/
│   │   ├── overlap/
│   │   ├── graph/
│   │   ├── ranking/
│   │   └── api/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
│
├── data/
│   ├── raw/
│   ├── cache/
│   ├── normalized/
│   └── output/
│
├── config/
│   └── gridlock.yaml
│
├── docs/
└── README.md
```

---

# 21. Deterministic Invariants

These are non-negotiable.

## I-1 — Provenance

Every accepted project must point back to a public source record.

## I-2 — No fabricated fields

Unknown date, voltage, cost, route, or operator remains unknown.

## I-3 — No AI geometry truth

AI may suggest candidates; only validated public geometry enters the engine.

## I-4 — Distance reproducibility

Given the same two geometries, GridLock must return the same closest distance and points.

## I-5 — Threshold reproducibility

Spatial classification uses one centralized configuration.

## I-6 — Timeline semantics

An in-service date gap must never be presented as a construction-window overlap.

## I-7 — Evidence reproducibility

Same evidence inputs → same Evidence Score.

## I-8 — Cross-utility edge requirement

No graph edge in v1 unless projects belong to different utilities and satisfy the spatial threshold.

## I-9 — Low evidence does not erase critical opportunities

Evidence affects trust presentation, not physical truth classification.

## I-10 — Approximation disclosure

Approximate geometries are explicitly marked.

---

# 22. Security, Safety, and Data Limits

This is public-infrastructure analysis. Keep the implementation deliberately narrow.

## Public data only

Only ingest public sources.

Never ingest, expose, scrape, infer, or attempt to obtain:

- CEII
- credentials
- private utility portals
- internal maps
- restricted engineering files
- private outage plans
- non-public vulnerability information

## Do not turn GridLock into an operational attack surface

The product should analyze public planning coordination, not provide operationally sensitive guidance.

Do not add:

- live control-system data
- SCADA integration
- real-time switching instructions
- security topology analysis
- exploitability assessment
- critical-node attack ranking

## Secret handling

- API keys only via environment variables.
- Never commit `.env` files.
- Add `.env*` to `.gitignore`.
- No keys in frontend bundles unless specifically designed as public tokens.
- If Mapbox is used, restrict token scope/domain where possible.

## Input hardening

For any uploaded or parsed document:

- enforce file type allowlist
- limit file size
- sanitize filenames
- never execute embedded macros/scripts
- do not evaluate document content as code
- treat extracted text as untrusted input

## LLM prompt-injection boundary

Public documents may contain arbitrary text.

When AI parses documents:

- document text is **data**, not instruction
- extraction prompt must require a strict schema
- ignore instructions found inside the source text
- reject unexpected tool/action requests
- validate every AI response against schema

## External API limits

### Overpass

Public infrastructure service; can timeout or rate-limit.

Rules:

- bulk pull once/few times
- cache response
- exponential backoff
- sensible timeout
- no tight retry loop
- demo never depends on live request

### Nominatim

Use only for unresolved fallback discovery.

- throttle requests
- cache results
- avoid bulk project-by-project dependence
- identify the application appropriately if required by the service policy

## Network failure strategy

Every external dependency should have a cached fixture/snapshot.

The app should still demo if Wi-Fi disappears.

## Resource limits

Set explicit ceilings to prevent accidental hackathon meltdown:

```text
max projects per utility in demo dataset: configurable
max Overpass response size: bounded by region/query
max uploaded document size: e.g. 50 MB
max AI extraction chunk size: bounded
max graph nodes/edges in UI: bounded / filtered
max API request duration: bounded
```

## Logging

Log:

- pipeline step
- project ID
- source ID
- match status
- evidence breakdown
- exceptions

Do not log secrets.

## Error policy

Fail visibly and conservatively.

Bad:

```text
Couldn't resolve geometry → invent coordinate → continue
```

Correct:

```text
Couldn't resolve geometry → mark unresolved → exclude from deterministic spatial claims
```

---

# 23. Reliability and Failure Modes

## Failure: OSM does not contain future project route

Fallback to verified endpoints / lower geometry evidence.

## Failure: OSM operator missing

Do not reject solely for a missing operator if name/voltage/region strongly support the candidate.

## Failure: similar substation names

Use region + voltage + operator + topology. If unresolved, route to review.

## Failure: Overpass unavailable

Use cached GeoJSON.

## Failure: one project lacks geometry

Keep the project in the project dataset but exclude it from unsupported spatial claims.

## Failure: no construction window

Use explicit in-service date gap only.

## Failure: connected component becomes huge

Apply zone span guards / split the component.

## Failure: AI extraction malformed

Schema validation fails → retry once with constrained extraction or mark unresolved.

## Failure: two source documents disagree

Do not silently choose. Preserve conflict/warning and use a deterministic source-precedence policy only if explicitly defined.

---

# 24. Testing Strategy

Do not wait until the end.

## Unit tests

### Normalization

- date parsing
- voltage parsing
- project ID normalization
- null preservation

### Matching

- exact name match
- abbreviated operator
- missing operator
- wrong-region rejection
- voltage conflict rejection

### Geometry

- point ↔ point
- point ↔ line
- line ↔ line
- crossing = zero distance
- fallback endpoint line

### Classification boundaries

Explicit tests for:

```text
0 km
1.599 km
1.600 km
7.999 km
8.000 km
39.999 km
40.000 km
```

Define inclusive/exclusive behavior once.

Recommended interpretation matching challenge wording:

```text
< 1.6
< 8
< 40
>= 40 discarded
```

### Timeline

- exact same date
- 90 days
- 180 days
- 365 days
- missing date
- true interval overlap

### Evidence

- deterministic score reproduction
- geometry downgrade
- missing source
- veto conflict

### Graph

- isolated project
- one edge
- multi-edge component
- chain requiring zone split

## Integration tests

At least one real known DESC ↔ GPC example should run end-to-end:

```text
source record
→ normalized project
→ geometry
→ relationship
→ zone
→ frontend JSON
```

---

# 25. V1 Acceptance Criteria

V1 is complete only when all of the following are true:

- [ ] At least two utilities are represented.
- [ ] Public project records are normalized with provenance.
- [ ] Geo infrastructure is loaded from cached public data.
- [ ] At least one real project has verified or transparently approximated geometry.
- [ ] Exact closest-distance logic works for available geometry.
- [ ] >40 km relationships are excluded.
- [ ] Spatial tiers work at required thresholds.
- [ ] Timeline relationship is computed without inventing windows.
- [ ] Evidence Quality is deterministic and explainable.
- [ ] Relationship graph exists.
- [ ] Coordination zones exist with anti-chain guards.
- [ ] Ranked planner-facing output exists.
- [ ] Interactive map works.
- [ ] User can click a zone and understand **why** it was flagged.
- [ ] User can inspect provenance/evidence.
- [ ] Demo works without live Overpass/Nominatim availability.

If any critical item above is missing, do **not** work on stretch goals.

---

# 26. 24-Hour Execution Plan

## Hour 0–2 — Freeze truth model

Goals:

- repository setup
- project schema
- relationship schema
- zone schema
- thresholds config
- frontend fixture JSON
- test harness

Deliverable:

```text
frontend can render fixture zones
backend has validated domain models
```

## Hour 2–6 — Real planning data

Goals:

- parse/seed DESC and GPC project records
- normalize fields
- preserve provenance
- build known-good sample set first

Avoid trying to parse every page perfectly before one path works.

## Hour 4–8 — Geo ingestion + matching

Goals:

- regional Overpass pull
- cached GeoJSON
- local candidate search
- deterministic matching
- evidence calculation

Deliverable:

```text
real project → resolved geometry
```

## Hour 6–10 — Core overlap engine

Goals:

- closest geometry distance
- intersection detection
- spatial tiers
- timeline relationships
- coordination playbooks

Deliverable:

```text
real pair → deterministic relationship object
```

## Hour 8–12 — Graph + zones

Goals:

- network graph
- connected components
- zone guards
- ranking

Deliverable:

```text
many relationships → few zones
```

## Hour 10–16 — Frontend

Goals:

- ranked zone landing view
- interactive map
- zone detail
- timeline view
- closest-point connector
- evidence drawer

## Hour 16–20 — Stitch + break it

Goals:

- real backend output replaces fixtures
- malformed / missing geometry tests
- no-internet demo test
- visual QA
- edge-case fixes

## Hour 20–22 — Polish core only

Goals:

- clearer labels
- loading/error states
- deterministic explanation copy
- provenance clarity

Do **not** start stretch work automatically.

## Hour 22–24 — Freeze and demo

Goals:

- bug freeze
- seed/cached dataset checked in or packaged appropriately
- backup demo path
- 2–3 minute presentation rehearsed
- screenshots/video fallback if practical

---

# 27. Demo Narrative

The demo should communicate one idea: **attention compression**.

## Suggested 3-minute flow

### 1. Problem

> “Utilities already publish what they plan to build. The problem is that those plans remain disconnected across organizations.”

### 2. Show noisy world

Show the map / total projects.

> “A map alone does not solve the coordination problem.”

### 3. Show GridLock compression

```text
100+ projects
→ valid overlaps
→ 3 coordination zones
```

> “GridLock reduces the entire planning set to the few cross-utility conversations that need to happen.”

### 4. Open strongest zone

Show:

- both project geometries
- exact closest-point connector
- distance
- timeline relationship
- coordination playbook

### 5. Show trust

Open evidence drawer.

> “AI helps us read messy public documents, but it does not decide what overlaps. Distance, timing, evidence, graph edges, and rankings are deterministic and reproducible.”

### 6. Close

> “GridLock turns public plans into verified coordination decisions.”

---

# 28. Metrics to Calculate From the Real Dataset

Do not invent performance claims.

Once the pipeline runs, calculate actual metrics:

## Attention Compression Ratio

```text
valid overlap relationships / coordination zones
```

Example only:

```text
24 pairwise relationships / 4 zones = 6× compression
```

Do not claim the example unless the real data produces it.

## Automatic resolution rate

```text
automatically resolved projects / projects needing geometry
```

This can support an actual manual-work reduction claim.

## Evidence distribution

```text
High / Medium / Low evidence project count
```

## Geometry-quality distribution

```text
full geometry
verified endpoints
single endpoint
approximate
unresolved
```

These are far more defensible than “AI accuracy 95%.”

---

# 29. Things We Are Explicitly NOT Building in V1

Do not scope-creep into:

- power flow simulation
- transient stability analysis
- NERC planning replacement
- grid reliability prediction
- national-scale utility ingestion
- every US utility
- user accounts/auth
- enterprise permissions
- live grid telemetry
- SCADA integrations
- outage control
- giant knowledge graph
- generic chatbot
- autonomous agent that decides coordination
- predictive ML model
- fake dollar savings
- production-grade distributed infrastructure

The smallest excellent product wins over a half-finished “platform.”

---

# 30. Locked Stretch Goals

> ## ⛔ DO NOT TOUCH ANY STRETCH GOAL UNLESS THE USER/TEAM LEAD EXPLICITLY SAYS TO START IT.
>
> Finishing V1, testing it, polishing the demo, and making the core deterministic pipeline trustworthy always outrank stretch work.
>
> An AI coding agent must **stop at the V1 boundary** unless explicitly authorized to continue.

Stretch order if and only if explicitly authorized:

## S1 — Coordination Playbooks

Very low effort.

Already derived from deterministic spatial tier:

```text
Crossing → crossing structures + outage sequencing
<1.6 km → ROW/access/permitting
<8 km → staging/deliveries/logistics
<40 km → crews/contractors/heavy equipment
```

Only build if not already treated as core presentation logic.

## S2 — Coordination Impact Estimator

Directly targets the challenge bonus.

For one zone, provide a rough transparent estimate using explicit assumptions.

Examples:

- duplicate staging yards avoided
- shared mobilization scenario
- land footprint range
- avoided duplicate contractor/equipment mobilization

Rules:

- use ranges
- expose every assumption
- label as illustrative / rough
- never fabricate engineering-grade savings

## S3 — What-If Schedule Simulator

Allow a user to shift a project date and deterministically recompute:

- timeline relation
- priority
- zone status

This turns detection into planning.

## S4 — Coordination Brief

Generate a shareable summary for one zone:

- projects
- map
- dates
- distance
- evidence
- likely coordination themes
- source references

AI may format/summarize, but all facts must come from verified engine output.

## S5 — Human Review Queue

UI for unresolved/low-evidence matches:

```text
4 projects need review
```

Actions:

- inspect candidates
- accept
- reject
- leave unresolved

Great for showing human-in-the-loop safety.

## S6 — Plan Update / Diff Engine

Compare old vs new public plans:

```text
+ new projects
- removed projects
↻ date/scope changes
⚠ newly-created coordination opportunities
```

This would evolve GridLock from one-off analysis into continuous coordination monitoring.

## S7 — Third Utility Drop-In

Prove extensibility by ingesting a third utility through the same normalized schema.

Do not build this unless the core system is unusually complete and stable.

---

# 31. Final Build Principle

If a decision is between:

```text
another feature
```

and

```text
making one real coordination zone undeniable,
auditable, fast, and beautiful
```

choose the second.

The final product should feel like this:

```text
PUBLIC PLANS
    ↓
VERIFIED DATA
    ↓
TRUE GEOMETRY
    ↓
DETERMINISTIC RELATIONSHIPS
    ↓
COORDINATION ZONES
    ↓
HUMAN ACTION
```

**GridLock wins by proving fewer, better decisions — not by producing more output.**

