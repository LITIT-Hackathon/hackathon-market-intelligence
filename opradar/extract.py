"""Gemini over the harvested advertisement text -> structured, cached, offline after.

    python -m opradar.enrich extract --project <gcp-project-id>

Reads  details.parquet   [opradar.enrich harvest]
Writes enrichment.parquet

This is the only place in OpRadar that calls a model, and it is a BUILD STEP.
It runs once, writes a parquet, and every consumer downstream reads that file.
The scorer never imports this module; the score stays offline and reproducible
from its config hash whether or not this has ever been run.

What it recovers that no rule can:

  technologies      [measured] 52% of IT postings carry no technology tag at
                    all, because the parser only ever had a job TITLE to match
                    a dictionary against. The stack is in the ad body.
  seniority         [measured] 78% are unknown for the same reason.
  buys_external     an advertiser writing "Unterstuetzung durch externe
                    Dienstleister" is stating that it buys what we sell. There
                    is no structured field for that anywhere on the board.
  blockers          Sicherheitsueberpruefung, Praesenzpflicht, verhandlungs-
                    sicheres Deutsch. A Vilnius team cannot serve those roles,
                    and a tool that only finds reasons to be optimistic is a
                    tool nobody trusts twice.

Every extracted claim that could be argued with carries `evidence` -- the
advertiser's own words, copied verbatim. Nothing here is believed on the
model's authority; it is all one click from the ad that produced it, which is
the same standard the rest of the pipeline is held to.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Bump when the schema or the instruction changes: cached rows carrying an
# older version are re-extracted rather than silently mixed with new ones.
SCHEMA_VERSION = 4

CACHE_NAME = "enrichment.parquet"

BLOCKERS = ["security_clearance", "onsite_only", "german_required",
            "eu_citizenship", "on_call", "travel_heavy"]

SCHEMA = {
    "type": "object",
    "properties": {
        "technologies": {
            "type": "array", "items": {"type": "string"},
            "description": "Concrete named technologies, normalised to their "
                           "common English spelling (Java, Kubernetes, SAP "
                           "S/4HANA, .NET, Azure). Skills and methods are not "
                           "technologies. Empty if the ad names none."},
        "seniority": {"type": "string",
                      "enum": ["junior", "mid", "senior", "lead", "unknown"]},
        "headcount": {"type": "integer",
                      "description": "How many people this one ad is hiring. 1 "
                                     "unless the ad says otherwise ('mehrere', "
                                     "'ein Team von', a stated number)."},
        "project_phase": {"type": "string",
                          "enum": ["greenfield", "migration", "rollout",
                                   "maintenance", "unclear"]},
        "project_topic": {"type": "string",
                          "description": "The named programme in <=6 words if "
                                         "the ad describes one (e.g. 'S/4HANA "
                                         "migration', 'SAP to cloud'), else ''."},
        "buys_external": {"type": "boolean",
                          "description": "True ONLY if the EMPLOYER buys "
                                         "external IT capacity for work like "
                                         "this: IT-Dienstleister, Beratungs"
                                         "haeuser, Freiberufler, Nearshoring, "
                                         "Arbeitnehmerueberlassung, "
                                         "Werkvertrag, 'externe Entwickler'. "
                                         "A supply chain of parts or hardware "
                                         "subcontractors is NOT this. Their "
                                         "own customers are NOT this. Being an "
                                         "IT provider themselves is NOT this. "
                                         "When unsure, false."},
        "blockers": {"type": "array",
                     "items": {"type": "string", "enum": BLOCKERS},
                     "description": "Hard requirements that would stop a "
                                    "non-German, non-resident supplier."},
        "language": {"type": "string",
                     "enum": ["german", "english", "both", "unknown"]},
        "evidence": {"type": "string",
                     "description": "One short verbatim quote from the ad, in "
                                    "the ad's own language, supporting "
                                    "buys_external or the blockers. Empty if "
                                    "neither applies. Never paraphrase, never "
                                    "translate. A quote that does not actually "
                                    "show the claim means the claim is wrong."},
    },
    "required": ["technologies", "seniority", "headcount", "project_phase",
                 "project_topic", "buys_external", "blockers", "language",
                 "evidence"],
}

INSTRUCTION = """You read IT job advertisements from the German federal job \
board (most are German, some English) and return structured facts about them.

