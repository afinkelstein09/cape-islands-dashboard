# coastsat_segmentation

Replaces the dashboard's NDWI-threshold shoreline detection with CoastSat's
deep-learning segmentation. Pulls Sentinel-2 imagery via Google Earth Engine
for all 19 zones, runs CoastSat's U-Net to classify water/land per pixel,
extracts the shoreline polyline per scene, and writes `zones_ml.json` at the
repo root.

This is the bigger of the two ML upgrades. Read the caveats below before
trusting any output.

## One-time setup

1. **Authenticate Earth Engine** (only needs to happen once per machine):
   ```bash
   pip install earthengine-api
   earthengine authenticate
   ```

2. **Install CoastSat** — not on PyPI, install from source:
   ```bash
   git clone https://github.com/kvos/CoastSat external/CoastSat
   pip install ./external/CoastSat
   ```

3. **Install the rest of the deps:**
   ```bash
   .venv/bin/pip install -r coastsat_segmentation/requirements.txt
   ```

## Run it

```bash
# Full pipeline (download + segment + compute):
.venv/bin/python -m coastsat_segmentation.run_pipeline

# Compute-only, from already-cached imagery (resumable — writes zones_ml.json
# after every zone, so a killed run picks up where it left off):
.venv/bin/python -m coastsat_segmentation.aggregate_cached
```

Imagery downloads to `coastsat_segmentation/imagery/<zone_id>_<year>/`
(gitignored). Final output: `zones_ml.json` at the repo root, matching the
schema in [ML_UPGRADE_SPEC.md](../ML_UPGRADE_SPEC.md).

A full run downloads ~15-20 GB of imagery and takes hours depending on
GEE quota and local CPU. The imagery cache persists between runs.

## Structure

```
coastsat_segmentation/
├── zones.py              # Polygons for all 19 zones (mirrors index.html)
├── download_imagery.py   # Sentinel-2 pull via GEE / CoastSat
├── segment_shorelines.py # CoastSat U-Net inference → shoreline polylines
├── transects.py          # Auto-placed cross-shore transects per zone
├── compute_erosion.py    # 3/5/7yr ft/yr rates via transect intersection
├── aggregate_cached.py   # Resumable orchestrator → zones_ml.json
├── run_pipeline.py       # Download + aggregate_cached, end to end
├── compare_rates.py      # Dev tool: compare ML rates vs dashboard values
├── grade_rates.py        # Dev tool: sanity-grade rates per zone
└── requirements.txt
```

## Caveats — please read

- **Erosion rates come from cross-shore transect intersection**
  (`transect_v3`): ~10 transects are auto-placed perpendicular to the local
  shoreline per zone, each scene's shoreline crossing is recorded per
  transect, yearly medians are regressed per transect, and the zone rate is
  the median across transects. Earlier mean-position and PCA-projection
  methods produced nonsense and were replaced.
- **Four zones have known-broken polygons** (buzzardsbay, mv_menemsha,
  dennis_brewster, barnstable): they span multiple coastlines (bay + ocean
  or wraparound), so auto-transect placement crosses two shores at once.
  Their rates are wrong until the polygons are split/refined.
- **Sand-color setting is global.** `sand_color: "default"` works for most
  Cape & Islands beaches. Gay Head Cliffs and zones with red/dark sediment
  may need `sand_color: "dark"` set per-zone — wire that into `zones.py`
  if outputs there look off.
- **Cloud threshold (`cloud_thresh: 0.5`) is conservative.** On the outer
  Cape during late autumn / winter you may need 0.3 to get usable scenes.
- **Zone polygons in `zones.py` mirror `index.html` `areaPolygons`.** They
  enclose the *zone of interest*, not strictly the shoreline. CoastSat
  extracts shorelines that fall within these polygons — make sure each one
  actually contains a coastline. Inland polygons (`buzzardsbay` etc.) will
  produce no shorelines and that's expected, not a bug.
- **First run computes a reference shoreline.** CoastSat asks you to draw
  one interactively if missing. Run once with `check_detection: True` in
  `segment_shorelines.py` to inspect detections per scene.
