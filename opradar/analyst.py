"""The analyst -- on-demand AI over facts that were counted in pandas.

    python -m opradar.ask --project <gcp-project-id>     serves this at /ai

This is the third place OpRadar calls a model, and it obeys the same contract
as the other two (`opradar.extract`, `opradar.narrate`):

    1. pandas   -> facts       every number, name, quote and URL, assembled
                               deterministically from the parquet files
    2. model    -> words       the model is handed ONLY the facts and returns
                               prose plus INDICES into the lists we gave it
    3. code     -> render      quotes and links are rendered from our own data,
                               never from the model's output

So the model cannot invent a company, a number, a job title or a quote. It
chooses which of our facts to talk about and how to say it. Two guards close
the remaining gap: `narrate.check` rejects any figure in the prose that is not
in the facts, and every citation is an integer index that is bounds-checked
before it is used.

Five tasks, all reachable from the UI:

    company     the README's own brief -- opportunity, reasoning, play, risks
    outreach    how to approach them, inside German law (see CHANNELS)
    summary     what a filtered list of companies has in common
    gap         a sourcing brief for one capability cell
    cohort      what a briefing cohort means for the week

Answers are cached to `analysis_cache.json` keyed by task, subject and a
version stamp, so a second click is instant, the demo works with the network
unplugged, and re-running costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import narrate
from .config import CONFIG, config_hash

# Bump when a schema or an instruction changes: cached answers carrying an
# older stamp are regenerated rather than mixed with new ones.
ANALYST_VERSION = 7

CACHE_NAME = "analysis_cache.json"

MAX_EVIDENCE = 8
MAX_QUOTES = 6


# ---------------------------------------------------------------------------
# state -- every table this module reads, loaded once
# ---------------------------------------------------------------------------

class State:
    """The parquet files behind every answer. Loaded lazily, shared, read-only.

    Missing optional tables are normal: `enrichment.parquet` exists only after
    `opradar.enrich extract` has run, and every fact builder below degrades to
    what it can actually count rather than assuming.
    """

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.lock = threading.Lock()
        self.opp = pd.read_parquet(self.dir / "opportunities.parquet")
        # Only the join is needed here: the citable job ads come from the
        # scorer's own `evidence` column, already trimmed and URL-bearing.
        self.postings = self._opt("postings.parquet",
                                  columns=["posting_id", "company_key"])
        self.enrich = self._opt("enrichment.parquet")
        self.details = self._opt("details.parquet")
        self.plan = self._opt("capability_plan.parquet")
        self.cells = self._opt("cells.parquet")
        self.brief = self._json("briefing.json")
        self.cache_path = self.dir / CACHE_NAME
        self.cache = self._load_cache()
        # company_key -> refnr list, built once; the per-company joins below
        # are the hot path and scanning 70k postings per click is not free
        self.refnrs: dict[str, list[str]] = {}
        if self.postings is not None:
            keys = self.opp["company_key"].tolist()
            sub = self.postings[self.postings["company_key"].isin(set(keys))]
            for key, grp in sub.groupby("company_key"):
                self.refnrs[str(key)] = grp["posting_id"].astype(str).tolist()

    def _opt(self, name: str, columns=None):
        path = self.dir / name
        if not path.exists():
            return None
        try:
            return pd.read_parquet(path, columns=columns)
        except Exception:                      # a column list that no longer fits
            return pd.read_parquet(path)

    def _json(self, name: str):
        path = self.dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_cache(self) -> dict:
        """Answers written by THIS version of the analyst.

        The version stamp is part of the cache key, so an answer written before
        a schema change is already unreachable. Dropping it on load as well
        keeps the file from growing a dead entry per change, and keeps the
        count the /ai probe reports honest -- it should say how many answers
        are ready, not how many were ever written.
        """
        if not self.cache_path.exists():
            return {}
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {k: v for k, v in raw.items()
                if isinstance(v, dict) and v.get("v") == ANALYST_VERSION}

    def get(self, key: str):
        with self.lock:
            return self.cache.get(key)

    def put(self, key: str, value: dict) -> None:
        with self.lock:
            self.cache[key] = value
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self.cache_path)

    def row(self, name: str) -> pd.Series | None:
        """One company by display name, then by key, then case-insensitively."""
        m = self.opp[self.opp["company_name"] == name]
        if not len(m):
            m = self.opp[self.opp["company_key"] == name]
        if not len(m):
            low = str(name).strip().lower()
            m = self.opp[self.opp["company_name"].astype(str).str.lower() == low]
        return None if not len(m) else m.iloc[0]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _j(v, default):
    """A column that may hold JSON text, a real object, or nothing."""
    if v is None or (isinstance(v, float) and v != v):
        return default
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return default
    return v


def _i(v, default=0):
    return default if v is None or pd.isna(v) else int(v)


def _f(v, default=0.0):
    return default if v is None or pd.isna(v) else round(float(v), 3)


def _pick(items: list, idx, limit: int) -> list:
    """Model-chosen indices -> our own objects. Out-of-range silently dropped.

    This is the whole citation guard: the model returns integers, so a
    hallucinated quote is not possible -- only a wrong choice among real ones.
    """
    out, seen = [], set()
    for raw in (idx or []):
        try:
            i = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(items) and i not in seen:
            seen.add(i)
            out.append(items[i])
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# facts -- pandas only, no model
# ---------------------------------------------------------------------------

SIGNAL_LABEL = {
    "unmet": "roles they cannot fill",
    "expansion": "hiring above their own baseline",
    "programme": "one concentrated programme, not scattered backfill",
    "seniority": "weighted to senior roles",
    "serviceability": "how much of it our bench could staff",
    "dealsize": "how many people we could place at once",
}

# Why each signal carries the weight it does. Quoted from config.py so the
# explanation on screen is the one the scorer was actually built on.
WEIGHT_WHY = {
    "unmet": "the definitional core, and the only signal verified against an "
             "authority outside our own snapshot",
    "programme": "the pattern the brief exists to find, though stack coverage "
                 "is only about half the pool",
    "serviceability": "an opportunity we cannot staff is not an opportunity, "
                      "but our bench is synthetic, so it discounts rather "
                      "than decides",
    "expansion": "real, but two observations support a direction, not a trend "
                 "-- deliberately the lowest",
    "seniority": "a strong buying trigger, on 24% coverage",
    "dealsize": "one placement is a body-shop order, a team is a project we "
                "can lead",
}


def company_facts(st: State, name: str) -> dict | None:
    """Everything we know about one company, counted, with its citations."""
    r = st.row(name)
    if r is None:
        return None
    key = str(r["company_key"])

    weights = CONFIG["signal_weights"]
    signals = []
    for sig, label in SIGNAL_LABEL.items():
        eff = _f(r.get(f"{sig}_eff"))
        signals.append({
            "signal": sig,
            "means": label,
            "strength_0_to_1": eff,
            "weight_in_score": weights.get(sig, 0),
            "share_of_this_score": _f(r.get(f"contrib_{sig}")),
            "why_it_carries_that_weight": WEIGHT_WHY.get(sig, ""),
        })

    evidence = _j(r.get("evidence"), [])[:MAX_EVIDENCE]
    citations = [{
        "n": i,
        "job_title": e.get("title"),
        "days_old_at_crawl": e.get("age_days"),
        "role_family": e.get("family"),
        "seniority": e.get("seniority"),
    } for i, e in enumerate(evidence)]

    timeline = _j(r.get("timeline"), [])
    live_ads = sum(1 for t in timeline if t.get("live") is True)
    dead_ads = sum(1 for t in timeline if t.get("live") is False)

    facts = {
        "company": str(r["company_name"]),
        "rank_in_pool": _i(r.get("rank")),
        "companies_in_pool": int(len(st.opp)),
        "opportunity_percentile": _f(r.get("opportunity")),
        "confidence_band": str(r.get("confidence_band")),
        "segment": str(r.get("segment")),
        "segment_confirmed_by_outside_source": bool(r.get("segment_verified")),
        "segment_reason": str(r.get("segment_reason") or ""),
        "signals": signals,
        "from_our_june_crawl": {
            "it_ads_we_hold": _i(r.get("it_n")),
            "of_those_still_live": live_ads,
            "of_those_taken_down": dead_ads,
            "open_over_6_weeks_at_crawl": _i(r.get("snap_aged_45")),
            "senior_or_lead_roles": _i(r.get("senior_k")),
            "median_ad_age_days": _i(r.get("median_age")),
            "technology_mix": _j(r.get("tech_mix"), {}),
            "role_mix": _j(r.get("role_mix"), {}),
        },
        "our_side": {
            "roles_we_hold_an_ad_for": _i(r.get("atoms_total")),
            "of_those_our_bench_covers": _i(r.get("atoms_covered")),
            "people_we_could_place_at_once": _f(r.get("placeable_w")),
            "skills_we_cannot_cover": _j(r.get("uncovered_families"), {}),
        },
        "citable_job_ads": citations,
    }

    if bool(r.get("live_verified")):
        facts["on_the_board_today"] = {
            "it_roles_open": _i(r.get("now_it_stock")),
            "of_those_open_over_a_month": _i(r.get("now_aged_open")),
            "new_it_roles_in_28_days": _i(r.get("now_it_flow_28")),
            "checked_on": str(r.get("ba_checked_at"))[:10],
        }
    else:
        facts["on_the_board_today"] = (
            "NOT RE-OBSERVED. The live board could not be matched to this "
            "company, so nothing is known about what they are doing now.")

    facts.update(_ad_text_facts(st, key))
    cohorts = cohorts_of(r)
    facts["behaviour"] = {
        "cohorts": cohorts,
        "what_they_mean": {c: COHORT_MEANING[c] for c in cohorts
                           if c in COHORT_MEANING},
    }
    facts["delivery"] = delivery_model(st, key)
    return facts


def _ad_text_facts(st: State, key: str) -> dict:
    """What reading the advertisements added, and the quotes we may cite."""
    out: dict = {"advertisement_text": "Not read for this company yet.",
                 "citable_quotes": []}
    refs = st.refnrs.get(key) or []
    if st.enrich is None or not refs:
        return out
    e = st.enrich[st.enrich["refnr"].isin(set(refs))]
    if not len(e):
        return out

    topics = [t for t in e["project_topic"].fillna("").tolist() if t.strip()]
    phases = {k: int(v) for k, v in e["project_phase"].value_counts().items()
              if k != "unclear"}
    techs: dict[str, int] = {}
    for v in e["technologies"].dropna():
        for t in _j(v, []):
            techs[t] = techs.get(t, 0) + 1
    blockers: dict[str, int] = {}
    for v in e["blockers"].dropna():
        for b in _j(v, []):
            blockers[b] = blockers.get(b, 0) + 1

    # Deduplicate, and put the commercially interesting quotes first. [measured]
    # a company's blocker quotes are near-identical by construction -- six ads
    # asking for "sehr gute Deutschkenntnisse" produce six of the same sentence,
    # which crowds out the one ad that says they already buy external help.
    quotes, seen = [], set()
    ranked = e.assign(_buy=e["buys_external"].fillna(False).astype(bool)) \
              .sort_values("_buy", ascending=False)
    for row in ranked.itertuples():
        q = (getattr(row, "evidence", "") or "").strip()
        if not q:
            continue
        # Punctuation-insensitive: [measured] "Sehr gute Deutsch- und gute
        # Englischkenntnisse." and the same sentence without the full stop are
        # two different strings and both reached the drawer, so five of six
        # quotes on the rank-1 company said the same thing.
        fold = re.sub(r"[^a-z0-9]+", " ", q.lower()).strip()[:60]
        if fold in seen:
            continue
        seen.add(fold)
        quotes.append({"quote": q, "refnr": str(row.refnr),
                       "buying_signal": bool(getattr(row, "_buy", False))})
        if len(quotes) >= MAX_QUOTES:
            break

    out["advertisement_text"] = {
        "ads_read_in_full": int(len(e)),
        "named_programmes_in_their_own_words": topics[:8],
        "project_phases": phases,
        "technologies_named_in_the_text": dict(
            sorted(techs.items(), key=lambda kv: -kv[1])[:12]),
        "ads_saying_they_already_buy_external_it": int(
            e["buys_external"].fillna(False).sum()),
        "requirements_we_could_not_meet": blockers,
        "languages": {k: int(v) for k, v in e["language"].value_counts().items()},
    }
    out["citable_quotes"] = [
        {"n": i, "quote": q["quote"], "is_a_buying_signal": q["buying_signal"]}
        for i, q in enumerate(quotes)]
    out["_quote_objects"] = quotes
    return out


def cohorts_of(r: pd.Series) -> list[str]:
    """The behaviours this company shows, by `opradar.brief`'s own definitions.

    Computed from the row rather than looked up in `briefing.json`, because
    that file lists only the top eight of each cohort for display -- reading
    membership out of it told us [measured] that the rank-1 company was "not
    in a cohort" while it was posting four new roles a month.

    A company can be in two at once: still advertising (accelerating) while
    four in five of its open roles rot (stuck) is a real and common shape.
    """
    if not bool(r.get("live_verified")):
        return ["not re-observed on the board"]
    stock, aged = _i(r.get("now_it_stock")), _i(r.get("now_aged_open"))
    flow, it_n = _i(r.get("now_it_flow_28")), _i(r.get("it_n"))
    out = []
    if flow == 0 and stock > 0 and aged >= stock:
        out.append("stalled")
    if stock >= 5 and aged / stock >= 0.8:
        out.append("stuck")
    if flow > 0:
        out.append("accelerating")
    if flow == 0 and it_n >= 3 and "stalled" not in out:
        out.append("quiet")
    return out or ["no notable change"]


def delivery_model(st: State, key: str) -> dict:
    """Managed delivery or staff augmentation -- decided in code, not by a model.

    This is a legal question, not a judgement call. Supplying people who work
    under the client's instructions in Germany is Arbeitnehmerueberlassung: it
    needs an AUEG licence, and the client's works council has a say under
    section 99 BetrVG. A Werk-/Dienstvertrag with our own steering avoids both.
    The board publishes its own labour-leasing flag, so where we have it the
    answer is observed rather than inferred.
    """
    out = {"verdict": "managed_delivery",
           "why": "Nothing in these advertisements asks for people under the "
                  "client's own direction, so a delivery contract with our own "
                  "steering is the safe shape.",
           "evidence": "no labour-leasing flag and no on-site-only requirement"}
    refs = set(st.refnrs.get(key) or [])
    if not refs:
        return out

    anue = 0
    if st.details is not None and "is_anue" in st.details.columns:
        d = st.details[st.details["refnr"].isin(refs)]
        anue = int(d["is_anue"].fillna(False).astype(bool).sum()) if len(d) else 0

    onsite = 0
    if st.enrich is not None:
        e = st.enrich[st.enrich["refnr"].isin(refs)]
        for v in e["blockers"].dropna() if len(e) else []:
            if "onsite_only" in _j(v, []):
                onsite += 1

    if anue:
        out = {"verdict": "leasing_licence_needed",
               "why": "The job board flags advertisements here as "
                      "Arbeitnehmerueberlassung, so this client already buys "
                      "leased labour. Selling that shape needs an AUEG licence "
                      "and works-council consent; a delivery contract does not.",
               "evidence": f"{anue} advertisement(s) carry the board's own "
                           f"labour-leasing flag"}
    elif onsite:
        out = {"verdict": "integration_risk",
               "why": "These roles are written to be worked on the client's "
                      "site. Once our people take the client's instructions on "
                      "site it is labour leasing in substance, so scope the "
                      "work as a deliverable we own.",
               "evidence": f"{onsite} advertisement(s) require on-site presence"}
    return out


def list_facts(st: State, names: list[str]) -> dict:
    """What a set of companies has in common. The set is the user's filter."""
    sel = st.opp[st.opp["company_name"].isin(set(names))] if names else st.opp
    if not len(sel):
        return {"companies": 0}

    tech: dict[str, int] = {}
    roles: dict[str, int] = {}
    for v in sel["tech_mix"]:
        for k, n in _j(v, {}).items():
            tech[k] = tech.get(k, 0) + int(n)
    for v in sel["role_mix"]:
        for k, n in _j(v, {}).items():
            roles[k] = roles.get(k, 0) + int(n)

    live = sel[sel["live_verified"] == True]                     # noqa: E712
    top = sel.sort_values("rank").head(6)
    return {
        "companies_in_this_view": int(len(sel)),
        "companies_in_the_whole_pool": int(len(st.opp)),
        "top_of_this_view": [
            {"rank": _i(r.rank), "company": r.company_name,
             "score": _f(r.opportunity),
             "it_ads": _i(r.it_n),
             "open_on_board_today": _i(r.now_it_stock),
             "open_over_a_month": _i(r.now_aged_open)}
            for r in top.itertuples()],
        "segments": {k: int(v) for k, v in sel["segment"].value_counts().items()},
        "confidence_bands": {k: int(v) for k, v
                             in sel["confidence_band"].value_counts().items()},
        "it_ads_we_hold_in_total": _i(sel["it_n"].sum()),
        "open_over_6_weeks_at_crawl": _i(sel["snap_aged_45"].sum()),
        "re_observed_on_the_board_today": int(len(live)),
        "open_on_the_board_today": _i(live["now_it_stock"].sum()),
        "of_those_open_over_a_month": _i(live["now_aged_open"].sum()),
        "new_it_roles_in_28_days": _i(live["now_it_flow_28"].sum()),
        "roles_we_hold_an_ad_for": _i(sel["atoms_total"].sum()),
        "of_those_our_bench_covers": _i(sel["atoms_covered"].sum()),
        "people_we_could_place": _f(sel["placeable_w"].sum()),
        "technology_mix": dict(sorted(tech.items(), key=lambda kv: -kv[1])[:10]),
        "role_mix": dict(sorted(roles.items(), key=lambda kv: -kv[1])[:8]),
    }


