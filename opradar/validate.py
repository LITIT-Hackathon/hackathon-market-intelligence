"""Validation without ground truth.

There are no labels saying "this company became a customer", so accuracy,
precision and recall are unavailable and claiming them would be dishonest. What
IS available is a set of properties the ranking must have if it is doing the
job, and each of these is a number that can be put on a slide and argued with.

    V1  divergence     it must not be a vacancy-count ranking in disguise
    V2  adversarial    no competitor, agency or unverified row near the top
    V3  sensitivity    the top 20 must survive +-20% on every weight
    V4  stability      the top 20 must survive deleting one vacancy per company
    V5  small-sample   thin-evidence rows must not dominate the head
    V6  traceability   every ranked row must carry clickable evidence
    V7  people         value must not be a skill count, and must reward
                       covering demand nobody else on the bench covers

V3 and V4 are the two that matter most and they test different things. V3 asks
whether the WEIGHTS are doing work the signals should be doing. V4 asks whether
the DATA is thin enough that one advertisement decides the leaderboard -- which,
on a pool whose median company has four vacancies, is the likelier failure.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import eligibility as el
from .config import CONFIG


def _spearman(a: pd.Series, b: pd.Series) -> float:
    a, b = pd.Series(a).astype(float), pd.Series(b).astype(float)
    ok = a.notna() & b.notna()
    if ok.sum() < 3:
        return float("nan")
    return round(float(a[ok].rank().corr(b[ok].rank())), 3)


# ---------------------------------------------------------------------------

def v1_divergence(ranked: pd.DataFrame) -> dict:
    rho = _spearman(ranked["opportunity"], ranked["it_n"])
    return {
        "spearman_vs_it_postings": rho,
        "verdict": "ok" if rho < 0.55 else "TOO CLOSE TO A VOLUME RANKING",
        "note": ("correlation cannot be zero -- unfilled demand is counted, and "
                 "counts grow with volume. The claim is divergence, not "
                 "independence: the top 20 must not be the volume top 20."),
        "top20_overlap_with_volume_top20": int(len(
            set(ranked.nlargest(20, "opportunity")["company_key"])
            & set(ranked.nlargest(20, "it_n")["company_key"]))),
    }


def v2_adversarial(ranked: pd.DataFrame, k: int = 20) -> dict:
    head = ranked.head(k)
    forbidden = head[head["segment"].isin(el.CHANNEL_SEGMENTS + el.NOISE_SEGMENTS)]
    unverified = head[~head["segment_verified"]]
    return {
        "top_k": k,
        "channel_or_noise_rows": forbidden[["company_name", "segment"]].to_dict("records"),
        "unverified_segment_rows": unverified["company_name"].tolist(),
        "defects": int(len(forbidden)),
        "verdict": "clean" if len(forbidden) == 0 else "CONTAMINATED",
        "note": ("unverified rows are not defects -- they are companies no "
                 "outside authority could confirm, and they are listed so a "
                 "human can check them before the list is worked."),
    }


def v3_sensitivity(feats: pd.DataFrame, svc: pd.DataFrame, pool: pd.DataFrame,
                   ranked: pd.DataFrame) -> dict:
    """Re-score under perturbed weights; report the worst top-K overlap."""
    from . import scoring

    cfg = CONFIG["validation"]
    k, base_w = cfg["top_k"], dict(CONFIG["signal_weights"])
    base = set(ranked.head(k)["company_key"])
    rng = np.random.default_rng(20260829)

    overlaps = []
    try:
        for _ in range(cfg["perturbation_samples"]):
            factors = 1 + rng.uniform(-cfg["perturbation"], cfg["perturbation"], len(base_w))
            CONFIG["signal_weights"] = {
                name: base_w[name] * f for name, f in zip(base_w, factors)}
            alt = scoring.score(feats, svc, pool)
            overlaps.append(len(base & set(alt.head(k)["company_key"])))
    finally:
        CONFIG["signal_weights"] = base_w

    return {
        "top_k": k, "min_overlap": int(min(overlaps)),
        "mean_overlap": round(float(np.mean(overlaps)), 1),
        "samples": len(overlaps),
        "verdict": "stable" if min(overlaps) >= 0.8 * k else "WEIGHT-SENSITIVE",
    }


def v4_jackknife(postings: pd.DataFrame, companies: pd.DataFrame,
                 segments: pd.DataFrame, ba, bench, ranked: pd.DataFrame,
                 k: int = 20, rounds: int = 3) -> dict:
    """Delete one vacancy per company and see whether the head survives.

    The sharpest honest test available on this data. The median ranked company
    has four IT vacancies, so if the ordering is really being decided by single
    advertisements this is where it shows -- and no amount of weight tuning can
    hide it.
    """
    from . import features, match, scoring

    base = set(ranked.head(k)["company_key"])
    overlaps, survivor_overlaps, dropouts = [], [], []
    for seed in range(rounds):
        rng = np.random.default_rng(1000 + seed)
        drop = (postings[postings["is_it_role"] & ~postings["is_training_role"]]
                .groupby("company_key")["posting_id"]
                .apply(lambda s: s.iloc[rng.integers(0, len(s))]))
        reduced = postings[~postings["posting_id"].isin(set(drop))]
        feats, pool = features.build(reduced, companies, segments, ba)
        if feats.empty:
            continue
        svc = match.serviceability(pool, bench)
        alt = scoring.score(feats, svc, pool)
        alt_keys = set(alt["company_key"])

        overlaps.append(len(base & set(alt.head(k)["company_key"])))
        # Separate two failure modes: a head row REORDERED (real instability)
        # vs a head row that fell below min_it_postings and left the pool
        # (threshold churn -- a known property of any count threshold, and a
        # company at exactly the minimum always loses a third of its evidence
        # here). Only the first says the SCORE is fragile.
        survivors = [c for c in ranked.head(k)["company_key"] if c in alt_keys]
        dropouts.append(k - len(survivors))
        if survivors:
            survivor_overlaps.append(
                len(set(survivors) & set(alt.head(k)["company_key"])) / len(survivors))

    if not overlaps:
        return {"top_k": k, "verdict": "not run"}
    surv = round(float(np.mean(survivor_overlaps)), 3) if survivor_overlaps else float("nan")
    return {
        "top_k": k, "rounds": len(overlaps),
        "min_overlap": int(min(overlaps)),
        "mean_overlap": round(float(np.mean(overlaps)), 1),
        "mean_pool_dropouts_from_head": round(float(np.mean(dropouts)), 1),
        "survivor_retention": surv,
        "verdict": "stable" if surv >= 0.7 else "ONE-VACANCY SENSITIVE",
        "note": ("one randomly chosen IT vacancy removed from every company; "
                 "survivor_retention scores only companies still above the "
                 "pool threshold, dropouts count threshold churn separately"),
    }


def v5_small_sample(ranked: pd.DataFrame, k: int = 20) -> dict:
    head, pool = ranked.head(k), ranked
    return {
        "top_k": k,
        "median_it_n_top": float(head["it_n"].median()),
        "median_it_n_pool": float(pool["it_n"].median()),
        "min_evidence_rows_in_top": int(head["it_n"].min()),
        "share_of_top_at_pool_minimum": round(
            float((head["it_n"] <= CONFIG["min_it_postings"]).mean()), 3),
        "verdict": "ok" if head["it_n"].median() >= pool["it_n"].median()
                   else "THIN-EVIDENCE ROWS DOMINATE THE HEAD",
        "note": ("the head should rest on MORE evidence than the pool average, "
                 "not less. A head made of three-posting companies is a "
                 "small-sample artefact whatever the signals say."),
    }


def v6_traceability(ranked: pd.DataFrame) -> dict:
    def n_ev(raw) -> int:
        try:
            return len(json.loads(raw)) if isinstance(raw, str) else 0
        except json.JSONDecodeError:
            return 0

    counts = ranked["evidence"].map(n_ev)
    urls = ranked["evidence"].map(
        lambda r: all(e.get("url") for e in json.loads(r)) if isinstance(r, str) else False)
    return {
        "rows_without_evidence": int((counts == 0).sum()),
        "rows_with_a_missing_url": int((~urls).sum()),
        "median_evidence_postings": float(counts.median()),
        "verdict": "clean" if (counts == 0).sum() == 0 else "UNTRACEABLE ROWS",
    }


def v7_people(value: pd.DataFrame, cells: pd.DataFrame) -> dict:
    rho_breadth = _spearman(value["value_raw"], value["tech_tags"].map(len))
    rho_unique = _spearman(value["value_raw"], value["uniqueness"])
    return {
        "value_vs_skill_count_spearman": rho_breadth,
        "value_vs_uniqueness_spearman": rho_unique,
        "verdict": "ok" if (rho_breadth < 0.6 and rho_unique > 0) else "LOOKS LIKE A SKILL COUNT",
        "note": ("'most skills wins' is the people-side equivalent of ranking "
                 "companies by vacancy count. Value should track UNIQUENESS of "
                 "coverage, not breadth of CV."),
        "cells": int(len(cells)),
        "cells_with_no_bench_coverage": int((cells["mean_coverage"] == 0).sum())
                                        if len(cells) else 0,
        "all_bench_labelled_synthetic": bool(len(value) and (value["source"] == "synthetic").all()),
        "label_precision_claims": "none, by design -- no ground-truth placements exist",
    }


def run_all(ranked: pd.DataFrame, feats: pd.DataFrame, svc: pd.DataFrame,
            pool: pd.DataFrame, value: pd.DataFrame, cells: pd.DataFrame,
            postings=None, companies=None, segments=None, ba=None,
            bench=None) -> dict:
    checks = {
        "companies": {
            "v1_divergence": v1_divergence(ranked),
            "v2_adversarial": v2_adversarial(ranked),
            "v3_sensitivity": v3_sensitivity(feats, svc, pool, ranked),
            "v5_small_sample": v5_small_sample(ranked),
            "v6_traceability": v6_traceability(ranked),
        },
        "people": v7_people(value, cells),
    }
    if postings is not None and bench is not None:
        checks["companies"]["v4_jackknife"] = v4_jackknife(
            postings, companies, segments, ba, bench, ranked)
    return checks
