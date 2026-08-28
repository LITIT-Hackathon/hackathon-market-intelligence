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

    # ---- Need signals (ALGORITHM.md 4.4) ----
    # thresholds chosen by measurement: >45d is the only candidate that
    # separates a majority of the pool; >90d rides along.
    "need_weights": {"n1": 35, "n2": 25, "n3": 20, "n4": 20},
    "n1": {"days_a": 45, "days_b": 90, "mix_a": 0.6, "mix_b": 0.4},
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
        # w_d: each atom weighted by its own N1 contribution -- an unfilled
        # role matters more than a fresh one
        "atom_weight_gt90": 1.0, "atom_weight_gt45": 0.8, "atom_weight_fresh": 0.4,
    },

    # ---- Pipeline B: people scoring (ALGORITHM_PEOPLE.md 5) ----
    "people": {
        "deploy_weights": {"seniority": 0.5, "readiness": 0.3, "breadth": 0.2},
        "readiness": {"now": 1.0, "in_30d": 0.7, "in_90d": 0.4, "unavailable": 0.0},
        "market_pull_days": 45,        # reuse of the N1 unfilled threshold
        "thin_cell": 5,                # P6 guardrail: 1/depth explodes below this
    },

    # ---- Evidence attached to every ranked company (ALGORITHM.md 4.7) ----
    "evidence": {"max_postings": 6, "oldest": 4, "freshest": 2},

    # ---- Validation (ALGORITHM.md 7) ----
    "validation": {"perturbation": 0.2, "perturbation_samples": 8, "top_k": 20},
}


def config_hash(cfg: dict = CONFIG) -> str:
    """Short stable hash of the whole configuration."""
    canon = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
