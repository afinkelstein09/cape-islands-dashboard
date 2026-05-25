"""Pull Sentinel-2 imagery for all 19 zones via Google Earth Engine.

Each zone is downloaded once per year, restricted to **September 1 – October 31**.
This is the late-summer / pre-storm window when beaches are at their full
"summer profile" — most coastal-change studies (USGS, MCZM) compare scenes in
the same season to avoid mixing seasonal beach rebuilding with real erosion.

Each year gets its own sitename (`zone_id_YYYY`) so CoastSat's metadata file
doesn't get overwritten between yearly calls.

Requires:
  - Authenticated Google Earth Engine account
  - CoastSat installed (cloned to ./external/CoastSat, added to PYTHONPATH)
"""

from __future__ import annotations

import os
from pathlib import Path

import ee

from .zones import ZONES_LATLNG, coastsat_polygon

IMAGERY_DIR = Path(__file__).parent / "imagery"
IMAGERY_DIR.mkdir(exist_ok=True)

# Google Cloud Project that owns the Earth Engine quota.
GEE_PROJECT = os.environ.get("GEE_PROJECT", "personal-dashboard-494604")

# Annual analysis window — September 1 through October 31.
SEASON_START = (9, 1)
SEASON_END = (10, 31)


def _ensure_ee_init() -> None:
    """Initialize Earth Engine if it hasn't been already."""
    try:
        ee.Number(1).getInfo()
    except Exception:
        ee.Initialize(project=GEE_PROJECT)


def yearly_sitename(zone_id: str, year: int) -> str:
    """The CoastSat sitename for one (zone, year) pair."""
    return f"{zone_id}_{year}"


def download_zone_year(zone_id: str, year: int) -> dict:
    """Retrieve September–October Sentinel-2 imagery for one zone, one year."""
    _ensure_ee_init()
    from coastsat import SDS_download  # lazy import; CoastSat only required at run-time

    sm, sd = SEASON_START
    em, ed = SEASON_END
    inputs = {
        "sitename": yearly_sitename(zone_id, year),
        "polygon": [coastsat_polygon(zone_id)],
        "dates": [f"{year}-{sm:02d}-{sd:02d}", f"{year}-{em:02d}-{ed:02d}"],
        "sat_list": ["S2"],
        "filepath": str(IMAGERY_DIR),
        "landsat_collection": "C02",
    }
    return SDS_download.retrieve_images(inputs)


# Zones whose polygon area exceeds GEE's 48 MB per-request download limit.
# These need to be split into sub-polygons (see TODO) before they can be
# processed. Skipped for now so they don't block the rest of the run.
SKIP_ZONES: set[str] = {
    "outercape",  # Wellfleet-to-Provincetown — ~700 km², way over limit.
                  # Split into north/middle/south sub-polygons later.
}


def download_all(start_year: int = 2018, end_year: int = 2024) -> dict[str, dict[int, dict]]:
    """Download imagery for all 19 zones × range of years (Sept–Oct each).

    Already-downloaded scenes are detected by CoastSat and skipped, so this
    function is safe to re-run after a crash to resume where it left off.
    """
    results: dict[str, dict[int, dict]] = {}
    total = len(ZONES_LATLNG) * (end_year - start_year + 1)
    done = 0
    for zone_id in ZONES_LATLNG:
        results[zone_id] = {}
        if zone_id in SKIP_ZONES:
            print(f"[skip] {zone_id} — polygon too large for single GEE request", flush=True)
            done += (end_year - start_year + 1)
            continue
        for year in range(start_year, end_year + 1):
            done += 1
            print(f"[{done}/{total}] {zone_id} {year} ...", flush=True)
            try:
                results[zone_id][year] = download_zone_year(zone_id, year)
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ failed: {e}", flush=True)
                results[zone_id][year] = {"error": str(e)}
    return results


if __name__ == "__main__":
    download_all()
