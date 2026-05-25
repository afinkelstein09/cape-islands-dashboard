"""Pull Sentinel-2 imagery for all 19 zones via Google Earth Engine.

Uses CoastSat's `SDS_download.retrieve_images`. Requires:
  - Authenticated Google Earth Engine account (`earthengine authenticate`)
  - CoastSat installed (`pip install coastsat` — pulls a fairly heavy dep tree
    including TensorFlow). See README.

This script is deliberately a thin wrapper so all CoastSat config lives here
and is easy to tune per region (cloud threshold, etc.).
"""

from __future__ import annotations

from pathlib import Path

from .zones import ZONES_LATLNG, coastsat_polygon

IMAGERY_DIR = Path(__file__).parent / "imagery"
IMAGERY_DIR.mkdir(exist_ok=True)


def download_zone(zone_id: str, dates: tuple[str, str]) -> dict:
    """Retrieve Sentinel-2 imagery for `zone_id` over `dates` (ISO YYYY-MM-DD).

    Returns CoastSat's metadata dict; raises if CoastSat isn't installed.
    """
    from coastsat import SDS_download  # imported lazily so the rest of the
                                       # pipeline doesn't require CoastSat
                                       # just to import the package.

    inputs = {
        "sitename": zone_id,
        "polygon": [coastsat_polygon(zone_id)],
        "dates": list(dates),
        "sat_list": ["S2"],
        "filepath": str(IMAGERY_DIR),
        "landsat_collection": "C02",
    }
    return SDS_download.retrieve_images(inputs)


def download_all(start: str = "2018-01-01", end: str = "2025-12-31") -> dict[str, dict]:
    """Download imagery for all 19 zones across the 7-year window.

    The 2yr/5yr/7yr splits happen downstream in compute_erosion.py — we pull
    the full range once and slice it per window.
    """
    results: dict[str, dict] = {}
    for zone_id in ZONES_LATLNG:
        try:
            results[zone_id] = download_zone(zone_id, (start, end))
        except Exception as e:  # noqa: BLE001 — surface per-zone failures
            print(f"[{zone_id}] download failed: {e}")
            results[zone_id] = {"error": str(e)}
    return results


if __name__ == "__main__":
    download_all()
