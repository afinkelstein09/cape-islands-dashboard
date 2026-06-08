# Cape and Islands Conservation Dashboard

> Live coastal-erosion and ecosystem-health monitoring across 19 zones in Cape Cod, Martha's Vineyard, and Nantucket.

**🌊 Live site:** [capeandislandsconservation.org](https://capeandislandsconservation.org)

A single-page conservation dashboard combining real NOAA tide-gauge data, ESA
Sentinel-2 satellite imagery, and two distinct machine-learning layers — a
deep-learning shoreline classifier and a Gaussian Process forecaster — into a
public-facing visualization that residents and educators can actually use.

---

## What it does

- **Tracks shoreline change** across 19 hand-defined coastal zones with
  CoastSat U-Net segmentation of Sentinel-2 imagery (10 m resolution,
  Sept–Oct seasonal window each year).
- **Pulls live ocean conditions** from the NOAA CO-OPS Woods Hole tide gauge
  (8447930) — sea surface temperature, sea level, salinity — and forecasts
  them with **Gaussian Process regression** including 90% confidence bands
  and automatic outlier detection.
- **Scores each zone** with a Hazard × Exposure × Vulnerability framework
  (the standard FEMA / IPCC approach), using quantile-based thresholds so
  the visualization always shows comparative risk across the region.
- **Shows everything** in an interactive Leaflet map with click-to-explore
  zone panels, animated charts, and a full methodology modal explaining how
  every number is computed.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  GitHub repo (this) ──► Netlify auto-deploy ──► live site         │
│                                                                   │
│  index.html (single-page)        Static JSON files                │
│   ├─ Leaflet map                  ├─ forecasts.json  (GP output)  │
│   ├─ Chart.js charts              └─ zones_ml.json   (CoastSat)   │
│   ├─ Live NOAA fetch                                              │
│   └─ Risk scoring (H × E × V)                                     │
│                                                                   │
│  Python pipelines (offline, on-demand)                            │
│   ├─ probabilistic_forecasting/   Gaussian Process forecasts      │
│   └─ coastsat_segmentation/       Sentinel-2 → U-Net → erosion    │
└──────────────────────────────────────────────────────────────────┘
```

- **Frontend:** vanilla HTML / CSS / JS in a single 4,000-line `index.html`.
  No frameworks, no build step, no backend.
- **Backend (offline):** two independent Python pipelines that produce
  static JSON files. The dashboard fetches them at load time.
- **Deployment:** Netlify, automatic on `git push` via `netlify.toml`.

---

## Repo layout

```
.
├── index.html                    # The entire dashboard (HTML + CSS + JS)
├── forecasts.json                # GP output for ocean charts
├── zones_ml.json                 # CoastSat U-Net output for shoreline rates
├── netlify.toml                  # Build config for auto-deploy
├── TRANSFERABLE_PATTERNS.md      # Patterns worth reusing on similar projects
│
├── probabilistic_forecasting/    # Python — Gaussian Process pipeline
│   ├── fetch_ocean_data.py       #   NOAA CO-OPS pulls (with disk cache)
│   ├── gp_forecast.py            #   scikit-learn GP regression + bands
│   ├── seed_data.py              #   Fallback values when API is unreachable
│   ├── run_pipeline.py           #   Orchestrator → forecasts.json
│   └── requirements.txt
│
└── coastsat_segmentation/        # Python — CoastSat U-Net pipeline
    ├── zones.py                  #   19 zone polygons (lat/lng)
    ├── download_imagery.py       #   Sentinel-2 via Google Earth Engine
    ├── segment_shorelines.py     #   CoastSat U-Net inference
    ├── transects.py              #   Auto-placed cross-shore transects
    ├── compute_erosion.py        #   Per-transect regression → ft/yr
    ├── aggregate_cached.py       #   Run inference on cached imagery
    ├── run_pipeline.py           #   Full orchestrator → zones_ml.json
    └── requirements.txt
```

---

## ML layers

### 1. Gaussian Process forecasting (live, on every chart)

Replaces the original OLS trend lines on the Ocean Data charts. Each forecast
is a scikit-learn `GaussianProcessRegressor` with a
`ConstantKernel × RBF + WhiteKernel` kernel — handles noise, gives a 90%
confidence envelope for free, and auto-tunes hyperparameters via
marginal-likelihood maximization. Outlier detection refits the model after
flagging years whose residuals exceed `3 × MAD-derived σ` and 10% of the
y-range. Output is `forecasts.json`.

Run with:
```bash
python -m probabilistic_forecasting.run_pipeline
```

### 2. CoastSat U-Net shoreline detection (offline ML)

For each zone, pulls Sentinel-2 scenes (Sept 1 – Oct 31 each year, 2018–2024)
through Google Earth Engine, runs CoastSat's trained U-Net classifier to
extract sub-pixel shoreline polylines, places ~10 auto-generated cross-shore
transects perpendicular to the local shoreline, measures the per-transect
crossing distance per year, and regresses to get 3yr / 5yr / 7yr erosion
rates in ft/yr. Output is `zones_ml.json`.

Requires:
- A Google Earth Engine account with a registered Cloud Project
- [CoastSat](https://github.com/kvos/CoastSat) cloned into `external/`
- The `coastsat` conda environment (see `coastsat_segmentation/README.md`)

Run with:
```bash
python -m coastsat_segmentation.run_pipeline
```

---

## Data sources

| Source | Used for |
|---|---|
| **NOAA CO-OPS Station 8447930** (Woods Hole) | Sea surface temperature, sea level, salinity — live |
| **ESA Sentinel-2** via Google Earth Engine | 10 m multispectral imagery for shoreline detection |
| **CoastSat** (UNSW Water Research Lab) | Pre-trained U-Net classifier for water/land segmentation |
| **USGS Coastal Change Hazards** | Long-term survey erosion rates (calibration / fallback) |
| **MA Coastal Zone Management** | Shoreline-change technical reports |
| **MassGIS / OLIVER** | Protected land parcels and habitat classifications |

---

## Local setup

```bash
# Clone
git clone https://github.com/afinkelstein09/cape-islands-dashboard
cd cape-islands-dashboard

# Serve the static site
python3 -m http.server 8765
# → open http://localhost:8765
```

Editing `index.html` and reloading is the entire dev loop. The dashboard
fetches `forecasts.json` and `zones_ml.json` from the same origin, so it
works offline against whatever is in the repo.

---

## Notes on the methodology

The dashboard tries to be honest about what's machine learning, what's
calibrated heuristic, and what's just published survey data:

- The **"ML Proj." line and confidence bands** on the ocean charts come from
  a real Gaussian Process — not a linear fit dressed up as ML.
- Zones with a **purple "ML" badge** use the CoastSat-derived 7-year rate;
  others fall back to NDWI / published survey values. *(Currently no zones
  carry the badge until polygon refinement is complete for the multi-coast
  zones — see `TRANSFERABLE_PATTERNS.md`.)*
- The **Composite Risk Index** uses a Hazard × Exposure × Vulnerability
  framework with **quantile-based thresholds** — "Low" means lower-risk
  *relative to other Cape & Islands zones*, not absolutely safe. Coastal
  zones in this region are all at some degree of risk.

Full breakdown in the **Methodology** modal accessible from the top nav of
the live site.

---

## Acknowledgments

- **CoastSat** ([Kilian Vos et al., UNSW](https://github.com/kvos/CoastSat))
  for the open-source shoreline-detection toolkit
- **NOAA** for free, well-documented tide-gauge APIs
- **ESA / Copernicus** for free Sentinel-2 imagery
- **Google Earth Engine** for the cloud processing layer

---

## Author

Built by [Andrew Finkelstein](https://github.com/afinkelstein09) — high school
sophomore, coastal conservation enthusiast.

Issues and questions welcome.
