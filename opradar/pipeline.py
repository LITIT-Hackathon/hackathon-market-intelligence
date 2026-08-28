"""Pipeline orchestration: raw dataset -> postings.parquet + companies.parquet + QA report."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import companies as companies_mod
from . import loading
from . import postings as postings_mod
from . import reference as ref
from . import report as report_mod


@dataclass
class Options:
    root: Path
    raw_path: Path | None = None
    out_dir: Path | None = None
    force_download: bool = False
    fuzzy: bool = False
    fuzzy_threshold: float = 0.92
    loose_keys: bool = False
    write_duckdb: bool = False
    stats: dict = field(default_factory=dict)

    @property
    def raw_file(self) -> Path:
        return self.raw_path or (self.root / "data" / "raw" / "german_job_postings.parquet")

    @property
    def output_dir(self) -> Path:
        return self.out_dir or (self.root / "data" / "processed")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(opts: Options) -> dict:
    started = time.time()
    opts.output_dir.mkdir(parents=True, exist_ok=True)

    # -- 1. load -------------------------------------------------------------
    _log("[1/6] loading raw dataset")
    loading.download(opts.raw_file, force=opts.force_download)
    raw = loading.load(opts.raw_file)
    _log(f"      {len(raw):,} raw rows, {len(raw.columns)} columns")

    # -- 2. parse postings ---------------------------------------------------
    _log("[2/6] parsing postings")
    df = postings_mod.parse(raw)
    _log(
        f"      {int(df['is_it_core'].sum()):,} IT postings (KldB 43x) "
        f"| {int(df['has_tech_signal'].sum()):,} with a tech signal in the title"
    )

    # -- 3. resolve companies ------------------------------------------------
    _log("[3/6] resolving company entities")
    keys = companies_mod.build_keys(df["employer_raw"])
    df = df.merge(keys, on="employer_raw", how="left")

    raw_distinct = int(df["employer_raw"].nunique())
    key_column = "company_key_loose" if opts.loose_keys else "company_key"
    df["company_key"] = df[key_column]

    merges: list = []
    if opts.fuzzy:
        weights = df["company_key"].value_counts().to_dict()
        mapping, merges = companies_mod.fuzzy_merge(
            df[["company_key"]].drop_duplicates(),
            weights=weights,
            threshold=opts.fuzzy_threshold,
        )
        df["company_key"] = df["company_key"].map(lambda k: mapping.get(k, k))
        _log(f"      fuzzy merge joined {len(merges)} key pairs")

    # Drop rows we cannot attribute to any employer.
    unattributed = int(df["company_key"].isna().sum() + (df["company_key"] == "").sum())
    df = df[df["company_key"].notna() & (df["company_key"] != "")].copy()

    resolved = int(df["company_key"].nunique())
    _log(f"      {raw_distinct:,} raw employer strings -> {resolved:,} entities "
         f"({unattributed} rows unattributed)")

    # -- 4. aggregate companies ----------------------------------------------
    _log("[4/6] aggregating and classifying companies")
    companies = companies_mod.build(df)
    name_lookup = companies.set_index("company_key")["company_name"]
    class_lookup = companies.set_index("company_key")["company_class"]
    competitor_lookup = companies.set_index("company_key")["is_competitor"]

    df["company_name"] = df["company_key"].map(name_lookup)
    df["company_class"] = df["company_key"].map(class_lookup)
    df["is_competitor_posting"] = df["company_key"].map(competitor_lookup).fillna(False)

    class_counts = companies["company_class"].value_counts().to_dict()
    _log("      " + " | ".join(f"{k}: {v:,}" for k, v in class_counts.items()))

    # -- 5. write ------------------------------------------------------------
    _log("[5/6] writing outputs")
    out_cols = [c for c in postings_mod.OUTPUT_COLUMNS if c in df.columns]
    out_cols += ["company_class", "is_competitor_posting"]
    postings_out = df[out_cols].copy()

    postings_path = opts.output_dir / "postings.parquet"
    companies_path = opts.output_dir / "companies.parquet"
    postings_out.to_parquet(postings_path, index=False)
    companies.to_parquet(companies_path, index=False)
    _log(f"      {postings_path}  ({len(postings_out):,} rows)")
    _log(f"      {companies_path}  ({len(companies):,} rows)")

    if opts.write_duckdb:
        _write_duckdb(opts.output_dir, postings_out, companies)

    # -- 6. report -----------------------------------------------------------
    _log("[6/6] building QA report")
    stats = report_mod.build_stats(
        raw=raw,
        postings=postings_out,
        companies=companies,
        raw_distinct_employers=raw_distinct,
        resolved_entities=resolved,
        unattributed_rows=unattributed,
        fuzzy_merges=merges,
        options=opts,
        elapsed_s=round(time.time() - started, 2),
    )

    (opts.output_dir / "parse_report.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8"
    )
    (opts.output_dir / "parse_report.md").write_text(
        report_mod.render_markdown(stats), encoding="utf-8"
    )
    _log(f"      {opts.output_dir / 'parse_report.md'}")
    _log(f"done in {stats['elapsed_s']}s")
    return stats


def _write_duckdb(out_dir: Path, postings: pd.DataFrame, companies: pd.DataFrame) -> None:
    try:
        import duckdb
    except ImportError:
        _log("      duckdb not installed -- skipping (pip install duckdb)")
        return

    db_path = out_dir / "opradar.duckdb"
    con = duckdb.connect(str(db_path))
    con.register("postings_df", postings)
    con.register("companies_df", companies)
    con.execute("CREATE OR REPLACE TABLE postings AS SELECT * FROM postings_df")
    con.execute("CREATE OR REPLACE TABLE companies AS SELECT * FROM companies_df")
    con.close()
    _log(f"      {db_path}")
