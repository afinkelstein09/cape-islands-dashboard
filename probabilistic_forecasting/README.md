# probabilistic_forecasting

Replaces the dashboard's client-side OLS "ML Proj." line with Gaussian Process
regression. Produces `forecasts.json` at the repo root with mean predictions,
90% confidence bands, and outlier-flagged years for SST, sea level rise,
salinity, and per-zone erosion.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r probabilistic_forecasting/requirements.txt
.venv/bin/python -m probabilistic_forecasting.run_pipeline
```

Output lands at `forecasts.json` in the repo root. Deploy that file alongside
`index.html`.

## What the GP does

Kernel: `ConstantKernel * RBF + WhiteKernel`. RBF smooths the trend, WhiteKernel
absorbs measurement noise, ConstantKernel sets prior variance. All bounds are
wide enough for sklearn's ML-II optimizer to fit without manual tuning.

Outlier handling is intentionally conservative: skipped entirely when `n < 8`,
flags only points whose residual exceeds both a robust-MAD threshold and 10% of
the y-range, and never strips more than 25% of points. This avoids the failure
mode where a clean monotonic series (e.g. NOAA SLR) gets its most recent values
mistakenly flagged.

## Caveats — read before trusting the numbers

- **Zone erosion fits are weak.** Each zone has only 4 datapoints (years 2012,
  2016, 2020, 2024). The GP will produce wide bands, especially on projections.
  That's honest, not a bug — the previous OLS line hid this uncertainty.
- **Salinity has no live source.** `fetch_salinity_history()` returns dashboard
  seed values. Wire in NOAA NCEI or a station-specific feed when ready.
- **NOAA CO-OPS may rate-limit or 502.** The fetcher falls back to seed data
  when calls fail, so the pipeline still produces output.
- **The cache** (`probabilistic_forecasting/cache/`) is gitignored and only
  stores raw NOAA responses by `(product, year)`. Delete it to force re-fetch.

## Structure

```
probabilistic_forecasting/
├── fetch_ocean_data.py   # NOAA CO-OPS pulls + cache
├── gp_forecast.py        # GP fit + 90% bands + outlier flagging
├── seed_data.py          # Fallback values + zone chartData
├── run_pipeline.py       # Orchestrator → forecasts.json
└── requirements.txt
```
