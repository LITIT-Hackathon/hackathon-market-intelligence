"""Every tunable in one place, each with the reason it holds that value.

Rule: nothing in features / scoring / match / people may hardcode a weight or a
threshold. The config hash is stamped into every output row, so the same hash
plus the same parquet must reproduce the same leaderboard exactly.

The harder rule, and the one that matters: a constant here needs a JUSTIFICATION
next to it. "+10 for a senior role" with no argument is unanswerable on stage.
Three kinds of justification appear below and they are labelled:

    [measured]  chosen because of a number observed in this pool
    [stated]    a business assumption, argued but not measured
    [scale]     a unit-setting constant with no ranking effect on its own
"""

from __future__ import annotations

import hashlib
import json

CONFIG: dict = {
    # ---- eligibility ------------------------------------------------------
    # Companies below this are not ranked: three vacancies is the point at
    # which "concentrated on one stack" stops being an artefact of having only
    # one or two ads. [measured] 333 companies clear it, 157 clear five.
    "min_it_postings": 3,

    # ---- feature extraction ----------------------------------------------
    "features": {
        # A programme is stood up over weeks, not months. 21 days is the window
        # the repo's own project detection already used and the top detections
        # (Telekom MMS 7 roles in 2 days, Deichmann 5 in one day) sit far
        # inside it, so the exact edge does not decide anything. [stated]
        "burst_window_days": 21,
        # Flow window. Must equal the live board's own `veroeffentlichtseit`
        # bucket so the two observations are like for like. [scale]
        "flow_window_days": 28,
    },

    # ---- statistical machinery -------------------------------------------
    "stats": {
        # Rows with fewer trials than this do not inform the prior's SPREAD --
        # including them makes the prior inherit the very noise it exists to
        # damp. [stated]
        "prior_min_trials": 5,
        "prior_min_rows": 20,
        # Used when the pool is degenerate (all rates identical, or one row).
        # A strength of 5 means "worth about five observations". [scale]
        "prior_fallback_strength": 5.0,
        "prior_max_strength": 200.0,
    },

    # ---- signal shaping ---------------------------------------------------
    "signals": {
        # Below this a factor cannot pull the geometric mean any further down.
        # At the heaviest weight (0.30) a fully dead dimension multiplies the
        # score by 0.05^0.30 = 0.41 -- a heavy penalty, not annihilation.
        # Annihilation would make the ranking a single-signal ranking whenever
        # any input is missing. [stated]
        "log_floor": 0.05,

        # S1. Half-point of the magnitude term: five roles open past a month is
        # half the magnitude signal. Chosen against the pool -- [measured] the
        # median company has 4 IT vacancies and the 90th percentile has 12, so
        # a half-point at 5 puts the median company mid-curve rather than
        # pinning most of the pool at one end.
        "unmet_half": 5.0,
        # Without a live check, "older than 45 days at crawl time" is the only
        # available proxy and it cannot separate unfilled from abandoned. Worth
        # about half of a verified observation. [stated]
        "unmet_proxy_evidence": 0.5,

        # S2. Additive smoothing on both flow windows, so 0 -> 2 does not read
        # as an infinite expansion. [scale]
        "expansion_smoothing": 2.0,
        # Scale of the logistic on the log-ratio: a company at 2x the pool's
        # median change scores ~0.67, at 4x ~0.80. [scale]
        "expansion_scale": 1.5,

        # S3. A burst needs at least three roles to be a burst at all, and the
        # magnitude half-point sits three above that -- six roles inside 21
        # days is half the burst signal. [stated]
        "burst_min_roles": 3,
        "burst_half": 3.0,
        # Floors keep the three-way product from zeroing on one weak leg while
        # still requiring all three to be present for a high score. [stated]
        "programme_conc_floor": 0.1,
        "programme_shape_floor": 0.25,
        # A stack claim needs postings that actually name a technology.
        # [measured] tech coverage is 50.4% of eligible postings, so three
        # tech-bearing ads is a realistic bar for full evidence.
        "programme_tech_evidence": 3.0,

        # S4. Three senior roles is half the magnitude signal; four postings
        # with a known seniority is full evidence. [measured] seniority is
        # observed on 23.7% of eligible postings, so four known is already an
        # above-average company.
        "senior_half": 3.0,
        "senior_evidence": 4.0,
    },

    # ---- how the signals combine -----------------------------------------
    # Exponents in a weighted geometric mean, so they express ELASTICITY (a 1%
    # change in this factor moves the score w%), not points. They are ordered
    # by two stated criteria: how directly the signal evidences unmet external
    # demand, and how well it is measured on this data.
    #
    #   unmet          the definitional core, and the only signal verified
    #                  against an authority outside our own snapshot
    #   programme      the pattern the brief exists to find, but stack coverage
    #                  is only ~50%
    #   serviceability an opportunity we cannot staff is not an opportunity,
    #                  but our bench is synthetic, so it discounts rather than
    #                  decides
    #   seniority      a strong buying trigger on 24% coverage
    #   expansion      real, but two observations support a direction, not a
    #                  trend -- deliberately the lowest
    "signal_weights": {
        "unmet": 0.30,
        "programme": 0.22,
        "serviceability": 0.18,
        "seniority": 0.15,
        "expansion": 0.15,
    },

    # ---- confidence -------------------------------------------------------
    # Reported beside the score, never folded into it.
    "confidence": {
        "weights": {"volume": 0.30, "verified": 0.30,
                    "observability": 0.25, "agreement": 0.15},
        # eight IT vacancies is half the volume component [measured]: 78 of the
        # 333-company pool reach eight, so it separates a real minority
        "volume_half": 8.0,
        "verify_partial": 0.6,
        "verify_none": 0.25,
        "band_high": 0.72, "band_medium": 0.55,
    },

    # ---- evidence attached to every ranked row ---------------------------
    "evidence": {"max_postings": 8},

    # ---- Layer C: match / serviceability ---------------------------------
    "match": {
        "coverage_weight": 0.7, "depth_weight": 0.3, "depth_saturation": 3,
        # partial credit when the best candidate sits exactly one seniority
        # level below the demand atom
        "adjacent_credit": 0.7,
        # An atom we cannot characterise is NOT a staffable atom. [measured]
        # 49.6% of eligible postings name no technology and 76.3% carry no
        # seniority, so treating either unknown as a pass made 39.5% of demand
        # match on role family alone and pinned serviceability near 1.0 for
        # everyone. Missing evidence earns partial credit instead: we genuinely
        # do not know whether we could staff it.
        "unknown_tech_credit": 0.5,
        "unknown_seniority_credit": 0.85,
        # an atom counts as "we could staff this" above this credit
        "strong_coverage": 0.7,
        # Atom weight by how long the role has been open. Unfilled-first, the
        # mirror of S1: the bench is graded hardest on the demand the client
        # has already failed to satisfy, because that is the demand actually
        # available to buy. [stated]
        "atom_weight_gt90": 1.0, "atom_weight_gt45": 0.8, "atom_weight_fresh": 0.5,
    },

    # ---- Algorithm B: capability portfolio + people ----------------------
    "people": {
        # Readiness of a consultant by availability band. [stated] -- a start
        # date beyond a quarter barely helps a client who is already late.
        "readiness": {"now": 1.0, "in_30d": 0.8, "in_90d": 0.45, "unavailable": 0.0},
        # Below this many consultants a cell's scarcity estimate is unstable
        # and is flagged rather than ranked. [stated]
        "thin_cell": 5,
        # Depth at which a cell stops being a staffing risk: three deployable
        # consultants covers one client team plus a replacement. [stated]
        "coverage_saturation": 3.0,
        # Deployability mix. Seniority dominates because German clients buy
        # senior capacity from nearshore and junior locally; readiness matters
        # more than breadth because a consultant who cannot start is worth
        # nothing this quarter. [stated]
        "deploy_weights": {"seniority": 0.45, "readiness": 0.35, "german": 0.20},
        # Marginal-value model: how much a person's absence would cost the
        # bench's ability to serve ranked demand. See people.py.
        "marginal_samples": 1,
    },

    # ---- validation -------------------------------------------------------
    "validation": {"perturbation": 0.2, "perturbation_samples": 12, "top_k": 20},
}


def config_hash(cfg: dict = CONFIG) -> str:
    """Short stable hash of the whole configuration."""
    canon = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
