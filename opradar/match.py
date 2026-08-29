"""Layer C -- the join between demand and bench, in both directions.

    Serviceability(company)  how much of THIS company's unfilled demand we
                             could actually staff                -> Algorithm A
    cell_demand(cell)        how much ranked demand sits in each capability
                             cell, so Algorithm B knows what is worth having

One object, read from two sides. That is the reason to have a matching layer at
all: without it the two rankings are unrelated lists, and the product cannot say
"this account is worth calling AND we can staff it", which is the only sentence
a delivery business actually needs.

DEMAND ATOM
    One posting -> one atom {role_family, tech_tags, seniority, age}. One
    consultant -> one supply atom {role_family, tech_tags, seniority}. Both
    vocabularies come from `reference.py`; neither side may define a second
    technology map, which is what keeps this a join rather than a research
    project.

MATCH RULE, per atom
    role_family equal
    AND tech overlap    -- an atom naming NO technology is not auto-failed
                           (49.6% of eligible titles name none, and zeroing
                           them would punish a data gap) but it is not a free
                           pass either: matching on role family alone earns
                           `unknown_tech_credit`, because it is not evidence
                           that we could staff the role
    AND seniority       -- candidate at or above the atom passes fully; exactly
                           one level below earns `adjacent_credit`; an atom
                           whose seniority is unknown earns
                           `unknown_seniority_credit`
    AND available

WEIGHTING
    Atoms are weighted by how long the role has been open, heaviest for the
    longest. That is deliberately the mirror of Algorithm A's unmet-demand
    signal: a vacancy the client filled last week was never available to us,
    and a vacancy they have failed to fill for three months is the one they
    will actually buy help for.

REGION IS NOT A CONSTRAINT
    The bench is nearshore and remote by construction, so location does not
    gate a match. German language capability does, commercially, and it enters
    through the bench's own deployability rather than as a hard filter -- it is
    a stated assumption and the UI says so.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import CONFIG


def atom_weight(age_days: float) -> float:
    m = CONFIG["match"]
    if age_days > 90:
        return m["atom_weight_gt90"]
    if age_days > 45:
        return m["atom_weight_gt45"]
    return m["atom_weight_fresh"]


def bench_by_family(bench: pd.DataFrame) -> dict[str, list[dict]]:
    usable = bench[bench["availability"] != "unavailable"]
    out: dict[str, list[dict]] = {}
    for family, grp in usable.groupby("role_family"):
        out[family] = [{"id": r.candidate_id, "rank": int(r.seniority_rank),
                        "tags": set(r.tech_tags)} for r in grp.itertuples()]
    return out


def atom_match(atom_rank, atom_tags: set, candidates: list[dict]
               ) -> tuple[float, int, list[str]]:
    """(best credit, number of matching candidates, their ids)."""
    m = CONFIG["match"]
    best, ids = 0.0, []
    for cand in candidates:
        if atom_tags:
            if not (atom_tags & cand["tags"]):
                continue
            tech_credit = 1.0
        else:
            tech_credit = m["unknown_tech_credit"]

        if atom_rank is None:
            sen_credit = m["unknown_seniority_credit"]
        elif cand["rank"] >= atom_rank:
            sen_credit = 1.0
        elif cand["rank"] == atom_rank - 1:
            sen_credit = m["adjacent_credit"]
        else:
            continue

        ids.append(cand["id"])
        best = max(best, tech_credit * sen_credit)
    return best, len(ids), ids


def _atoms(grp: pd.DataFrame):
    for atom in grp.itertuples():
        rank = None if atom.seniority_rank != atom.seniority_rank else int(atom.seniority_rank)
        tags = set(atom.tech_categories) if atom.tech_categories is not None else set()
        yield atom, rank, tags


def serviceability(eligible_pool: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """One row per company: serviceability in [0, 1] plus its decomposition."""
    m = CONFIG["match"]
    by_family = bench_by_family(bench)

    rows = []
    for key, grp in eligible_pool.groupby("company_key"):
        weight_sum = score_sum = 0.0
        covered = uncovered = strong = 0
        uncovered_families: dict[str, int] = {}

        for atom, rank, tags in _atoms(grp):
            coverage, n_match, _ = atom_match(rank, tags, by_family.get(atom.role_family, []))
            depth = min(1.0, n_match / m["depth_saturation"])
            w = atom_weight(atom.posting_age_days)

            weight_sum += w
            score_sum += w * (m["coverage_weight"] * coverage + m["depth_weight"] * depth)

            strong += int(coverage >= m["strong_coverage"])
            if coverage > 0:
                covered += 1
            else:
                uncovered += 1
                uncovered_families[atom.role_family] = \
                    uncovered_families.get(atom.role_family, 0) + 1

        rows.append({
            "company_key": key,
            "serviceability": round((score_sum / weight_sum) if weight_sum else 0.0, 4),
            "atoms_total": covered + uncovered,
            "atoms_covered": covered,
            "atoms_strong": strong,
            "atoms_uncovered": uncovered,
            # JSON string, not a dict: pyarrow unions dict keys across rows on
            # the parquet round-trip and nulls the gaps, corrupting the counts
            "uncovered_families": json.dumps(dict(sorted(
                uncovered_families.items(), key=lambda kv: -kv[1]))),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# the other direction: what is each capability cell worth?
# ---------------------------------------------------------------------------

def cell_demand(eligible_pool: pd.DataFrame, ranked: pd.DataFrame,
                bench: pd.DataFrame) -> pd.DataFrame:
    """Ranked demand aggregated per (role_family, seniority, tech tag) cell.

    This is the object Algorithm B is built on, and it is the reason the two
    algorithms are not mirror images. Algorithm A asks "who should we call?".
    This asks "what do the people we would need to answer those calls look
    like?" -- and it weights every vacancy by the OPPORTUNITY SCORE of the
    company that posted it, so demand sitting inside agencies and companies we
    would never call does not distort the capability plan.
    """
    weights = ranked.set_index("company_key")["pressure"].to_dict()
    by_family = bench_by_family(bench)

    rows: list[dict] = []
    for atom, rank, tags in _atoms(eligible_pool):
        cw = float(weights.get(atom.company_key, 0.0))
        if cw <= 0:
            continue
        w = cw * atom_weight(atom.posting_age_days)
        coverage, n_match, _ = atom_match(rank, tags, by_family.get(atom.role_family, []))
        seniority = atom.seniority_derived if atom.seniority_derived != "unknown" else "unknown"
        for tag in (sorted(tags) or ["unspecified"]):
            rows.append({"role_family": atom.role_family, "seniority": seniority,
                         "tech_tag": tag, "weight": w, "covered": coverage,
                         "matches": n_match, "company_key": atom.company_key})

    if not rows:
        return pd.DataFrame(columns=["role_family", "seniority", "tech_tag",
                                     "demand_weight", "atoms", "companies",
                                     "mean_coverage", "median_matches"])
    df = pd.DataFrame(rows)
    out = df.groupby(["role_family", "seniority", "tech_tag"]).agg(
        demand_weight=("weight", "sum"),
        atoms=("weight", "size"),
        companies=("company_key", "nunique"),
        mean_coverage=("covered", "mean"),
        median_matches=("matches", "median"),
    ).reset_index()
    out["demand_weight"] = out["demand_weight"].round(3)
    out["mean_coverage"] = out["mean_coverage"].round(4)
    # The gap: demand we are weakly positioned to serve. This is what should
    # drive hiring, and it is NOT the same as the largest demand.
    sat = CONFIG["people"]["coverage_saturation"]
    out["supply_depth"] = out["median_matches"].fillna(0)
    out["coverage_gap"] = (1.0 - np.clip(out["supply_depth"] / sat, 0, 1)
                           * out["mean_coverage"]).round(4)
    return out.sort_values("demand_weight", ascending=False).reset_index(drop=True)
