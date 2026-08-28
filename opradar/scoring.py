"""Pipeline A stage 2: signals -> ranked opportunities.

Everything here is arithmetic over the signals table:
    percentiles within the pool -> N1..N4 -> Need
    Confidence (reported beside the score, per ALGORITHM.md 4.5 -- the more
    specific instruction wins over the spine's shorthand: confidence is never
    folded into the ranking number)
    Opportunity = Need x Serviceability x DealSize

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

    # N1 -- fresh demand: mostly the age-weighted volume of the newest
    # postings, partly the age-weighted volume overall (fresh-first)
    s["n1"] = c1["mix_fresh"] * _pct(s["fresh_w"]) + c1["mix_volume"] * _pct(s["it_w"])

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
    if "has_live" in s.columns:
        # a verified-live ad is the freshest evidence there is
        recency[s["has_live"]] = c["recency_fresh"]

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
    """3-8 postings per company: the freshest first, plus the oldest still
    in range, with live URLs. This is what makes every score claim clickable.

    Confirmed-dead postings are excluded -- a 404 evidence link disproves the
    claim it was meant to support. Ages are effective ages (verified-alive
    postings age past the snapshot). Each entry carries live: true/false/null
    so the UI can badge verification state."""
    e = CONFIG["evidence"]

    if "alive" in grp.columns:
        dead = (grp["alive"].astype("boolean") == False).fillna(False)  # noqa: E712
        cand = grp[~dead]
        if cand.empty:                       # nothing verifiable left: show all
            cand = grp
    else:
        cand = grp
    age_col = "age_effective" if "age_effective" in cand.columns else "posting_age_days"

    freshest = cand.sort_values(age_col).head(e["freshest"])
    oldest = cand.sort_values(age_col, ascending=False).head(e["oldest"])
    seen, out = set(), []
    for r in pd.concat([freshest, oldest]).itertuples():
        if r.posting_id in seen:
            continue
        seen.add(r.posting_id)
        alive = getattr(r, "alive", None)
        posted = getattr(r, "posted_date", None)
        out.append({
            "title": r.title_clean,
            "url": r.source_url,
            "age": int(getattr(r, age_col)),
            "family": r.role_family,
            "live": None if pd.isna(alive) else bool(alive),
            "posted": str(posted.date()) if posted is not None and posted == posted else None,
        })
        if len(out) >= e["max_postings"]:
            break
    return json.dumps(out, ensure_ascii=False)


def _timeline(grp: pd.DataFrame) -> str:
    """Every eligible posting for one company, oldest first -- the series behind
    the open-roles timeline in the UI.

    The snapshot is a STOCK of ads that were still open on the crawl date, so
    each posting was demonstrably open from its posted date through to the
    snapshot: the cumulative count over time is a real open-roles curve. (A
    per-day posting histogram over the same data is not -- length bias makes
    posting-date trends meaningless, see the caveats section.)

    `gone` is the day we verified the ad had been taken down, expressed like
    every other age as days-before-snapshot, so a re-check run after the
    snapshot is negative. It is the only take-down date we actually observe:
    between the snapshot and that check we know nothing, and the UI draws that
    stretch as an explicit gap rather than pretending to a fill date.

    Unlike _evidence this keeps delisted postings -- in a timeline a role that
    went up and later came down is the point, not a broken citation."""
    g = grp.copy()
    g["gone_days"] = pd.NA
    if "checked_at" in g.columns and "snapshot_date" in g.columns and len(g):
        snap = g["snapshot_date"].iloc[0]
        chk = pd.to_datetime(g["checked_at"], utc=True, errors="coerce").dt.tz_localize(None)
        dead = (g["alive"].astype("boolean") == False).fillna(False)  # noqa: E712
        g["gone_days"] = (snap - chk).dt.days.where(dead)

    out = []
    for r in g.sort_values("posting_age_days", ascending=False).itertuples():
        alive = getattr(r, "alive", None)
        gone = getattr(r, "gone_days", None)
        posted = getattr(r, "posted_date", None)
        out.append({
            "title": r.title_clean,
            "url": r.source_url,
            "age": int(r.posting_age_days),
            "family": r.role_family,
            "live": None if pd.isna(alive) else bool(alive),
            "posted": str(posted.date()) if posted is not None and posted == posted else None,
            "gone": None if gone is None or pd.isna(gone) else int(gone),
        })
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
    s["deal_size"] = s["deal_size"].fillna(0.0)
    s["placeable_w"] = s["placeable_w"].fillna(0.0)
    # deal_size scales the score by how many people the contract could take:
    # covering one role perfectly is worth less than covering most of five
    s["opportunity"] = (s["need"] * s["serviceability"] * s["deal_size"]).round(1)

    # guardrail: excluded companies stay in the file, flagged with a reason --
    # transparency beats silent disappearance
    s["excluded"] = ~s["has_recent_90d"]
    s["exclusion_reason"] = s["excluded"].map(
        {True: f"no posting within {CONFIG['recency_guard_days']} days", False: None})

    evidence = eligible_pool.groupby("company_key").apply(_evidence, include_groups=False)
    s["evidence"] = s["company_key"].map(evidence)
    tl = eligible_pool.groupby("company_key").apply(_timeline, include_groups=False)
    s["timeline"] = s["company_key"].map(tl)

    s["config_hash"] = config_hash()

    ranked = s[~s["excluded"]].sort_values(
        ["opportunity", "confidence"], ascending=False).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    excluded = s[s["excluded"]].copy()
    excluded["rank"] = float("nan")   # keeps the column numeric after concat
    return pd.concat([ranked, excluded], ignore_index=True)
