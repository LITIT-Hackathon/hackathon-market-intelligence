"""Pipeline A stage 2: signals -> ranked opportunities.

Everything here is arithmetic over the signals table:
    percentiles within the pool -> N1..N4 -> Need
    Confidence (reported beside the score, per ALGORITHM.md 4.5 -- the more
    specific instruction wins over the spine's shorthand: confidence is never
    folded into the ranking number)
    Opportunity = Need x Serviceability

Every output row carries the config hash. Same hash + same parquet = same
leaderboard, or something is broken.
"""

from __future__ import annotations

import json

import pandas as pd

from .config import CONFIG, config_hash


def _pct(series: pd.Series) -> pd.Series:
    """Percentile rank within the pool, 0..1. Resists outliers by construction."""
    return series.rank(pct=True, method="average")


def need_components(signals: pd.DataFrame) -> pd.DataFrame:
    s = signals.copy()
    c1, c2, c3 = CONFIG["n1"], CONFIG["n2"], CONFIG["n3"]

    # N1 -- unmet demand
    s["n1"] = c1["mix_a"] * _pct(s["open_45"]) + c1["mix_b"] * _pct(s["open_90"])

    # N2 -- seniority pressure (count and share, both percentiled)
    s["n2"] = c2["mix_count"] * _pct(s["senior_n"]) + c2["mix_share"] * _pct(s["senior_share"])

    # N3 -- coherence. Damping BEFORE the percentile so every N shares a scale.
    damped = (
        s["hhi"]
        * (s["it_n"] / c3["volume_damp_at"]).clip(upper=1.0)
        * (s["tech_covered_n"] / c3["tech_damp_at"]).clip(upper=1.0)
    )
    s["n3"] = _pct(damped)

    # N4 -- momentum (raw already handles the zero-denominator case)
    s["n4"] = _pct(s["momentum_raw"])
    return s


def confidence(signals: pd.DataFrame) -> pd.DataFrame:
    s = signals.copy()
    c = CONFIG["confidence"]
    w = c["weights"]

    evidence = (s["it_n"] / c["evidence_saturation"]).clip(upper=1.0)

    recency = pd.Series(c["recency_old"], index=s.index)
    recency[s["has_recent_90d"]] = c["recency_90d"]
    recency[s["has_fresh_30d"]] = c["recency_fresh"]

    identity = pd.Series(c["identity_merged"], index=s.index)
    identity[s["name_variant_count"] == 1] = c["identity_clean"]
    identity[s["in_review"]] = c["identity_review"]

    s["confidence"] = (
        w["evidence"] * evidence
        + w["recency"] * recency
        + w["identity"] * identity
        + w["corrob"] * s["corrob"]
    ).round(4)
    s["confidence_band"] = pd.cut(
        s["confidence"],
        bins=[-1, c["band_medium"], c["band_high"], 2],
        labels=["low", "medium", "high"],
    ).astype(str)
    return s


def _evidence(grp: pd.DataFrame) -> str:
    """3-8 postings per company: the oldest unfilled plus the freshest, with
    live URLs. This is what makes every score claim clickable."""
    e = CONFIG["evidence"]
    oldest = grp.sort_values("posting_age_days", ascending=False).head(e["oldest"])
    freshest = grp.sort_values("posting_age_days").head(e["freshest"])
    seen, out = set(), []
    for r in pd.concat([oldest, freshest]).itertuples():
        if r.posting_id in seen:
            continue
        seen.add(r.posting_id)
        out.append({
            "title": r.title_clean,
            "url": r.source_url,
            "age": int(r.posting_age_days),
            "family": r.role_family,
        })
        if len(out) >= e["max_postings"]:
            break
    return json.dumps(out, ensure_ascii=False)


def score(signals: pd.DataFrame, serviceability: pd.DataFrame,
          eligible_pool: pd.DataFrame) -> pd.DataFrame:
    s = need_components(signals)
    s = confidence(s)

    w = CONFIG["need_weights"]
    total_w = sum(w.values())
    s["need"] = (
        (w["n1"] * s["n1"] + w["n2"] * s["n2"] + w["n3"] * s["n3"] + w["n4"] * s["n4"])
        / total_w * 100
    ).round(1)

    s = s.merge(serviceability, on="company_key", how="left")
    s["serviceability"] = s["serviceability"].fillna(0.0)
    s["opportunity"] = (s["need"] * s["serviceability"]).round(1)

    # guardrail: excluded companies stay in the file, flagged with a reason --
    # transparency beats silent disappearance
    s["excluded"] = ~s["has_recent_90d"]
    s["exclusion_reason"] = s["excluded"].map(
        {True: f"no posting within {CONFIG['recency_guard_days']} days", False: None})

    evidence = eligible_pool.groupby("company_key").apply(_evidence, include_groups=False)
    s["evidence"] = s["company_key"].map(evidence)

    s["config_hash"] = config_hash()

    ranked = s[~s["excluded"]].sort_values(
        ["opportunity", "confidence"], ascending=False).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    excluded = s[s["excluded"]].copy()
    excluded["rank"] = float("nan")   # keeps the column numeric after concat
    return pd.concat([ranked, excluded], ignore_index=True)
