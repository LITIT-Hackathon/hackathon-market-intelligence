"""The briefing -- what changed in the German IT market between our two looks.

    python -m opradar.brief          # writes briefing.json

We observe the board twice:

    2026-06-06   the crawl          every ad open that day, with its text
    today        `opradar.balive`   open stock and 7/28-day posting flow

One observation is a photograph and supports only "who is hiring". Two support
"who STOPPED", which is the question a salesperson actually asks, and which no
single snapshot can answer at all.

Everything here is computed in pandas and carries the company keys it was
computed from. No model is called and no number is ever generated: a narrator
laid over this file may only re-word what is already in it, so every figure in
the briefing stays one click from the company row that produced it. That is the
same standard `v6_traceability` holds the rest of the pipeline to, and it is
the whole reason this is a query engine with prose on top rather than a chatbot
over a pile of text.

Cohorts are behavioural, not sectoral. [measured] only 75 of 142 ranked
companies carry a usable branche label from the board and a third of those are
unnamed codes, so grouping by what companies DID is both better evidenced and
more useful than grouping by what industry they are filed under.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOP_N = 8


def _i(v, default=0):
    """Nullable Int64 -> int. `pd.NA == pd.NA` raises, so never self-compare."""
    return default if v is None or pd.isna(v) else int(v)


def _rows(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    out = []
    for r in df.itertuples():
        row = {"key": r.company_key, "name": r.company_name, "rank": _i(r.rank)}
        for c in cols:
            row[c] = _i(getattr(r, c, None))
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# cohorts
# ---------------------------------------------------------------------------

def cohorts(o: pd.DataFrame) -> dict:
    """The four things a company can be doing between our two observations.

    Only companies the live board answered for can appear here: without
    `now_it_flow_28` there is no second observation and therefore no change to
    report. Saying nothing about a company we did not re-observe is correct;
    inferring from the June snapshot alone is how a stale crawl gets presented
    as today's market.
    """
    m = o[o["live_verified"] == True].copy()          # noqa: E712
    for c in ("now_it_stock", "now_it_flow_28", "now_flow_7", "now_aged_open"):
        m[c] = pd.to_numeric(m.get(c), errors="coerce")

    # ACCELERATING -- posting more now than the crawl caught them doing
    acc = m[m["now_it_flow_28"] > 0].sort_values("now_it_flow_28", ascending=False)

    # QUIET -- had IT demand in June, nothing new on the board in four weeks
    quiet = m[(m["now_it_flow_28"] == 0) & (m["it_n"] >= 3)] \
        .sort_values("it_n", ascending=False)

    # STALLED -- the interesting one, and the one no existing signal names.
    # They stopped advertising AND nothing got filled: every role still open
    # today has been open over a month. A company that gave up on the job board
    # while the need is still there is the highest-intent shape in the data --
    # it has a problem and has stopped trying to solve it the cheap way.
    stalled = m[(m["now_it_flow_28"] == 0) & (m["now_it_stock"] > 0)
                & (m["now_aged_open"] >= m["now_it_stock"])] \
        .sort_values("now_it_stock", ascending=False)

    # STUCK -- still advertising, still not filling. Slower burn than stalled.
    st = m[m["now_it_stock"] >= 5].copy()
    st["aged_share"] = (st["now_aged_open"] / st["now_it_stock"]).round(2)
    stuck = st[st["aged_share"] >= 0.8].sort_values(
        ["aged_share", "now_it_stock"], ascending=False)

    return {
        "accelerating": _rows(acc.head(TOP_N),
                              ["it_n", "now_it_stock", "now_it_flow_28", "now_flow_7"]),
        "accelerating_n": len(acc),
        "quiet": _rows(quiet.head(TOP_N), ["it_n", "now_it_stock", "now_aged_open"]),
        "quiet_n": len(quiet),
        "stalled": _rows(stalled.head(TOP_N),
                         ["it_n", "now_it_stock", "now_aged_open"]),
        "stalled_n": len(stalled),
        "stuck": _rows(stuck.head(TOP_N), ["now_it_stock", "now_aged_open"]),
        "stuck_n": len(stuck),
        "observed_n": len(m),
    }


def demand_mix(data_dir: Path) -> dict:
    """Where the demand actually sits, weighted by opportunity.

    `cells.parquet` is already opportunity-weighted demand per role/seniority/
    tech cell, so this is a read rather than a second model of the same thing.
    """
    path = data_dir / "cells.parquet"
    if not path.exists():
        return {"tech": [], "families": []}
    c = pd.read_parquet(path)
    # "unspecified" is the parser's placeholder for an ad whose technology it
    # could not read -- [measured] 52% of IT postings. It is the largest cell by
    # weight and it is not a technology, so naming it as where demand
    # concentrates would be reporting our own blind spot as a market finding.
    c = c[~c["tech_tag"].isin(["unspecified", "", "none"])]
    tech = (c.groupby("tech_tag")["demand_weight"].sum()
            .sort_values(ascending=False).head(10))
    fam = (c.groupby("role_family")["demand_weight"].sum()
           .sort_values(ascending=False).head(8))
    return {
        "tech": [{"name": k, "weight": round(float(v), 1)} for k, v in tech.items()],
        "families": [{"name": k, "weight": round(float(v), 1)} for k, v in fam.items()],
    }


def our_side(o: pd.DataFrame, data_dir: Path) -> dict:
    """What of that demand we could actually take, and what is closed to us.

    Every key names its own unit, and every one of them is a COUNT OF ROLES.

    There used to be a `people_we_could_place` here, carrying the sum of
    `placeable_w`. That is not a headcount: it is a weighted sum of age x match
    credit, feeding the dealsize signal, and it is fractional for 60 of the 65
    companies that have one. Handed a key with "people" in its name the
    narrator duly wrote "109.2 people we could place", and the number guard
    passed it because the figure was real and only the noun was invented.
    Renaming it once was not enough -- the fix is to stop publishing a
    weighted sum as if it were a number of humans.

    Everything here is scoped to the companies that still have a live vacancy,
    because a role we cannot name is not a role anyone can be placed into.
    """
    staffable = o[o["atoms_total"] > 0]
    out = {
        "companies_ranked": len(o),
        "companies_with_live_roles": int(len(staffable)),
        "companies_with_nothing_to_staff": int((o["atoms_total"] == 0).sum()),
        "roles_our_bench_covers": int(staffable["atoms_covered"].fillna(0).sum()),
        "roles_live_in_our_crawl": int(staffable["atoms_total"].fillna(0).sum()),
    }
    # extraction is optional -- the briefing states blockers only if the
    # enrichment pass has actually run, never as an assumption
    epath = data_dir / "enrichment.parquet"
    if epath.exists():
        e = pd.read_parquet(epath)
        out["ads_read_in_full"] = len(e)
        out["ads_saying_they_buy_external_help"] = int(
            e["buys_external"].fillna(False).sum())
        out["ads_with_a_blocker_we_cannot_meet"] = int(
            (e["blocker_n"].fillna(0) > 0).sum())
        blk: dict[str, int] = {}
        for v in e["blockers"].dropna():
            for b in json.loads(v):
                blk[b] = blk.get(b, 0) + 1
        out["ads_per_blocker"] = dict(sorted(blk.items(), key=lambda kv: -kv[1]))
        phases = e["project_phase"].value_counts().to_dict()
        out["ads_per_project_phase"] = {k: int(v) for k, v in phases.items()}
    else:
        out["ads_read_in_full"] = 0
    return out


def call_list(o: pd.DataFrame, coh: dict, n: int = 6) -> list[dict]:
    """Who to ring, and the one sentence that says why.

    Deliberately not just the top of the ranking: the ranking answers "who has
    the most pressure", and this answers "who should hear from us this week",
    which weights a company that just went stalled above one that has been
    quietly strong for months.
    """
    stalled_keys = {r["key"] for r in coh["stalled"]}
    acc_keys = {r["key"] for r in coh["accelerating"]}
    out = []
    for r in o.sort_values("rank").itertuples():
        if len(out) >= n:
            break
        if r.atoms_total == 0:                       # nothing we could name to pitch
            continue
        stock, aged = _i(r.now_it_stock), _i(r.now_aged_open)
        cov, tot = _i(r.atoms_covered), _i(r.atoms_total)
        if r.company_key in stalled_keys:
            why = (f"Stopped advertising, still {stock} roles open and all of them "
                   f"over a month old. They have given up on the board, not on the need.")
        elif r.company_key in acc_keys:
            why = (f"{_i(r.now_it_flow_28)} new IT roles in four weeks on top of "
                   f"{stock} already open — they are scaling and losing the race.")
        elif aged and stock:
            why = (f"{aged} of {stock} roles open over a month. We can cover "
                   f"{cov} of the {tot} we hold ads for.")
        else:
            why = f"We can cover {cov} of the {tot} roles still up."
        out.append({"key": r.company_key, "name": r.company_name,
                    "rank": _i(r.rank), "opportunity": float(r.opportunity),
                    "why": why})
    return out


def headline(coh: dict, side: dict, mix: dict) -> str:
    """One deterministic sentence. A narrator may rewrite this; it may not
    invent a number that is not already in the JSON beside it."""
    bits = [f"{coh['observed_n']} companies re-observed on the board"]
    if coh["accelerating_n"]:
        bits.append(f"{coh['accelerating_n']} posting again")
    if coh["quiet_n"]:
        bits.append(f"{coh['quiet_n']} gone quiet")
    if coh["stalled_n"]:
        bits.append(f"{coh['stalled_n']} stalled with roles still open")
    tech = mix["tech"][0]["name"] if mix["tech"] else None
    tail = f" Demand concentrates in {tech}." if tech else ""
    return ", ".join(bits) + "." + tail


def build(data_dir: Path) -> dict:
    o = pd.read_parquet(data_dir / "opportunities.parquet")
    coh = cohorts(o)
    mix = demand_mix(data_dir)
    side = our_side(o, data_dir)

    checked = pd.to_datetime(o.get("ba_checked_at"), errors="coerce", utc=True)
    # the crawl date is a property of the snapshot, not of the live re-check;
    # read just that one column so this stays a cheap read of an 8.5MB file
    snap = pd.read_parquet(data_dir / "postings.parquet", columns=["snapshot_date"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crawl_date": str(snap["snapshot_date"].max())[:10],
        "board_date": str(checked.max())[:10] if checked.notna().any() else None,
        "headline": headline(coh, side, mix),
        "cohorts": coh,
        "demand": mix,
        "ours": side,
        "calls": call_list(o, coh),
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.brief")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    args = p.parse_args(argv)
    if not (args.data / "opportunities.parquet").exists():
        print("ERROR: run `python -m opradar.score` first.", file=sys.stderr)
        return 1

    b = build(args.data)
    out = args.data / "briefing.json"
    out.write_text(json.dumps(b, indent=2, ensure_ascii=False), encoding="utf-8")

    c = b["cohorts"]
    print(b["headline"], file=sys.stderr)
    print(f"  accelerating {c['accelerating_n']} | quiet {c['quiet_n']} "
          f"| stalled {c['stalled_n']} | stuck {c['stuck_n']}", file=sys.stderr)
    print(f"  -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
