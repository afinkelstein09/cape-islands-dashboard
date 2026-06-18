"""Aggregate whatever imagery is currently cached into zones_ml.json.

Resilient design: processes one zone at a time, writes zones_ml.json
**after every zone**. If the process gets killed mid-run, partial output
is preserved. Re-running picks up from where it left off — zones already
computed with the current method are skipped.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .compute_erosion import erosion_for_zone
from .segment_shorelines import extract_year
from .zones import ZONES_LATLNG

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "zones_ml.json"

START_YEAR = 2018
END_YEAR = 2024
METHOD_TAG = "transect_v5"


def _load_existing() -> dict:
    if not OUTPUT.exists():
        return {}
    try:
        body = json.loads(OUTPUT.read_text())
        return body.get("zones", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def _is_already_complete(zone_data: dict) -> bool:
    if not zone_data:
        return False
    rates = zone_data.get("erosion_rates", {})
    r7 = rates.get("7yr_avg_ft_per_yr")
    method = zone_data.get("model_metadata", {}).get("aggregation")
    return isinstance(r7, (int, float)) and method == METHOD_TAG


def _write(zones_out: dict) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zones": zones_out,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2))


def main() -> None:
    zones_out = _load_existing()

    zone_list = list(ZONES_LATLNG)
    for i, zone_id in enumerate(zone_list, 1):
        if _is_already_complete(zones_out.get(zone_id, {})):
            print(f"[{i}/{len(zone_list)}] {zone_id} — already complete ({METHOD_TAG}), skipping", flush=True)
            continue

        print(f"[{i}/{len(zone_list)}] {zone_id} — segmenting...", flush=True)
        per_year: dict[int, list[dict]] = {}
        for year in range(START_YEAR, END_YEAR + 1):
            try:
                detections = extract_year(zone_id, year)
                if detections:
                    per_year[year] = detections
            except Exception as e:  # noqa: BLE001
                print(f"  ! {zone_id} {year} segmentation failed: {e}", flush=True)

        result = erosion_for_zone(zone_id, per_year)
        n_detections = result["n_detections"]
        n_transects = result.get("n_transects", 0)
        r7_value = result["rates"]["7yr"].get("avg_ft_per_yr")

        if n_detections == 0:
            print(f"  no detections — skipping", flush=True)
            continue
        if n_transects == 0:
            print(f"  no transects could be generated (shoreline cluster too small/noisy) — skipping", flush=True)
            continue
        if r7_value is None:
            print(f"  could not compute 7yr rate — skipping", flush=True)
            continue

        zones_out[zone_id] = {
            "erosion_rates": {
                "3yr_avg_ft_per_yr": result["rates"]["3yr"]["avg_ft_per_yr"],
                "5yr_avg_ft_per_yr": result["rates"]["5yr"]["avg_ft_per_yr"],
                "7yr_avg_ft_per_yr": result["rates"]["7yr"]["avg_ft_per_yr"],
            },
            "n_transects_used": {k: result["rates"][k].get("n_transects", 0) for k in ("3yr", "5yr", "7yr")},
            "n_detections": n_detections,
            "n_transects": n_transects,
            "model_metadata": {
                "model": "coastsat_mlp_v1",
                "aggregation": METHOD_TAG,
                "source": "Sentinel-2 via Google Earth Engine",
                "season": "Sept 1 - Oct 31",
                "year_range": [START_YEAR, END_YEAR],
                "epsg": 32619,
            },
        }
        _write(zones_out)
        r3 = zones_out[zone_id]["erosion_rates"]["3yr_avg_ft_per_yr"]
        r5 = zones_out[zone_id]["erosion_rates"]["5yr_avg_ft_per_yr"]
        r7 = zones_out[zone_id]["erosion_rates"]["7yr_avg_ft_per_yr"]
        print(f"  ✓ {zone_id:<22} 3yr={r3 if r3 is None else f'{r3:+6.2f}'}  5yr={r5 if r5 is None else f'{r5:+6.2f}'}  7yr={r7:+6.2f} ft/yr · {n_detections} scenes · {n_transects} transects", flush=True)

    print(f"\nDone. {len(zones_out)} zones with ML data in {OUTPUT.relative_to(REPO_ROOT)}", flush=True)


if __name__ == "__main__":
    main()
