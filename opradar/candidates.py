"""Parser for the synthetic candidate dataset (michaelozon/candidate-matching-synthetic).

    python -m opradar.candidates

Produces the supply-side half of the market picture:

    candidates.parquet    10,000 candidate profiles, normalised
    openings.parquet       2,500 synthetic openings with a recomputed qualified pool
    skill_market.parquet      73 skills with supply, demand and a tension ratio
    role_market.parquet    role x seniority supply vs demand
    candidate_report.md    QA report, including a hard look at the "ground truth"

IMPORTANT -- what this dataset is and is not:

  * It is SYNTHETIC, LLM-generated. Distributions are near-uniform by construction
    (seniority splits 34/34/33, ten industries at ~10% each). Nothing here is a
    measurement of a real talent market.
  * It does NOT join to the German posting data. Only 7 of its 73 skills have an
    equivalent in our German extraction, and those 7 appear in 3.3% of German IT
    postings. There is no SAP, Azure, C#, .NET or embedded work in it.
  * Its "ground truth" matches are a fixed top-30 slice of a qualified pool that
    averages ~866 candidates, and they ignore seniority entirely.

So: use it to build and demo the matcher mechanics on realistic-shaped profiles.
Do not use it to claim anything about the German market, and do not report
retrieval precision against its labels.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import reference as ref

BASE_URL = (
    "https://huggingface.co/datasets/michaelozon/candidate-matching-synthetic/resolve/main"
)
FILES = {
    "resumes": "resumes/train-00000-of-00001.parquet",
    "jobs": "jobs/train-00000-of-00001.parquet",
    "matches": "matches/train-00000-of-00001.parquet",
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def download(raw_dir: Path, force: bool = False) -> dict[str, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    paths = {}
    for name, remote in FILES.items():
        dest = raw_dir / f"candidate_{name}.parquet"
        paths[name] = dest
        if dest.exists() and not force:
            continue
        url = f"{BASE_URL}/{remote}"
        _log(f"  downloading {name}")
        req = urllib.request.Request(url, headers={"User-Agent": "opradar/0.1"})
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp, open(tmp, "wb") as fh:
            while chunk := resp.read(1 << 16):
                fh.write(chunk)
        tmp.replace(dest)
    return paths


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return list(value)


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _band(years: int) -> str:
    for lo, hi, label in ref.EXPERIENCE_BANDS:
        if lo <= years <= hi:
            return label
    return "unknown"


def parse_candidates(resumes: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    df["candidate_id"] = resumes["resume_id"]
    df["role"] = resumes["role"]
    df["role_family"] = resumes["role"].map(ref.ROLE_TO_FAMILY).fillna("other")
    df["is_tech_role"] = df["role_family"].isin(ref.TECH_ROLE_FAMILIES) | df["role"].isin(
        ref.TECH_ROLES_EXTRA
    )

    df["seniority_raw"] = resumes["seniority"]
    df["seniority"] = resumes["seniority"].map(ref.CANDIDATE_SENIORITY).fillna("unknown")
    df["years_experience"] = resumes["years_experience"].astype(int)
    df["experience_band"] = df["years_experience"].map(_band)

    df["industry"] = resumes["industry"]
    df["industry_domain"] = resumes["industry"].map(ref.CANDIDATE_INDUSTRY_TO_DOMAIN)
    df["education"] = resumes["education"]
    df["education_rank"] = resumes["education"].map(ref.CANDIDATE_EDUCATION_RANK)

    skills = resumes["skills"].map(_as_list)
    df["skills"] = skills
    df["skill_count"] = skills.map(len)
    df["skill_families"] = skills.map(
        lambda ss: sorted({ref.SKILL_TO_FAMILY.get(s, "other") for s in ss})
    )
    df["primary_skill_family"] = skills.map(
        lambda ss: Counter(ref.SKILL_TO_FAMILY.get(s, "other") for s in ss).most_common(1)[0][0]
        if ss else "other"
    )
    df["summary"] = resumes["summary"]
    return df


def parse_openings(jobs: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    df["opening_id"] = jobs["job_id"]
    df["title"] = jobs["job_title"]
    df["role_family"] = jobs["job_title"].map(ref.ROLE_TO_FAMILY).fillna("other")
    df["is_tech_role"] = df["role_family"].isin(ref.TECH_ROLE_FAMILIES) | df["title"].isin(
        ref.TECH_ROLES_EXTRA
    )
    df["seniority_raw"] = jobs["seniority"]
    df["seniority"] = jobs["seniority"].map(ref.CANDIDATE_SENIORITY).fillna("unknown")
    df["industry"] = jobs["industry"]
    df["industry_domain"] = jobs["industry"].map(ref.CANDIDATE_INDUSTRY_TO_DOMAIN)
    df["must_have_skills"] = jobs["must_have_skills"].map(_as_list)
    df["nice_to_have_skills"] = jobs["nice_to_have_skills"].map(_as_list)
    df["must_count"] = df["must_have_skills"].map(len)
    df["nice_count"] = df["nice_to_have_skills"].map(len)
    df["description"] = jobs["description"]
    return df


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def skill_matrix(candidates: pd.DataFrame) -> tuple[np.ndarray, dict[str, int]]:
    """Boolean candidate x skill matrix. Turns pool computation into numpy slicing."""
    vocab = sorted({s for row in candidates["skills"] for s in row})
    index = {s: i for i, s in enumerate(vocab)}
    matrix = np.zeros((len(candidates), len(vocab)), dtype=bool)
    for i, row in enumerate(candidates["skills"]):
        for s in row:
            matrix[i, index[s]] = True
    return matrix, index


def compute_pools(
    candidates: pd.DataFrame,
    openings: pd.DataFrame,
    matrix: np.ndarray,
    index: dict[str, int],
    threshold: float = ref.MATCH_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recompute the documented matching rule ourselves.

    The dataset ships 30 "relevant" resumes per job. Recomputing the rule it
    documents (>= `threshold` of must-have skills held) shows those 30 are an
    arbitrary slice of a pool averaging several hundred. Worth knowing before
    anyone reports retrieval precision against these labels.
    """
    pool_sizes = np.zeros(len(openings), dtype=int)
    qualified_for = np.zeros(len(candidates), dtype=int)

    for j, must in enumerate(openings["must_have_skills"]):
        cols = [index[s] for s in must if s in index]
        if not cols:
            continue
        share = matrix[:, cols].sum(axis=1) / len(cols)
        ok = share >= threshold
        pool_sizes[j] = int(ok.sum())
        qualified_for += ok

    openings = openings.copy()
    openings["qualified_pool"] = pool_sizes
    openings["pool_share"] = (pool_sizes / max(len(candidates), 1)).round(4)

    candidates = candidates.copy()
    candidates["qualified_for_openings"] = qualified_for
    candidates["qualified_share"] = (qualified_for / max(len(openings), 1)).round(4)
    return candidates, openings


