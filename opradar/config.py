"""Scoring configuration -- every tunable in one place (ALGORITHM.md rule 2).

Nothing in signals/scoring/match/people_scoring may hardcode a weight or a
threshold. The config hash is stamped into every output row so any result is
reproducible: same config hash + same parquet = same leaderboard.
"""

from __future__ import annotations

import hashlib
import json

CONFIG: dict = {
    # ---- Pipeline A: eligibility + guardrails (ALGORITHM.md 3, 4.1, 4.6) ----
    "eligible_classes": ["end_client", "public_sector"],
    "min_it_postings": 3,
    "recency_guard_days": 90,

    # ---- Posting age policy ----
    # Fresh-first: a posting's weight falls linearly from 1.0 on the day it
    # is posted to 0.0 at hard_cap_days, and is dropped past that -- the
    # newer the ad, the more it counts, and a ~3-month-old ad counts nothing,
    # alive or not. Raise full_weight_days to give the newest ads a plateau.
    "age": {"full_weight_days": 0, "hard_cap_days": 90},

    # ---- Liveness (data/processed/liveness.parquet, opradar.liveness) ----
    # dead_weight: a confirmed-dead posting keeps a token residual weight --
    # it marks hiring energy and keeps the company on the board, but it can
    # never outrank verified-live demand (0.25 let high-churn posters whose
    # every ad was already gone top the fresh-first radar).
    "liveness": {"dead_weight": 0.1, "ttl_days": 7},

    # ---- Need signals ----
    # N1 is FRESH demand (product decision, supersedes ALGORITHM.md 4.4's
    # unfilled-demand reading): mostly the age-weighted volume of postings
    # newer than fresh_days, partly the age-weighted volume overall. days_a/
    # days_b only feed the >45d / >90d display columns.
    "need_weights": {"n1": 35, "n2": 25, "n3": 20, "n4": 20},
    "n1": {"days_a": 45, "days_b": 90,
           "fresh_days": 30, "mix_fresh": 0.6, "mix_volume": 0.4},
    "n2": {"mix_count": 0.6, "mix_share": 0.4},
    "n3": {"volume_damp_at": 5, "tech_damp_at": 3},
    "n4": {"window_days": 180},

    # ---- Confidence (ALGORITHM.md 4.5) ----
    "confidence": {
        "weights": {"evidence": 0.40, "recency": 0.25, "identity": 0.20, "corrob": 0.15},
        "evidence_saturation": 8,
        "recency_fresh": 1.0, "recency_90d": 0.7, "recency_old": 0.4,
        "identity_clean": 1.0, "identity_merged": 0.8, "identity_review": 0.5,
        "band_high": 0.75, "band_medium": 0.55,
    },

    # ---- Pipeline C: match (ALGORITHM.md 6 / ALGORITHM_PEOPLE.md 6) ----
    "match": {
        "coverage_weight": 0.7, "depth_weight": 0.3, "depth_saturation": 3,
        # partial credit when the best candidate sits exactly one seniority
        # level below the demand atom
        "adjacent_credit": 0.7,
        # An atom we cannot characterise is NOT a staffable atom. 49.6% of
        # eligible postings name no technology and 76.6% carry no seniority,
        # so treating either unknown as a pass made 39.5% of demand match on
        # role_family alone and pinned serviceability at ~1.0 for everyone.
        # Missing evidence now earns partial credit: we genuinely do not know
        # whether we could staff it, and the score should say so.
        "unknown_tech_credit": 0.5,
        "unknown_seniority_credit": 0.85,
        # an atom only counts as "we could staff this" above this credit
        "strong_coverage": 0.7,
        # w_d: fresh-first -- the newest demand matters most, so the bench
        # is graded hardest on whether it can serve what is being asked NOW
        "atom_weight_gt90": 0.3, "atom_weight_gt45": 0.6, "atom_weight_fresh": 1.0,
        # deal size: a contract is worth more the more people we could put on
        # it. placeable_w (freshness-weighted staffable roles) saturates here:
        # ~4 staffable roles = a full team-sized deal, 1 role = a thin one.
        "deal_saturation": 4,
    },

    # ---- Pipeline B: people scoring (ALGORITHM_PEOPLE.md 5) ----
    "people": {
        "deploy_weights": {"seniority": 0.5, "readiness": 0.3, "breadth": 0.2},
        "readiness": {"now": 1.0, "in_30d": 0.7, "in_90d": 0.4, "unavailable": 0.0},
        "market_pull_days": 45,        # reuse of the N1 unfilled threshold
        "thin_cell": 5,                # P6 guardrail: 1/depth explodes below this
    },

    # ---- Evidence attached to every ranked company (ALGORITHM.md 4.7) ----
    # fresh-first: panels lead with the newest ads
    "evidence": {"max_postings": 6, "freshest": 4, "oldest": 2},

    # ---- Validation (ALGORITHM.md 7) ----
    "validation": {"perturbation": 0.2, "perturbation_samples": 8, "top_k": 20},
}


def config_hash(cfg: dict = CONFIG) -> str:
    """Short stable hash of the whole configuration."""
    canon = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
