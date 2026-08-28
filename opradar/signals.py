"""Pipeline A stage 1: postings -> per-company IT-restricted aggregates.

Reads postings.parquet (the interface contract) and produces one row per
company in the eligible pool, carrying every raw ingredient the scorer needs.
No percentiles here -- scoring.py owns normalisation, this file owns counting.

Eligible posting (ALGORITHM.md 4.1):
    company_class in eligible_classes  AND  is_it_role  AND NOT is_training_role

Age policy + liveness (CONFIG["age"], CONFIG["liveness"]):
    Fresh-first. Every posting carries a signal_weight in [0, 1] that falls
    linearly with its posted age -- 1.0 the day it goes up, 0.0 at
    age.hard_cap_days, dropped past that, alive or not: the newest demand is
    what the radar surfaces. Liveness is a validity filter on top: a posting
    verified dead is damped by liveness.dead_weight (it was real demand, but
    it is no longer an open need) and never cited as evidence. Weight-zero
    postings are removed from the pool entirely, so downstream (match,
    market pull, evidence) never sees them.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import reference as ref
from .config import CONFIG


def role_family(title_fold: str) -> str:
    for fam, pattern in ref.ROLE_FAMILY_COMPILED:
        if pattern.search(title_fold):
            return fam
    return "dev"   # unreachable: the last pattern matches anything


def eligible_postings(postings: pd.DataFrame) -> pd.DataFrame:
    """The scorer's posting universe, with demand-atom fields attached."""
    mask = (
        postings["company_class"].isin(CONFIG["eligible_classes"])
        & postings["is_it_role"]
        & ~postings["is_training_role"]
    )
    elig = postings[mask].copy()

    folded = elig["title_clean"].fillna("").map(_fold)
    elig["role_family"] = folded.map(role_family)
    elig["seniority_rank"] = elig["seniority_derived"].map(ref.SENIORITY_RANK)
    return elig


def age_weight(age_days: pd.Series | np.ndarray | float) -> pd.Series | np.ndarray | float:
    """1.0 up to full_weight_days, linear to 0.0 at hard_cap_days, 0 beyond."""
    a = CONFIG["age"]
    full, cap = a["full_weight_days"], a["hard_cap_days"]
    return np.clip((cap - np.asarray(age_days, dtype=float)) / (cap - full), 0.0, 1.0)


