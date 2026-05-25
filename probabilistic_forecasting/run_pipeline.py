"""Run the full probabilistic forecasting pipeline.

Outputs forecasts.json at the repo root, structured per ML_UPGRADE_SPEC.md
section "Feature 2". The dashboard fetches this file at load time.

Usage (from the repo root):
    python -m probabilistic_forecasting.run_pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import seed_data
from .fetch_ocean_data import (
    fetch_salinity_history,
    fetch_slr_history,
    fetch_sst_history,
)
from .gp_forecast import fit_gp

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "forecasts.json"


def main() -> None:
    sst_years, sst_values = fetch_sst_history()
    slr_years, slr_values = fetch_slr_history()
    sal_years, sal_values = fetch_salinity_history()

    sst = fit_gp(sst_years, sst_values, horizon_years=5)
    slr = fit_gp(slr_years, slr_values, horizon_years=10)
    salinity = fit_gp(sal_years, sal_values, horizon_years=5)

    zone_forecasts: dict[str, dict] = {}
    for zone_id, chart in seed_data.ZONE_EROSION.items():
        # Per-zone histories have only 4 points. Bands will be wide — that's
        # honest output, not a bug. Horizon kept short for the same reason.
        try:
            forecast = fit_gp(seed_data.ZONE_EROSION_YEARS, chart, horizon_years=4)
        except ValueError:
            continue
        zone_forecasts[zone_id] = forecast.to_dict()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sst_forecast": sst.to_dict(),
        "slr_forecast": slr.to_dict(),
        "salinity_forecast": salinity.to_dict(),
        "zone_erosion_forecasts": zone_forecasts,
    }

    OUTPUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"  SST:      {len(sst.years)} pts, {len(sst.outliers_flagged)} outliers")
    print(f"  SLR:      {len(slr.years)} pts, {len(slr.outliers_flagged)} outliers")
    print(f"  Salinity: {len(salinity.years)} pts, {len(salinity.outliers_flagged)} outliers")
    print(f"  Zones:    {len(zone_forecasts)} forecasts")


if __name__ == "__main__":
    main()
