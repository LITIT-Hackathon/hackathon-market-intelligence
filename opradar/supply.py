"""P3 -- supply index: the bench aggregated per RoleAtom cell.

Cell = (role_family, seniority). This is the hand-off object Pipeline C
consumes; nothing downstream ever touches individual candidates for matching.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from .config import CONFIG


def build(bench: pd.DataFrame) -> pd.DataFrame:
    readiness_map = CONFIG["people"]["readiness"]
    rows = []
    for (family, seniority), grp in bench.groupby(["role_family", "seniority"]):
        tags: Counter = Counter()
        for t in grp["tech_tags"]:
            tags.update(t)
        available = grp[grp["availability"] != "unavailable"]
        rows.append({
            "role_family": family,
            "seniority": seniority,
            "seniority_rank": int(grp["seniority_rank"].iloc[0]),
            "depth": len(grp),
            "available_depth": len(available),
            "readiness": round(float(grp["availability"].map(readiness_map).mean()), 4),
            "german_speakers": int(grp["speaks_german"].sum()),
            "tech_tags": dict(tags.most_common()),
            # P6 guardrail: scarcity = 1/depth explodes on thin cells; those are
            # flagged and excluded from cell-level ranking, never silently ranked
            "thin_cell": len(grp) < CONFIG["people"]["thin_cell"],
        })
    return pd.DataFrame(rows).sort_values(
        ["role_family", "seniority_rank"]).reset_index(drop=True)
