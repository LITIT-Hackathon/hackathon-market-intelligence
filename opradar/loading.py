"""Fetch and load the raw dataset."""

from __future__ import annotations

import ssl
import sys
import urllib.request
from pathlib import Path

import pandas as pd

PARQUET_URL = (
    "https://huggingface.co/datasets/mischeiwiller/german-job-postings/"
    "resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"
)

EXPECTED_COLUMNS = {
    "id", "source", "source_url", "license", "provenance", "fetched_at",
    "posted_date", "lang", "title", "employer", "description_derived",
    "region", "nuts_code", "esco_occupation", "esco_skills", "is_green",
    "kldb_2010", "seniority", "salary_range",
}


def download(dest: Path, force: bool = False) -> Path:
    """Download the dataset parquet if it is not already cached."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest

    print(f"  downloading {PARQUET_URL}", file=sys.stderr)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(PARQUET_URL, headers={"User-Agent": "opradar/0.1"})
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp, open(tmp, "wb") as fh:
        while chunk := resp.read(1 << 16):
            fh.write(chunk)
    tmp.replace(dest)
    print(f"  saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)", file=sys.stderr)
    return dest


def load(path: Path) -> pd.DataFrame:
    """Load the raw parquet and sanity-check its shape."""
    df = pd.read_parquet(path)

    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"dataset schema changed -- missing columns: {sorted(missing)}. "
            "Update opradar/loading.py and opradar/postings.py before continuing."
        )

    extra = set(df.columns) - EXPECTED_COLUMNS
    if extra:
        print(f"  note: unexpected extra columns present: {sorted(extra)}", file=sys.stderr)

    return df
