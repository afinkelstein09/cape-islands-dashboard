"""Seed time series extracted from index.html.

Used when NOAA CO-OPS is unreachable, and as the source of truth for per-zone
erosion histories (the dashboard's chartData arrays). Updating the dashboard's
numbers and updating these should happen together until areaData is moved out
of index.html.
"""

# Ocean series — annual values matching the dashboard's chart fallbacks.
SST_YEARS = [2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025]
SST_VALUES_F = [53.4, 53.7, 54.0, 54.2, 54.5, 54.8, 55.1, 55.5, 55.8, 56.1, 56.4]

SLR_YEARS = [1993, 1997, 2001, 2005, 2009, 2013, 2017, 2021, 2024]
SLR_VALUES_IN = [0.0, 0.4, 0.9, 1.4, 1.9, 2.5, 3.2, 3.9, 4.7]

SALINITY_YEARS = [2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025]
SALINITY_VALUES_PSU = [31.8, 31.7, 31.6, 31.5, 31.4, 31.3, 31.2, 31.0, 30.9, 30.8, 30.7]

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
