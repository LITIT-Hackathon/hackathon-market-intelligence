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
    `opportunity` is an ABSOLUTE score out of 100, read off the model's own log
    scale. Every effective signal lives in [log_floor, 1], so their weighted
    geometric mean `pressure` does too, and the two ends are meanings rather
    than artefacts: the floor is a company that fails every dimension as hard
    as the model allows, and 1.0 is a company that maxes all six at once. The
    score is the row's position between them.

    NOBODY CAN SCORE 100, and not because it is capped. Four of the six signals
    are geometric means of saturating terms or logistic curves, all of which
    approach 1 without ever reaching it, so a perfect company is not a company
    this model can describe. On the shipped pool the best row is in the mid-70s
    and the worst is around 18 -- a company at the bottom of this board is still
    not the worst company the model can imagine, and saying so is the point.

    This replaced a percentile of the pool, which printed 100 for the top row
    whatever it scored, spaced every neighbour exactly 100/n apart whether the
    real gap was 7% or 0.2%, and moved a company's score when an unrelated
    company joined the pool. `percentile` keeps that reading beside the score,
    because "ahead of 87% of the pool" is a fair sentence -- it is just not a
    rating. `pressure` carries the raw geometric mean for cross-run comparison,
    and `points_*` decompose the score into each signal's share of it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import CONFIG, config_hash

SIGNALS = ["unmet", "expansion", "programme", "seniority",
           "serviceability", "dealsize"]


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


def fit_stale_weight(live: pd.Series, snap: pd.Series, paired: pd.Series) -> float:
    """How far to trust June's serviceability where the live one cannot exist.

    Fitted, not chosen. This is the textbook shrinkage weight for a quantity
    observed with error,

        w = var(signal) / (var(signal) + var(noise))

    estimated on the companies where BOTH numbers can be computed: `signal` is
    how much the live rate genuinely varies between companies, `noise` is how
    far June's reading of the same company misses it.

    It replaced a constant borrowed from S1's snapshot proxy, and the borrowing
    was wrong in a way that mattered. [measured] over 65 paired companies June's
    rate carries a bias of +0.004 and a mean absolute error of 0.065, against
    0.163 for the pool prior -- it is two and a half times the better estimate,
    and the borrowed 0.5 was throwing half of that away in favour of a prior
    that happens to sit high. Which is generous in exactly the wrong direction:
    it flattered the companies we can see least. The fitted weight is 0.79 on
    this pool, and raising it DEMOTES them, because it stops handing them the
    pool median for half their bench score.

    Falls back to the stated constant when too few companies carry both
    readings for the variances to mean anything.
    """
    if int(paired.sum()) < CONFIG["stats"]["prior_min_rows"]:
        return float(CONFIG["signals"]["bench_stale_evidence"])
    a = live[paired].astype(float)
    b = snap[paired].astype(float)
    signal = float(a.var(ddof=1))
    noise = float((b - a).var(ddof=1))
    if signal <= 0 or noise <= 0:
        return float(CONFIG["signals"]["bench_stale_evidence"])
    return float(np.clip(signal / (signal + noise), 0.0, 1.0))


