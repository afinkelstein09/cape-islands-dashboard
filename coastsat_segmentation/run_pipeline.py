"""End-to-end CoastSat pipeline -> zones_ml.json.

Step 1 downloads Sept-Oct Sentinel-2 imagery for every zone-year (skipping
anything already cached on disk). Step 2 hands off to aggregate_cached, which
segments shorelines with CoastSat's U-Net, computes 3/5/7yr erosion rates via
cross-shore transects (transect_v3), and writes zones_ml.json with a per-zone
checkpoint — so a killed run resumes where it left off.

Usage (from repo root with `PYTHONPATH=external/CoastSat` and the `coastsat`
mamba env active):
    python -m coastsat_segmentation.run_pipeline
"""

from __future__ import annotations

from .aggregate_cached import END_YEAR, START_YEAR, main as aggregate_main
from .download_imagery import download_all


def main() -> None:
    print(f"Step 1/2 — downloading Sentinel-2 Sept–Oct imagery for {START_YEAR}-{END_YEAR}...", flush=True)
    download_all(START_YEAR, END_YEAR)

    print("\nStep 2/2 — segmenting shorelines + computing erosion rates...", flush=True)
    aggregate_main()


if __name__ == "__main__":
    main()
