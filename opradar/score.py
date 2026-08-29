"""The scorer -- a separate program from the parser, joined by two parquet files.

    python -m opradar.balive        # optional: today's board (network, cached)
    python -m opradar.score         # deterministic, offline

Reads:   postings.parquet, companies.parquet   [parser]
         ba_live.parquet                       [optional, opradar.balive]
         liveness.parquet                      [optional, opradar.liveness]
         data/curated_segments.csv             [optional, hand-reviewed labels]

Writes:  segments.parquet          who is a prospect, who is a channel, and why
         opportunities.parquet     Algorithm A: ranked companies, decomposed
         cells.parquet             Layer C: opportunity-weighted demand per cell
         capability_plan.parquet   Algorithm B1: where to build capacity
         people_value.parquet      Algorithm B2: marginal value per consultant
         supply_index.parquet      bench depth per cell
         bench.parquet             the synthetic bench itself
         validation.json           V1-V7
         score_report.md           human-readable summary

Every stage reads a file and writes a file, so any stage is re-runnable alone
and a broken run costs yesterday's data rather than the demo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import bench_gen, eligibility, features, liveness, match, people
from . import scoring as scoring_mod
from . import validate as validate_mod
from .config import CONFIG, config_hash


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _load_optional(path: Path):
    return pd.read_parquet(path) if path.exists() else None


def run(data_dir: Path, root: Path, *, validate: bool = True) -> dict:
    started = time.time()

    _log("[1/7] loading parser output")
    postings = pd.read_parquet(data_dir / "postings.parquet")
    companies = pd.read_parquet(data_dir / "companies.parquet")

    ba = _load_optional(data_dir / "ba_live.parquet")
    if ba is None:
        _log("      no ba_live.parquet -- snapshot-only signals "
             "(run `python -m opradar.balive` for agency ground truth and real flow)")
    else:
        _log(f"      live board: {int(ba['ba_matched'].sum()):,} of {len(ba):,} "
             f"companies matched today")

    _log("[2/7] eligibility")
    curated = eligibility.load_curated(root / "data" / "curated_segments.csv")
    segments = eligibility.classify(companies, ba, curated)
    seg_counts = segments["segment"].value_counts().to_dict()
    _log("      " + " | ".join(f"{k}: {v:,}" for k, v in seg_counts.items()))
    if len(curated):
        _log(f"      {len(curated)} curated labels applied")

    _log("[3/7] features")
    feats, pool = features.build(postings, companies, segments, ba)
    # evidence-only: nothing downstream of here scores on it, but the UI
    # timeline needs to know which of these ads have since been taken down
    pool = liveness.attach(pool, data_dir)
    if "alive" in pool:
        checked = int(pool["alive"].notna().sum())
        if checked:
            _log(f"      liveness: {int((pool['alive'] == True).sum()):,} of {checked:,} "  # noqa: E712
                 f"re-checked vacancies still published")
    _log(f"      pool: {len(feats)} companies with >= {CONFIG['min_it_postings']} "
         f"eligible IT vacancies ({len(pool):,} vacancies)")
    if "live_verified" in feats:
        _log(f"      live-verified: {int(feats['live_verified'].sum())} companies")

    _log("[4/7] bench + serviceability (Layer C)")
    bench = bench_gen.generate()
    svc = match.serviceability(pool, bench)
    _log(f"      serviceability: mean {svc['serviceability'].mean():.2f}, "
         f"min {svc['serviceability'].min():.2f}, max {svc['serviceability'].max():.2f}")

    _log("[5/7] Algorithm A -- company opportunity")
    ranked = scoring_mod.score(feats, svc, pool)
    _log(f"      {len(ranked)} companies ranked | config {config_hash()}")

    _log("[6/7] Algorithm B -- capability plan and people")
    cells = match.cell_demand(pool, ranked, bench)
    plan = people.capability_plan(cells)
    value = people.person_value(bench, pool, ranked)
    supply = people.supply_index(bench)
    _log(f"      {len(cells)} demand cells, {len(bench)} consultants, "
         f"{int(supply['thin_cell'].sum())} thin bench cells")

    if validate:
        _log("[7/7] validation")
        checks = validate_mod.run_all(ranked, feats, svc, pool, value, cells,
                                      postings, companies, segments, ba, bench)
        c = checks["companies"]
        _log(f"      V1 rho={c['v1_divergence']['spearman_vs_it_postings']} "
             f"| V2 {c['v2_adversarial']['verdict']} "
             f"| V3 {c['v3_sensitivity']['min_overlap']}/{c['v3_sensitivity']['top_k']} "
             f"| V4 {c.get('v4_jackknife', {}).get('min_overlap', '-')}/"
             f"{c.get('v4_jackknife', {}).get('top_k', '-')}")
    else:
        # V4 alone re-derives features and re-matches the bench three times.
        # Worth every second before anyone trusts a number; pure overhead while
        # iterating on the model itself, which is what --quick is for.
        checks = {"companies": {}, "people": {}}
        _log("[7/7] validation SKIPPED (--quick) -- rankings are unverified")

    # ---- write ----
    def _jsonify(df, col):
        return df.assign(**{col: df[col].map(json.dumps)})

    segments.to_parquet(data_dir / "segments.parquet", index=False)
    ranked.drop(columns=["tech_counts", "families"], errors="ignore") \
          .assign(top_technologies=ranked["top_technologies"].map(json.dumps),
                  tech_mix=ranked["tech_counts"].map(json.dumps),
                  role_mix=ranked["families"].map(json.dumps)) \
          .to_parquet(data_dir / "opportunities.parquet", index=False)
    cells.to_parquet(data_dir / "cells.parquet", index=False)
    plan.to_parquet(data_dir / "capability_plan.parquet", index=False)
    _jsonify(value, "tech_tags").assign(languages=value["languages"].map(json.dumps)) \
        .to_parquet(data_dir / "people_value.parquet", index=False)
    _jsonify(supply, "tech_tags").to_parquet(data_dir / "supply_index.parquet", index=False)
    _jsonify(bench, "tech_tags").assign(languages=bench["languages"].map(json.dumps)) \
        .to_parquet(data_dir / "bench.parquet", index=False)
    if validate:
        (data_dir / "validation.json").write_text(
            json.dumps(checks, indent=2, default=str), encoding="utf-8")
    else:
        _log("      kept the previous validation.json rather than blanking it")
    (data_dir / "score_report.md").write_text(
        report(ranked, plan, value, checks, segments), encoding="utf-8")

    _log(f"done in {time.time() - started:.1f}s -> {data_dir / 'opportunities.parquet'}")
    return checks


# ---------------------------------------------------------------------------

def report(ranked: pd.DataFrame, plan: pd.DataFrame, value: pd.DataFrame,
           checks: dict, segments: pd.DataFrame) -> str:
    c = checks.get("companies") or {}
    out = [
        "# Score report",
        "",
        f"Config `{config_hash()}`. {len(ranked)} companies ranked.",
        "",
        "`opportunity` is a **percentile within this pool** -- 87 means ahead of "
        "87% of the eligible German companies we can see. There are no labels, "
        "so no absolute calibration exists and claiming one would be false "
        "precision. `pressure` is the underlying weighted geometric mean.",
        "",
        "## Top 15 opportunities",
        "",
        "| # | company | segment | opp | conf | IT ads | open >1m | live now | signals |",
        "| ---: | --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in ranked.head(15).itertuples():
        drivers = sorted(
            ((n, getattr(r, f"contrib_{n}")) for n in scoring_mod.SIGNALS),
            key=lambda kv: kv[1], reverse=True)[:2]
        # nullable Int64: pd.NA == pd.NA is NA, not False, so the usual
        # self-comparison NaN idiom raises instead of falling through
        aged = r.now_aged_open if pd.notna(r.now_aged_open) else "-"
        stock = r.now_it_stock if pd.notna(r.now_it_stock) else "-"
        out.append(
            f"| {int(r.rank)} | {r.company_name} | {r.segment}"
            f"{'' if r.segment_verified else ' *(unverified)*'} | **{r.opportunity}** "
            f"| {r.confidence_band} | {r.it_n} | {aged} | {stock} "
            f"| {', '.join(n for n, _ in drivers)} |")

    out += ["", "## Bottom 5 -- and why", "",
            "| # | company | opp | weakest signal |",
            "| ---: | --- | ---: | --- |"]
    for r in ranked.tail(5).itertuples():
        weakest = min(((n, getattr(r, f"{n}_eff")) for n in scoring_mod.SIGNALS),
                      key=lambda kv: kv[1])
        out.append(f"| {int(r.rank)} | {r.company_name} | {r.opportunity} "
                   f"| {weakest[0]} = {weakest[1]:.2f} |")

    out += ["", "## Segments", "",
            "| segment | companies | verified |", "| --- | ---: | ---: |"]
    for seg, grp in segments.groupby("segment"):
        out.append(f"| {seg} | {len(grp):,} | {int(grp['segment_verified'].sum()):,} |")

    out += ["", "## Algorithm B -- top capability gaps", "",
            "| # | cell | demand | coverage gap | bench depth |",
            "| ---: | --- | ---: | ---: | ---: |"]
    for r in plan.head(10).itertuples():
        out.append(f"| {int(r.priority_rank)} | {r.role_family} / {r.seniority} / "
                   f"{r.tech_tag} | {r.demand_weight:.1f} | {r.coverage_gap:.2f} "
                   f"| {r.supply_depth:.0f} |")

    out += ["", "## Algorithm B -- top consultants by marginal value "
            "(synthetic bench)", "",
            "| # | id | family | seniority | avail | value | unique | atoms |",
            "| ---: | --- | --- | --- | --- | ---: | ---: | ---: |"]
    for r in value.head(10).itertuples():
        out.append(f"| {int(r.rank)} | {r.candidate_id} | {r.role_family} | "
                   f"{r.seniority} | {r.availability} | **{r.value}** "
                   f"| {r.uniqueness:.2f} | {r.atoms_matched} |")

    out += ["", "## Validation", ""]
    if not c:
        out.append("**Not run** -- this build used `--quick`. Nothing here has been "
                   "checked for weight sensitivity or single-vacancy fragility; "
                   "re-run `python -m opradar.score` before trusting it.")
    else:
        for name, res in c.items():
            out.append(f"- **{name}**: {res.get('verdict', '')} "
                       f"`{json.dumps({k: v for k, v in res.items() if k not in ('note',)})[:220]}`")
        p = checks["people"]
        out.append(f"- **v7_people**: {p['verdict']} -- value vs skill count "
                   f"rho={p['value_vs_skill_count_spearman']}, vs uniqueness "
                   f"rho={p['value_vs_uniqueness_spearman']}")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.score")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--root", type=Path, default=root)
    p.add_argument("--quick", action="store_true",
                   help="skip V1-V7 for a fast iteration loop "
                        "(~5s instead of ~13s); leaves validation.json untouched")
    args = p.parse_args(argv)
    if not (args.data / "postings.parquet").exists():
        print("ERROR: run `python -m opradar` first.", file=sys.stderr)
        return 1
    run(args.data, args.root, validate=not args.quick)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