def gap_facts(st: State, cell: str) -> dict | None:
    """One capability cell: the demand behind it and who is asking for it.

    `cell` is "family/seniority/tech", the same triple the capability plan and
    the People screen use.
    """
    if st.plan is None:
        return None
    parts = [p.strip() for p in str(cell).split("/")]
    if len(parts) != 3:
        return None
    fam, sen, tech = parts
    m = st.plan[(st.plan["role_family"] == fam)
                & (st.plan["seniority"] == sen)
                & (st.plan["tech_tag"] == tech)]
    if not len(m):
        return None
    p = m.iloc[0]

    asking = []
    if st.cells is not None:
        # which ranked companies carry demand of this shape, by their own mix
        for r in st.opp.sort_values("rank").itertuples():
            mix = _j(r.tech_mix, {})
            roles = _j(r.role_mix, {})
            if tech in mix and fam in roles:
                asking.append({"rank": _i(r.rank), "company": r.company_name,
                               "ads_in_this_technology": int(mix[tech])})
            if len(asking) >= 8:
                break

    # `demand_weight` is an opportunity-weighted score with no unit, and it is
    # withheld for the reason `narrate.for_narrator` withholds the same figure:
    # handed the bare number the model writes "12.808 weighted demand units",
    # every digit of which is real and all of which is meaningless. The rank
    # carries everything we want said, and the counts are countable things.
    return {
        "cell": f"{fam} / {sen} / {tech}",
        "role_family": fam, "seniority": sen, "technology": tech,
        "priority_rank_in_the_plan": _i(p.get("priority_rank")),
        "cells_in_the_plan": int(len(st.plan)),
        "vacancies_of_this_shape": _i(p.get("atoms")),
        "companies_asking_for_it": _i(p.get("companies")),
        "consultants_on_our_bench_who_fit": _i(p.get("supply_depth")),
        # As a whole percent, not a 0-1 ratio. [measured] handed 0.15 the model
        # wrote "15% of the demand", which is the right idea with a unit it
        # invented -- the guard then flagged a correct sentence. Giving it the
        # percentage removes the conversion instead of policing it.
        "percent_of_this_demand_we_cannot_cover": round(
            _f(p.get("coverage_gap")) * 100),
        "who_is_asking": asking,
        "bench_is_synthetic": True,
    }


