"""Counting, and only counting: postings -> one row of raw numbers per company.

This module owns no judgement. It produces the observable quantities; the
signal definitions, the null models and the score live in `scoring.py`. The
split matters because "8 vacancies in 12 days, 5 of them Azure" is EVIDENCE and
must be quotable on its own, while "coherence = 0.71" is an INTERPRETATION that
should be re-derivable from the evidence at any time.

TWO OBSERVATIONS, NOT ONE
    The shipped snapshot was crawled on 2026-06-06. `opradar.balive` observes
    the same employers on the live board today. Nearly every worthwhile feature
    here comes from having both:

      * a posting still open months after the snapshot is unfilled demand, not
        an old advertisement -- the ambiguity that made the previous age policy
        flip between "old is good" and "fresh is good" simply disappears;
      * offers published in the last 28 days are genuine FLOW, comparable with
        the snapshot's own last-28-days flow, so hiring expansion becomes
        measurable instead of disclaimed.

    Where the live observation is missing the snapshot features still compute.
    Every live-derived column is prefixed `now_` and carries `live_verified`, so
    downstream code can tell measurement from assumption.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import reference as ref
from .config import CONFIG

# Role-family archetypes a delivery team needs. A burst of hiring that covers
# several of these looks like a team being stood up; a burst inside one of them
# looks like backfilling a single squad. Used by the programme signal.
TEAM_ARCHETYPES = {
    "lead": {"architect"},
    "build": {"dev", "data"},
    "run": {"ops", "security"},
    "assure": {"qa", "analyst", "support"},
}


def role_family(title_fold: str) -> str:
    for fam, pattern in ref.ROLE_FAMILY_COMPILED:
        if pattern.search(title_fold):
            return fam
    return "dev"   # unreachable: the last pattern matches anything


def _fold(text: str) -> str:
    from . import text as txt
    return txt.fold(text)


def eligible_postings(postings: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """Recent IT vacancies at companies we are willing to rank, with atom fields.

    Training roles are excluded because a company hiring apprentices is building
    capability in house -- the opposite of an outsourcing trigger. `seniority`
    cannot do that filtering: Ausbildung and Werkstudent ads split across the
    `entry` and `intern` bands, so ~4,000 apprenticeships survive a filter on
    `intern` alone. Hence `is_training_role` as its own column.
    """
    prospects = set(segments.loc[segments["is_prospect"], "company_key"])
    mask = (
        postings["company_key"].isin(prospects)
        & postings["is_it_role"]
        & ~postings["is_training_role"]
        # recency cap: see CONFIG["age"]. An advertisement older than this is
        # not demand anyone can sell into, whatever the crawl still lists.
        & (postings["posting_age_days"] <= CONFIG["age"]["hard_cap_days"])
    )
    elig = postings[mask].copy()
    folded = elig["title_clean"].fillna("").map(_fold)
    elig["role_family"] = folded.map(role_family)
    elig["seniority_rank"] = elig["seniority_derived"].map(ref.SENIORITY_RANK)
    elig["title_norm"] = folded.str.replace(r"[^a-z0-9 ]", " ", regex=True) \
                               .str.replace(r"\s+", " ", regex=True).str.strip()
    return elig


# ---------------------------------------------------------------------------
# per-company counting
# ---------------------------------------------------------------------------

def _burst(ages: np.ndarray, window_days: int) -> tuple[int, int]:
    """Largest number of postings inside any `window_days` window, and its span.

    Two pointers over sorted ages -- the postings are few, but this also keeps
    the definition unambiguous: it is the densest window that actually occurred,
    not a fixed calendar bucket that a programme can straddle and be missed by.
    """
    if len(ages) == 0:
        return 0, 0
    a = np.sort(ages)
    best, best_span, lo = 1, 0, 0
    for hi in range(len(a)):
        while a[hi] - a[lo] > window_days:
            lo += 1
        if hi - lo + 1 > best:
            best, best_span = hi - lo + 1, int(a[hi] - a[lo])
    return int(best), int(best_span)


def _team_shape(families: Counter) -> float:
    """Share of delivery archetypes present. 1.0 = lead + build + run + assure."""
    present = sum(1 for members in TEAM_ARCHETYPES.values()
                  if any(families.get(f, 0) for f in members))
    return present / len(TEAM_ARCHETYPES)


def build(postings: pd.DataFrame, companies: pd.DataFrame,
          segments: pd.DataFrame, ba: pd.DataFrame | None = None
          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (feature table over the prospect pool, its eligible postings)."""
    cfg = CONFIG["features"]
    elig = eligible_postings(postings, segments)

    comp_meta = companies.set_index("company_key")
    seg_meta = segments.set_index("company_key")

    rows = []
    for key, grp in elig.groupby("company_key"):
        n = len(grp)
        if n < CONFIG["min_it_postings"]:
            continue

        ages = grp["posting_age_days"].to_numpy(dtype=float)
        burst_n, burst_span = _burst(ages, cfg["burst_window_days"])

        families = Counter(grp["role_family"])
        tech_counter: Counter = Counter()
        tech_covered = 0
        for cats in grp["tech_categories"]:
            cats = list(cats) if cats is not None else []
            if cats:
                tech_covered += 1
                tech_counter.update(cats)

        # seniority is only OBSERVED on part of the pool, so the denominator is
        # the postings where it is known -- not all postings. Treating unknown
        # as "not senior" would make thin-evidence companies look junior-heavy.
        known_sen = grp["seniority_derived"].ne("unknown")
        senior_k = int(grp.loc[known_sen, "seniority_derived"].isin(["senior", "lead"]).sum())

        titles = grp["title_norm"]
        meta = comp_meta.loc[key]
        seg = seg_meta.loc[key]

        rows.append({
            "company_key": key,
            "company_name": meta["company_name"],
            "segment": seg["segment"],
            "segment_source": seg["segment_source"],
            "segment_verified": bool(seg["segment_verified"]),
            "segment_reason": seg["segment_reason"],

            # --- volume and age, from the snapshot ---
            "it_n": n,
            "it_n_all": int(meta["it_postings"]),
            "median_age": float(np.median(ages)),
            "p90_age": float(np.quantile(ages, 0.9)),
            "snap_flow_28": int((ages <= cfg["flow_window_days"]).sum()),
            "snap_flow_90": int((ages <= 90).sum()),
            "snap_aged_45": int((ages > 45).sum()),
            "snap_aged_90": int((ages > 90).sum()),

            # --- clustering ---
            "burst_n": burst_n,
            "burst_span_days": burst_span,
            "role_family_n": len(families),
            "team_shape": round(_team_shape(families), 4),
            "families": dict(families),

            # --- stack ---
            "tech_counts": dict(tech_counter),
            "tech_covered_n": tech_covered,
            "tech_total": int(sum(tech_counter.values())),

            # --- seniority (counts, not shares: shares are computed with a
            #     prior in scoring.py, where the pool rate is known) ---
            "senior_k": senior_k,
            "senior_n_known": int(known_sen.sum()),

            # --- duplicate seats: the same role advertised more than once is
            #     either a repost or two seats. Both mean unmet capacity. ---
            "dup_seats": int(n - titles.nunique()),

            "region_count": int(grp["region_clean"].nunique()),
            "top_technologies": [t for t, _ in tech_counter.most_common(6)],

            # --- identity, for confidence ---
            "name_variant_count": int(meta["name_variant_count"]),
            "it_corroboration": float(meta["it_corroboration"])
                                if meta["it_corroboration"] == meta["it_corroboration"] else 0.0,
        })

    feats = pd.DataFrame(rows)
    if feats.empty:
        return feats, elig.iloc[0:0]

    feats = _attach_live(feats, ba)
    pool = set(feats["company_key"])
    return feats, elig[elig["company_key"].isin(pool)].copy()


