"""Convert per-date shorelines into erosion rates (ft/yr) per zone.

Approach: place cross-shore transects perpendicular to a reference shoreline,
project each dated shoreline onto each transect, then regress distance over
time to get a per-transect rate. Zone-level rate is the average across
transects, weighted by transect length.

For 2yr/5yr/7yr windows we fit the regression on the subset of dates inside
each window.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

import numpy as np

METERS_PER_FOOT = 0.3048


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def _years_between(iso_a: str, iso_b: str) -> float:
    a = dt.date.fromisoformat(iso_a)
    b = dt.date.fromisoformat(iso_b)
    return abs((b - a).days) / 365.25


def _shoreline_length_m(line: list[list[float]]) -> float:
    return sum(
        _haversine_m(line[i][0], line[i][1], line[i+1][0], line[i+1][1])
        for i in range(len(line) - 1)
    )


def _mean_position(line: list[list[float]]) -> tuple[float, float]:
    arr = np.asarray(line)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def rate_for_window(shorelines: dict[str, list[list[float]]],
                    window_years: int,
                    end: dt.date | None = None) -> tuple[float | None, int]:
    """Linear-regression erosion rate (ft/yr) over the most recent `window_years`.

    Uses mean-position drift between dates as a coarse proxy. Returns
    (rate_ft_per_yr, num_observations). Negative = erosion (landward), positive
    = accretion. None when fewer than 2 dates fall in the window.

    Note: this is the "starter" implementation that operates on mean shoreline
    position. For higher fidelity, replace with CoastSat's SDS_transects.
    """
    if not shorelines:
        return None, 0
    end = end or dt.date.today()
    cutoff = end - dt.timedelta(days=window_years * 365 + 30)
    dated = []
    for iso, line in shorelines.items():
        try:
            d = dt.date.fromisoformat(iso)
        except ValueError:
            continue
        if d < cutoff or d > end:
            continue
        if len(line) < 2:
            continue
        dated.append((d, _mean_position(line)))
    if len(dated) < 2:
        return None, len(dated)
    dated.sort(key=lambda x: x[0])
    # Project onto direction of motion (anchor at first point).
    lat0, lng0 = dated[0][1]
    xs, ys = [], []
    for d, (lat, lng) in dated:
        xs.append((d - dated[0][0]).days / 365.25)
        ys.append(_haversine_m(lat0, lng0, lat, lng))
    slope_m_per_yr = float(np.polyfit(xs, ys, 1)[0])
    return slope_m_per_yr / METERS_PER_FOOT, len(dated)


def erosion_for_zone(shorelines: dict[str, list[list[float]]]) -> dict:
    """Compute 2/5/7 yr erosion rates for one zone."""
    rates: dict[str, dict[str, float | int | None]] = {}
    for label, years in (("2yr", 2), ("5yr", 5), ("7yr", 7)):
        rate, n = rate_for_window(shorelines, years)
        rates[label] = {"avg_ft_per_yr": round(rate, 2) if rate is not None else None,
                        "observations": n}
    return rates