def cohort_facts(st: State, cohort: str) -> dict | None:
    """One behavioural cohort out of the briefing, with its members."""
    if not st.brief:
        return None
    c = st.brief.get("cohorts") or {}
    if cohort not in ("stalled", "accelerating", "quiet", "stuck"):
        return None
    return {
        "cohort": cohort,
        "what_it_means": COHORT_MEANING[cohort],
        "companies_in_it": c.get(f"{cohort}_n", 0),
        "companies_re_observed_in_total": c.get("observed_n", 0),
        "members": c.get(cohort) or [],
        "crawl_date": st.brief.get("crawl_date"),
        "board_date": st.brief.get("board_date"),
        "our_side": st.brief.get("ours") or {},
    }


COHORT_MEANING = {
    "stalled": "Stopped advertising and filled nothing: every role still open "
               "today has been open over a month. They gave up on the job "
               "board, not on the need.",
    "accelerating": "Posted new IT roles in the last four weeks on top of what "
                    "was already open. Scaling faster than they can hire.",
    "quiet": "Had IT demand when we crawled and nothing new since. Either they "
             "solved it or they stopped looking here.",
    "stuck": "Still advertising, still not filling: four in five of their open "
             "roles have been up over a month.",
}


# ---------------------------------------------------------------------------
# what each task asks the model for
# ---------------------------------------------------------------------------

