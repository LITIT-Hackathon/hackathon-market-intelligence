"""Algorithm A: company features -> named signals -> one ranked opportunity.

    Opportunity = weighted geometric mean of
                  Unmet x Expansion x Programme x Seniority x Serviceability

WHY A GEOMETRIC MEAN AND NOT A WEIGHTED SUM
    The business logic is conjunctive, not additive. A company with no unmet
    demand is not an opportunity however coherent its hiring looks, and one we
    cannot staff is not an opportunity however loudly it is hiring. A sum lets a
    single large term carry a row that fails on everything else; a product
    requires every dimension to be non-trivial. In log space the product is
    additive again, so each signal's contribution to the final score is exactly
    `w_i * log(S_i)` and can be printed next to the number.

    The previous build used a weighted sum of percentiles and its own
    sensitivity check reported the top 20 reshuffling under +-20% weight
    perturbation. Multiplicative structure is part of the fix; shrinking thin
    evidence toward the pool prior (below) is the rest.

THE THREE STATISTICAL PROBLEMS THIS FILE EXISTS TO SOLVE
    1. TINY SAMPLES.  The median company in the pool has four IT vacancies. A
       raw share computed on four observations is noise, and percentile-ranking
       noise sorts noise to the top: in the previous build 90 of 260 ranked
       companies had exactly three postings, `momentum` was pinned at 1.0 for
       43% of the pool, and `senior_share` was exactly 0 for 44%. Every rate
       here is therefore an empirical-Bayes posterior against a Beta prior
       fitted to the pool, so a 1-of-2 does not outrank a 30-of-70.

    2. CONCENTRATION IS BIASED UPWARD AT LOW N.  A Herfindahl index over one
       technology is 1.0 by construction, which is why the previous N3 needed
       two hand-set damping constants. Replaced by a null model with a
       closed-form expectation: for n draws from the pool's own technology
       distribution, E[HHI] = 1/n + HHI_pool*(1 - 1/n). We score the EXCESS over
       that, which is scale-free and needs no tuning constant.

    3. MISSING EVIDENCE IS NOT BAD NEWS.  Each signal carries an evidence
       weight -- the share of the input we actually observed. The scored value
       is shrunk toward the pool prior in proportion to what is missing, so a
       company we know little about lands mid-pack rather than at either end,
       and the uncertainty is reported through Confidence instead of being
       silently priced into the rank.

WHAT THE NUMBER MEANS
    `opportunity` is a percentile within the eligible pool: 87 means "ahead of
    87% of the German companies in this pool". That is the only claim the data
    supports -- there are no labels, so no absolute calibration is available and
    a 0-100 absolute score would be false precision. `pressure` carries the raw
    geometric mean for cross-run comparison.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import CONFIG, config_hash

SIGNALS = ["unmet", "expansion", "programme", "seniority", "serviceability"]


# ---------------------------------------------------------------------------
# statistical primitives -- each one testable on its own
# ---------------------------------------------------------------------------

def fit_beta_prior(k: pd.Series, n: pd.Series) -> tuple[float, float]:
    """Method-of-moments Beta prior over a pool of (successes, trials).

    Only rows with enough trials to carry information about the SPREAD are used
    to fit; otherwise the prior is dominated by the same noisy small samples it
    exists to damp. Falls back to a weak, mean-matched prior when the pool is
    too small or degenerate.
    """
    mask = (n >= CONFIG["stats"]["prior_min_trials"]) & (n > 0)
    if mask.sum() < CONFIG["stats"]["prior_min_rows"]:
        mask = n > 0
    if mask.sum() == 0:
        return 1.0, 1.0

    p = (k[mask] / n[mask]).astype(float)
    m, v = float(p.mean()), float(p.var(ddof=1)) if mask.sum() > 1 else 0.0
    m = min(max(m, 1e-4), 1 - 1e-4)
    # var of a Beta is m(1-m)/(a+b+1); invert for the concentration
    if v <= 0 or v >= m * (1 - m):
        strength = float(CONFIG["stats"]["prior_fallback_strength"])
    else:
        strength = m * (1 - m) / v - 1.0
        strength = float(np.clip(strength, 1.0, CONFIG["stats"]["prior_max_strength"]))
    return m * strength, (1 - m) * strength


def eb_rate(k: pd.Series, n: pd.Series, alpha: float, beta: float) -> pd.Series:
    """Posterior mean of a rate under a Beta(alpha, beta) prior.

    (k + alpha) / (n + alpha + beta). With n large the prior washes out; with
    n small the estimate sits near the pool average, which is the honest answer
    when three observations are all you have.
    """
    return ((k.astype(float) + alpha) / (n.astype(float) + alpha + beta)).clip(0, 1)


def saturate(x, half: float):
    """x / (x + half): 0 at zero, 0.5 at `half`, asymptotically 1.

    Used wherever magnitude should matter with diminishing returns. Stating the
    half-point is the whole justification -- "five unfilled roles is half of the
    magnitude signal" is a claim a reader can argue with, unlike a raw weight.
    """
    v = np.asarray(x, dtype=float)
    return np.where(np.isnan(v), np.nan, v / (v + float(half)))


def excess_concentration(counts: dict, pool_hhi: float) -> float:
    """How much more concentrated a company's stack is than chance would give.

    Under n independent draws from the pool's category distribution,
        E[HHI] = 1/n + HHI_pool * (1 - 1/n)
    exactly. Scoring (HHI_obs - E) / (1 - E) removes the small-sample inflation
    that made a single-technology company look maximally focused, and needs no
    damping constant.
    """
    n = int(sum(counts.values()))
    if n <= 1:
        return 0.0
    hhi = sum((v / n) ** 2 for v in counts.values())
    expected = 1.0 / n + pool_hhi * (1.0 - 1.0 / n)
    if expected >= 1.0:
        return 0.0
    return float(np.clip((hhi - expected) / (1.0 - expected), 0.0, 1.0))


def _pct(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average")


# ---------------------------------------------------------------------------
# the signals
# ---------------------------------------------------------------------------

def signals(feats: pd.DataFrame) -> pd.DataFrame:
    """Attach S1..S4, their evidence weights, and the evidence behind them."""
    f = feats.copy()
    cfg = CONFIG["signals"]

    # ---- pool-level quantities the null models need ----
    pool_tech: dict[str, int] = {}
    for counts in f["tech_counts"]:
        for cat, v in (counts or {}).items():
            pool_tech[cat] = pool_tech.get(cat, 0) + v
    total_tech = sum(pool_tech.values()) or 1
    pool_hhi = sum((v / total_tech) ** 2 for v in pool_tech.values())
    f.attrs["pool_hhi"] = pool_hhi

    # =====================================================================
    # S1 -- UNMET DEMAND
    #   The definitional core. A vacancy still advertised today that was not
    #   published in the last 28 days has been open at least a month on the
    #   board's own evidence, not on our inference about a stale crawl.
    #   Rate says "they cannot fill things"; magnitude says "there is enough of
    #   it to be worth a conversation". Both are needed: a single stubborn
    #   vacancy at a company with one vacancy is a 100% failure rate and not an
    #   opportunity.
    #   Where the live board could not be consulted, the snapshot proxy is
    #   postings already older than 45 days at crawl time -- weaker, because an
    #   old advertisement may simply have been abandoned, and the evidence
    #   weight says so.
    # =====================================================================
    live = f["live_verified"].fillna(False).astype(bool)
    aged = pd.to_numeric(f["now_aged_open"], errors="coerce")
    stock = pd.to_numeric(f["now_it_stock"], errors="coerce")

    proxy_aged = f["snap_aged_45"].astype(float)
    proxy_stock = f["it_n"].astype(float)
    k_unmet = aged.where(live, proxy_aged)
    n_unmet = stock.where(live, proxy_stock)

    a1, b1 = fit_beta_prior(k_unmet.fillna(0), n_unmet.fillna(0))
    f["unmet_rate"] = eb_rate(k_unmet.fillna(0), n_unmet.fillna(0), a1, b1).round(4)
    f["unmet_count"] = k_unmet.fillna(0)
    f["unmet"] = (f["unmet_rate"] * saturate(f["unmet_count"], cfg["unmet_half"])).round(4)
    f["unmet_e"] = np.where(live, 1.0, cfg["unmet_proxy_evidence"])

    # =====================================================================
    # S2 -- EXPANSION AGAINST THE COMPANY'S OWN BASELINE
    #   Two 28-day flow windows, each measured at its own snapshot instant, so
    #   both are censored the same way and the comparison is like for like.
    #   This is the answer to "Company A posts 100/month and now posts 110;
    #   Company B posts 2 and now posts 12" -- the ratio, not the level.
    #   Divided through by the pool median ratio, because both windows also
    #   share a season and a crawl: without that standardisation a market-wide
    #   August slowdown reads as every company contracting.
    #   Only two observations exist, so this is a direction, not a trend, and it
    #   is deliberately the lowest-weighted of the demand signals.
    # =====================================================================
    k = cfg["expansion_smoothing"]
    now_flow = pd.to_numeric(f["now_it_flow_28"], errors="coerce")
    then_flow = f["snap_flow_28"].astype(float)
    ratio = (now_flow + k) / (then_flow + k)
    med = float(ratio[live].median()) if live.any() else 1.0
    f["expansion_ratio"] = (ratio / (med if med > 0 else 1.0)).round(4)
    # log-ratio, squashed: symmetric around parity, saturating at the extremes
    f["expansion"] = (1.0 / (1.0 + np.exp(-np.log(f["expansion_ratio"].clip(lower=1e-6))
                                          / cfg["expansion_scale"]))).round(4)
    f.loc[~live, "expansion"] = np.nan
    f["expansion_e"] = np.where(live, 1.0, 0.0)
    f["pool_expansion_median"] = round(med, 4)

    # =====================================================================
    # S3 -- PROGRAMME SIGNATURE  (the interaction that is the whole point)
    #   Eight vacancies alone mean nothing. Eight vacancies inside twelve days,
    #   concentrated on one stack, spanning architect + build + run, at a
    #   company that normally opens one a month, is a programme being stood up.
    #   Deliberately MULTIPLICATIVE across three independent observations, so
    #   none of them can carry it alone:
    #       burst   -- how much of their demand landed in one short window
    #       excess  -- how much more concentrated the stack is than chance
    #       shape   -- how many delivery archetypes the burst spans
    #   A recruitment agency posting 22 SAP roles in a zero-day span scores high
    #   on burst and concentration; it is removed by the eligibility gate, not
    #   by this signal, which is the correct division of labour.
    # =====================================================================
    burst_share = (f["burst_n"] / f["it_n"].clip(lower=1)).clip(0, 1)
    burst_mag = saturate(f["burst_n"] - (cfg["burst_min_roles"] - 1), cfg["burst_half"])
    f["burst_strength"] = (burst_share * np.clip(burst_mag, 0, 1)).round(4)
    f["excess_concentration"] = [round(excess_concentration(c or {}, pool_hhi), 4)
                                 for c in f["tech_counts"]]
    f["programme"] = (f["burst_strength"]
                      * f["excess_concentration"].clip(lower=cfg["programme_conc_floor"])
                      * f["team_shape"].clip(lower=cfg["programme_shape_floor"])).round(4)
    # evidence: a stack claim needs postings that actually name a technology
    f["programme_e"] = np.clip(f["tech_covered_n"] / cfg["programme_tech_evidence"], 0, 1)

    # =====================================================================
    # S4 -- SENIORITY PRESSURE
    #   Senior and lead roles are the hardest to hire and the strongest trigger
    #   for buying external capacity. The denominator is postings where
    #   seniority is KNOWN, not all postings: treating unknown as "not senior"
    #   would mark every thin-evidence company junior-heavy. Coverage is 23% of
    #   the pool, so the evidence weight is usually well below 1 and the signal
    #   spends most of its time shrunk toward the pool average -- which is the
    #   honest outcome for a field that is mostly missing.
    # =====================================================================
    a4, b4 = fit_beta_prior(f["senior_k"], f["senior_n_known"])
    f["senior_rate"] = eb_rate(f["senior_k"], f["senior_n_known"], a4, b4).round(4)
    f["seniority"] = (f["senior_rate"]
                      * saturate(f["senior_k"], cfg["senior_half"])).round(4)
    f["seniority_e"] = np.clip(f["senior_n_known"] / cfg["senior_evidence"], 0, 1)

    f["prior_alpha_unmet"], f["prior_beta_unmet"] = round(a1, 3), round(b1, 3)
    f["prior_alpha_senior"], f["prior_beta_senior"] = round(a4, 3), round(b4, 3)
    return f


# ---------------------------------------------------------------------------
# confidence -- orthogonal to the score, never folded into it
# ---------------------------------------------------------------------------

def confidence(scored: pd.DataFrame) -> pd.DataFrame:
    """How much to trust the row, on four independent grounds.

    Reported beside the score and never multiplied into it. "86, low confidence"
    and "86, high confidence" are different sales instructions -- the first says
    go and check, the second says go and call -- and a shrunk single number
    destroys that distinction while looking more precise.
    """
    s = scored.copy()
    c = CONFIG["confidence"]

    # 1. how much evidence exists at all. Snapshot ads and live IT stock are
    #    both observations of distinct vacancies; a company with 3 snapshot ads
    #    but 85 verified-live IT openings is rich in evidence, not poor, and
    #    the max of the two is a lower bound on what was actually observed.
    live_stock = pd.to_numeric(s.get("now_it_stock"), errors="coerce").fillna(0)
    volume = pd.Series(saturate(np.maximum(s["it_n"], live_stock), c["volume_half"]),
                       index=s.index)

    # 2. was it checked against an authority outside this dataset
    verified = np.where(s["segment_verified"] & s["live_verified"], 1.0,
               np.where(s["segment_verified"] | s["live_verified"], c["verify_partial"],
                        c["verify_none"]))

    # 3. how much of the score rests on observed rather than imputed input
    ev_cols = [f"{k}_e" for k in ("unmet", "expansion", "programme", "seniority")]
    observability = s[ev_cols].astype(float).mean(axis=1)

    # 4. do the signals agree? Four signals pointing the same way is a stronger
    #    case than one spike and three blanks, and disagreement is exactly what
    #    a human should be asked to adjudicate.
    eff = s[[f"{k}_eff" for k in ("unmet", "expansion", "programme", "seniority")]].astype(float)
    spread = eff.std(axis=1, ddof=0) / eff.mean(axis=1).replace(0, np.nan)
    agreement = (1.0 - spread.clip(0, 1)).fillna(0.5)

    w = c["weights"]
    s["confidence"] = (w["volume"] * volume + w["verified"] * verified
                       + w["observability"] * observability
                       + w["agreement"] * agreement).round(4)
    s["confidence_band"] = pd.cut(
        s["confidence"], bins=[-1, c["band_medium"], c["band_high"], 2],
        labels=["low", "medium", "high"]).astype(str)
    s["conf_volume"] = volume.round(3)
    s["conf_verified"] = np.round(verified, 3)
    s["conf_observability"] = observability.round(3)
    s["conf_agreement"] = agreement.round(3)
    return s


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------

def _evidence(grp: pd.DataFrame, max_n: int) -> str:
    """The postings behind the score, freshest first.

    Freshest first because the reader is deciding whether to call today, and
    the newest advertisement is both the most likely to still be open and the
    most natural thing to open a call with. The pool is already capped at
    CONFIG["age"]["hard_cap_days"], so nothing here is stale in absolute terms
    and the ordering is choosing between recent exhibits, not hiding old ones.
    Every entry keeps its live source URL so any number on screen is one click
    from the advertisement that produced it.
    """
    cand = grp.sort_values("posting_age_days", ascending=True)
    out = []
    for r in cand.head(max_n).itertuples():
        out.append({
            "title": r.title_clean,
            "url": r.source_url,
            "age_days": int(r.posting_age_days),
            "family": r.role_family,
            "seniority": r.seniority_derived,
            "tech": list(r.tech_categories) if r.tech_categories is not None else [],
        })
    return json.dumps(out, ensure_ascii=False)


def _timeline(grp: pd.DataFrame) -> str:
    """Every eligible vacancy for one company, oldest first -- the series behind
    the open-roles timeline in the UI.

    The snapshot is a STOCK of ads that were still open on the crawl date, so
    each vacancy was demonstrably open from its posted date through to the
    snapshot: the cumulative count over time is a real open-roles curve. (A
    per-day posting histogram over the same rows is not -- length bias makes
    posting-date trends meaningless.)

    `gone` is the day `opradar.liveness` verified the ad had been taken down,
    expressed like every other age as days-before-snapshot, so a re-check run
    after the snapshot is negative. It is the only take-down date we ever
    observe: between the snapshot and that check we know nothing, and the UI
    draws that stretch as an explicit gap rather than inventing a fill date.

    Unlike _evidence this keeps delisted vacancies -- in a timeline a role that
    went up and later came down is the point, not a broken citation.
    """
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


# ---------------------------------------------------------------------------
# the score
# ---------------------------------------------------------------------------

def score(feats: pd.DataFrame, serviceability: pd.DataFrame,
          eligible_pool: pd.DataFrame) -> pd.DataFrame:
    """Signals -> effective signals -> weighted geometric mean -> percentile."""
    s = signals(feats)
    s = s.merge(serviceability, on="company_key", how="left")
    s["serviceability"] = s["serviceability"].fillna(0.0)
    s["serviceability_e"] = 1.0

    w = CONFIG["signal_weights"]
    floor = CONFIG["signals"]["log_floor"]

    # Shrink each signal toward the pool prior in proportion to missing evidence.
    # The prior is the pool MEDIAN of the observed values -- unknown lands
    # mid-pack, which is what "we do not know" should cost: nothing either way.
    contributions = {}
    for name in SIGNALS:
        raw = s[name].astype(float)
        ev = s[f"{name}_e"].astype(float).clip(0, 1)
        prior = float(raw[ev >= 0.99].median()) if (ev >= 0.99).any() else float(raw.median())
        prior = 0.0 if prior != prior else prior
        eff = (ev * raw.fillna(0.0) + (1 - ev) * prior).clip(floor, 1.0)
        s[f"{name}_eff"] = eff.round(4)
        s[f"{name}_prior"] = round(prior, 4)
        contributions[name] = w[name] * np.log(eff)

    total_w = sum(w.values())
    log_score = sum(contributions.values()) / total_w
    s["pressure"] = np.exp(log_score).round(4)

    # Per-signal contribution in the same units as the score, so the UI can say
    # "unfilled demand is what put this company here" without a second model.
    for name in SIGNALS:
        s[f"contrib_{name}"] = (contributions[name] / total_w).round(4)

    s = confidence(s)

    # Presentation: a percentile inside the pool. Absolute calibration would be
    # false precision -- there are no labels to calibrate against.
    s["opportunity"] = (100 * _pct(s["pressure"])).round(1)

    evidence = eligible_pool.groupby("company_key").apply(
        _evidence, max_n=CONFIG["evidence"]["max_postings"], include_groups=False)
    s["evidence"] = s["company_key"].map(evidence)
    tl = eligible_pool.groupby("company_key").apply(_timeline, include_groups=False)
    s["timeline"] = s["company_key"].map(tl)
    s["config_hash"] = config_hash()

    s = s.sort_values(["opportunity", "confidence"], ascending=False).reset_index(drop=True)
    s["rank"] = s.index + 1
    return s
