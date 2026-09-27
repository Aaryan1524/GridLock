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

## 2. The noisy world (0:20–0:40) — planner Overview

Click **Open coordination planner**. The planner opens on the
**Overview**: one map of both states with every located project as a
faint line or dot, and the four coordination zones outlined on top.

> "Every line and dot here is a planned project from Dominion Energy South
> Carolina or Georgia Power. A map alone doesn't tell a planner where to
> look."

## 3. Compression (0:40–1:00) — Overview figures

Point at the figures along the bottom of the Overview.

> "Across **182** public projects, GridLock finds **55** cross-utility
> relationships and compresses them into **4** coordination zones —
> **13.75×** less to look at. It doesn't give planners more data; it tells
> them where to look."

Click the **01 Jasper – McIntosh** label on the map; its details slide
out on the right. Click **Investigate zone →** to open it in **Zones**.

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

## 5. Trust (1:45–2:15) — evidence drawer

Click the Dominion project in **Top coordination opportunity**.

> "Every result is traceable. This comes from the Dominion filing, **page
> 23**, project **06367 D - G**. Jasper matched an OpenStreetMap
> substation; Okatie is a human-verified location from a public siting
> filing. Evidence Quality is **Medium, 75/100**, and it says why —
> including that the route between them is a straight-line approximation."

> "AI never decides distance, overlap, evidence, ranking or zone
> membership here. The same inputs give byte-identical output."

Press Escape.

## 6. Coordination impact (2:15–2:40) — the panel's Coordination impact section

Scroll the zone panel to **Coordination impact**.

> "What could coordinating actually avoid? One shared staging yard —
> **3 to 20 acres** of temporary footprint — and **1 to 2** duplicate
> mobilizations. The expected saving is **up to $1,772,304**, out of **up
> to $3,544,608** of Dominion's published budget in play."

Point at the label and the assumptions:

> "It's labelled illustrative, and every number cites its source: yard
> sizes from a utility environmental filing, the 5.5% ceiling from MISO's
> cost guide. Georgia Power's costs are redacted, so GridLock doesn't
> estimate them."

## 7. Ranking with judgment (2:40–2:52) — click zone 2, Thurmond, in the rail

> "Thurmond is where two projects share an endpoint — both end at
> Thurmond Substation, **0 km** apart — but their dates are **3,074 days**
> apart, so it ranks below the timely Savannah zone instead of crowding
> it out."

Its Coordination impact section gives a reason instead of a number: the
dates are too far apart to share staging or a mobilization.

## 8. Close (2:52–3:00)

> "GridLock turns public plans into verified coordination decisions."

## If something goes wrong

- **Map shows "Bundled basemap"** — expected without internet; geometry,
  zones and distances are unaffected.
- **"GridLock data is unavailable"** — the API is not running or is on a
  different port; see the README's troubleshooting section.
- **Wrong theme for the room** — the sun / moon switch at the top right
  changes light and dark; the browser remembers the choice. Dark is the
  default.