Rules:
- Report only what the advertisement states. Do not infer, complete or \
generalise from what a role like this usually involves.
- When the ad does not say, use the 'unknown' / 'unclear' / empty option. An \
honest blank is worth more here than a confident guess. Most ads name no \
technology at all; an empty list is the correct answer, not a failure.
- `evidence` must be copied character-for-character from the ad. If you cannot \
quote it, do not claim it. Read the quote back before you answer: if it does \
not by itself demonstrate the claim, set the claim to false.
- Boilerplate (benefits, company history, equal-opportunity statements, \
application instructions) is not evidence of anything. Ignore it.
- `buys_external` is a commercial claim about the EMPLOYER purchasing IT \
services. It is the field most easily got wrong: a mention of subcontractors, \
partners, suppliers or customers is not it, and neither is an IT provider \
describing its own business. Only the employer engaging external IT people for \
work of the kind advertised counts.
"""


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------

SETUP = """
Gemini is not reachable yet. Two ways to fix that:

  Vertex AI (uses your Google Cloud credits)
    pip install google-genai
    gcloud auth application-default login
    python -m opradar.enrich extract --project YOUR_PROJECT_ID

  AI Studio key (quicker, no gcloud, separate free tier)
    pip install google-genai
    set GEMINI_API_KEY=...            (PowerShell: $env:GEMINI_API_KEY="...")
    python -m opradar.enrich extract

