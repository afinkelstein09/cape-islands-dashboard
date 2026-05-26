"""Convert per-year shoreline detections into erosion rates (ft/yr).

Aggregation strategy:
  1. Per (zone, year), average all Sept–Oct detections to one mean position.
     With ~12 cloud-free scenes per year, individual tide noise averages out.
  2. The result is a one-point-per-year time series of mean positions.
  3. For each sub-window (2yr, 5yr, 7yr), regress year → distance-from-anchor
     and report the slope as ft/yr (negative = erosion, positive = accretion).

This is the "starter" implementation. For production, replace with
CoastSat's `SDS_transects.compute_intersection` — that gives per-transect
rates at specific cross-shore lines rather than zone-blob averages.
"""

from __future__ import annotations

import math
from statistics import mean

import numpy as np

METERS_PER_FOOT = 0.3048


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _mean_position(detection_points: list[list[float]]) -> tuple[float, float]:
    arr = np.asarray(detection_points)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def annual_mean_positions(year_to_detections: dict[int, list[dict]]) -> dict[int, tuple[float, float]]:
    """{year: [{date, points}]} -> {year: (mean_lat, mean_lng)}."""
    out: dict[int, tuple[float, float]] = {}
    for year, detections in year_to_detections.items():
        if not detections:
            continue
        lats, lngs = [], []
        for det in detections:
            la, lo = _mean_position(det["points"])
            lats.append(la)
            lngs.append(lo)
        out[year] = (mean(lats), mean(lngs))
    return out


def _slope_ft_per_yr(positions: dict[int, tuple[float, float]]) -> float | None:
    """Regress year vs cumulative distance along the drift direction.

    Anchor is the earliest year's position. Negative slope = landward = erosion.
    """
    if len(positions) < 2:
        return None
    years = sorted(positions.keys())
    lat0, lng0 = positions[years[0]]
    xs, ys = [], []
    for y in years:
        lat, lng = positions[y]
        xs.append(y - years[0])
        ys.append(_haversine_m(lat0, lng0, lat, lng))
    slope_m_per_yr = float(np.polyfit(xs, ys, 1)[0])
    return slope_m_per_yr / METERS_PER_FOOT


def erosion_for_zone(year_to_detections: dict[int, list[dict]]) -> dict:
    """Compute 3yr and 7yr erosion rates from per-year detection lists."""
    positions = annual_mean_positions(year_to_detections)
    if not positions:
        return {
            "annual_positions": {},
            "rates": {k: {"avg_ft_per_yr": None, "n_years": 0} for k in ("3yr", "7yr")},
            "n_detections": 0,
        }
    last_year = max(positions.keys())
    rates: dict[str, dict] = {}
    for label, window in (("3yr", 3), ("7yr", 7)):
        sub = {y: p for y, p in positions.items() if y > last_year - window}
        rate = _slope_ft_per_yr(sub)
        rates[label] = {
            "avg_ft_per_yr": round(rate, 2) if rate is not None else None,
            "n_years": len(sub),
        }
    return {
        "annual_positions": {str(y): {"lat": round(p[0], 6), "lng": round(p[1], 6)}
                             for y, p in positions.items()},
        "rates": rates,
        "n_detections": sum(len(v) for v in year_to_detections.values()),
    }
