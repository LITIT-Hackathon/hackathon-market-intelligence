"""The scorer -- separate program from the parser, joined by postings.parquet.

    python -m opradar.score

Reads:   data/processed/postings.parquet, companies.parquet
Writes:  opportunities.parquet      ranked companies with full decomposition
         bench.parquet              synthetic bench (B3, German vocabulary)
         supply_index.parquet       P3 hand-off object
         market_pull.parquet        P4 German demand per RoleAtom cell
         people_value.parquet       P5 candidate ranking
         validation.json            V1-V3 + people checks
         score_report.md            human-readable summary

Every stage reads a file and writes a file; any stage re-runnable alone.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import bench_gen, market_pull, match, people_scoring, signals as signals_mod
from . import scoring as scoring_mod
from . import supply as supply_mod
from . import validate as validate_mod
from .config import CONFIG, config_hash


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(data_dir: Path) -> dict:
    started = time.time()

    _log("[1/7] loading parser output")
    postings = pd.read_parquet(data_dir / "postings.parquet")
    companies = pd.read_parquet(data_dir / "companies.parquet")

    _log("[2/7] signals (Pipeline A)")
    sig, eligible_pool = signals_mod.build(postings, companies)
    _log(f"      pool: {len(sig)} companies >= {CONFIG['min_it_postings']} eligible IT postings "
         f"({len(eligible_pool):,} postings)")

    _log("[3/7] bench + supply index (Pipeline B, B3)")
    bench = bench_gen.generate()
    supply_index = supply_mod.build(bench)
    _log(f"      bench {len(bench)} consultants -> {len(supply_index)} cells "
         f"({int(supply_index['thin_cell'].sum())} thin)")

    _log("[4/7] market pull from German postings (P4)")
    pull = market_pull.build(eligible_pool)

    _log("[5/7] match -> Serviceability (Pipeline C)")
    svc = match.serviceability(eligible_pool, bench)
    _log(f"      serviceability: mean {svc['serviceability'].mean():.2f}, "
         f"min {svc['serviceability'].min():.2f}, max {svc['serviceability'].max():.2f}")

    _log("[6/7] scoring")
    ranked = scoring_mod.score(sig, svc, eligible_pool)
    value, cells = people_scoring.score(bench, supply_index, pull)
    live = ranked[ranked["rank"].notna()]
    _log(f"      ranked {len(live)} companies "
         f"({int(ranked['excluded'].sum())} excluded by recency guard) "
         f"| config {config_hash()}")

    _log("[7/7] validation")
    checks = validate_mod.run_all(ranked, value, supply_index, bench)
    _log(f"      V1 rho={checks['companies']['v1_divergence']['spearman_vs_volume']} "
         f"| V2 {checks['companies']['v2_adversarial']['verdict']} "
         f"| V3 min overlap {checks['companies']['v3_sensitivity']['min_overlap']}/"
         f"{checks['companies']['v3_sensitivity']['top_k']}")

    # ---- write ----
    ranked.to_parquet(data_dir / "opportunities.parquet", index=False)
    bench.to_parquet(data_dir / "bench.parquet", index=False)
    supply_index.assign(tech_tags=supply_index["tech_tags"].map(json.dumps)) \
        .to_parquet(data_dir / "supply_index.parquet", index=False)
    cells.assign(tech_tags=cells["tech_tags"].map(json.dumps)) \
        .to_parquet(data_dir / "cells.parquet", index=False)
    pull.to_parquet(data_dir / "market_pull.parquet", index=False)

    # tech gap: eligible German postings mentioning each category vs bench
    # consultants holding the tag -- the B3 profile gap made visible
    from collections import Counter
    demand_c: Counter = Counter()
    for cats in eligible_pool["tech_categories"]:
        demand_c.update(list(cats) if cats is not None else [])
    bench_c: Counter = Counter()
    for tags in bench["tech_tags"]:
        bench_c.update(tags)
    gap = pd.DataFrame(
        [{"category": c,
          "demand_postings": int(demand_c.get(c, 0)),
          "bench_consultants": int(bench_c.get(c, 0))}
         for c in sorted(set(demand_c) | set(bench_c))]
    ).sort_values("demand_postings", ascending=False)
    gap.to_parquet(data_dir / "tech_gap.parquet", index=False)
    value.to_parquet(data_dir / "people_value.parquet", index=False)
    (data_dir / "validation.json").write_text(
        json.dumps(checks, indent=2, default=str), encoding="utf-8")
    (data_dir / "score_report.md").write_text(_report(ranked, value, checks), encoding="utf-8")

    _log(f"done in {time.time() - started:.1f}s -> {data_dir / 'opportunities.parquet'}")
    return checks


def _report(ranked: pd.DataFrame, value: pd.DataFrame, checks: dict) -> str:
    live = ranked[ranked["rank"].notna()]
    out = [
        "# Score report",
        "",
        f"Config `{config_hash()}`. {len(live)} companies ranked, "
        f"{int(ranked['excluded'].sum())} excluded by the recency guard.",
        "",
        "## Top 15 opportunities",
        "",
        "| # | company | class | opp | need | svc | conf | IT | >45d | >90d |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for r in live.head(15).itertuples():
        out.append(
            f"| {int(r.rank)} | {r.company_name} | {r.company_class} | **{r.opportunity}** "
            f"| {r.need} | {r.serviceability:.2f} | {r.confidence_band} "
            f"| {r.it_n} | {r.open_45} | {r.open_90} |")

    out += [
        "",
        "## Top 10 bench value (synthetic bench)",
        "",
        "| # | id | family | seniority | value | pull | scarcity | deploy |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in value.head(10).itertuples():
        out.append(
            f"| {int(r.rank)} | {r.candidate_id} | {r.role_family} | {r.seniority} "
            f"| **{r.value}** | {r.market_pull:.2f} | {r.scarcity:.2f} | {r.deployability:.2f} |")

    v = checks["companies"]
    out += [
        "",
        "## Validation",
        "",
        f"- **V1 divergence**: Spearman vs volume = {v['v1_divergence']['spearman_vs_volume']} "
        f"({v['v1_divergence']['verdict']})",
        f"- **V2 adversarial**: {v['v2_adversarial']['verdict']}",
        f"- **V3 sensitivity**: min top-{v['v3_sensitivity']['top_k']} overlap "
        f"{v['v3_sensitivity']['min_overlap']} across +-20% weight perturbations "
        f"({v['v3_sensitivity']['verdict']})",
        f"- **People V1**: value vs skill-count rho = "
        f"{checks['people']['value_vs_skill_count_spearman']} ({checks['people']['v1_verdict']})",
        f"- **Phantom supply tags**: {checks['people']['phantom_supply_tags']}",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.score")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    args = p.parse_args(argv)
    if not (args.data / "postings.parquet").exists():
        print("ERROR: run `python -m opradar` first.", file=sys.stderr)
        return 1
    run(args.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