Everything else in OpRadar runs without this. `enrich harvest`, the scorer and
the briefing all work on harvested text alone -- extraction makes them sharper,
it is not load-bearing.
"""


# The SDK warns about automatic function calling on every structured call.
# It does not apply here -- we pass a response schema, not tools -- and once per
# advertisement it drowns out the progress output.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)


def build_client(project: str | None, location: str):
    """A google-genai client, on Vertex when a project is given, else API key.

    Location defaults to europe-west4 upstream: EU residency on Vertex is
    configurable, not the default, and this is German labour-market data
    processed for an EU company.
    """
    try:
        from google import genai
    except ImportError:
        print("google-genai is not installed." + SETUP, file=sys.stderr)
        raise SystemExit(2)

    if project:
        return genai.Client(vertexai=True, project=project, location=location)
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("No --project and no GEMINI_API_KEY." + SETUP, file=sys.stderr)
        raise SystemExit(2)
    return genai.Client(api_key=key)


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

def build_prompt(row: pd.Series, max_chars: int = 9000) -> str:
    """One ad, trimmed. Ads run to [measured] 3.4k characters on average; the
    cap is a guard against an outlier, not a routine truncation."""
    body = (row.get("description") or "")[:max_chars]
    return (f"Titel: {row.get('title_source') or ''}\n"
            f"Beruf: {row.get('occupation_main') or ''}\n"
            f"Arbeitgeber: {row.get('firm_name') or ''}\n\n"
            f"Anzeige:\n{body}")


def extract_one(client, model: str, row: pd.Series, retries: int = 2) -> dict | None:
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=INSTRUCTION,
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=0.0,          # this is extraction, not writing
    )
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=model, contents=build_prompt(row), config=cfg)
            return json.loads(resp.text)
        except Exception as e:
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))     # quota/5xx: back off politely
                continue
            print(f"  ! {row.get('refnr')}: {type(e).__name__}: {e}", file=sys.stderr)
            return None
    return None


# ---------------------------------------------------------------------------
# guards -- the model proposes, deterministic code disposes
# ---------------------------------------------------------------------------

# Terms that actually mean "this employer engages external IT capacity". A
# supply chain word on its own does not: [measured] the first ad we extracted
# claimed buys_external on "coordination ... with customer, subcontractors and
# internal technical disciplines", which is a satellite programme's parts
# supply chain, not a company buying developers. Tightening the prompt twice
# did not move it, so the claim is checked instead of asked for -- the model
# has to quote the ad, and a quote is a checkable artefact.
BUYING_TERMS = (
    "dienstleister", "dienstleistung", "beratungshaus", "beratungsunternehmen",
    "beratungspartner", "freiberufler", "freelancer", "nearshor", "offshor",
    "arbeitnehmerueberlassung", "arbeitnehmerüberlassung", "werkvertrag",
    "personaldienstleist", "zeitarbeit", "externe entwickler",
    "externe mitarbeiter", "externen mitarbeitern", "externe berater",
    "externen beratern", "externe partner", "externen partnern",
    "externe unterstuetzung", "externe unterstützung", "external provider",
    "external service", "external consultan", "external developer",
    "staff augmentation", "managed service", "body leasing",
)

# "contractor" is a buying term; "subcontractor" is a supply-chain word, and
# the first contains the second. Substring matching cannot tell them apart --
# it is the exact mistake this guard exists to catch, so it gets a lookbehind.
BUYING_RE = re.compile(r"(?<!sub)contractor", re.I)


def confirm_buys_external(got: dict) -> tuple[bool, str]:
    """Keep `buys_external` only when its own quote demonstrates it.

    Returns (claim, reason-if-dropped). A claim we cannot see in the quote is
    not a weaker claim, it is an unsourced one, and this field is the most
    commercially loaded thing we extract -- it is the difference between "call
    them, they already buy this" and a wasted call.
    """
    if not got.get("buys_external"):
        return False, ""
    quote = (got.get("evidence") or "").lower()
    if not quote:
        return False, "no quote"
    if any(t in quote for t in BUYING_TERMS) or BUYING_RE.search(quote):
        return True, ""
    return False, "quote does not show it"


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=["refnr", "schema_version", "model", "extracted_at"])


def to_row(refnr: str, got: dict, model: str, now: str) -> dict:
    """One model response -> one cache row. Lists become JSON strings so the
    file round-trips through parquet the same way the rest of the pipeline's
    list columns do."""
    buys, dropped = confirm_buys_external(got)
    return {
        "refnr": refnr,
        "technologies": json.dumps(got.get("technologies") or [], ensure_ascii=False),
        "tech_n": len(got.get("technologies") or []),
        "seniority_llm": got.get("seniority") or "unknown",
        "headcount": int(got.get("headcount") or 1),
        "project_phase": got.get("project_phase") or "unclear",
        "project_topic": got.get("project_topic") or "",
        "buys_external": buys,
        "buys_dropped": dropped,
        "blockers": json.dumps(got.get("blockers") or [], ensure_ascii=False),
        "blocker_n": len(got.get("blockers") or []),
        "language": got.get("language") or "unknown",
        "evidence": got.get("evidence") or "",
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "extracted_at": now,
    }


def run(args) -> int:
    data_dir: Path = args.data
    details_path = data_dir / "details.parquet"
    if not details_path.exists():
        print("ERROR: run `python -m opradar.enrich harvest` first.", file=sys.stderr)
        return 1

    details = pd.read_parquet(details_path)
    have_text = details[details["description"].notna()
                        & (details["description"].astype(str).str.len() > 200)]
    if not len(have_text):
        print("No harvested descriptions to extract from.", file=sys.stderr)
        return 1

    cache_path = data_dir / CACHE_NAME
    cache = load_cache(cache_path)
    done = set(cache.loc[cache["schema_version"] == SCHEMA_VERSION, "refnr"]) \
        if len(cache) else set()

    todo = have_text[~have_text["refnr"].isin(done)]
    if args.limit:
        todo = todo.head(args.limit)

    chars = int(todo["description_chars"].fillna(0).sum())
    print(f"descriptions {len(have_text):,} | already extracted {len(done):,} "
          f"| extracting {len(todo):,} ({chars / 1e6:.2f}M chars, "
          f"~{chars / 3600:.0f}k tokens)", file=sys.stderr)
    if not len(todo):
        print("nothing to do.", file=sys.stderr)
        return 0

    client = build_client(args.project, args.location)
    now = datetime.now(timezone.utc).isoformat()
    rows, started = [], time.time()

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(extract_one, client, args.model, r)
                   for _, r in todo.iterrows()]
        for i, (fut, (_, r)) in enumerate(zip(futures, todo.iterrows()), 1):
            got = fut.result()
            if got:
                rows.append(to_row(r["refnr"], got, args.model, now))
            if i % 25 == 0:
                print(f"  {i:,}/{len(todo):,}  ok {len(rows):,} "
                      f"({time.time() - started:.0f}s)", file=sys.stderr)

    if not rows:
        print("no successful extractions -- nothing written.", file=sys.stderr)
        return 1

    new = pd.DataFrame(rows)
    merged = (pd.concat([cache[~cache["refnr"].isin(set(new["refnr"]))], new],
                        ignore_index=True) if len(cache) else new)
    merged.to_parquet(cache_path, index=False)

    print(f"done in {time.time() - started:.0f}s -> {cache_path}", file=sys.stderr)
    dropped = int((new["buys_dropped"] != "").sum())
    print(f"  {len(new):,} extracted | "
          f"{int((new['tech_n'] > 0).sum()):,} with a tech stack | "
          f"{int(new['buys_external'].sum()):,} confirmed buying external help | "
          f"{int((new['blocker_n'] > 0).sum()):,} carry a blocker", file=sys.stderr)
    if dropped:
        print(f"  {dropped:,} buys_external claims dropped: the quote did not "
              f"show it", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------

ATTACH_COLS = ["technologies", "tech_n", "seniority_llm", "headcount",
               "project_phase", "project_topic", "buys_external", "blockers",
               "blocker_n", "language", "evidence"]


def attach(pool: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    """Add extracted columns to a pool, from cache. Absent cache leaves them
    null, exactly as `liveness.attach` and `enrich.attach` do."""
    out = pool.copy()
    path = data_dir / CACHE_NAME
    if not path.exists() or not len(pool):
        for c in ATTACH_COLS:
            out[c] = pd.NA
        return out
    e = pd.read_parquet(path)
    keep = ["refnr"] + [c for c in ATTACH_COLS if c in e.columns]
    e = e[keep].drop_duplicates("refnr")
    out = out.merge(e, left_on="posting_id", right_on="refnr", how="left")
    if "refnr" in out.columns:
        out = out.drop(columns=["refnr"])
    for c in ATTACH_COLS:
        if c not in out.columns:
            out[c] = pd.NA
    return out