_CITE = {"type": "array", "items": {"type": "integer"},
         "description": "Indices (the `n` field) of the items you are citing. "
                        "Never write a quote or a job title yourself -- name "
                        "its number and it will be printed for you."}

COMPANY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "One sentence, max 18 words, naming what "
                                    "is happening at this company."},
        "opportunity": {"type": "string",
                        "description": "What we would sell them, in one "
                                       "sentence. Name the programme if the "
                                       "advertisements name one."},
        "why_now": {"type": "string",
                    "description": "Why this week rather than any other week. "
                                   "One or two sentences, built on the cohort "
                                   "and the board's own counts."},
        "reasoning": {"type": "string",
                      "description": "Two or three sentences: what the pattern "
                                     "of hiring means, and what it implies "
                                     "they cannot do alone. This is the "
                                     "argument, not a list of figures."},
        "play": {"type": "string",
                 "description": "The approach to take, in one or two "
                                "sentences. A framework agreement, a "
                                "dedicated team, a single pilot role -- say "
                                "which and why."},
        "risks": {"type": "array", "items": {"type": "string"},
                  "description": "Two to four reasons this lead could be a "
                                 "waste of time, each grounded in the facts: "
                                 "requirements we cannot meet, thin evidence, "
                                 "an unconfirmed segment, nothing left to "
                                 "staff, a need already three months old. Be "
                                 "specific. Never write that there are no "
                                 "risks."},
        "cite_ads": _CITE,
        "cite_quotes": _CITE,
    },
    "required": ["headline", "opportunity", "why_now", "reasoning", "play",
                 "risks", "cite_ads", "cite_quotes"],
}

