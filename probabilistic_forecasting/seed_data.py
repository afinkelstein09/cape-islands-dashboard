"""Seed time series extracted from index.html.

Used when NOAA CO-OPS is unreachable, and as the source of truth for per-zone
erosion histories (the dashboard's chartData arrays). Updating the dashboard's
numbers and updating these should happen together until areaData is moved out
of index.html.
"""

# Ocean series — annual values. Linearly interpolated between the dashboard's
# original biennial anchor points so charts show a value at every year.
SST_YEARS = list(range(2005, 2026))
SST_VALUES_F = [
    53.40, 53.55, 53.70, 53.85, 54.00, 54.10, 54.20, 54.35, 54.50, 54.65,
    54.80, 54.95, 55.10, 55.30, 55.50, 55.65, 55.80, 55.95, 56.10, 56.25,
    56.40,
]

SLR_YEARS = list(range(1993, 2026))
SLR_VALUES_IN = [
     0.00, -1.59, -0.47,  2.13,  2.38,  2.75,  1.34,  0.94,  1.29,  0.86,
     0.81,  1.26,  3.45,  2.69,  1.57,  3.09,  3.74,  5.64,  4.39,  4.09,
     3.46,  3.34,  2.69,  4.22,  4.62,  4.89,  5.79,  5.81,  5.89,  5.77,
     8.63,  7.99,  6.30,
]

SALINITY_YEARS = list(range(2005, 2026))
SALINITY_VALUES_PSU = [
    31.80, 31.75, 31.70, 31.65, 31.60, 31.55, 31.50, 31.45, 31.40, 31.35,
    31.30, 31.25, 31.20, 31.10, 31.00, 30.95, 30.90, 30.85, 30.80, 30.75,
    30.70,
]

# Per-zone erosion (m²/yr or ft/yr depending on zone — the dashboard treats the
# chartData array uniformly, so we do too). Years are uniform across all zones.
ZONE_EROSION_YEARS = [2012, 2016, 2020, 2024]

ZONE_EROSION = {
    "mv_gayhead":         [2.7, 3.0, 3.4, 4.8],
    "mv_southbeach":      [4.5, 6.1, 11.2, 8.1],
    "mv_longpoint":       [4.3, 6.5, 5.5, 6.4],
    "outercape":          [3.5, 4.8, 7.5, 9.9],
    "nauset":             [3.0, 4.6, 3.4, 8.1],
    "buzzardsbay":        [1.2, 1.2, 0.5, 1.2],
    "nantucket":          [4.9, 5.9, 5.1, 9.0],
    "wellfleet":          [2.1, 2.4, 2.7, 2.4],
    "mv_northshore":      [5.2, 3.2, 1.5, 2.5],
    "mv_chappaquiddick":  [4.4, 3.5, 3.8, 9.2],
    "mv_menemsha":        [2.8, 1.7, 1.2, 0.3],
    "chatham":            [5.9, 5.3, 16.5, 28.5],
    "dennis_brewster":    [8.2, 21.7, 12.7, 175.7],
    "barnstable":         [30.3, 13.8, 2.9, 23.3],
    "falmouth":           [0.5, 0.5, 0.4, 1.5],
    "bourne":             [0.7, 0.7, 1.2, 1.0],
    "elizabeth":          [3.3, 1.2, 0.9, 1.6],
    "nantucket_north":    [3.9, 3.2, 3.9, 10.0],
    "great_point":        [2.3, 2.4, 5.1, 8.1],
}
