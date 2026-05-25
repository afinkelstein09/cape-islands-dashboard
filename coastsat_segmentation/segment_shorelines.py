"""Segment water/land per Sentinel-2 scene and extract shorelines.

CoastSat does the heavy lifting: it preprocesses each scene (pan-sharpening,
cloud masking), classifies pixels via a trained CNN, and traces the
sand-water boundary as a polyline. We just wrap it with config tuned for the
mixed cliff/sand/marsh coastline of Cape & Islands.

Output per zone: a dict mapping ISO date strings -> list of [lat, lng] points
along the shoreline at that date.
"""

from __future__ import annotations

import numpy as np

from .download_imagery import IMAGERY_DIR
from .zones import ZONES_LATLNG, coastsat_polygon

# UTM zone 19N covers all of Cape Cod, the Vineyard, and Nantucket.
OUTPUT_EPSG = 32619

DEFAULT_SETTINGS = {
    "cloud_thresh": 0.5,
    "dist_clouds": 300,
    "output_epsg": OUTPUT_EPSG,
    "check_detection": False,  # set True locally to inspect masks visually
    "save_figure": True,
    "adjust_detection": False,
    "min_beach_area": 1000,    # m² — filter out tiny spurious sand patches
    "buffer_size": 150,        # m — search width around reference shoreline
    "min_length_sl": 200,      # m — drop shoreline segments shorter than this
    "cloud_mask_issue": False,
    "sand_color": "default",   # 'dark' if cliffs/dark sand dominate
    "pan_off": False,
    "max_dist_ref": 100,       # m
}


def extract_for_zone(zone_id: str, metadata: dict, settings: dict | None = None) -> dict:
    """Run CoastSat shoreline extraction for one zone.

    Returns {iso_date: [[lat, lng], ...]} so the dashboard JSON matches the
    spec without further conversion.
    """
    from coastsat import SDS_preprocess, SDS_shoreline

    s = dict(DEFAULT_SETTINGS)
    s.update({
        "inputs": {
            "sitename": zone_id,
            "polygon": [coastsat_polygon(zone_id)],
            "filepath": str(IMAGERY_DIR),
        },
    })
    if settings:
        s.update(settings)

    # Reference shoreline = mean of all scenes' coarse waterline, used as
    # the search center for fine extraction. CoastSat builds this on first
    # run and caches it under filepath/sitename/.
    SDS_preprocess.save_jpg(metadata, s)
    output = SDS_shoreline.extract_shorelines(metadata, s)

    # CoastSat returns shorelines in projected coords (UTM). Re-project to
    # lat/lng for the dashboard.
    from pyproj import Transformer
    to_latlng = Transformer.from_crs(f"EPSG:{OUTPUT_EPSG}", "EPSG:4326", always_xy=True)

    shorelines: dict[str, list[list[float]]] = {}
    for date, line in zip(output.get("dates", []), output.get("shorelines", [])):
        iso = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
        if line is None or len(line) == 0:
            continue
        arr = np.asarray(line)
        lng, lat = to_latlng.transform(arr[:, 0], arr[:, 1])
        shorelines[iso] = [[round(float(la), 6), round(float(lo), 6)]
                           for la, lo in zip(lat, lng)]
    return shorelines


def extract_all(metadata_by_zone: dict[str, dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for zone_id in ZONES_LATLNG:
        md = metadata_by_zone.get(zone_id)
        if not md or md.get("error"):
            out[zone_id] = {"error": (md or {}).get("error", "no metadata")}
            continue
        try:
            out[zone_id] = extract_for_zone(zone_id, md)
        except Exception as e:  # noqa: BLE001
            print(f"[{zone_id}] segmentation failed: {e}")
            out[zone_id] = {"error": str(e)}
    return out