def audit_ground_truth(
    candidates: pd.DataFrame,
    openings: pd.DataFrame,
    matches: pd.DataFrame,
    matrix: np.ndarray,
    index: dict[str, int],
) -> dict:
    """Check what the shipped labels actually encode."""
    cand_pos = {cid: i for i, cid in enumerate(candidates["candidate_id"])}
    seniority = candidates["seniority"].tolist()
    role = candidates["role"].tolist()
    open_seniority = dict(zip(openings["opening_id"], openings["seniority"]))
    open_title = dict(zip(openings["opening_id"], openings["title"]))
    must_by_id = dict(zip(openings["opening_id"], openings["must_have_skills"]))

    pairs = same_sen = same_role = rule_ok = 0
    listed = Counter()
    sizes = []

    for oid, ids in zip(matches["job_id"], matches["relevant_resume_ids"]):
        ids = _as_list(ids)
        sizes.append(len(ids))
        cols = [index[s] for s in must_by_id.get(oid, []) if s in index]
        for cid in ids:
            listed[cid] += 1
            i = cand_pos.get(cid)
            if i is None:
                continue
            pairs += 1
            same_sen += seniority[i] == open_seniority.get(oid)
            same_role += role[i] == open_title.get(oid)
            if cols:
                rule_ok += (matrix[i, cols].sum() / len(cols)) >= ref.MATCH_THRESHOLD

    return {
        "labelled_pairs": pairs,
        "labels_per_opening": {
            "min": int(min(sizes)) if sizes else 0,
            "max": int(max(sizes)) if sizes else 0,
            "mean": round(float(np.mean(sizes)), 1) if sizes else 0,
        },
        "satisfy_documented_rule": round(rule_ok / max(pairs, 1), 4),
        "same_seniority": round(same_sen / max(pairs, 1), 4),
        "same_role": round(same_role / max(pairs, 1), 4),
        "mean_qualified_pool": round(float(openings["qualified_pool"].mean()), 1),
        "labelled_share_of_pool": round(
            float(np.mean(sizes)) / max(float(openings["qualified_pool"].mean()), 1), 4
        ),
        "candidates_ever_labelled": len(listed),
        "listed_counts": listed,
    }


