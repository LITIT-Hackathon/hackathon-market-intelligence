"""Liveness check -- is a posting still published on arbeitsagentur.de?

    python -m opradar.liveness              # check the scoring pool (~2.3k)
    python -m opradar.liveness --all        # every eligible posting (~4.3k)

The dataset is a single snapshot; by scoring time a large share of its ads are
already gone. This module asks the same API the jobsuche SPA uses:

    GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service
        /pc/v4/jobdetails/{base64(refnr)}         X-API-Key: jobboerse-jobsuche

    200       -> alive (still published)
    404 / 410 -> dead  (delisted: filled or withdrawn)
    anything else / network error -> unknown (never overwrites a known state)

Results are cached in data/processed/liveness.parquet with a checked_at
timestamp; re-runs only re-check entries older than the TTL, so the scorer
stays deterministic between checks and a re-run costs seconds, not minutes.

Kept OUT of `python -m opradar.score` on purpose: the scorer must stay
offline-deterministic. It reads liveness.parquet if present, full stop.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .config import CONFIG

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "X-API-Key": "jobboerse-jobsuche",
    "Accept": "application/json",
}

DEAD_STATUSES = {404, 410}


def classify(status: int | None) -> bool | None:
    """HTTP status -> alive / dead / unknown (None)."""
    if status == 200:
        return True
    if status in DEAD_STATUSES:
        return False
    return None


def check_one(refnr: str, timeout: float = 10.0, retries: int = 1) -> tuple[str, int | None]:
    url = API + base64.b64encode(refnr.encode()).decode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return refnr, resp.status
        except urllib.error.HTTPError as e:
            if e.code in DEAD_STATUSES or e.code == 200:
                return refnr, e.code
            if attempt < retries:          # 403/429/5xx: one polite retry
                time.sleep(1.0 + attempt)
                continue
            return refnr, e.code
        except Exception:
            if attempt < retries:
                time.sleep(1.0 + attempt)
                continue
            return refnr, None
    return refnr, None


def scope_refnrs(postings: pd.DataFrame, all_eligible: bool = False) -> list[str]:
    """The postings whose liveness can move a score: the eligible pool of
    companies with enough IT postings to be ranked (no age cap here -- the
    check is exactly what can rescue an old-but-alive posting from the cap)."""
    from . import signals as sig
    elig = sig.eligible_postings(postings)
    if all_eligible:
        return elig["posting_id"].dropna().unique().tolist()
    counts = elig.groupby("company_key").size()
    keys = set(counts[counts >= CONFIG["min_it_postings"]].index)
    return elig.loc[elig["company_key"].isin(keys), "posting_id"].dropna().unique().tolist()


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=["refnr", "alive", "status", "checked_at"])


def run(data_dir: Path, all_eligible: bool = False, ttl_days: float | None = None,
        concurrency: int = 12, limit: int | None = None, timeout: float = 10.0) -> pd.DataFrame:
    ttl_days = CONFIG["liveness"]["ttl_days"] if ttl_days is None else ttl_days
    postings = pd.read_parquet(data_dir / "postings.parquet")
    refnrs = scope_refnrs(postings, all_eligible)

    cache_path = data_dir / "liveness.parquet"
    cache = load_cache(cache_path)
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=ttl_days)
    checked_at = pd.to_datetime(cache["checked_at"], utc=True, errors="coerce")
    fresh = set(cache.loc[(checked_at >= fresh_cutoff) & cache["alive"].notna(), "refnr"])

    todo = [r for r in refnrs if r not in fresh]
    if limit:
        todo = todo[:limit]
    print(f"scope {len(refnrs):,} postings | cached fresh {len(refnrs) - len(todo):,} "
          f"| checking {len(todo):,} (concurrency {concurrency})", file=sys.stderr)

    results: list[tuple[str, int | None]] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for i, res in enumerate(ex.map(lambda r: check_one(r, timeout), todo), 1):
            results.append(res)
            if i % 250 == 0:
                alive_n = sum(1 for _, st in results if classify(st) is True)
                print(f"  {i:,}/{len(todo):,}  alive so far {alive_n:,} "
                      f"({time.time() - started:.0f}s)", file=sys.stderr)

    new = pd.DataFrame(
        [{"refnr": r, "alive": classify(st), "status": st,
          "checked_at": now.isoformat()} for r, st in results])

    if len(new):
        # unknown results never overwrite a known alive/dead state
        known = new[new["alive"].notna()]
        unknown = new[new["alive"].isna()]
        unknown = unknown[~unknown["refnr"].isin(set(cache["refnr"]))]
        merged = pd.concat([cache[~cache["refnr"].isin(set(known["refnr"]))], known, unknown],
                           ignore_index=True)
    else:
        merged = cache
    merged["alive"] = merged["alive"].astype("boolean")
    merged.to_parquet(cache_path, index=False)

    done = merged[merged["refnr"].isin(set(refnrs))]
    alive_n = int((done["alive"] == True).sum())      # noqa: E712 (nullable bool)
    dead_n = int((done["alive"] == False).sum())      # noqa: E712
    unk_n = len(refnrs) - alive_n - dead_n
    print(f"done in {time.time() - started:.0f}s -> {cache_path}", file=sys.stderr)
    print(f"pool liveness: {alive_n:,} alive | {dead_n:,} dead | {unk_n:,} unknown "
          f"({alive_n / max(1, alive_n + dead_n) * 100:.1f}% of checked still live)",
          file=sys.stderr)
    return merged


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.liveness")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--all", action="store_true", help="check every eligible posting")
    p.add_argument("--ttl-days", type=float, default=None)
    p.add_argument("--concurrency", type=int, default=12)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    args = p.parse_args(argv)
    if not (args.data / "postings.parquet").exists():
        print("ERROR: run `python -m opradar` first.", file=sys.stderr)
        return 1
    run(args.data, args.all, args.ttl_days, args.concurrency, args.limit, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
