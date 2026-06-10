# CLAUDE.md — Session continuity for this project

Read this at the start of every new Claude session. It captures everything
a fresh Claude needs to pick up where the last session left off without
re-explaining context.

---

## Who I'm working with

**Andrew Finkelstein** — high school sophomore in Massachusetts (likely MA-09,
Bill Keating's district). Email: andrewjohnfinkelstein@gmail.com. Built the
original Cape & Islands Conservation Dashboard solo before AI assistance;
the recent ML upgrades (CoastSat segmentation, Gaussian Process forecasting,
v2 risk model) were built collaboratively with Claude Code.

**Communication style**: casual, often typo-tolerant ("juts", "lest", etc.).
Asks short questions, prefers short conversational answers when possible.
Pushes back when something looks wrong — trust that instinct. He often types
without precise capitalization or punctuation; that's normal.

---

## What this project is

**Live site:** https://capeandislandsconservation.org (Netlify auto-deploys from
GitHub `main`)

**GitHub:** https://github.com/afinkelstein09/cape-islands-dashboard (public)

A single-page static dashboard tracking coastal erosion and ecosystem health
across **19 zones** in Cape Cod, Martha's Vineyard, and Nantucket. The whole
dashboard is one `index.html` (~4,100 lines: HTML + inline CSS + inline JS).
Two Python pipelines produce the static JSON files the dashboard consumes:

> **This is an independent, ongoing project — that is the whole point of it.**
> Andrew built it for its own sake and will keep building it indefinitely. The
> Congressional App Challenge is a *side entry*, one near-term milestone he's
> choosing to submit it to — NOT the reason the project exists and NOT its sole
> goal. Don't let CAC framing drive design decisions; build the best long-lived
> civic dashboard, and the competition takes care of itself. When CAC and the
> long-term health of the project conflict, the project wins.

- `probabilistic_forecasting/` → produces `forecasts.json` (GP-based ocean
  forecasts with 90% confidence bands)
- `coastsat_segmentation/` → produces `zones_ml.json` (CoastSat U-Net derived
  erosion rates per zone)

---

## Side milestone: Congressional App Challenge (CAC)

Andrew plans to *also* submit this project to the **2026 Congressional App
Challenge** in **~170 days** (deadline typically early November) — as a side
entry, not the project's purpose (see the framing note above). The roadmap
below serves the project first; CAC just happens to benefit from the same work.

### Key research findings (verified via deep-research workflow)
- CAC rubric: 30 points total, split 50/50 Concept (15) / Technology (15)
- 3-min demo video is scored ~5/30 (one row of the rubric, not the entire submission)
- Live deployment is NOT required by rules — partial features are allowed
- MA-09 (Keating district) historical winners: PlimothARWalkingTour (2019),
  EZ Stats (2022), Safe (2023), Chase Places (2024). **None used ML.**
- District prefers locally-grounded civic framing. Solo high schoolers win
  regularly. Andrew's project exceeds the technical ceiling of every prior
  MA-09 winner.

### AI disclosure plan
CAC explicitly permits AI assistance with full disclosure. The plan is to
disclose specifically what Claude Code helped with (GP forecaster, CoastSat
transect aggregation, v2 risk model code, methodology docs) and emphasize
that the original ~3,000-line dashboard predates AI assistance, all design
decisions are Andrew's, and the WRWA validation shows real-world impact.

---

## Architecture decisions and why we made them

### Gaussian Process for ocean forecasts
- Use `ConstantKernel × RBF + WhiteKernel` — RBF smooths trend, WhiteKernel
  absorbs measurement noise, ConstantKernel sets prior variance.
- Bounds wide enough for sklearn's ML-II optimizer to fit without manual tuning.
- Outlier detection only when `n >= 8`; requires both `3 × MAD-σ` AND 10% of
  y-range; never strips more than 25% of points.
- This was deliberately conservative — earlier versions falsely flagged real
  monotonic trends as outliers.