# ---------------------------------------------------------------------------
# market aggregates -- the point of the whole exercise
# ---------------------------------------------------------------------------

def build_skill_market(candidates: pd.DataFrame, openings: pd.DataFrame) -> pd.DataFrame:
    """Supply vs demand per skill.

    Supply  = candidates holding the skill.
    Demand  = openings requiring it (must-have weighted 1.0, nice-to-have 0.5).
    Tension = (demand share / supply share), normalised so the market average is 1.0.

    The normalisation matters. Candidates carry ~6.5 skills and openings ask for ~4.5,
    so the raw ratio has a built-in bias of ~0.69 and nothing ever exceeds 1.0, which
    makes the number look meaningful while being uninterpretable. After normalising,
    above 1.0 genuinely means "the market wants this more than the bench carries it"
    -- the people-side mirror of time-on-market in the German posting data.
    """
    supply = Counter()
    for ss in candidates["skills"]:
        supply.update(ss)
    must = Counter()
    for ss in openings["must_have_skills"]:
        must.update(ss)
    nice = Counter()
    for ss in openings["nice_to_have_skills"]:
        nice.update(ss)

    n_c, n_o = max(len(candidates), 1), max(len(openings), 1)
    rows = []
    for skill in sorted(set(supply) | set(must) | set(nice)):
        s, m, ni = supply[skill], must[skill], nice[skill]
        weighted = m + 0.5 * ni
        supply_share = s / n_c
        demand_share = weighted / n_o
        rows.append({
            "skill": skill,
            "skill_family": ref.SKILL_TO_FAMILY.get(skill, "other"),
            "supply": s,
            "supply_share": round(supply_share, 4),
            "demand_must": m,
            "demand_nice": ni,
            "demand_weighted": round(weighted, 1),
            "demand_share": round(demand_share, 4),
            "tension_raw": round(demand_share / supply_share, 4) if supply_share else None,
        })

    market = pd.DataFrame(rows)
    baseline = market["demand_share"].sum() / max(market["supply_share"].sum(), 1e-9)
    market["tension"] = (market["tension_raw"] / baseline).round(3)
    market.attrs["tension_baseline"] = round(baseline, 4)
    return market.sort_values("tension", ascending=False).reset_index(drop=True)


