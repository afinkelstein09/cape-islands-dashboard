"""Convert per-year shoreline detections into erosion rates (ft/yr) using
**cross-shore transects**.

For each zone:
  1. Pool every detected shoreline point across every year (UTM 19N).
  2. Generate ~10 auto-placed transects perpendicular to the local shoreline
     direction (see transects.py).
  3. For each transect, find where every scene's shoreline polyline crosses it
     and record the distance from the inland end of the transect. That's the
     scene's shoreline position at that transect.
  4. Within each year, take the median crossing per transect (robust to tide
     phase variation across the ~10 cloud-free Sept–Oct scenes).
  5. For each requested window (3yr, 5yr, 7yr), regress (year → position) per
     transect to get a per-transect slope in m/yr.
  6. Take the **median** across transects to get the zone-level rate. Median
     is robust to one transect catching a sand spit or sub-zone anomaly.
  7. Convert m/yr to ft/yr. Positive = accretion (offshore drift), negative =
     erosion (landward drift).

This handles wrapping coastlines correctly because each transect is a local
measurement — no single global "alongshore direction" assumed.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import theilslopes
from shapely.geometry import LineString

from .transects import generate_transects, latlng_to_utm_array, main_shoreline_cluster

METERS_PER_FOOT = 0.3048

# Max distance (m) a detected shoreline point may sit from the reference
# coastline (the main cluster) before it's discarded. Mirrors CoastSat's
# `max_dist_ref`; 150 m is a touch looser than the canonical 100 m because our
# reference is data-derived rather than hand-drawn.
MAX_DIST_REF_M = 150.0

# A transect must have at least this many yearly positions before its slope
# is trusted — two points is just a line through noise. Three is the floor
# that still lets the 3yr window (which spans at most three yearly medians)
# produce a rate; Theil–Sen is well-defined at n=3.
MIN_YEARS_PER_TRANSECT = 3
# Fraction trimmed from each tail of the per-transect slope distribution
# before taking the zone median, to drop transects that caught a spit,
# inlet, or the wrong shoreline.
TRANSECT_TRIM_FRAC = 0.20


def transect_crossing(transect_start: np.ndarray, transect_end: np.ndarray,
                      shoreline_utm: np.ndarray) -> float | None:
    """Distance from the inland transect end to where the shoreline crosses.

    Returns None if the shoreline doesn't cross the transect. If it crosses
    multiple times (e.g. across a sand spit), takes the **most-offshore**
    crossing — that's the seaward extent of the beach face.
    """
    if len(shoreline_utm) < 2:
        return None
    transect = LineString([transect_start.tolist(), transect_end.tolist()])
    shoreline = LineString(shoreline_utm.tolist())
    if not transect.intersects(shoreline):
        return None
    inter = transect.intersection(shoreline)
    if inter.is_empty:
        return None
    if inter.geom_type == "Point":
        return float(transect.project(inter))
    if inter.geom_type == "MultiPoint":
        return float(max(transect.project(p) for p in inter.geoms))
    if inter.geom_type == "LineString":
        # Collinear overlap — take the endpoint closest to offshore
        endpts = list(inter.coords)
        return float(max(transect.project(LineString([p, p]).centroid) for p in endpts))
    return None


def _filter_to_reference(shoreline_utm: np.ndarray, ref_tree: cKDTree | None) -> np.ndarray:
    """Drop shoreline points farther than MAX_DIST_REF_M from the reference coast.

    This is the post-hoc equivalent of CoastSat's `max_dist_ref`: a scene that
    detected the wrong shoreline (the bay side of a two-coast polygon, or inland
    speckle) gets those points removed before we measure a crossing.
    """
    if ref_tree is None or len(shoreline_utm) == 0:
        return shoreline_utm
    dists, _ = ref_tree.query(shoreline_utm)
    return shoreline_utm[dists <= MAX_DIST_REF_M]


def _per_transect_year_positions(
    transects: list[tuple[np.ndarray, np.ndarray]],
    year_to_detections: dict[int, list[dict]],
    ref_tree: cKDTree | None = None,
) -> list[dict[int, float]]:
    """For each transect, compute the median shoreline-crossing distance per year.

    Returns a list (one per transect) of {year: median_crossing_m_from_inland}.
    """
    result: list[dict[int, float]] = []
    for ts, te in transects:
        year_positions: dict[int, list[float]] = {}
        for year, detections in year_to_detections.items():
            for det in detections:
                shoreline_utm = latlng_to_utm_array(det.get("points", []))
                shoreline_utm = _filter_to_reference(shoreline_utm, ref_tree)
                d = transect_crossing(ts, te, shoreline_utm)
                if d is not None:
                    year_positions.setdefault(year, []).append(d)
        median_by_year = {y: float(np.median(crs)) for y, crs in year_positions.items() if crs}
        result.append(median_by_year)
    return result


def _slope_m_per_yr(year_to_position: dict[int, float]) -> float | None:
    """Robust per-transect slope (m/yr) via Theil–Sen.

    Theil–Sen is the median of all pairwise slopes, so a single bad year
    (cloud edge, high-tide scene) can't yank the fit the way ordinary
    least-squares does. Requires MIN_YEARS_PER_TRANSECT points.
    """
    if len(year_to_position) < MIN_YEARS_PER_TRANSECT:
        return None
    years = np.array(sorted(year_to_position.keys()), dtype=float)
    positions = np.array([year_to_position[int(y)] for y in years], dtype=float)
    slope = float(theilslopes(positions, years)[0])
    return slope


def _trimmed_median(values: list[float]) -> float:
    """Median after dropping TRANSECT_TRIM_FRAC from each tail.

    Drops transects whose slope is an outlier relative to the others
    (a transect crossing a spit/inlet or, in a broken polygon, the wrong
    shore). With few transects the trim is skipped so we never throw away
    most of the data.
    """
    arr = np.sort(np.array(values, dtype=float))
    k = int(len(arr) * TRANSECT_TRIM_FRAC)
    if k > 0 and len(arr) - 2 * k >= 3:
        arr = arr[k:len(arr) - k]
    return float(np.median(arr))


def erosion_for_zone(zone_id: str, year_to_detections: dict[int, list[dict]]) -> dict:
    """Compute 3yr / 5yr / 7yr erosion rates via per-transect linear regression.

    Sign: positive ft/yr = accretion (seaward), negative = erosion (landward).
    """
    # Pool every detection point in UTM for transect generation
    pooled = []
    for detections in year_to_detections.values():
        for det in detections:
            pooled.extend(det.get("points", []))
    pts_utm = latlng_to_utm_array(pooled)
    transects = generate_transects(zone_id, pts_utm)

    if not transects:
        return _empty_result(year_to_detections, transects)

    # Reference coastline = the main detection cluster. Crossings from points
    # far off it (wrong coast / inland speckle) are filtered out, our stand-in
    # for CoastSat's max_dist_ref.
    ref = main_shoreline_cluster(pts_utm)
    ref_tree = cKDTree(ref) if len(ref) >= 20 else None

    per_transect = _per_transect_year_positions(transects, year_to_detections, ref_tree)
    n_detections = sum(len(v) for v in year_to_detections.values())

    rates: dict[str, dict] = {}
    last_year = max(
        (max(t.keys()) for t in per_transect if t),
        default=None,
    )
    for label, window in (("3yr", 3), ("5yr", 5), ("7yr", 7)):
        if last_year is None:
            rates[label] = {"avg_ft_per_yr": None, "n_transects": 0}
            continue
        cutoff = last_year - window
        per_transect_slopes: list[float] = []
        for tdata in per_transect:
            sub = {y: p for y, p in tdata.items() if y > cutoff}
            slope = _slope_m_per_yr(sub)
            if slope is not None:
                per_transect_slopes.append(slope)
        if per_transect_slopes:
            median_slope_m = _trimmed_median(per_transect_slopes)
            rates[label] = {
                "avg_ft_per_yr": round(median_slope_m / METERS_PER_FOOT, 2),
                "n_transects": len(per_transect_slopes),
            }
        else:
            rates[label] = {"avg_ft_per_yr": None, "n_transects": 0}

    return {
        "annual_positions": {},  # not meaningful at zone level with transects
        "rates": rates,
        "n_detections": n_detections,
        "n_transects": len(transects),
    }


def _empty_result(year_to_detections, transects) -> dict:
    n_detections = sum(len(v) for v in year_to_detections.values())
    return {
        "annual_positions": {},
        "rates": {k: {"avg_ft_per_yr": None, "n_transects": 0} for k in ("3yr", "5yr", "7yr")},
        "n_detections": n_detections,
        "n_transects": len(transects),
    }
