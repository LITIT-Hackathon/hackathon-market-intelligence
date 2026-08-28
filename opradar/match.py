"""Pipeline C -- the join (ALGORITHM_PEOPLE.md 6).

For each eligible company: decompose its postings into demand atoms, test each
atom against the bench, aggregate to Serviceability(C) in [0, 1].

Match rule per atom d:
    role_family equal
    AND tech overlap        (an atom with NO tech signal passes this test --
                             ~45% of eligible titles name no technology, and
                             auto-failing them would zero half the market
                             for a data-coverage reason, not a real one)
    AND seniority           (candidate rank >= atom rank passes fully;
                             exactly one below earns adjacent_credit;
                             an atom with UNKNOWN seniority passes)
    AND availability != unavailable

coverage(d) = best credit over candidates; depth(d) = min(1, matches / depth_saturation)
Serviceability = sum(w_d * (0.7*coverage + 0.3*depth)) / sum(w_d)

w_d weights each atom by its own N1 contribution: unfilled roles dominate.
Region is NOT a match constraint: the bench is nearshore/remote by definition.
Stated as an assumption in the UI.
"""

from __future__ import annotations

import json

import pandas as pd

from .config import CONFIG


def _atom_weight(age_days: float) -> float:
    m = CONFIG["match"]
    if age_days > 90:
        return m["atom_weight_gt90"]
    if age_days > 45:
        return m["atom_weight_gt45"]
    return m["atom_weight_fresh"]


def _bench_by_family(bench: pd.DataFrame) -> dict[str, list[dict]]:
    usable = bench[bench["availability"] != "unavailable"]
    out: dict[str, list[dict]] = {}
    for family, grp in usable.groupby("role_family"):
        out[family] = [
            {"rank": int(r.seniority_rank), "tags": set(r.tech_tags)}
            for r in grp.itertuples()
        ]
    return out


def _atom_match(atom_rank, atom_tags: set, candidates: list[dict]) -> tuple[float, int]:
    """Returns (best credit, number of matching candidates)."""
    m = CONFIG["match"]
    best, n = 0.0, 0
    for cand in candidates:
        if atom_tags and not (atom_tags & cand["tags"]):
            continue
        if atom_rank is None or cand["rank"] >= atom_rank:
            credit = 1.0
        elif cand["rank"] == atom_rank - 1:
            credit = m["adjacent_credit"]
        else:
            continue
        n += 1
        best = max(best, credit)
    return best, n


def serviceability(eligible_pool: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """One row per company: serviceability plus its decomposition."""
    m = CONFIG["match"]
    by_family = _bench_by_family(bench)

    rows = []
    for key, grp in eligible_pool.groupby("company_key"):
        weight_sum = score_sum = 0.0
        covered = uncovered = 0
        uncovered_families: dict[str, int] = {}

        for atom in grp.itertuples():
            candidates = by_family.get(atom.role_family, [])
            atom_rank = None if atom.seniority_rank != atom.seniority_rank else int(atom.seniority_rank)
            atom_tags = set(atom.tech_categories) if atom.tech_categories is not None else set()

            coverage, n_match = _atom_match(atom_rank, atom_tags, candidates)
            depth = min(1.0, n_match / m["depth_saturation"])

            # age policy: thresholds on the verified-effective age, and the
            # whole atom damped by its signal weight (stale or delisted
            # postings should not demand bench coverage at full strength)
            age = getattr(atom, "age_effective", atom.posting_age_days)
            sw = getattr(atom, "signal_weight", 1.0)
            w = _atom_weight(age) * (sw if sw == sw else 1.0)
            weight_sum += w
            score_sum += w * (m["coverage_weight"] * coverage + m["depth_weight"] * depth)

            if coverage > 0:
                covered += 1
            else:
                uncovered += 1
                uncovered_families[atom.role_family] = uncovered_families.get(atom.role_family, 0) + 1

        rows.append({
            "company_key": key,
            "serviceability": round(score_sum / weight_sum, 4) if weight_sum else 0.0,
            "atoms_total": covered + uncovered,
            "atoms_covered": covered,
            "atoms_uncovered": uncovered,
            # JSON string, not a dict: pyarrow unions dict keys across rows on
            # the parquet round-trip and nulls the gaps, corrupting the counts
            "uncovered_families": json.dumps(dict(sorted(
                uncovered_families.items(), key=lambda kv: -kv[1]))),
        })
    return pd.DataFrame(rows)
