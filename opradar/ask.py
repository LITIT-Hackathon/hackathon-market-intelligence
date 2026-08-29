"""The ask-box -- questions about the pool, answered by pandas.

    python -m opradar.ask --project <gcp-project-id>
    -> http://127.0.0.1:8765

The model NEVER sees the data and never produces a figure. One question makes
two calls, and neither of them can invent anything:

    1. question  -> QuerySpec        a filter/sort/limit object, schema-bound,
                                     every field name checked against a
                                     whitelist before it goes near a DataFrame
    2. pandas    -> result table     deterministic, ~5ms, the same numbers the
                                     rest of the product shows
    3. table     -> prose            the model is handed ONLY the result table

So every number in an answer is in the table printed beneath it, and every row
carries its rank so it can be found in the Opportunities tab. A retrieval
chatbot over the same corpus would give up exactly the property that makes this
product defensible -- `v6_traceability` reports zero rows without evidence, and
an answer nobody can check is worth less than no answer.

Runs on the standard library. This is a demo tool for one machine: it binds to
loopback, holds credentials server-side so the shipped HTML never carries a key,
and is not hardened for anything else.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# what a question is allowed to touch
# --------------------------------------------------------------------------
# A whitelist, not a sanitiser. The model proposes a field NAME; nothing it
# writes ever reaches eval, query() or getattr. An unknown name is refused.
FIELDS: dict[str, tuple[str, str]] = {
    "name":            ("company_name", "company name"),
    "segment":         ("segment", "end_client / public_sector / it_vendor / agency"),
    "rank":            ("rank", "1 is the best opportunity"),
    "score":           ("opportunity", "0-100 percentile within the pool"),
    "confidence":      ("confidence_band", "low / medium / high"),
    "ads_june":        ("it_n", "IT ads we crawled in June"),
    "open_now":        ("now_it_stock", "IT roles open on the board today"),
    "aged_now":        ("now_aged_open", "of those, open over a month"),
    "new_it_28d":      ("now_it_flow_28", "new IT postings in the last 28 days"),
    # The board publishes no IT-only 7-day flow, so this counts postings of
    # EVERY kind. Named for what it is: side by side with new_it_28d the old
    # name produced "183 new in 7 days, 10 in 28 days" for Deutsche Bahn, which
    # is impossible and was read straight off two columns measuring
    # different things.
    "new_all_roles_7d": ("now_flow_7", "new postings of ANY kind in the last 7 "
                                       "days, IT and non-IT together. NOT "
                                       "comparable with new_it_28d and never a "
                                       "measure of IT hiring on its own."),
    "roles_live":      ("atoms_total", "roles from our crawl still live"),
    "roles_covered":   ("atoms_covered", "of those, our bench can cover"),
    "placeable":       ("placeable_w", "people we could place at once"),
    "median_age":      ("median_age", "median age of their ads, days"),
    "unmet":           ("unmet", "0-1, cannot fill what they advertise"),
    "expansion":       ("expansion", "0-1, hiring above their own baseline"),
    "programme":       ("programme", "0-1, concentrated in one technology"),
    "seniority":       ("seniority", "0-1, weighted to senior roles"),
    "verified":        ("live_verified", "re-observed on the board today"),
    # Derived, because the filter grammar compares a field to a CONSTANT and
    # the most natural questions here compare two fields. "Where can our bench
    # cover every open role" was answered "nothing matched" while 49 companies
    # qualified -- the question was not unanswerable, it was inexpressible.
    "covers_all":      ("_covers_all", "true when our bench covers EVERY live "
                                       "role we hold an ad for"),
    "coverage_share":  ("_coverage_share", "0-1, share of their live roles our "
                                           "bench covers"),
    "aged_share":      ("_aged_share", "0-1, share of today's open roles that "
                                       "are over a month old"),
}


def prepare(o: pd.DataFrame) -> pd.DataFrame:
    """Add the derived columns FIELDS promises. Called once when the pool loads."""
    d = o.copy()
    tot = pd.to_numeric(d.get("atoms_total"), errors="coerce")
    cov = pd.to_numeric(d.get("atoms_covered"), errors="coerce")
    stock = pd.to_numeric(d.get("now_it_stock"), errors="coerce")
    aged = pd.to_numeric(d.get("now_aged_open"), errors="coerce")
    d["_covers_all"] = ((tot > 0) & (cov >= tot)).fillna(False)
    d["_coverage_share"] = (cov / tot.where(tot > 0)).round(3)
    d["_aged_share"] = (aged / stock.where(stock > 0)).round(3)
    return d

COHORTS = ["stalled", "accelerating", "quiet", "stuck", "any"]
OPS = ["gt", "gte", "lt", "lte", "eq", "ne", "contains"]

SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "cohort": {"type": "string", "enum": COHORTS,
                   "description": "Behavioural cohort. 'stalled' = stopped "
                                  "advertising but roles still open and all "
                                  "aged. 'accelerating' = posted in the last "
                                  "28 days. 'quiet' = had June demand, nothing "
                                  "new. 'stuck' = 80%+ of open roles aged. "
                                  "'any' for no cohort filter."},
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(FIELDS)},
                    "op": {"type": "string", "enum": OPS},
                    "value": {"type": "string",
                              "description": "Compared as a number when the "
                                             "field is numeric, else as text."},
                },
                "required": ["field", "op", "value"],
            },
        },
        "sort": {"type": "string", "enum": list(FIELDS)},
        "descending": {"type": "boolean"},
        "limit": {"type": "integer", "description": "1-25."},
        "show": {"type": "array", "items": {"type": "string", "enum": list(FIELDS)},
                 "description": "Columns to return, beyond name and rank."},
        "answerable": {"type": "boolean",
                       "description": "False if the question cannot be answered "
                                      "from these fields at all."},
        "why_not": {"type": "string",
                    "description": "If answerable is false, one plain sentence "
                                   "saying what is missing. Empty otherwise."},
    },
    "required": ["cohort", "filters", "sort", "descending", "limit", "show",
                 "answerable", "why_not"],
}


def _field_doc() -> str:
    return "\n".join(f"  {k:14} {d}" for k, (_, d) in FIELDS.items())


PLANNER = f"""You turn a question about German companies into a query spec.

