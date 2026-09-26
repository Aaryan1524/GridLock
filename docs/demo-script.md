# Three-minute demo

One idea: **attention compression**. The flow follows the handoff's §27.
Every number below is on screen and comes from `data/output/gridlock.json`;
if the data changes, rerun `gridlock run --offline --skip-ingest` and
update the figures here.

Nothing below needs the network. From the repository root, in two
terminals:

```bash
# terminal 1
(cd backend && uv run gridlock serve)                   # API on :8010

# terminal 2
(cd frontend && pnpm install && pnpm build && pnpm start)   # UI on :3000
```

## 1. The problem (0:00–0:20) — landing page, hero

> "Utilities already publish what they plan to build. The problem is that
> those plans stay disconnected across organizations — separate PDFs,
> separate timelines, compared by hand."

Point at the **Old way / With GridLock** section as you say it.

## 2. The noisy world (0:20–0:40) — planner, map zoomed out

Click **Open coordination planner**, then zoom the map out (scroll or
pinch) until both states and every faint project line are visible.

> "Every line and dot here is a planned project from Dominion Energy South
> Carolina or Georgia Power. A map alone doesn't tell a planner where to
> look."

## 3. Compression (0:40–1:00) — planner header and zone rail

> "Across **182** public projects, GridLock finds **55** cross-utility
> relationships and compresses them into **4** coordination zones —
> **13.75×** less to look at. It doesn't give planners more data; it tells
> them where to look."

Click **Jasper – McIntosh** in the rail; the map flies back to it.

## 4. The strongest opportunity (1:00–1:45) — zone 1

> "The top zone is **Jasper – McIntosh** on the Savannah River: **14**
> projects, **33** relationships, one conversation."

Point at the map connector:

> "Dominion's Jasper – Okatie 230 kV line and Georgia Power's McIntosh –
> Purrysburg reactors come within **4.89 km** — measured closest point to
> closest point, not centre to centre."

Point at the panel figures and the timeline:

> "Their in-service dates are **152 days** apart, and at that distance the
> coordination is **site logistics**: shared staging yards, deliveries,
> crews."

## 5. Trust (1:45–2:30) — evidence drawer

Click the Dominion project in **Top coordination opportunity**.

> "Every result is traceable. This comes from the Dominion filing, **page
> 23**, project **06367 D - G**. Jasper matched an OpenStreetMap
> substation; Okatie is a human-verified location from a public siting
> filing. Evidence Quality is **Medium, 75/100**, and it says why —
> including that the route between them is a straight-line approximation."

> "AI never decides distance, overlap, evidence, ranking or zone
> membership here. The same inputs give byte-identical output."

Press Escape.

## 6. Ranking with judgment (2:30–2:50) — click zone 2, Thurmond

> "Thurmond is where two projects physically touch — **0 km** — but their
> dates are **3,074 days** apart, so it ranks below the timely Savannah
> zone instead of crowding it out."

## 7. Close (2:50–3:00)

> "GridLock turns public plans into verified coordination decisions."

## If something goes wrong

- **Map shows "Bundled basemap"** — expected without internet; geometry,
  zones and distances are unaffected.
- **"GridLock data is unavailable"** — the API is not running or is on a
  different port; see the README's troubleshooting section.
