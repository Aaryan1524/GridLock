# Data and design decisions

Every judgment call that shapes GridLock's numbers, with the reason and
the evidence that drove it. All were made on 2026-09-26 against the real
source data. When a result looks surprising, check here first.

## Sources and scope

1. **Georgia Power scope is sponsors GPC + SAV (138 projects).** The IRP
   lists 208 projects; GTC (54), MEAG (14) and DU (2) are separate
   utilities. SAV is Georgia Power's Savannah zone, and the sponsor's
   worked example treats it as Georgia Power. Configured in
   `config/utilities/gpc.yaml` (`included_sponsors`).
2. **Parsing is deterministic regex; AI is off, permanently for V1.** Both
   PDFs label every field, so regex is simpler and reproducible. The plan
   forbids AI from deciding geometry, distance, evidence, edges or zones.
   `ai.enabled: true` is rejected by config validation.
3. **Raw documents are not committed.** They live in the gitignored
   `data/raw/`; normalized records, the OSM cache and outputs are
   committed so a fresh clone runs offline.
4. **The CEII notice is stripped from stored text.** Every page of the
   Georgia Power public-disclosure copy carries it. Records keep only the
   project's own text, plus document and page for provenance.
5. **The sponsor spreadsheet is an oracle, never an input.** It is a
   secondary source (invariants I-1, I-3) and measures centre to centre in
   miles. `gridlock oracle` compares against it; nothing reads its
   coordinates into the pipeline.

## Normalization

6. **Endpoints come from the title's lead section.** It ends at the first
   voltage token or colon; `SAV:`, `CC -` and `GRID -` prefixes are
   dropped; any dash separates sites; parentheticals such as `(APC)` are
   kept as qualifiers. Anything ambiguous is flagged in
   `data/review/endpoint_review.csv`.
7. **Georgia Power dates: need date is the in-service date; start date is
   `filedStartDate`.** Start→need is never stored as a construction window
   (I-6). Where the summary table and detail page disagree (3 projects),
   the detail page wins by configured precedence and both values are kept
   with a warning.
8. **Unparseable dates stay null.** DESC-6859's "10/1/2025 (phase 1) and
   10/1/2026 (phase 2)" is kept verbatim with a warning, not guessed.
9. **Redacted costs stay null.** All Georgia Power costs read `REDACTED`;
   the raw string is kept in `source.rawFields`.

## Geometry resolution

10. **OSM region widened to −86.0°W and relations included.** Georgia runs
    to about −85.6°; the margin keeps Alabama tie points. Relations add 39
    multipolygon substations.
11. **Operator aliases come from the cache's operator table.** DESC's former
    name (SCE&G, in several spellings) is an alias; without it Bluffton
    was wrongly rejected.
12. **A neighbouring utility's substation needs evidence in the filing.**
    Accepted only with a matching qualifier (`WEBB (APC)`), a tie keyword
    in the title or description ("bus tie" excluded), or for co-owners of
    Georgia's Integrated Transmission System. This rejected Grady, Florida.
13. **Region and voltage vetoes.** Endpoints must fall in the utility's
    service area (SAV projects use the Savannah zone, which separates the
    two Goshens). A voltage conflicts only when the project exceeds the
    substation's highest known voltage, because OSM often tags only the
    high side.
14. **Namesakes are resolved by topology.** Each project takes the best
    name-scoring combination whose endpoints sit within 250 km. This picks
    Hammond, GA over "Hammonds", SC. Same-named yards within 3 km are one
    site; exact ties further apart are marked ambiguous, never guessed.
15. **Okatie is a human-verified override.** OSM has it only as an unnamed
    230 kV yard (`way/1064022697`). SC PSC Docket 2023-115-E, Exhibit A
    places DESC's Okatie 230 kV Substation there; the team confirmed it.
16. **Hooks and Purrysburg stay unresolved.** No public source names their
    location, and the sponsor sheet has no coordinates for them either.

## Overlap, zones and priority

17. **Distance thresholds are the handoff's kilometres, with strict upper
    bounds.** Touching is CROSSING; < 1.6 km, < 8 km, < 40 km; 40 km and
    beyond is discarded.
18. **Mixed timelines use the in-service gap.** DESC has in-service dates
    only; Georgia Power has filed start→need spans. The in-service gap is
    the primary signal; a separate flag marks an in-service date inside
    the other's filed span, never called a construction overlap.
19. **Zones partition relationships, not projects.** Removing edges to
    split chains dropped sponsor overlaps from every zone. Growing zones
    from the strongest relationship keeps every relationship in exactly
    one zone; a project may sit in two zones.
20. **The 730-day timeline guard warns instead of splitting.** 48 of 55
    relationships are over a year apart; splitting left about 44
    single-relationship zones (1.2× compression). Zones carry the warning
    and their date span; `zones.timeline_guard: split` restores splitting.
21. **Untimely crossings drop to MEDIUM priority.** A crossing or shared
    corridor more than 730 days apart is MEDIUM, so Thurmond (0 km,
    3,074-day gap) no longer outranks the timely Savannah zone. The
    spatial tier is unchanged.
22. **Zone cards use one relationship's figures.** A zone's headline takes
    distance, tier and gap from its top relationship, so the numbers
    always describe one real pair.
23. **Resolution metrics use four buckets that always reconcile.** 182 =
    119 located automatically + 1 via human-verified points + 59 named
    sites not resolved + 3 titles naming no site. The automatic rate is
    119 of 179 projects that name a site.

## Delivery

24. **API port is 8010.** Port 8000 was taken on the development machine,
    so the frontend would silently call the wrong server; `/api/health`
    also returns a service name the frontend checks.
25. **The frontend works offline.** Fonts are bundled from npm; the map
    falls back to a bundled U.S. Census 2023 state-boundary file; the
    MapLibre worker is served from `public/vendor`.
26. **Priority tones and labels come from the payload.** The frontend holds
    no thresholds, rules, tier meanings or utility names.