COMPANY_INSTRUCTION = """You brief the sales lead of a Lithuanian IT services \
company that staffs and delivers projects at German companies.

You are given facts about ONE German company, all counted from job-posting \
data. Write the brief from them.

Hard rules:
- Every number you write MUST appear in the facts. Do not add, total, average, \
round or derive any figure. If the facts do not support a sentence, do not \
write it.
- Never attach a unit the facts do not attach. A bare count is a count.
- Do not quote the advertisements yourself and do not write job titles. Put \
the number of the quote in `cite_quotes` and the number of the ad in \
`cite_ads`; they are printed under your text automatically.
- Do not invent anything about the company that is not here: no headcount, no \
revenue, no funding, no technology that is not listed, no named people.
- If `on_the_board_today` says the company was not re-observed, say what we \
know from the June crawl and do not imply anything about today.

What this reader cares about, in order: a company that stopped advertising \
while its roles are still open (the facts call this cohort "stalled" -- the \
best kind of lead, because the need is unmet and they have stopped solving it \
the cheap way); a company scaling faster than it can hire; and whether our own \
bench could actually take the work.

`risks` is not a formality. A tool that only finds reasons to be optimistic is \
one nobody trusts twice, so argue against the lead honestly.

Plain and specific. Short sentences. No marketing register, no "landscape", \
no "leverage", no "in today's fast-moving market"."""


OUTREACH_SCHEMA = {
    "type": "object",
    "properties": {
        "opening_line": {"type": "string",
                         "description": "The first sentence to say on the "
                                        "phone, in German, Sie-form. It must "
                                        "name the concrete thing we observed, "
                                        "never 'I was looking at your job "
                                        "board'."},
        "call_script_de": {"type": "string",
                           "description": "A short phone script in German, "
                                          "Sie-form: the reason for calling, "
                                          "one pain, one question. Under 90 "
                                          "words. No greeting boilerplate."},
        "call_script_en": {"type": "string",
                           "description": "The same script in English, for the "
                                          "rep who does not speak German."},
        "written_note": {"type": "string",
                         "description": "A short written note in German for a "
                                        "letter or a LinkedIn connection "
                                        "request. Under 60 words."},
        "expect_to_hear": {"type": "array", "items": {"type": "string"},
                           "description": "Two or three objections they are "
                                          "likely to raise, each with the "
                                          "one-sentence answer, formatted "
                                          "'Objection -- answer'."},
        "cite_quotes": _CITE,
    },
    "required": ["opening_line", "call_script_de", "call_script_en",
                 "written_note", "expect_to_hear", "cite_quotes"],
}

OUTREACH_INSTRUCTION = """You prepare a first approach to a German company for \
a Lithuanian IT services firm.

You are given facts counted from job postings, and a legal channel ruling that \
has already been made for you. Write the approach.

Hard rules:
- Every number MUST appear in the facts. Do not derive figures.
- German text is Sie-form throughout, and reads like a person wrote it.
- Lead with the business situation, never with the mechanics of how we found \
them. "Sie besetzen seit Monaten Rollen im SAP-Umfeld nicht" is right; "ich \
habe Ihre Stellenanzeigen gesehen" is wrong -- it is the line that gets a rep \
hung up on.
- One pain. Not three. The facts contain many; choose the one the figures \
support best.
- Do not promise a rate, a headcount, a timeline or a saving. Nothing in the \
facts supports any of those.
- Respect `delivery`: if the ruling is `managed_delivery`, offer a delivery \
contract we own the outcome of, not bodies under their direction. If the \
ruling is `leasing_licence_needed` or `integration_risk`, do not offer staff \
augmentation at all -- scope the work as a deliverable instead.
- Quote the advertisement only by number in `cite_quotes`."""


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "One sentence, max 18 words, naming what "
                                    "this set of companies has in common."},
        "paragraphs": {"type": "array", "items": {"type": "string"},
                       "description": "Two short paragraphs, 40-60 words each: "
                                      "what the group is doing, and what it "
                                      "means for who to call first."},
        "watch_out": {"type": "string",
                      "description": "One sentence on what this view does NOT "
                                     "show -- companies not re-observed, thin "
                                     "evidence, roles we could not staff."},
    },
    "required": ["headline", "paragraphs", "watch_out"],
}

SUMMARY_INSTRUCTION = """You summarise a filtered list of German companies for \
the sales lead of a Lithuanian IT services firm.

Every number you write MUST appear in the facts you are given. Name at most \
four companies; the list itself is on screen beneath you and repeating it in \
prose is worse than useless. Say what the group has in common and who to call \
first. Plain sentences, no marketing register, no invented units."""


GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "One sentence naming the gap and its size."},
        "what_it_costs_us": {"type": "string",
                             "description": "One or two sentences on what we "
                                            "cannot sell because of this gap, "
                                            "grounded in the demand figures."},
        "who_to_hire": {"type": "string",
                        "description": "The profile to look for, in one or two "
                                       "sentences: role family, seniority and "
                                       "the technology. Describe the person, "
                                       "not a headcount."},
        "caveat": {"type": "string",
                   "description": "One sentence noting the bench these figures "
                                  "are measured against is synthetic."},
    },
    "required": ["headline", "what_it_costs_us", "who_to_hire", "caveat"],
}