The data is one row per company, already ranked as a sales opportunity. \
Available fields:

{_field_doc()}

We observed each company twice: a job-board crawl on 2026-06-06 (ads_june, \
roles_live, roles_covered) and the live board today (open_now, aged_now, \
new_28d, new_7d). Questions about who STOPPED or STARTED are about the \
difference, which is what the cohorts encode.

When the question is about who STOPPED, STARTED, is STUCK or has gone QUIET, \
set `cohort` rather than rebuilding it from filters. The cohorts encode \
conditions the raw fields cannot express alone -- 'stalled' also requires that \
every role still open is already over a month old, which no single field says.

Choose the smallest spec that answers the question. Set answerable=false when \
the question needs something not in the list above -- salaries, contact people, \
head counts, anything about a company not in this pool. Guessing is worse than \
saying so."""

WRITER = """You answer a question using ONLY the result table you are given.

- Every number you write must be visible in the table. Do not total, average or \
derive anything.
- Two or three sentences. Lead with the direct answer, then the most useful \
detail. Name at most four companies however many rows there are, then give the \
count: the table below your answer already lists them all, and repeating it in \
prose is worse than useless.
- ROW COUNT is stated above the table. Say nothing matched ONLY when it is 0. \
A column of zeros is data, not emptiness: "0 new postings in 28 days" is \
precisely the finding for a question about who stopped.
- When you state how many, use total_matched, never the number of rows shown. \
The table is truncated; the count is not.
- Never write a column key. `column_meanings` says what each one measures -- \
use those words. "243 new IT postings in the last 28 days", not "243.0 \
new_it_28d".
- Do not attach a unit the column name does not carry.
- Name companies exactly as the table spells them.
- No preamble, no "based on the data", no bullet lists."""


# --------------------------------------------------------------------------
# execution -- pandas only, no model
# --------------------------------------------------------------------------

def cohort_mask(o: pd.DataFrame, name: str) -> pd.Series:
    """The same four definitions `opradar.brief` uses, applied row-wise."""
    if name in ("any", "", None):
        return pd.Series(True, index=o.index)
    live = o["live_verified"] == True                    # noqa: E712
    stock = pd.to_numeric(o.get("now_it_stock"), errors="coerce")
    aged = pd.to_numeric(o.get("now_aged_open"), errors="coerce")
    flow = pd.to_numeric(o.get("now_it_flow_28"), errors="coerce")
    if name == "stalled":
        return live & (flow == 0) & (stock > 0) & (aged >= stock)
    if name == "accelerating":
        return live & (flow > 0)
    if name == "quiet":
        return live & (flow == 0) & (o["it_n"] >= 3)
    if name == "stuck":
        return live & (stock >= 5) & ((aged / stock) >= 0.8)
    return pd.Series(True, index=o.index)


def execute(o: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, list[str], int]:
    """Apply a spec. Every field name is resolved through FIELDS or dropped.

    Returns the limited rows AND how many matched before the limit. Without
    that second number the writer reports the limit as the answer -- [measured]
    "there are 10 such companies" for a filter that matched 19.
    """
    notes: list[str] = []
    df = o[cohort_mask(o, spec.get("cohort", "any"))]

    for f in spec.get("filters") or []:
        key, op, raw = f.get("field"), f.get("op"), f.get("value")
        if key not in FIELDS or op not in OPS:
            notes.append(f"ignored an unknown filter ({key} {op})")
            continue
        col = FIELDS[key][0]
        if col not in df.columns:
            continue
        s = df[col]
        if op == "contains":
            df = df[s.astype(str).str.contains(str(raw), case=False, na=False)]
            continue
        num = pd.to_numeric(s, errors="coerce")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            # a text comparison on a text column is legitimate (segment == ...)
            df = df[s.astype(str).str.lower() == str(raw).lower()] if op == "eq" \
                else df[s.astype(str).str.lower() != str(raw).lower()]
            continue
        df = df[{"gt": num > val, "gte": num >= val, "lt": num < val,
                 "lte": num <= val, "eq": num == val, "ne": num != val}[op]]

    sort_key = spec.get("sort") or "rank"
    sort_col = FIELDS.get(sort_key, ("rank", ""))[0]
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=not spec.get("descending", False),
                            na_position="last")

    total = len(df)
    limit = max(1, min(int(spec.get("limit") or 10), 25))
    show = [s for s in (spec.get("show") or []) if s in FIELDS]
    cols = ["rank", "name"] + [s for s in show if s not in ("rank", "name")]
    if sort_key not in cols:
        cols.append(sort_key)
    real = [FIELDS[c][0] for c in cols if FIELDS[c][0] in df.columns]
    return df[real].head(limit), notes, total


def to_table(df: pd.DataFrame, total: int | None = None) -> dict:
    inv = {v[0]: k for k, v in FIELDS.items()}
    rows = json.loads(df.to_json(orient="records", double_precision=2))
    cols = [inv.get(c, c) for c in df.columns]
    return {"columns": cols,
            # what each column MEANS, so the writer can say it in English
            # instead of pasting the key into a sentence
            "column_meanings": {c: FIELDS[c][1] for c in cols if c in FIELDS},
            "showing": len(rows),
            "total_matched": len(rows) if total is None else total,
            "rows": [{inv.get(k, k): v for k, v in r.items()} for r in rows]}


# --------------------------------------------------------------------------
# the two model calls
# --------------------------------------------------------------------------

def plan(client, model: str, question: str) -> dict:
    from google.genai import types
    resp = client.models.generate_content(
        model=model, contents=question,
        config=types.GenerateContentConfig(
            system_instruction=PLANNER, response_mime_type="application/json",
            response_schema=SPEC_SCHEMA, temperature=0.0))
    return json.loads(resp.text)


def narrate(client, model: str, question: str, table: dict) -> str:
    from google.genai import types
    # The row count is stated in words as well as implied by the array, because
    # [measured] a table whose every value in the asked-about column was 0.0 --
    # the correct answer to "who stopped advertising" -- came back as "nothing
    # matched your request" with six rows sitting in front of it.
    n = len(table.get("rows") or [])
    payload = (f"Question: {question}\n\nROW COUNT: {n}\n\nResult table:\n"
               f"{json.dumps(table, ensure_ascii=False, indent=1)}")
    resp = client.models.generate_content(
        model=model, contents=payload,
        config=types.GenerateContentConfig(
            system_instruction=WRITER, temperature=0.2))
    return (resp.text or "").strip()


def answer(client, model: str, o: pd.DataFrame, question: str) -> dict:
    spec = plan(client, model, question)
    if not spec.get("answerable", True):
        return {"answer": spec.get("why_not")
                or "That is not something this dataset can answer.",
                "spec": spec, "table": {"columns": [], "rows": []},
                "answerable": False}
    df, notes, total = execute(o, spec)
    table = to_table(df, total)
    text = narrate(client, model, question, table)
    return {"answer": text, "spec": spec, "table": table,
            "answerable": True, "notes": notes}


# --------------------------------------------------------------------------
# server
# --------------------------------------------------------------------------

def make_handler(ui_dir: Path, state: dict):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ui_dir), **kw)

        def log_message(self, fmt, *a):           # one line per question, not per asset
            pass

        def _json(self, code: int, body: dict):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path.rstrip("/") == "/ask":
                return self._json(200, {"ok": True, "model": state["model"]})
            return super().do_GET()

        def do_POST(self):
            if self.path.rstrip("/") != "/ask":
                return self._json(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                q = (json.loads(self.rfile.read(n) or b"{}").get("q") or "").strip()
            except Exception:
                return self._json(400, {"error": "bad request"})
            if not q:
                return self._json(400, {"error": "empty question"})
            print(f"  ? {q}", file=sys.stderr, flush=True)
            try:
                out = answer(state["client"], state["model"], state["pool"], q)
            except Exception as e:
                traceback.print_exc()
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            print(f"  > {out['answer'][:110]}", file=sys.stderr, flush=True)
            return self._json(200, out)

    return Handler


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.ask")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--ui", type=Path, default=root / "ui")
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--project", default=None)
    p.add_argument("--location", default="europe-west4")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)

    src = args.data / "opportunities.parquet"
    if not src.exists():
        print("ERROR: run `python -m opradar.score` first.", file=sys.stderr)
        return 1
    if not (args.ui / "index.html").exists():
        print("ERROR: run `python -m opradar.ui` first.", file=sys.stderr)
        return 1

    from .extract import build_client
    state = {"pool": prepare(pd.read_parquet(src)), "model": args.model,
             "client": build_client(args.project, args.location)}

    srv = ThreadingHTTPServer(("127.0.0.1", args.port),
                              make_handler(args.ui, state))
    print(f"OpRadar ask -- {len(state['pool'])} companies, model {args.model}",
          file=sys.stderr)
    print(f"  open http://127.0.0.1:{args.port}/   (ctrl-c to stop)",
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