### CoastSat shoreline detection
- Sept–Oct seasonal window each year (compares beaches at "summer profile" —
  after rebuilding, before nor'easter season). Matches how MCZM does surveys.
- **Year range:** 2018-2024. *(2025 isn't included — known gap; Andrew flagged
  this. Could add 2025 in a quick follow-up run.)*
- **Aggregation method = `transect_v3`** (in `compute_erosion.py`). Earlier
  methods (mean-position centroid, then cross-shore PCA projection) produced
  nonsense. Transect intersection is the correct method.
- **Known broken zones**: buzzardsbay, mv_menemsha, dennis_brewster,
  barnstable. Their polygons cover multiple coastlines (bay + ocean sides
  or wraparound). The auto-transect placement can't handle this. Fix
  requires polygon refinement, not code changes.
- **outercape is skipped entirely** — polygon too big for GEE's 48 MB
  per-request download limit. Eventually split into 3 sub-polygons.

### Risk index (v2)
- **Composite Risk Index** = Hazard × Exposure × Vulnerability framework
  (FEMA / IPCC standard). Replaces the original weighted-sum approach.
- **Composite via arithmetic-mean-styled geometric calc** with `Math.cbrt(h*e*v)`.
- **Quantile thresholds**: bottom 33% green, middle 33% orange, top 33% red.
  Set at runtime in `calibrateV2Thresholds()`. "Low" here means *relatively
  lower than other Cape & Islands zones*, not absolutely safe — this is
  documented in the methodology modal.
- **Per-zone metadata** (`ZONE_RISK_META`) is currently hand-coded estimates
  for beach type, building density, exposure, armoring. Should eventually
  be replaced with real GIS data.
- v1 risk model (`computeRiskScore`, `buildRiskScoreHTML`) is kept as dead
  code in `index.html` for fallback / comparison.

---

## Current state

### What's live
- GP forecasts for SST, SLR, Salinity with 90% confidence bands and outlier
  detection (`forecasts.json` deployed)
- Live NOAA fetch from Woods Hole 8447930
- Polygon map with click-to-explore panels
- v2 Hazard × Exposure × Vulnerability risk model (`zones_ml.json` NOT yet
  deployed live — see below)
- Full methodology modal explaining everything
- ML badges next to SST / SLR / Salinity chart titles
- GitHub → Netlify auto-deploy

### What's paused / not yet live
- **`zones_ml.json` is NOT pushed live yet.** The `transect_v3` numbers look
  reasonable for ~10 of 18 zones; the 4 broken-polygon zones (buzzardsbay,
  mv_menemsha, dennis_brewster, barnstable) produce wrong-sign or excessive
  values. Don't push until polygon refinement is done.
- **CoastSat aggregator stopped mid-run** at 11/18 zones (the process keeps
  getting killed by something — likely Mac sleep despite caffeinate, or
  Claude Code background-task time limits).
- All 126 zone-years of Sentinel-2 imagery are cached on disk (~19 GB in
  `coastsat_segmentation/imagery/`).

### Known issues
- Salinity has no live data source (still uses seed values from `seed_data.py`)
- Mobile responsive layout not yet built
- No glossary / educational tooltips yet
- No mobile-responsive CSS yet

---

## Roadmap (the active task list)

In priority order for the project (CAC is one milestone along the way, not the
target these are aimed at):

1. **Finish CoastSat for all 18 zones + ship `zones_ml.json` to live** — refine
   the 4 broken polygons, complete the 7 remaining zones, push. Biggest visual
   change. Activates purple ML badges everywhere.
2. **Real GIS data for v2 risk model** — replace hand-coded metadata with MA
   parcel data (buildings), USGS DEM (elevation), proper beach-type classification.
3. **Glossary tooltips + "why does this matter?" callouts** — educational layer.
4. **Mobile responsive layout** — media queries for side panel, chart grid,
   stat bar, methodology modal.
5. **CAC submission prep** — LICENSE file, 3-min demo video (Andrew writes/records
   solo), AI disclosure, project description.

Things NOT to do:
- Don't try to build a separate WRWA water-quality dashboard for CAC. Reference
  it in the narrative but submit only Cape & Islands.
- Don't add unnecessary features. Every new feature = more code to maintain
  long-term (and, secondarily, more to defend to judges). Keep it focused.

---

## Key files

| File | What's in it |
|---|---|
| `index.html` | The entire dashboard, ~4,100 lines |
| `README.md` | GitHub-facing project description |
| `TRANSFERABLE_PATTERNS.md` | Lessons learned, usable for future dashboards |
| `ML_UPGRADE_SPEC.md` | Andrew's original spec that started the ML work |
| `forecasts.json` | GP forecaster output (deployed) |
| `zones_ml.json` | CoastSat output (NOT deployed yet) |
| `probabilistic_forecasting/gp_forecast.py` | The GP regression core (cleanest math file) |
| `coastsat_segmentation/compute_erosion.py` | Transect intersection math |
| `coastsat_segmentation/aggregate_cached.py` | Resilient zone-by-zone orchestrator |
| `coastsat_segmentation/zones.py` | The 19 zone polygons |
| `netlify.toml` | Build config (publish dir = `publish/`, copies index.html + JSONs) |

---

## Workflow conventions

- **Edit → commit → push** triggers Netlify auto-deploy in ~30s. Always sanity-
  check JS syntax with `node --check` before pushing.
- **Author identity**: `Andrew Finkelstein <andrewjohnfinkelstein@gmail.com>`
- **Branch**: `main` only. No PRs.
- **Don't commit** the `external/`, `.venv/`, `coastsat_segmentation/imagery/`,
  or `classification/` directories — they're gitignored for good reasons.
- **JS sanity-check command:**
  ```bash
  python -c "import re; html=open('index.html').read(); scripts=re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', html, re.DOTALL); open('/tmp/check.js','w').write('\n'.join(scripts))" && node --check /tmp/check.js
  ```

## How to resume a CoastSat run
```bash
caffeinate -dis bash -c "PYTHONPATH=external/CoastSat mamba run -n coastsat python -u -m coastsat_segmentation.aggregate_cached" > /tmp/aggregate.log 2>&1 &
```
The aggregator is resumable — restart picks up where it left off thanks to
the per-zone checkpoint in `zones_ml.json`.

## How to verify changes locally before deploy
```bash
python3 -m http.server 8765 --directory /Users/andrewfinkekelstein/Desktop/cape-islands-dashboard
# then open http://localhost:8765
```

---

## Open questions / decisions deferred

- Should the 2025 year be added to the CoastSat windows? (Currently 2018-2024)
- For the v2 risk model: should "Low" become an absolute threshold (e.g., <4)
  or stay quantile-based?
- Should the `computeRiskScore` / `buildRiskScoreHTML` v1 dead code be deleted
  or kept for reference?
- WRWA water-quality dashboard direction (separate project — referenced in the
  CAC narrative but not built here)

---

## Reference: the WRWA opportunity

Andrew met with a representative of the Westport River Watershed Alliance
who saw the dashboard and wants to collaborate on a water-quality version
this summer. Reference that in the CAC narrative ("the methodology is being
adapted for other watersheds"). Don't try to build a WRWA dashboard for
CAC — it would dilute the submission.