GAP_INSTRUCTION = """You advise the delivery lead of a Lithuanian IT services \
firm on which capability to add next.

You are given one capability cell: the demand for it, how many companies ask \
for it, and how deep our bench is. Every number you write must appear in \
those facts.

Do not invent a hiring target. "Hire ten of these" is a figure nobody \
counted; the vacancy count and the bench depth are in the facts and they make \
the case on their own. No salaries, no timelines, no costs, none of which are \
here. The bench is synthetic and you must say so once, in `caveat`, without \
hedging the rest."""


COHORT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "One sentence, max 18 words."},
        "what_to_do": {"type": "string",
                       "description": "Two or three sentences on what this "
                                      "cohort means for the week's calls."},
        "first_calls": {"type": "array", "items": {"type": "string"},
                        "description": "Two or three company names taken "
                                       "EXACTLY from the members list, each "
                                       "with a half-sentence reason."},
    },
    "required": ["headline", "what_to_do", "first_calls"],
}

COHORT_INSTRUCTION = """You brief a sales lead on one behavioural cohort of \
German companies.

Every number MUST appear in the facts. Name only companies that appear in the \
members list, spelled exactly as they are there. Say what the cohort means for \
who to ring this week. Plain sentences, no marketing register."""


# ---------------------------------------------------------------------------
# the model call, and the guard around it
# ---------------------------------------------------------------------------

def _call(client, model: str, instruction: str, schema: dict, facts: dict,
          temperature: float = 0.25) -> dict:
    from google.genai import types
    payload = json.dumps({k: v for k, v in facts.items()
                          if not k.startswith("_")},
                         ensure_ascii=False, indent=1)
    resp = client.models.generate_content(
        model=model, contents=payload,
        config=types.GenerateContentConfig(
            system_instruction=instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature))
    return json.loads(resp.text)


def _prose_of(got: dict) -> str:
    """Every string the model produced, for the number check."""
    out: list[str] = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(got)
    return " ".join(out)


# German text legitimately carries figures the facts do not: a date, a
# Paragraph reference, a time of day. The guard only ever looked at numbers
# above twelve, so this list stays very short.
_GUARD_EXEMPT = {"99"}          # section 99 BetrVG, cited in the legal note

_PCT = re.compile(r"(\d[\d.,]*)\s*%")


def _bad_percentages(prose: str, allowed: set[str]) -> list[str]:
    """Percent signs attached to a number the facts do not state.

    `narrate.check_units` bans the percent sign outright, and it is right to:
    the briefing it guards holds no percentages at all, so one in the prose was
    always invented. The analyst's facts sometimes DO hold a percentage, so
    here the sign is checked rather than banned -- a percentage we counted may
    be quoted, and one we did not still cannot be.
    """
    bad = []
    for tok in _PCT.findall(prose):
        clean = tok.rstrip(".,").replace(",", "")
        if clean not in allowed and clean.rstrip("0").rstrip(".") not in allowed:
            bad.append(tok + "%")
    return bad


def guard(got: dict, facts: dict) -> list[str]:
    """Figures in the prose that are not in the facts. Empty list is a pass."""
    allowed = narrate.allowed_numbers(facts) | _GUARD_EXEMPT
    prose = _prose_of(got)
    return narrate.check(prose, allowed) + _bad_percentages(prose, allowed)


# ---------------------------------------------------------------------------
# tasks -- facts -> model -> render blocks
# ---------------------------------------------------------------------------

def _ad_links(evidence: list, idx) -> dict | None:
    picked = _pick(evidence, idx, MAX_EVIDENCE)
    if not picked:
        return None
    return {"kind": "links", "label": "The advertisements behind this",
            "items": [{"title": e.get("title"), "url": e.get("url"),
                       "meta": f"{e.get('age_days')}d old · {e.get('family')}"}
                      for e in picked]}


def _quote_block(facts: dict, idx) -> dict | None:
    picked = _pick(facts.get("_quote_objects") or [], idx, MAX_QUOTES)
    if not picked:
        return None
    return {"kind": "quotes", "label": "In their own words",
            "items": [{"quote": q["quote"],
                       "note": "says they buy external IT" if q["buying_signal"] else ""}
                      for q in picked]}


DELIVERY_LABEL = {
    "managed_delivery": ("Sell managed delivery", "pos"),
    "leasing_licence_needed": ("Leasing licence needed for staff augmentation", "warn"),
    "integration_risk": ("On-site integration risk", "warn"),
}


def task_company(st: State, client, model: str, args: dict) -> dict:
    name = str(args.get("company") or "")
    facts = company_facts(st, name)
    if facts is None:
        raise KeyError(f"{name!r} is not in the ranked pool")

    got = _call(client, model, COMPANY_INSTRUCTION, COMPANY_SCHEMA, facts)
    bad = guard(got, facts)

    r = st.row(name)
    evidence = _j(r.get("evidence"), [])[:MAX_EVIDENCE]
    dlabel, dtone = DELIVERY_LABEL.get(facts["delivery"]["verdict"],
                                       ("Delivery model", ""))

    blocks = [
        {"kind": "lede", "text": got["headline"]},
        {"kind": "section", "label": "The opportunity", "text": got["opportunity"]},
        {"kind": "section", "label": "Why now", "text": got["why_now"]},
        {"kind": "section", "label": "Reasoning", "text": got["reasoning"]},
        {"kind": "section", "label": "The play", "text": got["play"]},
        {"kind": "verdict", "label": dlabel, "tone": dtone,
         "text": facts["delivery"]["why"],
         "note": "Observed: " + facts["delivery"]["evidence"]},
        {"kind": "bullets", "label": "Why this could be a waste of time",
         "tone": "warn", "items": got["risks"]},
    ]
    q = _quote_block(facts, got.get("cite_quotes"))
    if q:
        blocks.append(q)
    links = _ad_links(evidence, got.get("cite_ads"))
    if links:
        blocks.append(links)

    return _wrap(st, "company", name, blocks, bad, model,
                 title=facts["company"],
                 subtitle=f"Rank {facts['rank_in_pool']} of "
                          f"{facts['companies_in_pool']} · "
                          f"{facts['confidence_band']} confidence · "
                          + ", ".join(facts["behaviour"]["cohorts"]))


