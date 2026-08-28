"""Pipeline C -- the join (ALGORITHM_PEOPLE.md 6).

For each eligible company: decompose its postings into demand atoms, test each
atom against the bench, aggregate to Serviceability(C) in [0, 1].

Match rule per atom d:
    role_family equal
    AND tech overlap        (an atom naming NO technology is not auto-failed --
                             49.6% of eligible titles name none, and zeroing
                             them would punish a data gap rather than a real
                             one -- but it is not a free pass either: it earns
                             unknown_tech_credit, because matching on role
                             family alone is not evidence that we can staff it)
    AND seniority           (candidate rank >= atom rank passes fully;
                             exactly one below earns adjacent_credit;
                             an UNKNOWN seniority earns unknown_seniority_credit)
    AND availability != unavailable

    credit(d) = tech_credit * seniority_credit

Treating both unknowns as passes made 39.5% of demand match on role_family
alone and pinned serviceability near 1.0 for every company, which made the
factor inert. Partial credit for missing evidence is what makes it discriminate.

coverage(d) = best credit over candidates; depth(d) = min(1, matches / depth_saturation)
Serviceability = sum(w_d * (0.7*coverage + 0.3*depth)) / sum(w_d)

w_d is fresh-first: the newest demand carries the most weight, so the bench is
graded hardest on what is being asked for NOW (config match.atom_weight_*).
Atoms are further damped by signal_weight, so a stale or delisted posting
does not demand full bench coverage.
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
        if atom_tags:
            if not (atom_tags & cand["tags"]):
                continue
            tech_credit = 1.0
        else:
            # no technology named in the title: we matched on role family only
            tech_credit = m["unknown_tech_credit"]

        if atom_rank is None:
            sen_credit = m["unknown_seniority_credit"]
        elif cand["rank"] >= atom_rank:
            sen_credit = 1.0
        elif cand["rank"] == atom_rank - 1:
            sen_credit = m["adjacent_credit"]
        else:
            continue

        n += 1
        best = max(best, tech_credit * sen_credit)
    return best, n


def serviceability(eligible_pool: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """One row per company: serviceability plus its decomposition."""
    m = CONFIG["match"]
    by_family = _bench_by_family(bench)

    rows = []
    for key, grp in eligible_pool.groupby("company_key"):
        weight_sum = score_sum = 0.0
        covered = uncovered = strong = 0
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

            if coverage >= m["strong_coverage"]:
                strong += 1
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
            "atoms_strong": strong,
            "atoms_uncovered": uncovered,
            # JSON string, not a dict: pyarrow unions dict keys across rows on
            # the parquet round-trip and nulls the gaps, corrupting the counts
            "uncovered_families": json.dumps(dict(sorted(
                uncovered_families.items(), key=lambda kv: -kv[1]))),
        })
    return pd.DataFrame(rows)
