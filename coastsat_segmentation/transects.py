"""Auto-generate cross-shore transects for each zone from detected shoreline points.

A transect is a short line segment running from inland to offshore, perpendicular
to the local shoreline direction. We measure where each year's shoreline crosses
each transect; year-over-year changes in that crossing distance are the real
erosion / accretion signal, free of the "mean centroid drifts because coverage
changes" problem that broke the simpler aggregation methods.

Algorithm:
  1. Cluster all detected points spatially (DBSCAN) — picks the main shoreline
     and ignores small disconnected detections.
  2. PCA on the main cluster gives the dominant alongshore direction.
  3. Sample N anchor points evenly along that direction.
  4. Each anchor gets a LOCAL PCA (within ±300 m) to recompute the alongshore
     direction at that point — this handles curving coastlines that a single
     global PCA can't capture.
  5. The cross-shore direction is the local perpendicular, sign-aligned so the
     "offshore" end always points away from the zone polygon centroid.

Output: list of (start_xy, end_xy) tuples in UTM 19N meters. start is inland,
end is offshore — so `LineString(transect).project(crossing_point)` gives the
crossing's distance from the inland anchor.
"""

from __future__ import annotations

import numpy as np
from pyproj import Transformer
from sklearn.cluster import DBSCAN

from .zones import ZONES_LATLNG

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32619", always_xy=True)

# Tunables
CLUSTER_EPS_M = 250
CLUSTER_MIN_SAMPLES = 5
N_TRANSECTS = 10
TRANSECT_HALF_LENGTH_M = 500
LOCAL_DIRECTION_WINDOW_M = 400


def polygon_centroid_utm(zone_id: str) -> np.ndarray:
    coords = ZONES_LATLNG[zone_id]
    lat = sum(c[0] for c in coords) / len(coords)
    lng = sum(c[1] for c in coords) / len(coords)
    e, n = _TO_UTM.transform(lng, lat)
    return np.array([float(e), float(n)])


def latlng_to_utm_array(points_latlng: list[list[float]]) -> np.ndarray:
    """Convert [[lat, lng], ...] to N×2 UTM array."""
    if not points_latlng:
        return np.empty((0, 2))
    arr = np.asarray(points_latlng)
    e, n = _TO_UTM.transform(arr[:, 1], arr[:, 0])  # pyproj wants (lng, lat)
    return np.column_stack([e, n])


def main_shoreline_cluster(pts_utm: np.ndarray) -> np.ndarray:
    """Return the largest spatially-connected cluster of detection points.

    This is our stand-in for a CoastSat reference shoreline: the dominant
    coastline in the zone. Detections far from it (the wrong coast in a
    multi-shore polygon, or speckle inland) can then be rejected, mirroring
    CoastSat's `max_dist_ref` filter without a second segmentation pass.
    """
    if len(pts_utm) < 20:
        return np.empty((0, 2))
    db = DBSCAN(eps=CLUSTER_EPS_M, min_samples=CLUSTER_MIN_SAMPLES).fit(pts_utm)
    labels = db.labels_
    valid_labels = labels[labels >= 0]
    if len(valid_labels) == 0:
        return np.empty((0, 2))
    largest_label = int(np.bincount(valid_labels).argmax())
    return pts_utm[labels == largest_label]


def generate_transects(zone_id: str, pts_utm: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Build cross-shore transects for `zone_id` from pooled detection points.

    pts_utm: N×2 array of detected shoreline points (UTM 19N).
    Returns list of (start, end) tuples, where start is inland and end is offshore.
    """
    if len(pts_utm) < 20:
        return []

    main = main_shoreline_cluster(pts_utm)
    if len(main) < 20:
        return []

    # Global PCA on the main cluster to find the dominant alongshore direction
    centered = main - main.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    alongshore_global = vh[0] / np.linalg.norm(vh[0])
    projections = centered @ alongshore_global

    sorted_idx = np.argsort(projections)
    proj_sorted = projections[sorted_idx]
    pts_sorted = main[sorted_idx]

    span = proj_sorted[-1] - proj_sorted[0]
    if span < 200:
        return []

    poly_center = polygon_centroid_utm(zone_id)

    # Sample N anchor points evenly along the alongshore axis. Skip endpoints
    # slightly so we don't anchor at coastline edges where PCA is unstable.
    fractions = np.linspace(0.05, 0.95, N_TRANSECTS)
    transects: list[tuple[np.ndarray, np.ndarray]] = []

    for f in fractions:
        target_proj = proj_sorted[0] + f * span
        # Local window of points near the target projection along alongshore axis
        local_mask = np.abs(proj_sorted - target_proj) < LOCAL_DIRECTION_WINDOW_M
        local_pts = pts_sorted[local_mask]
        if len(local_pts) < 5:
            continue

        anchor = local_pts.mean(axis=0)
        local_centered = local_pts - anchor
        _, _, lvh = np.linalg.svd(local_centered, full_matrices=False)
        local_alongshore = lvh[0] / np.linalg.norm(lvh[0])
        # Cross-shore = 90° rotation of alongshore
        cross_shore = np.array([-local_alongshore[1], local_alongshore[0]])

        # Sign-align: offshore should point AWAY from polygon centroid
        to_offshore = anchor - poly_center
        if cross_shore @ to_offshore < 0:
            cross_shore = -cross_shore

        start = anchor - TRANSECT_HALF_LENGTH_M * cross_shore  # inland
        end = anchor + TRANSECT_HALF_LENGTH_M * cross_shore    # offshore
        transects.append((start, end))

    return transects