def task_outreach(st: State, client, model: str, args: dict) -> dict:
    name = str(args.get("company") or "")
    facts = company_facts(st, name)
    if facts is None:
        raise KeyError(f"{name!r} is not in the ranked pool")

    # The channel is a legal question and is decided here, not by the model.
    facts["channel_ruling"] = CHANNELS
    got = _call(client, model, OUTREACH_INSTRUCTION, OUTREACH_SCHEMA, facts)
    bad = guard(got, facts)

    blocks = [
        {"kind": "lede", "text": got["opening_line"]},
        {"kind": "script", "label": "On the phone — German", "lang": "de",
         "text": got["call_script_de"]},
        {"kind": "script", "label": "On the phone — English", "lang": "en",
         "text": got["call_script_en"]},
        {"kind": "script", "label": "Letter or LinkedIn note — German",
         "lang": "de", "text": got["written_note"]},
        {"kind": "bullets", "label": "Expect to hear", "items": got["expect_to_hear"]},
        {"kind": "verdict", "label": "Allowed channels", "tone": "warn",
         "text": CHANNELS["allowed"],
         "note": CHANNELS["not_allowed"]},
    ]
    q = _quote_block(facts, got.get("cite_quotes"))
    if q:
        blocks.append(q)

    return _wrap(st, "outreach", name, blocks, bad, model,
                 title=f"Approaching {facts['company']}",
                 subtitle="Drafted for a human to send, never sent automatically")


# The rule, stated once, applied by code. Cold electronic advertising to a
# business needs prior consent in Germany (UWG section 7); a telephone call to
# a business is permitted where there is a concrete indication of interest,
# which an open advertisement for what we sell is. Post is unrestricted.
CHANNELS = {
    "allowed": "Telephone and post. A company advertising roles we could staff "
               "is a concrete indication of interest, which is what a business "
               "call requires.",
    "not_allowed": "Not cold email and not a LinkedIn or XING message: in "
                   "Germany both count as electronic advertising and need "
                   "prior consent, business-to-business included. A connection "
                   "request carrying no advertising is fine.",
}


def task_summary(st: State, client, model: str, args: dict) -> dict:
    names = [str(n) for n in (args.get("companies") or [])]
    label = str(args.get("label") or "this view")
    facts = list_facts(st, names)
    if not facts.get("companies_in_this_view"):
        raise KeyError("nothing in this view to summarise")

    got = _call(client, model, SUMMARY_INSTRUCTION, SUMMARY_SCHEMA, facts)
    bad = guard(got, facts)

    blocks = [{"kind": "lede", "text": got["headline"]}]
    blocks += [{"kind": "para", "text": p} for p in got["paragraphs"]]
    blocks.append({"kind": "verdict", "label": "What this does not show",
                   "tone": "warn", "text": got["watch_out"], "note": ""})
    blocks.append({"kind": "table", "label": "Counted from the filtered rows",
                   "columns": ["companies", "IT ads", "open today",
                               "open over a month", "we could place"],
                   "rows": [[facts["companies_in_this_view"],
                             facts["it_ads_we_hold_in_total"],
                             facts["open_on_the_board_today"],
                             facts["of_those_open_over_a_month"],
                             facts["people_we_could_place"]]]})

    key = hashlib.sha256("|".join(sorted(names)).encode()).hexdigest()[:16]
    return _wrap(st, "summary", key, blocks, bad, model,
                 title=f"{facts['companies_in_this_view']} companies",
                 subtitle=label)


def task_gap(st: State, client, model: str, args: dict) -> dict:
    cell = str(args.get("cell") or "")
    facts = gap_facts(st, cell)
    if facts is None:
        raise KeyError(f"{cell!r} is not in the capability plan")

    got = _call(client, model, GAP_INSTRUCTION, GAP_SCHEMA, facts)
    bad = guard(got, facts)

    blocks = [
        {"kind": "lede", "text": got["headline"]},
        {"kind": "section", "label": "What it costs us", "text": got["what_it_costs_us"]},
        {"kind": "section", "label": "Who to hire", "text": got["who_to_hire"]},
        {"kind": "verdict", "label": "Caveat", "tone": "warn",
         "text": got["caveat"], "note": ""},
    ]
    if facts["who_is_asking"]:
        blocks.append({"kind": "table", "label": "Ranked companies asking for it",
                       "columns": ["rank", "company", "ads in this technology"],
                       "rows": [[a["rank"], a["company"], a["ads_in_this_technology"]]
                                for a in facts["who_is_asking"]]})

    return _wrap(st, "gap", cell, blocks, bad, model,
                 title=facts["cell"],
                 subtitle=f"Priority {facts['priority_rank_in_the_plan']} in the "
                          f"capability plan")


