"""P4 -- market pull: German demand per RoleAtom cell.

This is the correction to the closed loop (ALGORITHM_PEOPLE.md 3.6): demand is
measured from the REAL eligible German postings produced by Pipeline A, never
from the synthetic openings. Reuses the N1 idea -- unfilled vacancies (open
past the configured threshold) are the demand that matters.

A posting with unknown seniority counts toward EVERY seniority level of its
family: a role that states no level can be served by any level, and ~3/4 of
the market states nothing. Seniority-specific pull therefore differentiates
only where postings actually declare a level -- which is honest.
"""

from __future__ import annotations

import pandas as pd

from . import reference as ref
from .config import CONFIG

_SENIORITIES = ["junior", "mid", "senior", "lead"]


def build(eligible: pd.DataFrame) -> pd.DataFrame:
    unfilled_days = CONFIG["people"]["market_pull_days"]

    eligible = eligible.copy()
    if "age_effective" not in eligible.columns:
        eligible["age_effective"] = eligible["posting_age_days"]
    if "signal_weight" not in eligible.columns:
        eligible["signal_weight"] = 1.0

    def _unfilled(df: pd.DataFrame, days: float) -> float:
        return round(float(df.loc[df["age_effective"] > days, "signal_weight"].sum()), 2)

    rows = []
    for family in ref.ROLE_FAMILIES_ATOM:
        fam = eligible[eligible["role_family"] == family]
        unknown = fam[fam["seniority_rank"].isna()]
        # family-level row (seniority="all"): each posting counted once -- the
        # per-seniority rows double-count unknown-seniority postings by design
        # (an unstated role can be served by any level), so charts use this row
        rows.append({
            "role_family": family, "seniority": "all",
            "demand_postings": len(fam),
            "demand_stated": int(fam["seniority_rank"].notna().sum()),
            "unfilled_45": _unfilled(fam, unfilled_days),
            "unfilled_90": _unfilled(fam, 90),
            "companies": int(fam["company_key"].nunique()),
        })
        for seniority in _SENIORITIES:
            rank = ref.SENIORITY_RANK[seniority]
            stated = fam[fam["seniority_rank"] == rank]
            pool = pd.concat([stated, unknown])
            rows.append({
                "role_family": family,
                "seniority": seniority,
                "demand_postings": len(pool),
                "demand_stated": len(stated),
                "unfilled_45": _unfilled(pool, unfilled_days),
                "unfilled_90": _unfilled(pool, 90),
                "companies": int(pool["company_key"].nunique()),
            })
    return pd.DataFrame(rows)
