"""Pull annual-average ocean data from NOAA CO-OPS for Woods Hole 8447930.

Falls back to seed_data values when the API is unreachable so the pipeline can
always produce output. The dashboard already does live latest-value fetches at
runtime — this script is for assembling the multi-year history the GP fits on.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import requests

from . import seed_data

NOAA_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
STATION = "8447930"  # Woods Hole, MA
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _annual_mean(values: Iterable[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _fetch_month(product: str, year: int, month: int, units: str = "english") -> list[float] | None:
    """Pull one month of `product` readings. Returns list of floats or None on failure."""
    cache_file = CACHE_DIR / f"{product}_{year}_{month:02d}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            pass

    days = _DAYS_IN_MONTH[month - 1] + (1 if month == 2 and _is_leap(year) else 0)
    params = {
        "product": product,
        "application": "cape_islands_dashboard",
        "station": STATION,
        "begin_date": f"{year}{month:02d}01",
        "end_date":   f"{year}{month:02d}{days:02d}",
        "datum": "MLLW",
        "time_zone": "lst",
        "units": units,
        "format": "json",
        "interval": "h",  # hourly readings — NOAA sensor products are
                          # capped at 31 days per request, so monthly chunks
                          # are the largest window we can ask for.
    }
    try:
        resp = requests.get(NOAA_BASE, params=params, timeout=20)
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if "error" in body:
        return None

    data = body.get("data") or []
    values: list[float] = []
    for row in data:
        raw = row.get("v") or row.get("value")
        if raw in (None, ""):
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue

    if values:
        cache_file.write_text(json.dumps(values))
    return values or None


def _fetch_year(product: str, year: int, units: str = "english") -> list[float] | None:
    """Aggregate `product` readings for an entire year (one mean per month).

    Returns up to 12 monthly means, or None if every month failed.
    """
    monthly_means: list[float] = []
    for m in range(1, 13):
        raw = _fetch_month(product, year, m, units=units)
        if not raw:
            continue
        monthly_means.append(sum(raw) / len(raw))
    return monthly_means or None


def _fetch_monthly_mean(year: int) -> list[float] | None:
    """The `monthly_mean` product (used for SLR) accepts a full-year range."""
    cache_file = CACHE_DIR / f"monthly_mean_{year}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            pass
    params = {
        "product": "monthly_mean",
        "application": "cape_islands_dashboard",
        "station": STATION,
        "begin_date": f"{year}0101",
        "end_date":   f"{year}1231",
        "datum": "MLLW",
        "time_zone": "lst",
        "units": "english",
        "format": "json",
    }
    try:
        resp = requests.get(NOAA_BASE, params=params, timeout=20)
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if "error" in body:
        return None
    data = body.get("data") or []
    msls: list[float] = []
    for row in data:
        v = row.get("MSL")
        if v in (None, ""):
            continue
        try:
            msls.append(float(v))
        except (TypeError, ValueError):
            continue
    if msls:
        cache_file.write_text(json.dumps(msls))
    return msls or None


def fetch_sst_history(start: int = 2005, end: int | None = None) -> tuple[list[int], list[float]]:
    end = end or dt.date.today().year
    years: list[int] = []
    means: list[float] = []
    for y in range(start, end + 1):
        monthly = _fetch_year("water_temperature", y)
        mean = _annual_mean(monthly) if monthly else None
        if mean is not None:
            years.append(y)
            means.append(round(mean, 2))
    if len(years) >= 4:
        return years, means
    return list(seed_data.SST_YEARS), list(seed_data.SST_VALUES_F)


def fetch_slr_history(start: int = 1993, end: int | None = None) -> tuple[list[int], list[float]]:
    """Return annual MSL relative to 1993 baseline, in inches."""
    end = end or dt.date.today().year
    years: list[int] = []
    msl_in: list[float] = []
    baseline: float | None = None
    for y in range(start, end + 1):
        monthly = _fetch_monthly_mean(y)
        mean = _annual_mean(monthly) if monthly else None
        if mean is None:
            continue
        # NOAA returns MSL in feet relative to MLLW; convert to inches and
        # rebase to the first observed year.
        inches = mean * 12.0
        if baseline is None:
            baseline = inches
        years.append(y)
        msl_in.append(round(inches - baseline, 2))
    if len(years) >= 4:
        return years, msl_in
    return list(seed_data.SLR_YEARS), list(seed_data.SLR_VALUES_IN)


def fetch_salinity_history() -> tuple[list[int], list[float]]:
    """Salinity isn't on the CO-OPS API for this station; use the dashboard's
    historical series until a real source is wired up."""
    return list(seed_data.SALINITY_YEARS), list(seed_data.SALINITY_VALUES_PSU)