def attach_liveness(elig: pd.DataFrame, liveness: pd.DataFrame | None) -> pd.DataFrame:
    """Adds alive / age_effective / signal_weight, drops weight-zero postings."""
    out = elig.copy()

    if liveness is not None and len(liveness):
        lv = liveness[["refnr", "alive", "checked_at"]].drop_duplicates("refnr")
        out = out.merge(lv, left_on="posting_id", right_on="refnr", how="left")
        out = out.drop(columns=["refnr"])
    else:
        out["alive"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
        out["checked_at"] = pd.NaT

    out["alive"] = out["alive"].astype("boolean")
    is_dead = (~out["alive"].astype("boolean")).fillna(False).to_numpy(dtype=bool)

    # ages are posted-date ages relative to the snapshot: the radar ranks
    # the newest demand, so the snapshot is treated as the present
    out["age_effective"] = out["posting_age_days"].astype(float)

    # fresh-first decay for everyone; delisted ads additionally damped
    w = age_weight(out["age_effective"])
    w = np.where(is_dead, w * CONFIG["liveness"]["dead_weight"], w)
    out["signal_weight"] = np.round(w, 4)

    return out[out["signal_weight"] > 0].copy()


def _fold(text: str) -> str:
    from . import text as txt
    return txt.fold(text)


def _hhi(categories: list[list[str]]) -> tuple[float, int]:
    """Herfindahl index over tech-category occurrences; N3's concentration core."""
    counts: Counter = Counter()
    covered = 0
    for cats in categories:
        cats = list(cats) if cats is not None else []
        if cats:
            covered += 1
            counts.update(cats)
    total = sum(counts.values())
    if not total:
        return 0.0, covered
    return sum((v / total) ** 2 for v in counts.values()), covered


def build(postings: pd.DataFrame, companies: pd.DataFrame,
          liveness: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (signals table over the eligible pool, eligible postings)."""
    elig = attach_liveness(eligible_postings(postings), liveness)

    n1c, n4c = CONFIG["n1"], CONFIG["n4"]
    comp_meta = companies.set_index("company_key")

    rows = []
    for key, grp in elig.groupby("company_key"):
        it_n = len(grp)
        if it_n < CONFIG["min_it_postings"]:
            continue

        age = grp["age_effective"]
        snap_age = grp["posting_age_days"]
        w = grp["signal_weight"]
        it_w = float(w.sum())

        live_n = int((grp["alive"] == True).sum())    # noqa: E712 (nullable bool)
        dead_n = int((grp["alive"] == False).sum())   # noqa: E712

        # Ratio/mix signals describe demand that still EXISTS: dead postings
        # get a residual in the volume signals (dead_weight), but a uniform
        # damping cancels out of any ratio, which let companies whose every
        # ad was already delisted keep perfect momentum. So shares and
        # concentration are computed over non-dead postings only.
        dead_mask = (grp["alive"].astype("boolean") == False).fillna(False)  # noqa: E712
        cur = grp[~dead_mask.to_numpy(dtype=bool)]
        w_cur = cur["signal_weight"]
        it_w_cur = float(w_cur.sum())

        senior_mask = grp["seniority_derived"].isin(["senior", "lead"])
        senior_w = float(w[senior_mask].sum())
        senior_cur_w = float(w_cur[cur["seniority_derived"].isin(["senior", "lead"])].sum())
        hhi, tech_covered = _hhi(list(cur["tech_categories"]))

        # N4 momentum: fresh share of the still-existing recent window.
        # Zero denominator -> raw 0 (nothing current = no momentum).
        window_w = float(w_cur[cur["posting_age_days"] <= n4c["window_days"]].sum())
        fresh_w = float(w_cur[cur["is_fresh_30d"].astype(bool)].sum())

        meta = comp_meta.loc[key]
        rows.append({
            "company_key": key,
            "company_name": meta["company_name"],
            "company_class": meta["company_class"],
            "it_n": it_n,
            "it_w": round(it_w, 2),
            "fresh_w": round(float(w[snap_age <= n1c["fresh_days"]].sum()), 2),
            "open_45": round(float(w[age > n1c["days_a"]].sum()), 2),
            "open_90": round(float(w[age > n1c["days_b"]].sum()), 2),
            "senior_n": int(senior_mask.sum()),
            "senior_w": round(senior_w, 2),
            "senior_share": senior_cur_w / it_w_cur if it_w_cur else 0.0,
            "hhi": hhi,
            "tech_covered_n": tech_covered,
            "fresh_n": int(grp["is_fresh_30d"].sum()),
            "window_n": int((snap_age <= n4c["window_days"]).sum()),
            "momentum_raw": (fresh_w / window_w) if window_w else 0.0,
            "median_age": float(age.median()),
            "region_count": int(grp["region_clean"].nunique()),
            "top_technologies": [t for t, _ in Counter(
                t for techs in grp["technologies"] for t in techs).most_common(6)],
            # liveness (checked = every pool posting after the backfill)
            "live_n": live_n,
            "dead_n": dead_n,
            "checked_n": live_n + dead_n,
            "live_rate": (live_n / (live_n + dead_n)) if (live_n + dead_n) else float("nan"),
            "has_live": bool(live_n > 0),
            # confidence ingredients
            "name_variant_count": int(meta["name_variant_count"]),
            "class_confidence": float(meta["class_confidence"]),
            "in_review": bool(meta["needs_review"]) or bool(meta["needs_review_t2"]),
            "corrob": float(meta["it_corroboration"]) if meta["it_corroboration"] == meta["it_corroboration"] else 0.0,
            "has_fresh_30d": bool(fresh_w > 0),
            # a verified-live ad is current by definition, whatever its age
            "has_recent_90d": bool((snap_age <= CONFIG["recency_guard_days"]).sum() > 0
                                   or live_n > 0),
        })

    signals = pd.DataFrame(rows)
    pool_keys = set(signals["company_key"])
    return signals, elig[elig["company_key"].isin(pool_keys)].copy()
