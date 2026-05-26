"""End-to-end CoastSat pipeline -> zones_ml.json.

For each of the 19 zones, pulls Sept–Oct Sentinel-2 imagery for each year
2018-2024, runs CoastSat's U-Net to extract shoreline polylines, aggregates
per-year mean positions, and regresses 2/3/5/7yr erosion rates.

Usage (from repo root with `PYTHONPATH=external/CoastSat` and the `coastsat`
mamba env active):
    python -m coastsat_segmentation.run_pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .compute_erosion import erosion_for_zone
from .download_imagery import download_all
from .segment_shorelines import extract_all
from .zones import ZONES_LATLNG

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "zones_ml.json"

START_YEAR = 2018
END_YEAR = 2024  # last complete year as of 2026


def main() -> None:
    print(f"Step 1/3 — downloading Sentinel-2 Sept–Oct imagery for {START_YEAR}-{END_YEAR}...", flush=True)
    download_all(START_YEAR, END_YEAR)

    print("\nStep 2/3 — segmenting shorelines with CoastSat U-Net...", flush=True)
    shorelines = extract_all(START_YEAR, END_YEAR)

    print("\nStep 3/3 — computing erosion rates per zone...", flush=True)
    zones_out: dict[str, dict] = {}
    for zone_id in ZONES_LATLNG:
        per_year = shorelines.get(zone_id, {})
        result = erosion_for_zone(per_year)
        zones_out[zone_id] = {
            "annual_positions": result["annual_positions"],
            "erosion_rates": {
                "3yr_avg_ft_per_yr": result["rates"]["3yr"]["avg_ft_per_yr"],
                "7yr_avg_ft_per_yr": result["rates"]["7yr"]["avg_ft_per_yr"],
            },
            "observations": {k: result["rates"][k]["n_years"] for k in ("3yr","7yr")},
            "n_detections": result["n_detections"],
            "model_metadata": {
                "model": "coastsat_unet_v1",
                "source": "Sentinel-2 via Google Earth Engine",
                "season": "Sept 1 - Oct 31",
                "year_range": [START_YEAR, END_YEAR],
                "epsg": 32619,
            },
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zones": zones_out,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUTPUT.relative_to(REPO_ROOT)} ({len(zones_out)} zones)", flush=True)


if __name__ == "__main__":
    main()
