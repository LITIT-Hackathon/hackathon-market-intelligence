"""Pipeline A stage 1: postings -> per-company IT-restricted aggregates.

Reads postings.parquet (the interface contract) and produces one row per
company in the eligible pool, carrying every raw ingredient the scorer needs.
No percentiles here -- scoring.py owns normalisation, this file owns counting.

Eligible posting (ALGORITHM.md 4.1):
    company_class in eligible_classes  AND  is_it_role  AND NOT is_training_role
"""

from __future__ import annotations

from collections import Counter

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


def build(postings: pd.DataFrame, companies: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (signals table over the eligible pool, eligible postings)."""
    elig = eligible_postings(postings)

    n1c, n4c = CONFIG["n1"], CONFIG["n4"]
    comp_meta = companies.set_index("company_key")

    rows = []
    for key, grp in elig.groupby("company_key"):
        it_n = len(grp)
        if it_n < CONFIG["min_it_postings"]:
            continue

        age = grp["posting_age_days"]
        senior_n = int(grp["seniority_derived"].isin(["senior", "lead"]).sum())
        hhi, tech_covered = _hhi(list(grp["tech_categories"]))

        # N4 momentum: fresh share of the recent window. Zero-denominator ->
        # raw 0 (a company whose every posting is >180d old has no momentum).
        window_n = int((age <= n4c["window_days"]).sum())
        fresh_n = int(grp["is_fresh_30d"].sum())

        meta = comp_meta.loc[key]
        rows.append({
            "company_key": key,
            "company_name": meta["company_name"],
            "company_class": meta["company_class"],
            "it_n": it_n,
            "open_45": int((age > n1c["days_a"]).sum()),
            "open_90": int((age > n1c["days_b"]).sum()),
            "senior_n": senior_n,
            "senior_share": senior_n / it_n,
            "hhi": hhi,
            "tech_covered_n": tech_covered,
            "fresh_n": fresh_n,
            "window_n": window_n,
            "momentum_raw": (fresh_n / window_n) if window_n else 0.0,
            "median_age": float(age.median()),
            "region_count": int(grp["region_clean"].nunique()),
            "top_technologies": [t for t, _ in Counter(
                t for techs in grp["technologies"] for t in techs).most_common(6)],
            # confidence ingredients
            "name_variant_count": int(meta["name_variant_count"]),
            "class_confidence": float(meta["class_confidence"]),
            "in_review": bool(meta["needs_review"]) or bool(meta["needs_review_t2"]),
            "corrob": float(meta["it_corroboration"]) if meta["it_corroboration"] == meta["it_corroboration"] else 0.0,
            "has_fresh_30d": bool(fresh_n > 0),
            "has_recent_90d": bool((age <= CONFIG["recency_guard_days"]).sum() > 0),
        })

    signals = pd.DataFrame(rows)
    pool_keys = set(signals["company_key"])
    return signals, elig[elig["company_key"].isin(pool_keys)].copy()
