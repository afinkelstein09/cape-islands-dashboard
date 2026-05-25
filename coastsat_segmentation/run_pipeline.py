"""End-to-end CoastSat pipeline → zones_ml.json.

Requires:
  - `earthengine authenticate` completed (GEE access)
  - `pip install -r coastsat_segmentation/requirements.txt`

Usage (from the repo root):
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


def main() -> None:
    print("Step 1/3 — downloading Sentinel-2 imagery via GEE...")
    metadata = download_all()

    print("Step 2/3 — segmenting shorelines with CoastSat U-Net...")
    shorelines = extract_all(metadata)

    print("Step 3/3 — computing 2/5/7 yr erosion rates...")
    zones_out: dict[str, dict] = {}
    for zone_id in ZONES_LATLNG:
        z = shorelines.get(zone_id, {})
        if isinstance(z, dict) and z.get("error"):
            zones_out[zone_id] = {"error": z["error"]}
            continue
        rates = erosion_for_zone(z)
        # Flatten to spec schema
        zones_out[zone_id] = {
            "shorelines": [{"date": d, "positions": pts} for d, pts in sorted(z.items())],
            "erosion_rates": {
                "2yr_avg_ft_per_yr": rates["2yr"]["avg_ft_per_yr"],
                "5yr_avg_ft_per_yr": rates["5yr"]["avg_ft_per_yr"],
                "7yr_avg_ft_per_yr": rates["7yr"]["avg_ft_per_yr"],
            },
            "observations": {k: rates[k]["observations"] for k in ("2yr", "5yr", "7yr")},
            "model_metadata": {
                "model": "coastsat_unet_v1",
                "source": "Sentinel-2 via Google Earth Engine",
                "epsg": 32619,
            },
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zones": zones_out,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUTPUT.relative_to(REPO_ROOT)} — {len(zones_out)} zones")


if __name__ == "__main__":
    main()
