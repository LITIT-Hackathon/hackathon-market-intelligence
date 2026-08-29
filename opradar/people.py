"""Algorithm B -- the capability portfolio, and what a person is worth in it.

WHAT A "PEOPLE OPPORTUNITY" ACTUALLY IS
    Not "this person is impressive". A delivery business does not want the best
    engineers in the abstract; it wants the people who let it say yes to work it
    currently has to decline. So the object being ranked is not a person's
    merit, it is their MARGINAL CONTRIBUTION to the bench's ability to serve
    demand that Algorithm A has already ranked and priced.

    That definition does three things a skill-count or "technical fit" score
    cannot:

      * it makes a two-skill consultant covering an uncovered, high-demand cell
        worth more than an eight-skill consultant who duplicates four colleagues
        -- "more skills wins" is the people-side version of "more vacancies
        wins", and it is wrong for the same reason;
      * it makes value depend on WHO ELSE IS ON THE BENCH, which is what makes
        this a portfolio problem rather than a scoring problem;
      * it makes availability decisive rather than decorative: a consultant who
        cannot start unlocks nothing this quarter, whatever their CV says.

    Formally the bench's coverage of demand is a submodular set function and
    this is its discrete derivative -- leave-one-out, exact, not sampled.

WHY IT IS NOT THE MIRROR IMAGE OF ALGORITHM A
    Algorithm A is a detection problem over time-stamped events at companies:
    is something happening here, is it unmet, is it coherent, is it now.
    Algorithm B is an allocation problem over a portfolio: given demand we can
    already see, where is our capacity thin, and who moves that. A has
    baselines, bursts and confidence; B has coverage, redundancy and marginal
    value. They share exactly one object -- the cell demand table in `match.py`
    -- and nothing else.

TWO OUTPUTS, IN THIS ORDER
    1. THE CAPABILITY PLAN, per (role_family, seniority, tech) cell: how much
       ranked demand sits there and how badly we cover it. This is the durable
       answer -- who to hire, where to train, what to stop selling -- and it
       does not depend on any individual.
    2. PERSON VALUE, per consultant on the bench, as the marginal contribution
       above. Useful for prioritising who to keep free, who to move, and which
       profile to recruit next.

HONESTY NOTE
    The bench in this repo is SYNTHETIC (`bench_gen.py`, every row carries
    `source='synthetic'`). Nothing here measures a real talent market; it
    measures a real DEMAND market against a stated bench profile. The demand
    side is real German postings, which is the half that had to be real for the
    capability plan to mean anything.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG
from .match import atom_weight, bench_by_family


def _depth(n: int) -> float:
    return min(1.0, n / CONFIG["match"]["depth_saturation"])


# ---------------------------------------------------------------------------
# 1. the capability plan
# ---------------------------------------------------------------------------

def capability_plan(cells: pd.DataFrame) -> pd.DataFrame:
    """Rank capability cells by demand we are badly placed to serve.

    priority = demand_weight x coverage_gap

    Deliberately NOT demand alone. The largest cell is usually the one we
    already cover; investing there buys nothing. The product of size and gap is
    what a capacity plan is actually optimising, and it is the number that
    should decide the next hire.
    """
    if cells.empty:
        return cells.assign(priority=[], priority_rank=[])
    # A plan row must name something a recruiter can act on. A cell whose tech
    # is unspecified AND whose seniority is unknown ("dev / ? / ?") is real
    # demand but an unactionable instruction; it stays in cells.parquet for the
    # totals and is excluded from the plan.
    c = cells[(cells["tech_tag"] != "unspecified")
              | (cells["seniority"] != "unknown")].copy()
    if c.empty:
        return c.assign(priority=[], priority_rank=[])
    c["priority"] = (c["demand_weight"] * c["coverage_gap"]).round(3)
    c = c.sort_values("priority", ascending=False).reset_index(drop=True)
    c["priority_rank"] = c.index + 1
    # percentile presentation, same convention as the company score
    c["priority_score"] = (100 * c["priority"].rank(pct=True, method="average")).round(1)
    return c


# ---------------------------------------------------------------------------
# 2. person value = marginal contribution to serving ranked demand
# ---------------------------------------------------------------------------

def _atom_credits(atom_rank, atom_tags: set, candidates: list[dict]
                  ) -> list[tuple[str, float]]:
    """(candidate_id, credit) for every candidate that matches this atom."""
    m = CONFIG["match"]
    out = []
    for cand in candidates:
        if atom_tags:
            if not (atom_tags & cand["tags"]):
                continue
            tech = 1.0
        else:
            tech = m["unknown_tech_credit"]

        if atom_rank is None:
            sen = m["unknown_seniority_credit"]
        elif cand["rank"] >= atom_rank:
            sen = 1.0
        elif cand["rank"] == atom_rank - 1:
            sen = m["adjacent_credit"]
        else:
            continue
        out.append((cand["id"], tech * sen))
    return out


def deployability(bench: pd.DataFrame) -> pd.Series:
    """Can this person actually be sold into German delivery, and how soon.

    Seniority, readiness and German capability -- not skill breadth. Breadth is
    deliberately absent: it is the thing that makes a naive people score wrong,
    and whatever value it has is already counted, precisely, by the marginal
    contribution (a broad consultant matches more atoms, so their marginal
    value is larger IF those atoms were not already covered).
    """
    p = CONFIG["people"]
    w = p["deploy_weights"]
    max_rank = max(bench["seniority_rank"].max(), 1)
    seniority = bench["seniority_rank"] / max_rank
    readiness = bench["availability"].map(p["readiness"]).fillna(0.0)
    german = bench.get("speaks_german", pd.Series(False, index=bench.index)).astype(float)
    return (w["seniority"] * seniority + w["readiness"] * readiness
            + w["german"] * german).round(4)


def person_value(bench: pd.DataFrame, eligible_pool: pd.DataFrame,
                 ranked: pd.DataFrame) -> pd.DataFrame:
    """Marginal value of each consultant against opportunity-weighted demand.

    For every demand atom we know each matching consultant's credit. Removing
    one consultant changes the atom's contribution in two ways: coverage falls
    to the second-best credit if they were the unique best, and depth falls by
    one place. Summing that difference over all atoms, weighted by the posting's
    age and the opportunity score of the company that posted it, gives exactly
    what the bench would lose if that person were not on it.
    """
    m = CONFIG["match"]
    by_family = bench_by_family(bench)
    company_weight = ranked.set_index("company_key")["pressure"].to_dict()

    loss = {cid: 0.0 for cid in bench["candidate_id"]}
    atoms_touched = {cid: 0 for cid in bench["candidate_id"]}
    sole_cover = {cid: 0 for cid in bench["candidate_id"]}

    for atom in eligible_pool.itertuples():
        cw = float(company_weight.get(atom.company_key, 0.0))
        if cw <= 0:
            continue
        w = cw * atom_weight(atom.posting_age_days)
        rank = None if atom.seniority_rank != atom.seniority_rank else int(atom.seniority_rank)
        tags = set(atom.tech_categories) if atom.tech_categories is not None else set()

        credits = _atom_credits(rank, tags, by_family.get(atom.role_family, []))
        if not credits:
            continue
        n = len(credits)
        best = max(c for _, c in credits)
        # second best over the multiset, i.e. what remains if one holder leaves
        second = max((c for _, c in credits if c < best), default=0.0)
        holders = [cid for cid, c in credits if c >= best]

        base = m["coverage_weight"] * best + m["depth_weight"] * _depth(n)
        depth_drop = _depth(n) - _depth(n - 1)

        for cid, credit in credits:
            atoms_touched[cid] += 1
            if credit >= best and len(holders) == 1:
                without = m["coverage_weight"] * second + m["depth_weight"] * _depth(n - 1)
                sole_cover[cid] += 1
            else:
                without = m["coverage_weight"] * best + m["depth_weight"] * _depth(n - 1)
            loss[cid] += w * (base - without)
            _ = depth_drop     # kept explicit: depth is where a duplicate earns

    b = bench.copy()
    b["marginal_demand"] = b["candidate_id"].map(loss).round(4)
    b["atoms_matched"] = b["candidate_id"].map(atoms_touched)
    b["atoms_sole_cover"] = b["candidate_id"].map(sole_cover)
    b["deployability"] = deployability(b)

    # Uniqueness: of the demand this person can reach, how much would nobody
    # else reach as well. This is the diagnostic that explains the ranking to a
    # delivery manager: "we have four of these" versus "she is the only one".
    b["uniqueness"] = np.where(b["atoms_matched"] > 0,
                               b["atoms_sole_cover"] / b["atoms_matched"].clip(lower=1), 0.0)
    b["uniqueness"] = b["uniqueness"].round(4)

    # Value = what the bench would lose, discounted by whether we can actually
    # deploy them. Multiplicative: an unavailable consultant's marginal value is
    # real but not realisable this quarter, and the ranking is a work list.
    raw = b["marginal_demand"] * b["deployability"]
    b["value_raw"] = raw.round(4)
    b["value"] = (100 * raw.rank(pct=True, method="average")).round(1)
    b = b.sort_values("value_raw", ascending=False).reset_index(drop=True)
    b["rank"] = b.index + 1
    return b


def supply_index(bench: pd.DataFrame) -> pd.DataFrame:
    """Bench depth per (role_family, seniority) cell -- the hand-off object."""
    p = CONFIG["people"]
    rows = []
    for (family, seniority), grp in bench.groupby(["role_family", "seniority"]):
        available = grp[grp["availability"] != "unavailable"]
        tags: set[str] = set()
        for t in grp["tech_tags"]:
            tags.update(t)
        rows.append({
            "role_family": family, "seniority": seniority,
            "depth": len(grp), "deployable": len(available),
            "ready_now": int((grp["availability"] == "now").sum()),
            "german_speakers": int(grp.get("speaks_german", pd.Series(dtype=bool)).sum()),
            "tech_tags": sorted(tags),
            "thin_cell": len(grp) < p["thin_cell"],
        })
    return pd.DataFrame(rows).sort_values(["role_family", "seniority"]).reset_index(drop=True)
