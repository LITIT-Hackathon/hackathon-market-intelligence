"""Live evidence from the Bundesagentur job board -- the second snapshot.

    python -m opradar.balive            # candidate pool (companies with >=2 IT ads)
    python -m opradar.balive --all      # every company with >=1 eligible IT ad

WHY THIS STAGE EXISTS
    The shipped dataset is ONE crawl (2026-06-06). A single snapshot cannot
    distinguish "posted recently" from "still unfilled", and it cannot measure
    hiring flow at all -- the monthly counts in it are a survival curve, not a
    demand curve (RESEARCH.md 3.1). Every velocity or acceleration claim built
    on `posted_date` alone is therefore backwards.

    The same public API the dataset came from is still live. Querying it today
    gives a SECOND observation of the same companies, which turns three guesses
    into measurements:

    1. AGENCY GROUND TRUTH.  Each offer carries `pav` (private placement) and
       `zeitarbeit` (labour leasing) flags, and every employer carries a
       `branche` (industry) code. Name-regex classification is replaced by the
       source's own labels. This is the highest-value field here: without it
       the leaderboard fills with recruitment agencies and IT vendors.

    2. REAL FLOW.  `veroeffentlichtseit` buckets give offers published in the
       last 7 / 28 days per employer. Flow against stock is a genuine hiring
       velocity measure, immune to the snapshot's survivorship bias.

    3. REAL STOCK NOW.  What the company still has open today, and what it has
       opened since the snapshot.

WHAT IT COSTS
    Two GET requests per company, ~0.2 s each, cached to disk with a TTL. The
    scorer never calls this module -- it reads the parquet if present and falls
    back to snapshot-only signals if absent, so scoring stays offline and
    deterministic (ALGORITHM.md 8, rule 1).

CAVEATS THAT MUST TRAVEL WITH THE OUTPUT
    - `arbeitgeber` is an EXACT-STRING filter. We try each observed name variant
      and keep the best hit; a company whose BA employer string has since
      changed reads as zero. Zero live offers is therefore "not found", not
      "stopped hiring" -- `ba_matched` distinguishes the two.
    - Facet counts cover the employer's WHOLE portfolio (all occupations). The
      berufsfeld facet is used to carve out the IT slice.
    - This is a second point in time, not a time series. It supports "more or
      less than in June", not a trend line.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "Mozilla/5.0 (compatible; OpRadar/1.0; research)",
    "Accept": "application/json",
}
# BA's certificate chain is incomplete, so verification has to be off for the
# request to complete at all. Read-only public data, no credentials sent.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# berufsfeld facet labels that constitute "IT" on the BA taxonomy. Measured
# 2026-08-29: these four carry ~23k of ~820k live offers.
IT_BERUFSFELDER = {
    "Informatik",
    "IT-Netzwerktechnik, -Administration, -Organisation",
    "Softwareentwicklung und Programmierung",
    "IT-Systemanalyse, -Anwendungsberatung und -Vertrieb",
}

# `branche` facet codes, derived empirically on 2026-08-29 by querying each code
# and reading off the employers it returns. The BA publishes no code list, so
# these labels are OUR inference from evidence -- but the two that matter are
# unambiguous:
#   27 -> PerZukunft Arbeitsvermittlung, Recrutis Consulting, rocket match
#   28 -> TimePartner, ARWA, persona service, MANPOWER, Neo Temp
BRANCHE_LABEL = {
    "1": "Baugewerbe / technische Dienstleistungen",
    "3": "Maschinen- und Anlagenbau",
    "5": "Fahrzeugbau und Industrie",
    "6": "Finanz-, Versicherungs- und Gesundheitswesen",
    "9": "Handel",
    "11": "Information und Kommunikation (IT)",
    "13": "Handel, Verkehr und Logistik",
    "18": "Oeffentliche Verwaltung",
    "27": "Private Arbeitsvermittlung",
    "28": "Arbeitnehmerueberlassung",
}
# Industries meaning "this company sells people": the segment a talent supplier
# competes with rather than sells to.
BRANCHE_AGENCY = {"27", "28"}
BRANCHE_IT = {"11"}


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

def _get(params: dict, timeout: float = 25.0, retries: int = 2) -> dict | None:
    """Returns the payload, {} for a definitive empty answer, None on failure."""
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                return {}
            if attempt == retries:
                return None
        except Exception:
            if attempt == retries:
                return None
        time.sleep(0.6 * (attempt + 1))
    return None


def _counts(payload: dict, facet: str) -> dict:
    return ((payload.get("facetten") or {}).get(facet) or {}).get("counts") or {}


def _it_slice(payload: dict) -> int:
    bf = _counts(payload, "berufsfeld")
    return int(sum(v for k, v in bf.items() if k in IT_BERUFSFELDER))


# ---------------------------------------------------------------------------
# one company
# ---------------------------------------------------------------------------

def fetch_company(company_key: str, name_variants: list[str]) -> dict:
    """Two calls: the employer's whole live portfolio, and its last 28 days.

    Name variants are tried longest-first: BA employer strings carry branch and
    division suffixes, and the longer form is the one actually advertised under.
    The first variant returning any offer wins.
    """
    row: dict = {
        "company_key": company_key, "ba_matched": False, "ba_name_used": None,
        "ba_stock": 0, "ba_it_stock": 0, "ba_flow_28": 0, "ba_it_flow_28": 0,
        "ba_flow_7": 0, "ba_pav_true": 0, "ba_za_true": 0,
        "ba_branche": None, "ba_branche_label": None, "ba_error": False,
        "ba_checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    payload = None
    for name in sorted({v for v in name_variants if v}, key=len, reverse=True)[:4]:
        got = _get({"arbeitgeber": name, "angebotsart": 1, "size": 1, "page": 1})
        if got is None:
            row["ba_error"] = True
            continue
        if int(got.get("maxErgebnisse") or 0) > 0:
            payload, row["ba_name_used"] = got, name
            break
    if payload is None:
        return row

    row["ba_matched"] = True
    row["ba_stock"] = int(payload.get("maxErgebnisse") or 0)
    row["ba_it_stock"] = _it_slice(payload)
    row["ba_pav_true"] = int(_counts(payload, "pav").get("true", 0))
    row["ba_za_true"] = int(_counts(payload, "zeitarbeit").get("true", 0))
    vs = _counts(payload, "veroeffentlichtseit")
    row["ba_flow_28"] = int(vs.get("28", 0))
    row["ba_flow_7"] = int(vs.get("7", 0))

    branche = _counts(payload, "branche")
    if branche:
        top = max(branche.items(), key=lambda kv: kv[1])[0]
        row["ba_branche"] = top
        row["ba_branche_label"] = BRANCHE_LABEL.get(top, f"branche {top}")

    # second call: the IT slice of the last 28 days -- real flow, IT only
    recent = _get({"arbeitgeber": row["ba_name_used"], "angebotsart": 1,
                   "veroeffentlichtseit": 28, "size": 1, "page": 1})
    if recent:
        row["ba_it_flow_28"] = _it_slice(recent)
    elif recent is None:
        row["ba_error"] = True
    return row


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def candidate_pool(postings: pd.DataFrame, companies: pd.DataFrame,
                   min_it: int = 2) -> pd.DataFrame:
    """Companies worth spending a request on: anyone with real IT demand.

    Deliberately WIDER than the scored pool. The point of this stage is to
    decide who is eligible, so a company the name rules already excluded must
    still be checked before it is dropped -- and one they wrongly admitted must
    be checked before it is ranked.
    """
    it = postings[postings["is_it_role"] & ~postings["is_training_role"]]
    counts = it.groupby("company_key").size()
    keys = set(counts[counts >= min_it].index)
    sub = companies[companies["company_key"].isin(keys)].copy()
    return sub[["company_key", "company_name", "name_variants"]]


def run(data_dir: Path, min_it: int = 2, workers: int = 6,
        limit: int | None = None, ttl_days: int = 7) -> pd.DataFrame:
    postings = pd.read_parquet(data_dir / "postings.parquet")
    companies = pd.read_parquet(data_dir / "companies.parquet")
    pool = candidate_pool(postings, companies, min_it)
    if limit:
        pool = pool.head(limit)

    out_path = data_dir / "ba_live.parquet"
    cached = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame()
    fresh_keys: set[str] = set()
    if len(cached):
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=ttl_days)
        checked = pd.to_datetime(cached["ba_checked_at"], utc=True, errors="coerce")
        fresh_keys = set(cached.loc[checked >= cutoff, "company_key"])

    todo = pool[~pool["company_key"].isin(fresh_keys)]
    print(f"[balive] {len(pool)} companies in pool, {len(todo)} to fetch "
          f"({len(fresh_keys)} cached within {ttl_days}d)", file=sys.stderr)

    rows: list[dict] = []
    if len(todo):
        jobs = [(r.company_key,
                 list(r.name_variants) if r.name_variants is not None else [])
                for r in todo.itertuples()]
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for row in executor.map(lambda a: fetch_company(*a), jobs):
                rows.append(row)
                done += 1
                if done % 100 == 0:
                    print(f"[balive]   {done}/{len(jobs)}", file=sys.stderr)

    keep = cached[cached["company_key"].isin(fresh_keys)] if len(cached) else pd.DataFrame()
    result = pd.concat([keep, pd.DataFrame(rows)], ignore_index=True) \
               .drop_duplicates("company_key", keep="last")

    result.to_parquet(out_path, index=False)
    matched = int(result["ba_matched"].sum())
    print(f"[balive] {len(result)} rows -> {out_path} "
          f"({matched} matched, {len(result) - matched} not found on the board today)",
          file=sys.stderr)
    return result


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(prog="opradar.balive")
    ap.add_argument("--data", type=Path, default=root / "data" / "processed")
    ap.add_argument("--min-it", type=int, default=2)
    ap.add_argument("--all", action="store_true", help="every company with >=1 IT ad")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    run(args.data, min_it=1 if args.all else args.min_it,
        workers=args.workers, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
