"""Segment water/land per Sentinel-2 scene and extract shorelines.

CoastSat does the heavy lifting: it preprocesses each scene (pan-sharpening,
cloud masking), classifies pixels via a trained CNN, and traces the
sand-water boundary as a polyline. We just wrap it with config tuned for the
mixed cliff/sand/marsh coastline of Cape & Islands.

Output per zone: a dict mapping year -> list of {date, points_latlng} for
every scene where a shoreline was detected. Per-year aggregation happens in
compute_erosion.py.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # avoid the macOS GUI backend (showMaximized() crashes)

import pickle

import numpy as np

from .download_imagery import IMAGERY_DIR, yearly_sitename
from .zones import coastsat_polygon

OUTPUT_EPSG = 32619  # UTM zone 19N — covers Cape Cod, Vineyard, Nantucket

DEFAULT_SETTINGS = {
    "cloud_thresh": 0.5,
    "dist_clouds": 300,
    "s2cloudless_prob": 40,
    "output_epsg": OUTPUT_EPSG,
    "check_detection": False,
    "save_figure": False,   # CoastSat's figure code uses showMaximized
                            # which crashes on macOS; we only need shoreline
                            # points, not the preview PNGs.
    "adjust_detection": False,
    "min_beach_area": 1000,
    "buffer_size": 150,
    "min_length_sl": 200,
    "cloud_mask_issue": False,
    "sand_color": "default",
    "pan_off": False,
    "max_dist_ref": 100,
}


def _settings_for(zone_id: str, year: int) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s["inputs"] = {
        "sitename": yearly_sitename(zone_id, year),
        "polygon": [coastsat_polygon(zone_id)],
        "filepath": str(IMAGERY_DIR),
    }
    return s


def _reproject_to_latlng(line) -> list[list[float]]:
    """CoastSat returns shorelines in UTM; convert to (lat, lng) pairs."""
    from pyproj import Transformer
    to_latlng = Transformer.from_crs(f"EPSG:{OUTPUT_EPSG}", "EPSG:4326", always_xy=True)
    arr = np.asarray(line)
    lng, lat = to_latlng.transform(arr[:, 0], arr[:, 1])
    return [[round(float(la), 6), round(float(lo), 6)] for la, lo in zip(lat, lng)]


def extract_year(zone_id: str, year: int) -> list[dict]:
    """Run CoastSat on one (zone, year). Returns list of {date, points_latlng}."""
    from coastsat import SDS_preprocess, SDS_shoreline

    site_dir = IMAGERY_DIR / yearly_sitename(zone_id, year)
    md_path = site_dir / f"{yearly_sitename(zone_id, year)}_metadata.pkl"
    if not md_path.exists():
        return []
    with open(md_path, "rb") as f:
        metadata = pickle.load(f)

    settings = _settings_for(zone_id, year)
    # Build JPG previews CoastSat needs internally
    SDS_preprocess.save_jpg(metadata, settings, use_matplotlib=True)

    output = SDS_shoreline.extract_shorelines(metadata, settings)
    detections: list[dict] = []
    for date, line in zip(output.get("dates", []), output.get("shorelines", [])):
        if line is None or len(line) == 0:
            continue
        iso = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
        detections.append({"date": iso, "points": _reproject_to_latlng(line)})
    return detections


