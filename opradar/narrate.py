"""The narrator -- prose over `briefing.json`, and nothing more than prose.

    python -m opradar.narrate --project <gcp-project-id>

Reads  briefing.json          [opradar.brief]
Writes briefing_narrated.json

This runs at BUILD time and its output is baked into the static page, so the
shipped UI never calls a model, never carries an API key, and works with no
network at all. That is the whole reason the summariser is split from the
ask-box: a summary can be written once, a question cannot.

The model is given the finished JSON and told it may only re-word what is
already in it. It has no access to the postings, the pool, or any tool that
could produce a new figure -- so the worst it can do is describe the briefing
badly, never invent a company or a number. If it emits a number that is not in
the JSON, `check()` catches it and the run fails rather than shipping it.

Falling back is free: `ui_brief` renders `brief.headline`, which is computed in
pandas, whenever this has not been run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "One sentence, max 20 words, naming the "
                                    "single most important change."},
        "paragraphs": {
            "type": "array", "items": {"type": "string"},
            "description": "Two or three short paragraphs, 40-60 words each.",
        },
    },
    "required": ["headline", "paragraphs"],
}

INSTRUCTION = """You write a weekly market briefing for the sales lead of a \
Lithuanian IT services company that staffs projects at German companies.

You are given a JSON object of facts already computed from two observations of \
the German federal job board. Write the briefing from it.

Hard rules:
- Every number you write MUST appear in the JSON. Do not add, total, average, \
round or derive any figure. If you want to say something the JSON does not \
support, do not say it.
- Name companies only if they appear in the JSON.
- No greeting, no sign-off, no "in conclusion", no restating the rules.

- Never attach a unit to a number the JSON does not attach it to. No percent \
signs, no currency, no "x times". A bare count is a count.

What matters to this reader, in order: companies that stopped advertising while \
their roles are still open (the JSON calls these "stalled" -- these are the \
best leads, because the need is unmet and they have stopped solving it the \
cheap way), companies scaling faster than they can hire, and where our own \
bench could actually take the work.

Write connected prose, not a list of facts with full stops between them. Each \
paragraph makes ONE point and uses only the two or three figures that carry it; \
a paragraph that recites every company in a cohort is a table, and we already \
have the table. Say what the pattern means for someone deciding who to ring.

Plain and specific. Short sentences. No marketing register, no "landscape", no \
"leverage", no "in today's fast-moving market"."""


def check(text: str, allowed: set[str]) -> list[str]:
    """Numbers in the prose that are not in the facts.

    The narrator's one real failure mode is arithmetic -- summing two cohorts,
    converting a count to a percentage -- and it is invisible in fluent prose.
    Small numbers are skipped: "two or three roles" is English, not a claim.
    """
    bad = []
    for tok in re.findall(r"\d[\d.,]*", text):
        clean = tok.rstrip(".,").replace(",", "")
        if not clean:
            continue
        try:
            val = float(clean)
        except ValueError:
            continue
        if val <= 12:                      # counting words, dates, "four weeks"
            continue
        if clean not in allowed and clean.rstrip("0").rstrip(".") not in allowed:
            bad.append(tok)
    return bad


def check_units(text: str) -> list[str]:
    """Percent signs. The briefing holds no percentages, so a % in the prose is
    always a unit the narrator attached by itself -- the failure that survived
    the number check, because the digits were real and only the meaning was not.
    """
    return re.findall(r"\d[\d.,]*\s*%", text)


def allowed_numbers(b: dict) -> set[str]:
    """Every number anywhere in the briefing, as strings."""
    out: set[str] = set()

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                # Field NAMES legitimise their own numbers: `now_it_flow_28`
                # makes "the last 28 days" a description of the measure, not a
                # figure the narrator invented. Without this the guard rejects
                # correct prose for naming the window it is reporting on.
                for tok in re.findall(r"\d+", str(k)):
                    out.add(tok)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, bool):
            return
        elif isinstance(v, (int, float)):
            out.add(str(v))
            out.add(str(int(v)) if float(v).is_integer() else str(v))
        elif isinstance(v, str):
            for tok in re.findall(r"\d[\d.]*", v):
                out.add(tok.rstrip("."))
    walk(b)
    return out


def for_narrator(b: dict) -> dict:
    """The briefing as the narrator should see it.

    Two things are withheld deliberately.

    `demand.*.weight` is an opportunity-weighted score with no unit. Handed the
    bare number the model wrote "data is 43.9% of tech demand" -- every digit
    of which is in the JSON, so `check()` passed it, and all of which is wrong.
    The unit was invented, not the figure. Rank order carries everything we
    actually want said here, so the weights do not go.

    `headline` is withheld because the model otherwise returns it verbatim and
    we get the deterministic sentence back with an API bill attached.
    """
    out = {k: v for k, v in b.items() if k != "headline"}
    dem = out.get("demand") or {}
    out["demand"] = {
        k: [i["name"] for i in v]                 # ranked, most demand first
        for k, v in dem.items() if isinstance(v, list)
    }
    return out


def write(client, model: str, b: dict) -> dict:
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=INSTRUCTION,
        response_mime_type="application/json",
        response_schema=SCHEMA,
        temperature=0.3,          # prose, but not a creative writing exercise
    )
    payload = json.dumps(for_narrator(b), ensure_ascii=False, indent=1)
    resp = client.models.generate_content(model=model, contents=payload, config=cfg)
    return json.loads(resp.text)


def run(args) -> int:
    data_dir: Path = args.data
    src = data_dir / "briefing.json"
    if not src.exists():
        print("ERROR: run `python -m opradar.brief` first.", file=sys.stderr)
        return 1
    b = json.loads(src.read_text(encoding="utf-8"))

    from .extract import build_client
    client = build_client(args.project, args.location)
    got = write(client, args.model, b)

    prose = " ".join([got.get("headline", "")] + list(got.get("paragraphs") or []))
    bad = check(prose, allowed_numbers(b)) + check_units(prose)
    if bad and not args.force:
        print(f"REFUSED: the narration states figures the briefing does not: "
              f"{sorted(set(bad))}", file=sys.stderr)
        print("This is the guard working. Re-run to resample, or --force to "
              "write it anyway.", file=sys.stderr)
        return 2

    out = {
        "headline": got.get("headline", ""),
        "paragraphs": got.get("paragraphs") or [],
        "model": args.model,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": b.get("generated_at"),
        "unverified_numbers": sorted(set(bad)),
    }
    dst = data_dir / "briefing_narrated.json"
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  {out['headline']}", file=sys.stderr)
    print(f"  {len(out['paragraphs'])} paragraphs -> {dst}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.narrate")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--project", default=None)
    p.add_argument("--location", default="europe-west4")
    p.add_argument("--force", action="store_true",
                   help="write even if the number check fails")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