def task_cohort(st: State, client, model: str, args: dict) -> dict:
    cohort = str(args.get("cohort") or "")
    facts = cohort_facts(st, cohort)
    if facts is None:
        raise KeyError(f"{cohort!r} is not a cohort")

    got = _call(client, model, COHORT_INSTRUCTION, COHORT_SCHEMA, facts)
    bad = guard(got, facts)

    blocks = [
        {"kind": "lede", "text": got["headline"]},
        {"kind": "section", "label": "What to do about it", "text": got["what_to_do"]},
        {"kind": "bullets", "label": "Call these first", "items": got["first_calls"]},
    ]
    return _wrap(st, "cohort", cohort, blocks, bad, model,
                 title=cohort.capitalize(),
                 subtitle=f"{facts['companies_in_it']} companies · "
                          f"{facts['crawl_date']} crawl → {facts['board_date']} board")


TASKS = {
    "company": task_company,
    "outreach": task_outreach,
    "summary": task_summary,
    "gap": task_gap,
    "cohort": task_cohort,
}


# ---------------------------------------------------------------------------
# wrapping, caching, entry point
# ---------------------------------------------------------------------------

def _wrap(st: State, task: str, subject: str, blocks: list,
          bad: list, model: str, title: str, subtitle: str) -> dict:
    """Attach the provenance every generated block on this product carries."""
    when = datetime.now(timezone.utc).isoformat()
    foot = [f"Written by {model} from figures counted in pandas",
            f"config {config_hash()}"]
    if st.brief:
        foot.append(f"{st.brief.get('crawl_date')} crawl → "
                    f"{st.brief.get('board_date')} board")
    out = {
        "task": task, "subject": subject, "title": title, "subtitle": subtitle,
        "blocks": blocks,
        "footer": " · ".join(foot),
        "model": model, "written_at": when,
        "unverified_numbers": sorted(set(bad)),
        "v": ANALYST_VERSION,
    }
    if bad:
        # The guard fired. Say so on the block itself rather than hiding it:
        # a figure we cannot trace is exactly the thing this product exists
        # not to print silently.
        out["blocks"] = blocks + [{
            "kind": "verdict", "label": "Unverified figures", "tone": "warn",
            "text": "This text states " + ", ".join(sorted(set(bad)))
                    + " — figures that are not in the facts underneath it. "
                      "Treat them as unchecked.",
            "note": "The number guard flagged this automatically."}]
    return out


def cache_key(task: str, subject: str) -> str:
    raw = f"{ANALYST_VERSION}|{config_hash()}|{task}|{subject}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def run(st: State, client, model: str, task: str, args: dict,
        refresh: bool = False) -> dict:
    """One analysis. Cached by task and subject, so a second click is free."""
    if task not in TASKS:
        raise KeyError(f"unknown task {task!r}")
    subject = str(args.get("company") or args.get("cell")
                  or args.get("cohort") or "")
    if task == "summary":
        names = sorted(str(n) for n in (args.get("companies") or []))
        subject = hashlib.sha256("|".join(names).encode()).hexdigest()[:16]

    key = cache_key(task, subject)
    if not refresh:
        hit = st.get(key)
        if hit:
            return {**hit, "cached": True}

    out = TASKS[task](st, client, model, args)
    out["cached"] = False
    st.put(key, out)
    return out


# ---------------------------------------------------------------------------
# cli -- warm the cache before a demo
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(
        prog="opradar.analyst",
        description="Generate and cache the AI analyses the UI asks for.")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--project", default=None)
    p.add_argument("--location", default="europe-west4")
    p.add_argument("--top", type=int, default=10,
                   help="warm the company brief for the top N companies")
    p.add_argument("--outreach", type=int, default=6,
                   help="also warm the approach for the top N")
    p.add_argument("--cohorts", action="store_true",
                   help="warm all four briefing cohorts")
    p.add_argument("--gaps", type=int, default=0,
                   help="warm the top N capability gaps")
    p.add_argument("--refresh", action="store_true",
                   help="regenerate even when cached")
    args = p.parse_args(argv)

    if not (args.data / "opportunities.parquet").exists():
        print("ERROR: run `python -m opradar.score` first.", file=sys.stderr)
        return 1

    from .extract import build_client
    st = State(args.data)
    client = build_client(args.project, args.location)

    jobs: list[tuple[str, dict]] = []
    top = st.opp.sort_values("rank")
    for r in top.head(args.top).itertuples():
        jobs.append(("company", {"company": r.company_name}))
    for r in top.head(args.outreach).itertuples():
        jobs.append(("outreach", {"company": r.company_name}))
    if args.cohorts:
        jobs += [("cohort", {"cohort": c})
                 for c in ("stalled", "accelerating", "quiet", "stuck")]
    if args.gaps and st.plan is not None:
        for r in st.plan.head(args.gaps).itertuples():
            jobs.append(("gap", {"cell": f"{r.role_family}/{r.seniority}/{r.tech_tag}"}))

    ok = fail = 0
    for i, (task, a) in enumerate(jobs, 1):
        subject = a.get("company") or a.get("cell") or a.get("cohort")
        try:
            out = run(st, client, args.model, task, a, refresh=args.refresh)
            flag = "cached" if out.get("cached") else "written"
            warn = (f"  !! unverified {out['unverified_numbers']}"
                    if out.get("unverified_numbers") else "")
            print(f"  [{i}/{len(jobs)}] {task:9} {subject[:38]:38} {flag}{warn}",
                  file=sys.stderr)
            ok += 1
        except Exception as e:                 # one bad row must not stop a warm-up
            print(f"  [{i}/{len(jobs)}] {task:9} {subject[:38]:38} FAILED "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
            fail += 1

    print(f"\n{ok} ready, {fail} failed -> {st.cache_path}", file=sys.stderr)
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
