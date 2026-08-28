"""Validation without ground truth (ALGORITHM.md 7 / ALGORITHM_PEOPLE.md 7).

V1  divergence  -- rank correlation vs the naive volume ranking must be LOW
V2  adversarial -- named defects: forbidden classes / NTT in the prospect list
V3  sensitivity -- top-20 must survive +-20% weight perturbation
People V1/V2    -- value vs skill-count correlation; no phantom supply
V4              -- enforced by absence: nothing here touches the fixture labels
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG


def _spearman(a: pd.Series, b: pd.Series) -> float:
    """Spearman = Pearson on ranks. Avoids the scipy dependency."""
    return float(a.rank().corr(b.rank()))


def v1_divergence(ranked: pd.DataFrame) -> dict:
    live = ranked[ranked["rank"].notna()]
    rho = _spearman(live["opportunity"], live["it_n"])
    return {
        "spearman_vs_volume": round(rho, 3),
        "verdict": "ok" if rho < 0.8 else "TOO CLOSE TO A VOLUME RANKING",
        "note": "correlation with it_n cannot be ~0 -- N1 counts unfilled postings, "
                "which grows with volume. The claim is divergence, not independence.",
    }


def v2_adversarial(ranked: pd.DataFrame) -> dict:
    live = ranked[ranked["rank"].notna()]
    bad_class = live[~live["company_class"].isin(CONFIG["eligible_classes"])]
    ntt = live[live["company_name"].str.contains(
        r"(?<![A-Za-z0-9])NTT(?![A-Za-z0-9])", case=False, regex=True)]
    defects = len(bad_class) + len(ntt)
    return {
        "forbidden_class_rows": bad_class["company_name"].tolist(),
        "ntt_rows": ntt["company_name"].tolist(),
        "defects": defects,
        "verdict": "clean" if defects == 0 else f"{defects} NAMED DEFECTS",
    }


def v3_sensitivity(signals_scored: pd.DataFrame) -> dict:
    """Recompute Need under perturbed weights; measure top-K stability."""
    v = CONFIG["validation"]
    w0 = CONFIG["need_weights"]
    live = signals_scored[signals_scored["rank"].notna()].copy()

    base_top = set(live.nlargest(v["top_k"], "opportunity")["company_key"])
    rng = np.random.default_rng(7)
    overlaps = []
    for _ in range(v["perturbation_samples"]):
        w = {k: val * (1 + rng.uniform(-v["perturbation"], v["perturbation"]))
             for k, val in w0.items()}
        total = sum(w.values())
        need = (w["n1"] * live["n1"] + w["n2"] * live["n2"]
                + w["n3"] * live["n3"] + w["n4"] * live["n4"]) / total * 100
        opp = need * live["serviceability"]
        top = set(live.assign(_o=opp).nlargest(v["top_k"], "_o")["company_key"])
        overlaps.append(len(base_top & top))

    return {
        "top_k": v["top_k"],
        "min_overlap": int(min(overlaps)),
        "mean_overlap": round(float(np.mean(overlaps)), 1),
        "verdict": "stable" if min(overlaps) >= v["top_k"] - 3 else "WEIGHT-SENSITIVE",
    }


def people_checks(value: pd.DataFrame, supply_index: pd.DataFrame,
                  bench: pd.DataFrame) -> dict:
    rho = _spearman(value["value"], value["skill_breadth"])

    # no supply cell may claim a tech tag no candidate in it actually holds
    phantom = 0
    for cell in supply_index.itertuples():
        members = bench[(bench["role_family"] == cell.role_family)
                        & (bench["seniority"] == cell.seniority)]
        held = set().union(*members["tech_tags"]) if len(members) else set()
        phantom += sum(1 for tag in cell.tech_tags if tag not in held)

    return {
        "value_vs_skill_count_spearman": round(rho, 3),
        "v1_verdict": "ok" if abs(rho) < 0.5 else "SKILL-COUNT RANKING",
        "phantom_supply_tags": phantom,
        "thin_cells_flagged": int(supply_index["thin_cell"].sum()),
        "all_synthetic_labelled": bool((bench["source"] == "synthetic").all()),
        "label_precision_claims": "none, by design (V4)",
    }


def run_all(ranked: pd.DataFrame, value: pd.DataFrame,
            supply_index: pd.DataFrame, bench: pd.DataFrame) -> dict:
    return {
        "companies": {
            "v1_divergence": v1_divergence(ranked),
            "v2_adversarial": v2_adversarial(ranked),
            "v3_sensitivity": v3_sensitivity(ranked),
        },
        "people": people_checks(value, supply_index, bench),
    }