def build_role_market(candidates: pd.DataFrame, openings: pd.DataFrame) -> pd.DataFrame:
    """Supply vs demand per role x seniority cell."""
    supply = candidates.groupby(["role", "seniority"]).agg(
        supply=("candidate_id", "size"),
        median_years=("years_experience", "median"),
    )
    demand = openings.groupby(["title", "seniority"]).size().rename("demand")
    demand.index.names = ["role", "seniority"]

    cell = supply.join(demand, how="outer").fillna({"supply": 0, "demand": 0})
    cell = cell.reset_index()
    cell["role_family"] = cell["role"].map(ref.ROLE_TO_FAMILY).fillna("other")
    cell["is_tech_role"] = cell["role_family"].isin(ref.TECH_ROLE_FAMILIES) | cell["role"].isin(
        ref.TECH_ROLES_EXTRA
    )

    n_c = max(cell["supply"].sum(), 1)
    n_o = max(cell["demand"].sum(), 1)
    cell["supply_share"] = (cell["supply"] / n_c).round(4)
    cell["demand_share"] = (cell["demand"] / n_o).round(4)
    # demand_share and supply_share each sum to 1 across cells, so this ratio is
    # already centred on 1.0 -- no extra normalisation needed here.
    cell["tension"] = (cell["demand_share"] / cell["supply_share"].replace(0, np.nan)).round(3)

    top = {}
    for (role, sen), grp in candidates.groupby(["role", "seniority"]):
        counter = Counter()
        for ss in grp["skills"]:
            counter.update(ss)
        top[(role, sen)] = [s for s, _ in counter.most_common(6)]
    cell["top_skills"] = [top.get((r, s), []) for r, s in zip(cell["role"], cell["seniority"])]

    return cell.sort_values("demand", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def build_report(candidates, openings, skill_market, role_market, audit, bridge, elapsed) -> dict:
    def top(series, n=12):
        return {str(k): int(v) for k, v in series.value_counts().head(n).items()}

    return {
        "elapsed_s": elapsed,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "michaelozon/candidate-matching-synthetic (MIT, synthetic)",
        "counts": {
            "candidates": int(len(candidates)),
            "openings": int(len(openings)),
            "skills": int(len(skill_market)),
            "roles": int(candidates["role"].nunique()),
            "role_cells": int(len(role_market)),
            "tech_candidates": int(candidates["is_tech_role"].sum()),
        },
        "distributions": {
            "role": top(candidates["role"], 24),
            "role_family": top(candidates["role_family"]),
            "seniority": top(candidates["seniority"]),
            "experience_band": top(candidates["experience_band"]),
            "industry": top(candidates["industry"]),
            "education": top(candidates["education"]),
            "primary_skill_family": top(candidates["primary_skill_family"]),
        },
        "skills": {
            "vocabulary": int(len(skill_market)),
            "per_candidate_mean": round(float(candidates["skill_count"].mean()), 2),
            "per_candidate_min": int(candidates["skill_count"].min()),
            "per_candidate_max": int(candidates["skill_count"].max()),
            "unmapped_to_family": int((skill_market["skill_family"] == "other").sum()),
            "tension_baseline": skill_market.attrs.get("tension_baseline"),
            "tension_spread": [
                round(float(skill_market["tension"].min()), 2),
                round(float(skill_market["tension"].max()), 2),
            ],
            "highest_tension": [
                {"skill": r.skill, "family": r.skill_family, "supply": int(r.supply),
                 "demand": float(r.demand_weighted), "tension": float(r.tension)}
                for r in skill_market.head(10).itertuples()
            ],
            "lowest_tension": [
                {"skill": r.skill, "family": r.skill_family, "supply": int(r.supply),
                 "demand": float(r.demand_weighted), "tension": float(r.tension)}
                for r in skill_market.tail(10).iloc[::-1].itertuples()
            ],
        },
        "pools": {
            "mean_qualified_pool": round(float(openings["qualified_pool"].mean()), 1),
            "min_qualified_pool": int(openings["qualified_pool"].min()),
            "max_qualified_pool": int(openings["qualified_pool"].max()),
            "mean_qualified_for_per_candidate": round(
                float(candidates["qualified_for_openings"].mean()), 1
            ),
        },
        "ground_truth_audit": {k: v for k, v in audit.items() if k != "listed_counts"},
        "bridge_to_german_data": bridge,
    }


def render_report(s: dict) -> str:
    c, d, sk, gt, br = s["counts"], s["distributions"], s["skills"], s["ground_truth_audit"], s["bridge_to_german_data"]

    def table(dct, k="key", v="count"):
        lines = [f"| {k} | {v} |", "| --- | ---: |"]
        lines += [f"| {a} | {b:,} |" if isinstance(b, int) else f"| {a} | {b} |"
                  for a, b in dct.items()]
        return "\n".join(lines)

    out = [
        "# Candidate parse report",
        "",
        f"Generated by `opradar.candidates` in {s['elapsed_s']}s from {s['source']}.",
        "",
        "> **This dataset is synthetic and LLM-generated.** Its distributions are near-uniform",
        "> by construction, so nothing here measures a real talent market. It is a fixture for",
        "> building and demoing the matcher on realistic-shaped profiles.",
        "",
        "## Counts",
        "",
        f"- Candidates: **{c['candidates']:,}** ({c['tech_candidates']:,} in tech roles)",
        f"- Openings: **{c['openings']:,}**",
        f"- Skill vocabulary: **{c['skills']}** · Roles: **{c['roles']}** · "
        f"Role x seniority cells: {c['role_cells']}",
        "",
        "## Does it join to the German posting data?",
        "",
        f"**Barely.** {br['overlapping_skills']} of {br['candidate_vocabulary']} candidate skills have "
        f"an equivalent in our German extraction ({br['overlap_pct']}%), and those appear in only "
        f"**{br['german_it_coverage_pct']}%** of German IT postings.",
        "",
        f"Shared: {', '.join(br['overlapping']) or 'none'}",
        "",
        f"Missing from the candidate vocabulary but common in German IT demand: "
        f"{', '.join(br['missing_from_candidates'])}.",
        "",
        "> Consequence: treat this as a **standalone supply-side fixture**. Matching it against",
        "> German postings needs a skill-vocabulary bridge that does not exist yet.",
        "",
        "## The shipped 'ground truth' does not mean what it looks like",
        "",
        f"- Labelled pairs: {gt['labelled_pairs']:,} "
        f"({gt['labels_per_opening']['mean']:.0f} per opening, always the same size)",
        f"- Share satisfying the documented rule: **{gt['satisfy_documented_rule'] * 100:.1f}%** — "
        "so the labels are internally consistent...",
        f"- ...but the qualified pool averages **{gt['mean_qualified_pool']:,.0f} candidates**, "
        f"of which the labels cover **{gt['labelled_share_of_pool'] * 100:.1f}%**.",
        f"- Labels sharing the opening's seniority: **{gt['same_seniority'] * 100:.1f}%** "
        "(random baseline ~33%) — seniority is ignored entirely.",
        f"- Labels sharing the opening's role title: {gt['same_role'] * 100:.1f}% "
        "(random baseline ~4%) — role does carry signal.",
        "",
        "> **Do not report retrieval precision against these labels.** They are an arbitrary",
        "> top-30 slice of a much larger qualified set, so unlabelled correct answers are",
        "> everywhere and any honest matcher will look wrong.",
        "",
        "## Skill market",
        "",
        f"Vocabulary {sk['vocabulary']}, {sk['per_candidate_mean']} skills per candidate "
        f"({sk['per_candidate_min']}-{sk['per_candidate_max']}). "
        f"Unmapped to a family: {sk['unmapped_to_family']}.",
        "",
        f"Tension = (demand share ÷ supply share), normalised so the market average is 1.0 "
        f"(raw baseline {sk['tension_baseline']}). Above 1.0 = the market wants it more than "
        f"the bench carries it. Observed spread: {sk['tension_spread'][0]}–{sk['tension_spread'][1]} "
        "— narrow, because the generator is close to uniform. On real data expect 0.2–5.",
        "",
        "| skill | family | supply | demand | tension |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for r in sk["highest_tension"]:
        out.append(f"| {r['skill']} | {r['family']} | {r['supply']:,} | {r['demand']:,.0f} | "
                   f"**{r['tension']:.2f}** |")
    out += ["", "Lowest tension — oversupplied on this bench:", "",
            "| skill | family | supply | demand | tension |", "| --- | --- | ---: | ---: | ---: |"]
    for r in sk["lowest_tension"]:
        out.append(f"| {r['skill']} | {r['family']} | {r['supply']:,} | {r['demand']:,.0f} | "
                   f"{r['tension']:.2f} |")

    out += [
        "",
        "## Pools",
        "",
        f"- Qualified candidates per opening: mean **{s['pools']['mean_qualified_pool']:,.0f}**, "
        f"range {s['pools']['min_qualified_pool']:,}–{s['pools']['max_qualified_pool']:,}",
        f"- Openings each candidate qualifies for: mean "
        f"{s['pools']['mean_qualified_for_per_candidate']:,.0f} of {c['openings']:,}",
        "",
        "> Both numbers are enormous because the vocabulary is only 73 skills wide and profiles",
        "> carry 5–8 of them. A real bench matched against real postings is far sparser.",
        "",
        "## Distributions",
        "",
        table(d["seniority"], "seniority", "candidates"),
        "",
        table(d["experience_band"], "experience", "candidates"),
        "",
        table(d["role_family"], "role family", "candidates"),
        "",
        table(d["industry"], "industry", "candidates"),
        "",
        table(d["education"], "education", "candidates"),
        "",
        "> Note how flat these are. That is the generator, not the labour market.",
        "",
    ]
    return "\n".join(out)


def bridge_analysis(skill_market: pd.DataFrame, german_postings: Path | None) -> dict:
    """Measure how much of the German demand this vocabulary can actually express."""
    def norm(x: str) -> str:
        return x.lower().replace(".", "").replace("/", "").replace(" ", "").replace("-", "")

    ours = {norm(k): k for k in ref.TECH_COMPILED}
    vocab = skill_market["skill"].tolist()
    overlapping = [v for v in vocab if norm(v) in ours]
    bridge = {ours[norm(v)] for v in overlapping}

    coverage, missing = None, []
    if german_postings and german_postings.exists():
        p = pd.read_parquet(german_postings, columns=["is_it_core", "technologies"])
        it = p[p["is_it_core"]]
        counts = Counter()
        for t in it["technologies"]:
            counts.update(t)
        with_bridge = sum(1 for t in it["technologies"] if any(x in bridge for x in t))
        coverage = round(100 * with_bridge / max(len(it), 1), 1)
        missing = [k for k, _ in counts.most_common(12) if k not in bridge][:8]

    return {
        "candidate_vocabulary": len(vocab),
        "overlapping_skills": len(overlapping),
        "overlap_pct": round(100 * len(overlapping) / max(len(vocab), 1)),
        "overlapping": sorted(overlapping),
        "german_it_coverage_pct": coverage if coverage is not None else "n/a",
        "missing_from_candidates": missing,
    }


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def run(root: Path, out_dir: Path, force: bool = False) -> dict:
    started = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)

    _log("[1/5] loading candidate dataset")
    paths = download(root / "data" / "raw", force=force)
    resumes = pd.read_parquet(paths["resumes"])
    jobs = pd.read_parquet(paths["jobs"])
    matches = pd.read_parquet(paths["matches"])
    _log(f"      {len(resumes):,} resumes · {len(jobs):,} openings · {len(matches):,} match records")

    _log("[2/5] parsing profiles and openings")
    candidates = parse_candidates(resumes)
    openings = parse_openings(jobs)

    _log("[3/5] recomputing qualified pools")
    matrix, index = skill_matrix(candidates)
    candidates, openings = compute_pools(candidates, openings, matrix, index)
    audit = audit_ground_truth(candidates, openings, matches, matrix, index)
    candidates["listed_for_openings"] = candidates["candidate_id"].map(
        audit["listed_counts"]
    ).fillna(0).astype(int)
    openings["listed_matches"] = openings["opening_id"].map(
        dict(zip(matches["job_id"], matches["relevant_resume_ids"].map(len)))
    ).fillna(0).astype(int)

    _log("[4/5] building skill and role markets")
    skill_market = build_skill_market(candidates, openings)
    role_market = build_role_market(candidates, openings)
    bridge = bridge_analysis(skill_market, out_dir / "postings.parquet")
    _log(f"      {len(skill_market)} skills · {len(role_market)} role cells · "
         f"bridge to German data: {bridge['overlap_pct']}% of vocabulary")

    _log("[5/5] writing outputs")
    candidates.to_parquet(out_dir / "candidates.parquet", index=False)
    openings.to_parquet(out_dir / "openings.parquet", index=False)
    skill_market.to_parquet(out_dir / "skill_market.parquet", index=False)
    role_market.to_parquet(out_dir / "role_market.parquet", index=False)

    report = build_report(candidates, openings, skill_market, role_market, audit, bridge,
                          round(time.time() - started, 2))
    (out_dir / "candidate_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out_dir / "candidate_report.md").write_text(render_report(report), encoding="utf-8")
    for name in ["candidates", "openings", "skill_market", "role_market", "candidate_report"]:
        _log(f"      {out_dir / name}.parquet" if name != "candidate_report"
             else f"      {out_dir / 'candidate_report.md'}")
    _log(f"done in {report['elapsed_s']}s")
    return report


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.candidates",
                                description="Parse the synthetic candidate dataset.")
    p.add_argument("--root", type=Path, default=root)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--force-download", action="store_true")
    args = p.parse_args(argv)
    run(args.root, args.out or (args.root / "data" / "processed"), args.force_download)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