def _attach_live(feats: pd.DataFrame, ba: pd.DataFrame | None) -> pd.DataFrame:
    """Join today's board observation. Absent, the `now_*` columns stay null.

    Null is deliberate and is NOT filled with zero anywhere: zero live offers is
    a measurement ("they have nothing open"), null is the absence of one ("we
    could not look"). Collapsing the two is how a scorer starts punishing
    companies for our data gaps.
    """
    mapping = (("ba_it_stock", "now_it_stock"), ("ba_it_flow_28", "now_it_flow_28"),
               ("ba_flow_7", "now_flow_7"), ("ba_stock", "now_stock"))
    if ba is None or not len(ba):
        for _, dst in mapping:
            feats[dst] = pd.NA
        feats["now_aged_open"] = pd.NA
        feats["live_verified"] = False
        return feats

    cols = ["company_key", "ba_matched", "ba_checked_at"] + [s for s, _ in mapping]
    sub = ba[[c for c in cols if c in ba.columns]].copy()
    out = feats.merge(sub, on="company_key", how="left")
    matched = out["ba_matched"].fillna(False).astype(bool)

    out["live_verified"] = matched
    for src, dst in mapping:
        out[dst] = out[src].where(matched) if src in out.columns else pd.NA

    # IT roles live today that were NOT published in the last 28 days: open for
    # at least a month, on an authority that is not our own snapshot. This is
    # the cleanest unmet-demand quantity in the whole system.
    out["now_aged_open"] = (out["now_it_stock"] - out["now_it_flow_28"]).clip(lower=0)
    return out.drop(columns=[c for c in ("ba_matched",) + tuple(s for s, _ in mapping)
                             if c in out.columns])
