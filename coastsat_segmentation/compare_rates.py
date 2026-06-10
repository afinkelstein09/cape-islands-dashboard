"""Compare CoastSat-derived erosion rates against the dashboard's current
survey/NDWI rates per zone.

Reads zones_ml.json (CoastSat output) and the dashboard's hardcoded
erosionRate from index.html, prints a side-by-side table flagging zones
where the two methods disagree by more than 2 ft/yr.

Usage:
    .venv/bin/python -m coastsat_segmentation.compare_rates
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_dashboard_rates() -> dict[str, float]:
    """Extract the hardcoded `erosionRate: 'X ft/yr'` per zone from index.html."""
    html = (REPO_ROOT / "index.html").read_text()
    block_match = re.search(r"const areaData = \{(.+?)^\};$", html, re.DOTALL | re.MULTILINE)
    if not block_match:
        return {}
    block = block_match.group(1)
    out: dict[str, float] = {}
    # Match each top-level zone key, then find its erosionRate within
    for m in re.finditer(r"^\s*([a-z_]+):\s*\{(.+?)^\s*\},$", block, re.DOTALL | re.MULTILINE):
        zone_id, body = m.group(1), m.group(2)
        rate_m = re.search(r"erosionRate:\s*['\"]([\d.]+)\s*ft", body)
        if rate_m:
            out[zone_id] = float(rate_m.group(1))
    return out


def main() -> None:
    ml_path = REPO_ROOT / "zones_ml.json"
    if not ml_path.exists():
        print("zones_ml.json not found yet — run the CoastSat pipeline first.")
        return
    ml = json.loads(ml_path.read_text()).get("zones", {})
    survey = parse_dashboard_rates()

    print(f"{'Zone':<22} {'Survey':>10} {'CoastSat':>10} {'Δ':>8} {'Flag':<12} {'Scenes':>8}")
    print("-" * 76)

    diffs: list[tuple[str, float]] = []
    for zone_id in sorted(set(survey) | set(ml)):
        s = survey.get(zone_id)
        m_data = ml.get(zone_id, {})
        c = m_data.get("erosion_rates", {}).get("7yr_avg_ft_per_yr") if m_data else None
        n = m_data.get("n_detections", 0) if m_data else 0

        s_str = f"{s:>10.2f}" if s is not None else f"{'—':>10}"
        c_str = f"{abs(c):>10.2f}" if isinstance(c, (int, float)) else f"{'—':>10}"

        flag = ""
        delta = ""
        if s is not None and isinstance(c, (int, float)):
            d = abs(c) - s
            diffs.append((zone_id, d))
            delta = f"{d:+.2f}"
            if abs(d) > 5:
                flag = "DISAGREE !"
            elif abs(d) > 2:
                flag = "differ"
            else:
                flag = "ok"
        elif c is None and zone_id in ml:
            flag = "no-data"
        elif zone_id not in ml:
            flag = "pending"

        print(f"{zone_id:<22} {s_str} {c_str} {delta:>8} {flag:<12} {n:>8}")

    if diffs:
        print(f"\nMean disagreement (|ΔCoastSat-survey|): {sum(abs(d) for _,d in diffs)/len(diffs):.2f} ft/yr")
        print(f"Largest disagreement: {max(diffs, key=lambda x: abs(x[1]))}")


if __name__ == "__main__":
    main()
