"""Enrichment -- everything the job board tells us that we were throwing away.

    python -m opradar.enrich harvest     # network, cached, no AI, no cloud
    python -m opradar.enrich extract     # Gemini over the harvested text (Vertex)

`opradar.liveness` already asks the board about every posting in the pool:

    GET .../pc/v4/jobdetails/{base64(refnr)}      X-API-Key: jobboerse-jobsuche

and reads the HTTP status code. The body of that same response carries [measured]
5,676 characters of advertisement text plus a dozen fields the parser never saw,
including three the scorer currently has to GUESS at:

  istArbeitnehmerUeberlassung   the board's own labour-leasing flag. We infer
                                agency status from company-name rules today.
  arbeitgeberKundennummerHash   a stable employer identity. Without it "BMW AG"
                                and "BMW Group" rank separately off split
                                evidence -- [measured] #3 and #72.
  aenderungsdatum               when the advertiser last TOUCHED the ad. An ad
                                first published in June and edited in July is a
                                company still fighting to fill it; posting age
                                alone cannot tell that from an abandoned listing.

So `harvest` costs nothing we were not already spending and needs no model at
all. `extract` then runs Gemini over the harvested descriptions to recover the
things no rule can read: [measured] 52% of IT postings have no technology tag
because the parser only ever had a job TITLE to match against.

Both phases follow the same contract as the parser, `balive` and `liveness`:
a separate program, cached to parquet, read by the scorer as an artifact.
No model is ever called from the scoring path, so the score stays offline,
deterministic and reproducible from its config hash.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "X-API-Key": "jobboerse-jobsuche",
    "Accept": "application/json",
}

DEAD_STATUSES = {404, 410}

# Same reasoning as liveness.DEFAULT_TTL_DAYS: this is an evidence layer, not a
# scoring parameter, so it stays out of CONFIG and out of the config hash.
DEFAULT_TTL_DAYS = 7.0

CACHE_NAME = "details.parquet"

# The response fields worth keeping, and the names we give them. Everything
# else in the payload is either already in postings.parquet or is board
# plumbing (allianzpartner*, istBetreut, chiffrenummer).
FIELDS = {
    "stellenangebotsBeschreibung": "description",
    "stellenangebotsTitel": "title_source",
    "firma": "firm_name",
    "arbeitgeberKundennummerHash": "employer_hash",
    "istArbeitnehmerUeberlassung": "is_anue",
    "istPrivateArbeitsvermittlung": "is_private_agency",
    "datumErsteVeroeffentlichung": "first_published",
    "aenderungsdatum": "last_modified",
    "vertragsdauer": "contract_duration",
    "verguetungsangabe": "pay_note",
    "homeofficemoeglich": "remote_ok",
    "homeofficetyp": "remote_type",
    "arbeitszeitVollzeit": "full_time",
    "hauptberuf": "occupation_main",
    "alternativBeruf1": "occupation_alt1",
    "alternativBeruf2": "occupation_alt2",
    "quereinstiegGeeignet": "career_changer_ok",
}


# ---------------------------------------------------------------------------
# harvest -- phase A, free ground truth
# ---------------------------------------------------------------------------

def parse_detail(payload: dict) -> dict:
    """Flatten one jobdetails response into the columns we keep."""
    row: dict = {}
    for src, dst in FIELDS.items():
        row[dst] = payload.get(src)

    # start date sits one level down and is the closest thing the board gives
    # us to urgency -- "wanted from last month" reads differently to "from Q1"
    ez = payload.get("eintrittszeitraum")
    row["start_date"] = ez.get("von") if isinstance(ez, dict) else None

    # first location only: a posting listed in three cities is one vacancy the
    # advertiser is flexible about, not three, and the pool already carries the
    # parser's own region_clean for the aggregate view
    locs = payload.get("stellenlokationen")
    if isinstance(locs, list) and locs:
        adr = locs[0].get("adresse") or {}
        row["plz"] = adr.get("plz")
        row["ort"] = adr.get("ort")
        row["location_n"] = len(locs)
    else:
        row["plz"] = row["ort"] = None
        row["location_n"] = 0

    row["description_chars"] = len(row["description"] or "")
    return row


def fetch_one(refnr: str, timeout: float = 12.0, retries: int = 1
              ) -> tuple[str, int | None, dict | None]:
    """One posting -> (refnr, status, parsed body or None).

    404/410 is a real answer -- the advertisement is gone and there is no body
    to read. Anything else gets one polite retry before we record it as unknown,
    exactly as liveness does, so a flaky minute never turns into a dead ad.
    """
    url = API + base64.b64encode(refnr.encode()).decode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
                return refnr, resp.status, parse_detail(body)
        except urllib.error.HTTPError as e:
            if e.code in DEAD_STATUSES:
                return refnr, e.code, None
            if attempt < retries:
                time.sleep(1.0 + attempt)
                continue
            return refnr, e.code, None
        except Exception:
            if attempt < retries:
                time.sleep(1.0 + attempt)
                continue
            return refnr, None, None
    return refnr, None, None


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    cols = ["refnr", "status", "fetched_at"] + list(FIELDS.values()) + [
        "start_date", "plz", "ort", "location_n", "description_chars"]
    return pd.DataFrame(columns=cols)


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """Columns the board implies but does not state.

    `refresh_days` is the gap between first publication and the last edit. It
    is the one field here that is genuinely new information about DEMAND rather
    than about the advertisement: an employer who came back and touched the ad
    six weeks in is an employer who still has not filled the role and knows it.
    Posting age cannot distinguish that from a listing nobody has looked at
    since it went up.
    """
    out = df.copy()
    first = pd.to_datetime(out.get("first_published"), errors="coerce", utc=True)
    last = pd.to_datetime(out.get("last_modified"), errors="coerce", utc=True)
    out["refresh_days"] = (last - first).dt.days
    out["was_refreshed"] = (out["refresh_days"].fillna(0) > 0)
    return out


def harvest(data_dir: Path, root: Path, all_eligible: bool = False,
            ttl_days: float | None = None, concurrency: int = 12,
            limit: int | None = None, timeout: float = 12.0) -> pd.DataFrame:
    from . import eligibility, liveness

    ttl_days = DEFAULT_TTL_DAYS if ttl_days is None else ttl_days
    postings = pd.read_parquet(data_dir / "postings.parquet")
    companies = pd.read_parquet(data_dir / "companies.parquet")
    ba_path = data_dir / "ba_live.parquet"
    ba = pd.read_parquet(ba_path) if ba_path.exists() else None
    segments = eligibility.classify(
        companies, ba, eligibility.load_curated(root / "data" / "curated_segments.csv"))

    # identical scope to liveness: IT vacancies at companies we would rank, so
    # we never spend a request on an agency that can never be a prospect
    refnrs = liveness.scope_refnrs(postings, segments, all_eligible)

    cache_path = data_dir / CACHE_NAME
    cache = load_cache(cache_path)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ttl_days)
    if len(cache):
        seen_at = pd.to_datetime(cache["fetched_at"], utc=True, errors="coerce")
        # a 404 is settled -- an advertisement does not come back from the dead,
        # so it never needs re-fetching whatever the TTL says
        settled = cache["status"].isin(DEAD_STATUSES)
        fresh = set(cache.loc[(seen_at >= cutoff) | settled, "refnr"])
    else:
        fresh = set()

    todo = [r for r in refnrs if r not in fresh]
    if limit:
        todo = todo[:limit]
    print(f"scope {len(refnrs):,} postings | cached {len(refnrs) - len(todo):,} "
          f"| fetching {len(todo):,} (concurrency {concurrency})", file=sys.stderr)

    rows, started = [], time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for i, (refnr, status, parsed) in enumerate(
                ex.map(lambda r: fetch_one(r, timeout), todo), 1):
            row = {"refnr": refnr, "status": status, "fetched_at": now.isoformat()}
            if parsed:
                row.update(parsed)
            rows.append(row)
            if i % 250 == 0:
                got = sum(1 for r in rows if r.get("description"))
                print(f"  {i:,}/{len(todo):,}  bodies {got:,} "
                      f"({time.time() - started:.0f}s)", file=sys.stderr)

    new = pd.DataFrame(rows)
    if len(new):
        merged = pd.concat(
            [cache[~cache["refnr"].isin(set(new["refnr"]))], new], ignore_index=True)
    else:
        merged = cache
    merged = derive(merged)
    merged.to_parquet(cache_path, index=False)

    scope = merged[merged["refnr"].isin(set(refnrs))]
    bodies = int(scope["description"].notna().sum()) if "description" in scope else 0
    gone = int(scope["status"].isin(DEAD_STATUSES).sum()) if len(scope) else 0
    print(f"done in {time.time() - started:.0f}s -> {cache_path}", file=sys.stderr)
    print(f"pool: {bodies:,} descriptions | {gone:,} delisted (no body) "
          f"| {len(refnrs) - bodies - gone:,} unknown", file=sys.stderr)
    if bodies:
        anue = int(scope["is_anue"].fillna(False).astype(bool).sum())
        refreshed = int(scope["was_refreshed"].fillna(False).astype(bool).sum())
        chars = int(scope["description_chars"].fillna(0).sum())
        print(f"ground truth: {anue:,} Arbeitnehmerueberlassung | "
              f"{refreshed:,} re-touched by the advertiser | "
              f"{chars / 1e6:.1f}M characters of ad text", file=sys.stderr)
    return merged


# ---------------------------------------------------------------------------
# attach -- how the rest of the pipeline reads this
# ---------------------------------------------------------------------------

ATTACH_COLS = ["description", "employer_hash", "is_anue", "is_private_agency",
               "contract_duration", "remote_ok", "remote_type", "start_date",
               "occupation_main", "refresh_days", "was_refreshed",
               "description_chars", "plz", "ort"]


def attach(pool: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    """Add the harvested columns to an eligible pool, from cache.

    Absent cache leaves every column null and the caller simply sees an
    un-enriched pool, exactly as `liveness.attach` behaves. Nothing here is
    required for the scorer to run.
    """
    out = pool.copy()
    path = data_dir / CACHE_NAME
    if not path.exists() or not len(pool):
        for c in ATTACH_COLS:
            out[c] = pd.NA
        return out
    d = pd.read_parquet(path)
    keep = ["refnr"] + [c for c in ATTACH_COLS if c in d.columns]
    d = d[keep].drop_duplicates("refnr")
    out = out.merge(d, left_on="posting_id", right_on="refnr", how="left") \
             .drop(columns=["refnr"])
    for c in ATTACH_COLS:
        if c not in out.columns:
            out[c] = pd.NA
    return out


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.enrich")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="fetch job-ad bodies from the board (no AI)")
    h.add_argument("--data", type=Path, default=root / "data" / "processed")
    h.add_argument("--root", type=Path, default=root)
    h.add_argument("--all", action="store_true",
                   help="every eligible IT posting, not just rankable companies")
    h.add_argument("--ttl-days", type=float, default=None)
    h.add_argument("--concurrency", type=int, default=12)
    h.add_argument("--limit", type=int, default=None)
    h.add_argument("--timeout", type=float, default=12.0)

    e = sub.add_parser("extract", help="Gemini over the harvested descriptions")
    e.add_argument("--data", type=Path, default=root / "data" / "processed")
    e.add_argument("--root", type=Path, default=root)
    e.add_argument("--limit", type=int, default=None)
    e.add_argument("--model", default="gemini-2.5-flash")
    e.add_argument("--project", default=None)
    e.add_argument("--location", default="europe-west4")
    e.add_argument("--concurrency", type=int, default=8)

    args = p.parse_args(argv)
    if not (args.data / "postings.parquet").exists():
        print("ERROR: run `python -m opradar` first.", file=sys.stderr)
        return 1

    if args.cmd == "harvest":
        harvest(args.data, args.root, all_eligible=args.all, ttl_days=args.ttl_days,
                concurrency=args.concurrency, limit=args.limit, timeout=args.timeout)
        return 0

    from . import extract as extract_mod
    return extract_mod.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
