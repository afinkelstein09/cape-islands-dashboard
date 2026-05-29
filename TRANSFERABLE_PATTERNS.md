# Patterns worth reusing on the next conservation dashboard

A short playbook distilled from building the Cape & Islands Conservation
dashboard. Written so a future Claude session (or future me) can skim it and
get up to speed on what worked, what didn't, and what to do differently
when starting a new project — like the Westport River Watershed Alliance
water-quality dashboard.

---

## Architecture choices that earned their keep

- **Single-file static `index.html`** deployed on Netlify. No backend, no
  database, no React. The whole site is HTML + inline CSS + inline JS +
  static JSON files. Loads in <1 sec, hosting costs $0, and the only thing
  needed to update content is `git push`. This scales fine for any
  zone-count under ~50.
- **Static JSON files as the data interface.** The Python pipelines
  (`probabilistic_forecasting/`, `coastsat_segmentation/`) produce JSON
  files (`forecasts.json`, `zones_ml.json`) that the dashboard `fetch()`es
  on load. This cleanly separates "data computation" from "data display"
  and means the dashboard always works even if a pipeline is broken
  (graceful fallback to inline seed values).
- **GitHub → Netlify auto-deploy with a `netlify.toml`.** The build
  command copies just the public files (`index.html`, JSON) into a
  `publish/` folder. Python pipeline code and large imagery aren't shipped.
  Every `git push` deploys to production in ~30 seconds.

---

## Data-flow pattern that worked everywhere

For every live data source (NOAA tide gauge, etc.):

1. **Pipeline tries the live API.** If it succeeds, cache the response to disk
   under a `cache/` directory keyed by `(product, year, month)`.
2. **If the API fails, fall back to a `seed_data.py`** file containing the
   last-known-good values. The pipeline always produces output.
3. **Dashboard fetches the JSON at runtime.** If the JSON is missing
   (e.g. just deployed for the first time), JS falls back to inline values
   baked into `index.html`.

This three-layer fallback (live → seed → inline) means nothing the user
sees is ever blank or broken. It also lets you ship the dashboard before
the data pipelines are finalized.

**The "always succeeds" pattern is the right default for public-facing
science dashboards.** Better to show stale data with a clear timestamp
than to show an error.

---

## UI patterns to copy

- **Polygon-based zone map (Leaflet).** Each "zone" is a polygon defined
  in JS with a stable ID. Click opens a side panel with that zone's data.
  Hover tooltips show the name. Color = a composite score mapped to
  High/Medium/Low.
- **Methodology modal with a numbered flow.** Walk visitors through the
  data sources, methods, and assumptions in a single dialog accessible
  from the top nav. **Be honest about what's machine learning and what
  isn't.** For WRWA, this matters even more — students need to know what
  the computer is doing vs. what a scientist did.
- **Time-series chart with 90% confidence bands.** Chart.js supports
  fill-between-datasets (`fill: '-1'`) for shaded bands. Stack a dashed
  mean line on top with `borderDash: [6,3]`. Match the band edges and the
  mean line in the same color family. Hide the band helper datasets from
  the legend with a filter.
- **Small purple "ML" badge** next to anything driven by a real ML model
  (not just hardcoded heuristics). Click-target shows a tooltip with one
  sentence of explanation.
- **Intro modal on first visit.** sessionStorage key so it stays dismissed
  on return. Three-to-four-step walkthrough is the right size.
- **Composite score with a transparent weight breakdown.** Each zone gets
  a 0–10 score combining several factors with documented weights. Show the
  weights publicly in the methodology. Be honest that they're judgment
  calls, not validated by outcome data.

---

## ML patterns that worked

- **Gaussian Process regression for time-series forecasting.**
  scikit-learn's `GaussianProcessRegressor` with a
  `ConstantKernel * RBF + WhiteKernel` is the sweet spot — handles noisy
  observations, gives you 90% confidence bands for free, and
  auto-tunes via marginal-likelihood maximization. Works on annual
  averages with as few as ~20 datapoints.
- **Outlier detection by residuals.** After fitting, flag points whose
  residual exceeds both `3 × MAD-derived σ` and a small fraction of the
  y-range. Refit without them. Don't flag for series with <8 points.
- **Display the band, hide the math.** Visitors see "the dashboard's
  uncertain about exactly how warm 2030 will be" — they don't need to
  see the kernel hyperparameters. Methodology page has the science.

## ML patterns that struggled (and why)

- **Auto-placed transects on irregular polygons.** CoastSat shoreline
  detection per scene works great; the per-zone aggregation broke down
  on polygons that wrap multiple coastlines (e.g. Buzzards Bay covering
  3 separate shores). Lesson: any zone-level rate that depends on
  geometric aggregation needs polygons drawn for that purpose — not the
  zone-display polygons.
- **Mean-position aggregation for shoreline change.** The naive
  "average all detected points to one (lat, lng) per year" approach
  produces garbage rates because varying detection coverage swamps the
  real signal. Either use proper cross-shore transects or measure area
  change instead of position.

---

## What's NEW for an educational (student-audience) dashboard

Things THIS dashboard doesn't have but a WRWA-style dashboard would need:

- **Glossary / tooltip system for jargon.** Hover any underlined term
  (TMDL, eutrophication, hypoxia, DO) → small popover with a plain-English
  definition + a "learn more" link. Vocab is a real barrier for student
  audiences.
- **"Why does this matter?" callouts.** Every chart should answer this
  in one sentence. "Sea level is rising 0.12 inches/year" is data;
  "Sea level rise of 1 inch over 10 years means storm surge reaches X
  feet further inland during a typical nor'easter" is education.
- **A "ask a question" / question-of-the-week mode.** Pose a science
  question, let the dashboard guide students to data that answers it.
- **Lesson-plan downloads.** PDF or simple Markdown handouts per topic
  that teachers can use in class with the dashboard as a live exhibit.
- **Citation / data-source labels everywhere.** Students learn good
  scientific practice from seeing every chart sourced.

---

## Operational lessons

- **Always `caffeinate -dis` long-running Python jobs.** And accept that
  some force-kill mechanism (system, parent shell, OS) will still
  occasionally kill them. Design pipelines to be **resumable**: write
  output after every unit of work and skip already-completed units on
  restart.
- **Static deployment is freeing.** No server to maintain, no
  database to back up, no auth to manage. The site sustains itself.
- **Honesty about uncertainty is a feature, not a bug.** Visitors
  trust a dashboard more when it says "we're not sure about X" than
  when it pretends to know. Confidence bands and "see methodology"
  links do this work for you.

---

## Quick-start for the next project

When starting a new dashboard from scratch with these patterns:

1. Scaffold a single `index.html` with Leaflet + Chart.js inline.
2. Drop in the methodology modal, intro modal, and zone-panel patterns.
3. Define your polygons in JS (or a static JSON).
4. Build a Python pipeline that produces a single JSON file per data
   type (forecasts.json, etc.).
5. Set up `netlify.toml` + GitHub auto-deploy *before* writing much
   code — instant feedback loop.
6. Add ML layers only where you can be honest about what they do.
   Resist adding "ML" labels to plain regressions.

That's the playbook.