def blend(*legs):
    """Geometric mean of the legs of ONE signal.

    A signal assembled from several sub-observations that must all hold is a
    conjunction, and this file already argues, at the top, that the right form
    for a conjunction is a weighted geometric mean rather than a raw product:
    a product requires every dimension to be non-trivial, and a geometric mean
    does that WITHOUT collapsing the scale. The signals were not obeying their
    own rule internally. A product of three sub-unit legs cannot reach the
    scale of a single observation, so a signal built that way can never spend
    the weight the config gives it:

        [measured] `programme` -- nominal weight 0.20, the second heaviest of
        six -- had a pool maximum of 0.211 against serviceability's 1.000, and
        delivered 2.5% of the ranking's variance against serviceability's
        37.5%. As a geometric mean of the same three legs its maximum is 0.595,
        which is the scale the rest of the model is already on.

    The legs, their floors and their ordering are untouched; only the scale
    is, so nothing about which company beats which ON THIS SIGNAL changes.
    What changes is how much of the ranking the signal is allowed to decide,
    which is what its weight was supposed to say in the first place.
    """
    prod = legs[0]
    for leg in legs[1:]:
        prod = prod * leg
    return np.clip(prod, 0.0, None) ** (1.0 / len(legs))


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
    f["unmet"] = blend(f["unmet_rate"],
                       saturate(f["unmet_count"], cfg["unmet_half"])).round(4)
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
    #   The three legs combine as a GEOMETRIC MEAN, not a raw product: a
    #   product of three sub-unit numbers cannot reach the scale of the other
    #   five signals, which is how a 0.20 weight came to decide 2.5% of the
    #   ranking. See `blend`. Zero on any leg is still zero on the signal,
    #   which is the conjunctive property this signal exists for.
    f["programme"] = blend(
        f["burst_strength"].clip(lower=cfg["programme_burst_floor"]),
        f["excess_concentration"].clip(lower=cfg["programme_conc_floor"]),
        f["team_shape"].clip(lower=cfg["programme_shape_floor"])).round(4)
    # Evidence, on two grounds, and the weaker one wins. A stack claim needs
    # postings that actually name a technology; a SHAPE claim needs enough
    # postings for a cluster to be a fact about the company rather than about
    # how many of its advertisements our one crawl happened to catch. Three
    # ads cannot exhibit "eight vacancies inside twelve days" -- for them this
    # signal is not weak evidence, it is no evidence, and the model's standing
    # rule for no evidence is the pool prior plus a dent in confidence.
    f["programme_e"] = np.minimum(
        np.clip(f["tech_covered_n"] / cfg["programme_tech_evidence"], 0, 1),
        np.clip(f["it_n"] / cfg["programme_volume_evidence"], 0, 1))

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
    f["seniority"] = blend(f["senior_rate"],
                           saturate(f["senior_k"], cfg["senior_half"])).round(4)
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

    # 3. how much of the score rests on observed rather than imputed input.
    #    ALL SIX, weighted by how much of the score each one carries. This
    #    listed only the four market signals back when the two bench evidence
    #    weights were the constant 1.0 and adding them would have moved
    #    nothing. They are not constant any more -- a company whose every
    #    advertisement has come down is scored on June's bench fit and on no
    #    deal size at all -- and leaving them out let exactly the rows with the
    #    least visible evidence read "high confidence": [measured] Deutsche
    #    Telekom, with not one live vacancy we can see, was one of them.
    w_sig = CONFIG["signal_weights"]
    tot_w = sum(w_sig.values())
    observability = sum(
        (w_sig[k] / tot_w) * s[f"{k}_e"].astype(float) for k in SIGNALS)

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

# The pool carries 58 columns; these two functions read seven of them. Grouping
# the wide frame made every per-company `sort_values` reorder all 58 and every
# `itertuples` build a 58-field row -- [measured] 3.4s of a 4.0s score() call
# for 943 rows, against 0.10s of actual groupby overhead. Narrowing first is
# semantically identical: sort_values derives its permutation from the key
# column alone, so the surviving columns cannot change the ordering.
_EVIDENCE_COLS = ["company_key", "posting_age_days", "title_clean", "source_url",
                  "role_family", "seniority_derived", "tech_categories"]
_TIMELINE_COLS = ["company_key", "posting_age_days", "title_clean", "source_url",
                  "role_family", "alive", "posted_date", "gone_days"]


