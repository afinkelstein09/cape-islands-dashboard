"""Grade each CoastSat-derived erosion rate against the dashboard's
hardcoded `erosionRate` value (survey-derived). Surfaces:
  - Zones where CoastSat agrees with the survey (ship these)
  - Zones where CoastSat disagrees by a believable amount (recent
    acceleration vs long-term average — ship with note)
  - Zones with cartoon-sized rates (don't ship — likely polygon issue)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_survey_rates() -> dict[str, float]:
    html = (REPO_ROOT / "index.html").read_text()
    m = re.search(r"const areaData = \{(.+?)^\};$", html, re.DOTALL | re.MULTILINE)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, float] = {}
    for zm in re.finditer(r"^\s*([a-z_]+):\s*\{(.+?)^\s*\},$", block, re.DOTALL | re.MULTILINE):
        zone_id, body = zm.group(1), zm.group(2)
        rm = re.search(r"erosionRate:\s*['\"]([\d.]+)\s*ft", body)
        if rm:
            out[zone_id] = float(rm.group(1))
    return out


def grade(survey: float, coastsat_signed: float) -> tuple[str, str]:
    """Return (verdict, reason). Verdicts: ship, ship-note, hold."""
    cs = abs(coastsat_signed)
    diff = cs - survey
    if cs > 50:
        return "HOLD", f"cartoon-sized ({cs:.1f} ft/yr is not physical)"
    if cs > 30:
        return "HOLD", f"too high ({cs:.1f} ft/yr — likely polygon issue)"
    if abs(diff) <= 2:
        return "SHIP", f"matches survey ({survey:.1f} vs {cs:.1f})"
    if abs(diff) <= 5:
        return "SHIP", f"close to survey ({survey:.1f} vs {cs:.1f}, Δ={diff:+.1f})"
    if diff > 0:
        return "SHIP*", f"recent {cs:.1f} > long-term {survey:.1f} (Δ={diff:+.1f}, plausible accel)"
    return "REVIEW", f"recent {cs:.1f} < long-term {survey:.1f} (Δ={diff:+.1f}, unusual)"


def main() -> None:
    survey = parse_survey_rates()
    ml = json.loads((REPO_ROOT / "zones_ml.json").read_text()).get("zones", {})

    print(f"{'Zone':<22} {'Survey':>8} {'CS 7yr':>8} {'Verdict':<8} {'Reason'}")
    print("-" * 90)

    summary: dict[str, int] = {}
    for zone_id in sorted(set(survey) | set(ml)):
        s = survey.get(zone_id)
        m_data = ml.get(zone_id, {})
        c = m_data.get("erosion_rates", {}).get("7yr_avg_ft_per_yr") if m_data else None

        if s is None and c is None:
            continue
        if c is None:
            print(f"{zone_id:<22} {s:>8.1f} {'—':>8} {'PENDING':<8} not yet in zones_ml.json")
            summary["PENDING"] = summary.get("PENDING", 0) + 1
            continue
        if s is None:
            print(f"{zone_id:<22} {'—':>8} {c:>+8.2f} {'?':<8} no survey rate to compare against")
            continue

        verdict, reason = grade(s, c)
        summary[verdict.rstrip("*")] = summary.get(verdict.rstrip("*"), 0) + 1
        print(f"{zone_id:<22} {s:>8.1f} {c:>+8.2f} {verdict:<8} {reason}")

    print()
    print("Summary:", summary)


if __name__ == "__main__":
    main()
