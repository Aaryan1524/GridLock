# Three-minute demo

One idea: **attention compression**. Every number below is on screen and
comes from `data/output/gridlock.json`; if the data changes, rerun
`gridlock run --offline --skip-ingest` and update the figures here.

Start the demo from a terminal with the network off if you like; nothing
below needs it.

```bash
cd backend && uv run gridlock serve        # API on :8010
cd frontend && pnpm build && pnpm start    # UI on :3000
```

## 1. The problem (0:00–0:25) — landing page, hero

> "Utilities already publish what they plan to build. The problem is that
> those plans stay disconnected across organizations — separate PDFs,
> separate timelines, compared by hand."

Point at the **Old way / With GridLock** section as you say it.

## 2. What GridLock found (0:25–0:50) — landing page, result strip

> "Across **182** public projects from Dominion Energy South Carolina and
> Georgia Power, GridLock finds **55** cross-utility relationships — and
> compresses them into **4** coordination zones. That's **13.75×** less
> for a planner to look at."

> "GridLock doesn't give planners more data. It tells them where to look."

Click **Open coordination planner**.

## 3. The strongest opportunity (0:50–1:40) — planner, zone 1 selected

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

## 4. Trust (1:40–2:30) — evidence drawer

Click the Dominion project in **Top coordination opportunity**.

> "Every result is traceable. This comes from the Dominion filing, **page
> 23**, project **06367 D - G**. Jasper matched an OpenStreetMap
> substation; Okatie is a human-verified location from a public siting
> filing. Evidence Quality is **Medium, 75/100**, and it tells you why —
> including that the route between them is a straight-line approximation."

> "AI never decides distance, overlap, evidence, ranking or zone
> membership here. It's deterministic: the same inputs give byte-identical
> output."

Press Escape.

## 5. Ranking with judgment (2:30–2:50) — click zone 2, Thurmond

> "Thurmond is where two projects physically touch — **0 km** — but their
> dates are **3,074 days** apart, so it ranks below the timely Savannah
> zone instead of crowding it out."

## 6. Close (2:50–3:00)

> "GridLock turns public plans into verified coordination decisions."

## If something goes wrong

- **Map shows "Bundled basemap"** — expected without internet; geometry,
  zones and distances are unaffected.
- **"GridLock data is unavailable"** — the API is not running or is on a
  different port; see the README's troubleshooting section.
