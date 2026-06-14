# Cape & Islands Conservation Dashboard — ML Upgrade Spec

## Context

I have a single-file coastal conservation dashboard (`index.html`) deployed on Netlify at capeandislandsconservation.org. It monitors 19 coastal zones across Martha's Vineyard, Nantucket, and Cape Cod. Currently it uses:

- **NDWI thresholds** on Sentinel-2 imagery to estimate shoreline position and erosion rates (client-side, hardcoded per zone)
- **OLS linear regression** for ocean data trend projections (SST, sea level, salinity) — labeled "ML Proj." on charts
- **Weighted multi-factor scoring** (hand-tuned weights) for a "Composite Risk Index" per zone

I want to upgrade this to use **real ML** with two new capabilities:

---

## Feature 1: Deep-Learning Shoreline Segmentation

### What it replaces
The current system uses NDWI (Normalized Difference Water Index) from Sentinel-2 bands to classify water vs. land with a simple threshold. This breaks on wet sand, cliff shadows, seaweed, and breaking waves.

### What I want
A deep-learning model (U-Net or similar) that segments Sentinel-2 imagery into water/land per pixel, producing accurate shoreline positions over time. Look into **CoastSat** (https://github.com/kvos/coastsat) as a starting point — it already does this with Sentinel-2 and Landsat.

### Requirements
- Process Sentinel-2 imagery for all 19 zones via Google Earth Engine (I have a GEE account)
- Extract shoreline positions at 3 time windows: 2-year, 5-year, 7-year (matching the current dashboard intervals)
- Compute erosion rates from shoreline change over time
- Output a JSON file that the dashboard can consume, structured per zone:

```json
{
  "zone_id": {
    "shorelines": [
      { "date": "2018-03-15", "positions": [[lat, lng], ...] },
      ...
    ],
    "erosion_rates": {
      "2yr_avg_ft_per_yr": 5.2,
      "5yr_avg_ft_per_yr": 4.1,
      "7yr_avg_ft_per_yr": 3.8
    },
    "confidence": 0.92,
    "model_metadata": {
      "model": "coastsat_mlp_v1",
      "training_images": 1200,
      "accuracy": 0.94
    }
  }
}
```

### Current zone data for reference
The 19 zones and their current hardcoded erosion rates are in the `areaData` object in `index.html`. Each zone has `erosionRate` (survey historical), `satelliteRate` (current NDWI-derived), and chart data with yearly measurements. Zone IDs: `aquinnah`, `chappaquiddick`, `edgartown`, `gayhead-cliffs`, `katama`, `lamberts-cove`, `menemsha`, `oak-bluffs`, `vineyard-haven`, `west-tisbury`, `cape-poge`, `coatue`, `cisco-beach`, `dionis`, `madaket`, `sankaty`, `sconset`, `surfside`, `great-point`.

---

## Feature 2: Probabilistic Erosion & Ocean Forecasting

### What it replaces
OLS linear regression trend lines on the ocean data charts (SST, sea level, salinity). Currently displays a single dashed "ML Proj." line — no uncertainty quantification. A bad data point (like the SST dropping to 30°F from a sensor glitch) gets treated the same as good data.

### What I want
Replace OLS with **Gaussian Process regression** or **Bayesian regression** that produces:
- A mean prediction line (replaces the current "ML Proj." dashed line)
- 90% confidence envelope (shaded band around the prediction)
- Automatic outlier detection/handling (so a bad sensor reading doesn't skew the forecast)

### Requirements
- Apply to: SST (annual avg °F), sea level rise (mm/yr), salinity (PSU)
- Also apply to per-zone erosion time series (the chartData arrays in each zone)
- Projection horizon: 5 years for SST/salinity, 10 years for SLR, variable for erosion
- Output JSON:

```json
{
  "sst_forecast": {
    "years": [2005, 2006, ..., 2031],
    "mean": [52.1, 52.4, ...],
    "upper_90": [52.8, 53.1, ...],
    "lower_90": [51.4, 51.7, ...],
    "outliers_flagged": [2025],
    "model": "gaussian_process",
    "kernel": "RBF + WhiteNoise"
  },
  "zone_erosion_forecasts": {
    "aquinnah": {
      "years": [...],
      "mean": [...],
      "upper_90": [...],
      "lower_90": [...]
    }
  }
}
```

### Dashboard integration for confidence bands
The current Chart.js charts need to render the confidence envelope. Chart.js supports fill between datasets — use `fill: '+1'` or `fill: '-1'` with a transparent color for the band. Replace the current `addTrendProjection()` and `addSLRTrendProjection()` functions to read from the pre-computed JSON instead of doing client-side OLS.

---

## Architecture

```
Python pipeline (runs offline or on schedule)
├── coastsat_segmentation/
│   ├── download_imagery.py    # Pull Sentinel-2 from GEE
│   ├── segment_shorelines.py  # U-Net inference
│   ├── compute_erosion.py     # Shoreline change → rates
│   └── output_zones.json      # Result
├── probabilistic_forecasting/
│   ├── fetch_ocean_data.py    # Pull from NOAA CO-OPS
│   ├── gp_forecast.py         # Gaussian process fitting
│   └── output_forecasts.json  # Result
├── requirements.txt
└── run_pipeline.py            # Orchestrator

Dashboard (Netlify static site)
└── index.html                 # Reads JSONs, renders everything
```

The pipeline outputs JSON files that get deployed alongside `index.html` to Netlify. The dashboard fetches them on load (or they can be inlined).

---

## Tech Stack
- Python 3.10+
- CoastSat or custom U-Net (PyTorch or TensorFlow)
- Google Earth Engine Python API (`earthengine-api`)
- scikit-learn (GaussianProcessRegressor)
- NumPy, pandas
- NOAA CO-OPS API for ocean data

---

## Current Dashboard File
The full dashboard is a single `index.html` file. Key sections relevant to this upgrade:

1. **`areaData` object** (~line 850–1950): All 19 zones with erosion rates, habitat data, chart data arrays, risk factors, analysis text
2. **`addTrendProjection()` function** (~line 3520): Current OLS implementation that adds "ML Proj." line to Chart.js instances
3. **`addSLRTrendProjection()` function** (~line 3590): Same for sea level bar charts
4. **`computeRiskScore()` function** (~line 3636): Composite Risk Index — will need to incorporate ML-derived erosion rates and GP confidence as inputs
5. **`RISK_WEIGHTS` object** (~line 3639): Current weights — erosionRate: 0.45, trend: 0.15, habitatStress: 0.15, recentAccel: 0.15, riskFactors: 0.10
6. **Chart instances**: `sstChartInstance`, `salinityChartInstance`, `slrChartInstance` — need confidence band rendering

---

## Priority
1. Start with probabilistic forecasting (Gaussian Process) — it's faster to implement and immediately upgrades the "ML Proj." charts with real ML
2. Then tackle CoastSat shoreline segmentation — bigger lift but transforms the erosion data quality
3. Finally, update `computeRiskScore()` to weight ML-derived confidence into the Composite Risk Index

---

## Notes
- The current `index.html` will be provided alongside this spec
- Keep "ML Proj." as the chart label — that's intentional
- The Composite Risk Index naming is intentional (not "ML risk score")
- I have a Google Earth Engine account already set up
- Dashboard is deployed on Netlify as a static site