def _narrow(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Keep `cols`, tolerating the optional ones (alive/gone_days) being absent."""
    return df[[c for c in cols if c in df.columns]]


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


def _timeline_prep(pool: pd.DataFrame) -> pd.DataFrame:
    """Add `gone_days` to the whole pool at once, for `_timeline`.

    This used to run inside the per-company function. pandas' datetime parsing
    carries a large fixed cost per call, so paying it once per company -- on
    top of copying every group -- cost [measured] 2.3s of a 4.0s score() call
    for 943 rows. Vectorised over the pool it is a few milliseconds, and
    snapshot_date is a single crawl timestamp so the arithmetic is identical.
    """
    g = pool.copy()
    g["gone_days"] = pd.NA
    if {"checked_at", "snapshot_date", "alive"} <= set(g.columns) and len(g):
        chk = pd.to_datetime(g["checked_at"], utc=True, errors="coerce").dt.tz_localize(None)
        dead = (g["alive"].astype("boolean") == False).fillna(False)  # noqa: E712
        g["gone_days"] = (g["snapshot_date"] - chk).dt.days.where(dead)
    return g


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
    out = []
    for r in grp.sort_values("posting_age_days", ascending=False).itertuples():
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
          eligible_pool: pd.DataFrame, *, evidence: bool = True) -> pd.DataFrame:
    """Signals -> effective signals -> weighted geometric mean -> percentile.

    `evidence=False` skips the citation and timeline payloads. They are pure
    presentation -- the UI needs them, the ranking does not -- and they cost
    [measured] 3.9s of a 4.0s call, against 0.12s for the entire scoring model.
    Validation re-scores this pool 15 times (V3 perturbs weights 12x, V4
    jackknifes 3x) and discards those payloads every time, which is where 59
    of the run's 74 seconds went.
    """
    s = signals(feats)
    s = s.merge(serviceability, on="company_key", how="left")
    s["serviceability"] = s["serviceability"].fillna(0.0)
    s["dealsize"] = s["dealsize"].fillna(0.0)
    s["placeable_w"] = s["placeable_w"].fillna(0.0)
    s["atoms_total"] = s["atoms_total"].fillna(0)

    # THE BENCH SIGNALS MUST NOT SCORE THE AGE OF OUR OWN CRAWL.
    #
    # They answer "how much of this company's unfilled demand could we staff",
    # measured over the vacancies we hold that are still live. Where at least
    # one survives, that is a full observation and is scored as one -- a
    # company with live roles we cannot cover has genuinely earned a zero, and
    # handing it the pool median instead was the regression that put six
    # unstaffable companies in the top 20.
    #
    # Where NONE survives there is nothing to measure, and scoring it as zero
    # is a statement about our snapshot rather than about the company:
    # [measured] 77 companies were floored on both bench signals for that
    # reason, 48 of them have IT roles open on today's board, and one of them
    # is Deutsche Telekom -- 37 open, 32 of them open past a month -- sitting
    # at rank 42. The board reports counts, not roles, so it cannot tell us
    # what those 37 are; that is missing evidence, which this model shrinks
    # toward the prior rather than scores as bad news.
    #
    # So the fallback is the same arithmetic over the vacancies we DO hold,
    # at the reduced weight S1 already uses for its own snapshot proxy. The
    # weaker claim is stated: the roles they advertise now look like the roles
    # they advertised in June. It is not a free pool median -- it is this
    # company's own measured bench fit, discounted for being out of date.
    #
    # ONLY SERVICEABILITY GETS THAT FALLBACK, AND THE REASON IS MEASURABLE.
    # Serviceability is a RATE -- what share of this company's kind of work our
    # bench can take -- and a rate survives its advertisements expiring:
    # [measured] over the 65 companies where both can be computed, June's rate
    # differs from the live one by +0.004, and is the higher of the two on only
    # 23 of them. Dealsize is a COUNT, and a count does not survive: the same
    # comparison puts June +0.268 above live, because June still contains every
    # role that has since been filled or withdrawn. Falling back on it would
    # hand a company credit for the size of a deal that no longer exists.
    #
    # So dealsize takes no fallback at all. We cannot see today's roles, the
    # board gives counts rather than roles, and "how many people could we place
    # on this" is therefore unobserved -- which this model answers with the pool
    # prior and a dent in confidence, not with a number.
    # (Estimating it as June's coverage rate x today's open count was the other
    # candidate. It stacks an inference on an extrapolation, throws away the
    # atom weighting the rate itself is built from, and is GENEROUS where the
    # honest answer is silence: it would have given Deutsche Telekom a full
    # 10 of 10.)
    held = s["atoms_total"].fillna(0).astype(float) > 0
    # fitted BEFORE the fallback overwrites the live column it is fitted on
    stale_w = fit_stale_weight(s["serviceability"], s.get("serviceability_snap",
                                                          s["serviceability"]),
                               held & s.get("serviceability_snap", s["serviceability"]).notna())
    for name in ("serviceability", "placeable_w"):
        snap = s.get(f"{name}_snap")
        snap = s[name] if snap is None else snap.fillna(0.0)
        s[name] = s[name].where(held, snap)
    s["serviceability_e"] = np.where(held, 1.0, stale_w)
    s["dealsize_e"] = np.where(held, 1.0, 0.0)
    s["bench_from_snapshot"] = ~held
    s["bench_stale_weight"] = round(stale_w, 4)

    # What the two bench signals were actually computed on, so no reader is
    # ever shown "we could staff 74" beside "roles we could fill: none of 0".
    s["atoms_scored"] = s["atoms_total"].where(held, s.get("atoms_held", 0)).fillna(0).astype(int)
    s["atoms_scored_covered"] = (s["atoms_covered"]
                                 .where(held, s.get("atoms_covered_snap", 0))
                                 .fillna(0).astype(int))

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

    # ---- the printed score ------------------------------------------------
    # An ABSOLUTE position on the model's own log scale, not a percentile.
    # `pressure` lives in [floor, 1] because every effective signal does, and
    # both ends are meanings: the floor is a company that fails every dimension
    # as hard as the model allows, 1.0 is one that maxes all six at once.
    #
    #     opportunity = 100 * (1 + log(pressure) / -log(floor))
    #
    # Nobody reaches 100, and not because of a cap: `unmet`, `seniority` and
    # `programme` are geometric means of saturating terms and `expansion` is a
    # logistic, so all four approach 1 without arriving. `pressure` would have
    # to be exactly 1. The pool's best company reaches the mid-70s.
    #
    # What this fixes, over the percentile it replaces: the top row no longer
    # prints 100 by construction; a 0.7-point gap no longer means a 7% drop at
    # the top of the board and a 0.2% drop in the middle; and a company's score
    # no longer moves when an unrelated company joins the pool. The percentile
    # is kept beside it, because "ahead of 87% of the pool" is still a fair
    # sentence -- it is just not a rating.
    span = -np.log(floor)
    s["opportunity"] = (100.0 * (1.0 + np.log(s["pressure"]) / span)).round(1)
    s["percentile"] = (100 * _pct(s["pressure"])).round(1)

    # The same number, decomposed into points. Each signal's weight IS its
    # budget -- unmet can award 27 of the 100, dealsize 10 -- and it awards the
    # share of that budget equal to its own position on the same log scale.
    # These six columns sum to `opportunity` exactly, so "unfilled demand is 21
    # of this company's 64 points" needs no second model to say.
    out_of = CONFIG["score"]["points_out_of"]
    for name in SIGNALS:
        pos = 1.0 + np.log(s[f"{name}_eff"].astype(float)) / span
        s[f"points_{name}"] = (out_of * (w[name] / total_w) * pos).round(2)
        s[f"budget_{name}"] = round(out_of * w[name] / total_w, 2)

    if evidence:
        cites = (_narrow(eligible_pool, _EVIDENCE_COLS).groupby("company_key")
                 .apply(_evidence, max_n=CONFIG["evidence"]["max_postings"],
                        include_groups=False))
        s["evidence"] = s["company_key"].map(cites)
        tl = (_narrow(_timeline_prep(eligible_pool), _TIMELINE_COLS)
              .groupby("company_key").apply(_timeline, include_groups=False))
        s["timeline"] = s["company_key"].map(tl)
    s["config_hash"] = config_hash()

    s = s.sort_values(["opportunity", "confidence"], ascending=False).reset_index(drop=True)
    s["rank"] = s.index + 1
    return s
