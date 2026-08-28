"""CLI entry point:  python -m opradar [options]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import Options, run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opradar",
        description="Parse the German job-postings dataset into clean postings + companies tables.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="project root (default: the repo containing this package)",
    )
    p.add_argument("--raw", type=Path, default=None, help="path to the raw parquet file")
    p.add_argument("--out", type=Path, default=None, help="output directory")
    p.add_argument(
        "--force-download", action="store_true", help="re-download the raw dataset"
    )
    p.add_argument(
        "--fuzzy",
        action="store_true",
        help="enable blocked fuzzy merging of company keys (off by default: "
        "over-merging invents companies that do not exist)",
    )
    p.add_argument(
        "--fuzzy-threshold", type=float, default=0.92, help="similarity cutoff (default 0.92)"
    )
    p.add_argument(
        "--loose-keys",
        action="store_true",
        help="also strip country/group qualifiers (Deutschland, Group, Holding) when "
        "grouping. Merges more, and sometimes merges wrongly.",
    )
    p.add_argument("--duckdb", action="store_true", help="also write a DuckDB database")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    opts = Options(
        root=args.root,
        raw_path=args.raw,
        out_dir=args.out,
        force_download=args.force_download,
        fuzzy=args.fuzzy,
        fuzzy_threshold=args.fuzzy_threshold,
        loose_keys=args.loose_keys,
        write_duckdb=args.duckdb,
    )
    try:
        run(opts)
    except Exception as exc:  # surface the actual problem, not a traceback wall
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
