"""Build a self-contained static UI from the parsed tables.

    python -m opradar.ui            # writes ui/index.html, then open it
    python -m opradar.ui --open     # ...and open it in the browser
    python -m opradar.ui --scope all

One HTML file with the data embedded: no server, no network. It opens by
double-click and keeps working when the venue wifi does not.

The page itself is a React app in `ui/` (Vite + TypeScript). `npm run build`
there produces `ui/dist/app.html` -- every script and stylesheet inlined --
and this module's only job is to compute the payload and drop it into that
template's data tag. The built template is committed, so refreshing the data
never needs Node; only changing the UI does:

    cd ui && npm install && npm run build     # after editing ui/src
    python -m opradar.ui                      # after re-running the pipeline
    cd ui && npm run dev                      # live-reload against ui/payload.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import reference as ref
from .ui_brief import build_brief

SCOPES = {
    "it": ("is_it_core", "IT postings (KldB 43x)"),
    "it_extended": ("is_it_extended", "IT and adjacent engineering postings (KldB 43/41/27/25)"),
    "all": (None, "all postings"),
}

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "ui" / "dist" / "app.html"

# The empty tag `ui/app.html` ships; the payload goes inside it. Matched by
# attribute rather than by exact text so a reordered attribute in a future
# Vite version cannot silently break the build.
DATA_TAG = re.compile(
    r'<script\b[^>]*\bid="opradar-data"[^>]*>\s*</script>', re.IGNORECASE)


# ---------------------------------------------------------------------------
# payload
# ---------------------------------------------------------------------------

def _dictionary(values: pd.Series) -> tuple[list[str], list[int | None]]:
    """String column -> (vocabulary, indices). Roughly halves the embedded JSON."""
    vocab: dict[str, int] = {}
    out: list[int | None] = []
    for v in values:
        if v is None or (isinstance(v, float) and v != v):
            out.append(None)
            continue
        v = str(v)
        if v not in vocab:
            vocab[v] = len(vocab)
        out.append(vocab[v])
    return list(vocab), out


def _list_dictionary(values: pd.Series) -> tuple[list[str], list[list[int]]]:
    vocab: dict[str, int] = {}
    out: list[list[int]] = []
    for lst in values:
        row = []
        for v in (lst if lst is not None else []):
            v = str(v)
            if v not in vocab:
                vocab[v] = len(vocab)
            row.append(vocab[v])
        out.append(row)
    return list(vocab), out


def build_charts(postings: pd.DataFrame, companies: pd.DataFrame) -> dict:
    groups = postings["kldb_group"].value_counts().head(10)
    it_group = ref.KLDB_GROUP["43"]

    classes = companies.groupby("company_class")["postings"].sum().sort_values(ascending=False)
    competitor_classes = {ref.CLASS_STAFFING, ref.CLASS_IT_SERVICES}

    it = postings[postings["is_it_core"]]
    tech = Counter()
    for t in it["technologies"]:
        tech.update(t)
    domains = Counter()
    for d in postings["domains"]:
        domains.update(d)

    level_order = ["helper", "skilled", "specialist", "expert"]
    levels = postings["kldb_level"].value_counts()

    months = (
        postings["posted_year_month"].value_counts().sort_index().tail(18)
    )

    age = postings["posting_age_days"]
    buckets = [
        ("0-30d", int(((age >= 0) & (age <= 30)).sum())),
        ("31-60d", int(((age > 30) & (age <= 60)).sum())),
        ("61-90d", int(((age > 60) & (age <= 90)).sum())),
        ("91-180d", int(((age > 90) & (age <= 180)).sum())),
        ("180d+", int((age > 180).sum())),
    ]

    regions = postings["region_clean"].value_counts().head(16)
    pop = {k: v for k, v in ref.REGION_POPULATION_M.items()}
    from . import text as txt
    pop_folded = {txt.fold(k): v for k, v in pop.items()}

    return {
        "kldb_groups": [[k, int(v), k == it_group] for k, v in groups.items()],
        "classes": [
            [k.replace("_", " "), int(v), k in competitor_classes] for k, v in classes.items()
        ],
        "tech": [[k, int(v)] for k, v in tech.most_common(14)],
        "domains": [[k, int(v)] for k, v in domains.most_common(10)],
        "levels": [
            [f"{lv} — {ref.KLDB_LEVEL[c][1].split(' ')[0]}", int(levels.get(lv, 0))]
            for c, (lv, _) in ref.KLDB_LEVEL.items()
            if lv in level_order
        ],
        "months": [[str(k)[2:], int(v)] for k, v in months.items()],
        "age_buckets": [[k, v] for k, v in buckets],
        "regions": [
            [k, int(v), pop_folded.get(txt.fold(str(k)))] for k, v in regions.items()
        ],
    }


def build_talent(data_dir: Path) -> dict | None:
    """Supply-side payload. Returns None when the candidate parser has not been run."""
    cand_path = data_dir / "candidates.parquet"
    if not cand_path.exists():
        return None

    candidates = pd.read_parquet(cand_path)
    openings = pd.read_parquet(data_dir / "openings.parquet")
    skills = pd.read_parquet(data_dir / "skill_market.parquet")
    report = json.loads((data_dir / "candidate_report.json").read_text(encoding="utf-8"))

    def counts(col, df=candidates, n=24):
        return [[str(k), int(v)] for k, v in df[col].value_counts().head(n).items()]

    skill_vocab, skill_idx = _list_dictionary(candidates["skills"])

    cand_cols = ["candidate_id", "role", "role_family", "seniority", "years_experience",
                 "industry", "education", "skills", "qualified_for_openings"]
    cand_rows = [
        [r.candidate_id, r.role, r.role_family, r.seniority, int(r.years_experience),
         r.industry, r.education, sk, int(r.qualified_for_openings)]
        for r, sk in zip(candidates.itertuples(), skill_idx)
    ]

    skill_cols = ["skill", "skill_family", "supply", "supply_share", "demand_must",
                  "demand_nice", "demand_weighted", "demand_share", "tension"]
    skill_rows = [
        [r.skill, r.skill_family, int(r.supply), float(r.supply_share), int(r.demand_must),
         int(r.demand_nice), float(r.demand_weighted), float(r.demand_share), float(r.tension)]
        for r in skills.itertuples()
    ]

    top_supply = skills.nlargest(14, "supply")
    return {
        "meta": {
            "candidates": int(len(candidates)),
            "openings": int(len(openings)),
            "skill_vocabulary": int(len(skills)),
            "tech_candidates": int(candidates["is_tech_role"].sum()),
            "mean_pool": float(openings["qualified_pool"].mean()),
            "mean_skills": float(candidates["skill_count"].mean()),
            "bridge_pct": report["bridge_to_german_data"]["overlap_pct"],
            "bridge_coverage": report["bridge_to_german_data"]["german_it_coverage_pct"],
            "bridge_shared": report["bridge_to_german_data"]["overlapping"],
            "bridge_missing": report["bridge_to_german_data"]["missing_from_candidates"],
        },
        "charts": {
            "role_family": counts("role_family"),
            "seniority": counts("seniority"),
            "experience": sorted(counts("experience_band"), key=lambda r: r[0]),
            "industry": counts("industry"),
            "education": counts("education"),
            "skill_family": counts("primary_skill_family"),
            "supply_demand": [
                [r.skill, float(r.supply_share), float(r.demand_share), float(r.tension)]
                for r in top_supply.itertuples()
            ],
            "tension_top": [[r.skill, float(r.tension)] for r in skills.head(10).itertuples()],
            "tension_bottom": [[r.skill, float(r.tension)]
                               for r in skills.tail(10).iloc[::-1].itertuples()],
            "role_demand": [[str(k), int(v)] for k, v in
                            openings["title"].value_counts().head(14).items()],
        },
        "dicts": {"skills": skill_vocab},
        "candidates": {"cols": cand_cols, "rows": cand_rows},
        "skills": {"cols": skill_cols, "rows": skill_rows},
        "quality": report["ground_truth_audit"],
        "options": {
            "roles": sorted(candidates["role"].unique().tolist()),
            "seniority": sorted(candidates["seniority"].unique().tolist()),
            "industries": sorted(candidates["industry"].unique().tolist()),
            "families": sorted(candidates["role_family"].unique().tolist()),
        },
    }


def build_radar(data_dir: Path) -> dict | None:
    """Ranked opportunities + validation. None until the scorer has run.

    Mirrors the scorer's own model: five signals, each already shrunk toward
    the pool prior by its evidence weight, combined as a weighted geometric
    mean and presented as a percentile. The UI ships the effective signals so
    the weight sliders can recompute the ranking in the browser against the
    same arithmetic rather than a second, looser model.
    """
    path = data_dir / "opportunities.parquet"
    if not path.exists():
        return None
    opp = pd.read_parquet(path)
    checks = json.loads((data_dir / "validation.json").read_text(encoding="utf-8"))

    seg_path = data_dir / "segments.parquet"
    segments = pd.read_parquet(seg_path) if seg_path.exists() else None
    channels = int(segments["is_channel"].sum()) if segments is not None else 0

    def _j(v, default):
        return json.loads(v) if isinstance(v, str) else (v if v is not None else default)

    def _int_or_none(v):
        return None if pd.isna(v) else int(v)

    rows = []
    for r in opp.itertuples():
        tl = _j(r.timeline, [])
        rows.append([
            int(r.rank), r.company_name, r.segment, not bool(r.segment_verified),
            float(r.opportunity), round(float(r.pressure), 4),
            # the five effective signals, in config order
            round(float(r.unmet_eff), 4), round(float(r.expansion_eff), 4),
            round(float(r.programme_eff), 4), round(float(r.seniority_eff), 4),
            round(float(r.serviceability_eff), 4), round(float(r.dealsize_eff), 4),
            float(r.serviceability), float(r.dealsize), float(r.placeable_w),
            int(r.atoms_covered), int(r.atoms_uncovered),
            _j(r.uncovered_families, {}),
            float(r.confidence), r.confidence_band,
            int(r.it_n), int(r.snap_aged_45), int(r.snap_aged_90), int(r.senior_k),
            int(r.median_age), _j(r.top_technologies, []),
            sum(1 for t in tl if t.get("live") is True),
            sum(1 for t in tl if t.get("live") is False),
            # today's board, where we could observe it: the score rests on
            # these, while the citations below can only be June's crawl
            bool(r.live_verified),
            _int_or_none(r.now_it_stock), _int_or_none(r.now_aged_open),
            tl,
        ])

    v = checks["companies"]
    cfg = __import__("opradar.config", fromlist=["CONFIG"]).CONFIG
    return {
        "meta": {
            "ranked": int(len(opp)),
            "channels": channels,
            "config_hash": str(opp["config_hash"].iloc[0]) if len(opp) else "",
            "weights": dict(cfg["signal_weights"]),
            "floor": cfg["signals"]["log_floor"],
        },
        "cols": ["rank", "name", "segment", "review", "opp", "pressure",
                 "unmet", "expansion", "programme", "seniority", "svcsig", "dealsig",
                 "svc", "deal", "placeable", "covered", "uncovered", "uncovered_families",
                 "conf", "band", "it_n", "open45", "open90", "senior_n",
                 "median_age", "techs", "live_n", "dead_n",
                 "verified", "now_stock", "now_aged", "timeline"],
        "rows": rows,
        "validation": {
            "v1_rho": v["v1_divergence"]["spearman_vs_it_postings"],
            "v1_verdict": v["v1_divergence"]["verdict"],
            "v2": v["v2_adversarial"]["verdict"],
            "v3_min": v["v3_sensitivity"]["min_overlap"],
            "v3_k": v["v3_sensitivity"]["top_k"],
            "v3_verdict": v["v3_sensitivity"]["verdict"],
        },
    }


def build_bench(data_dir: Path) -> dict | None:
    """Bench, per-consultant marginal value, and the capability plan.

    Reads only what the current scorer writes: market_pull.parquet and
    tech_gap.parquet belonged to the retired pipeline and are no longer
    produced, so demand per tag and per family is derived from cells.parquet,
    which is opportunity-weighted rather than a raw posting count.
    """
    path = data_dir / "people_value.parquet"
    if not path.exists():
        return None
    value = pd.read_parquet(path)
    cells = pd.read_parquet(data_dir / "cells.parquet")
    plan = pd.read_parquet(data_dir / "capability_plan.parquet")
    supply = pd.read_parquet(data_dir / "supply_index.parquet")
    bench = pd.read_parquet(data_dir / "bench.parquet")
    checks = json.loads((data_dir / "validation.json").read_text(encoding="utf-8"))

    def _l(v):
        return json.loads(v) if isinstance(v, str) else list(v if v is not None else [])

    thin = {(r.role_family, r.seniority): bool(r.thin_cell) for r in supply.itertuples()}
    depth = {(r.role_family, r.seniority): int(r.depth) for r in supply.itertuples()}
    # marginal demand is an absolute weight; the UI reads it as a band, so it
    # is normalised to the strongest consultant on the bench
    pull_max = max(1e-9, float(value["marginal_demand"].max()))
    uniq_max = max(1e-9, float(value["uniqueness"].max()))

    cand_rows = [
        [int(r.rank), r.candidate_id, r.role_family, r.seniority,
         int(r.years_experience), _l(r.tech_tags), r.availability,
         bool(r.speaks_german), float(r.value),
         round(float(r.marginal_demand) / pull_max, 4),
         round(float(r.uniqueness) / uniq_max, 4), float(r.deployability),
         thin.get((r.role_family, r.seniority), False),
         int(r.atoms_matched), depth.get((r.role_family, r.seniority), 0)]
        for r in value.itertuples()
    ]
    cell_rows = [
        [r.role_family, r.seniority, r.tech_tag, round(float(r.demand_weight), 2),
         round(float(r.coverage_gap), 3), int(r.supply_depth), int(r.atoms),
         int(r.companies), int(r.priority_rank)]
        for r in plan.itertuples()
    ]

    have: dict[str, int] = {}
    for tags in bench["tech_tags"]:
        for tag in set(_l(tags)):
            have[tag] = have.get(tag, 0) + 1
    dem = cells.groupby("tech_tag")["atoms"].sum()
    tags = sorted(set(dem.index) | set(have), key=lambda t: -int(dem.get(t, 0)))
    gap = [[t, int(dem.get(t, 0)), int(have.get(t, 0))] for t in tags]

    fam_dem = cells.groupby("role_family")["atoms"].sum()
    fam_depth = value.groupby("role_family").size()
    supply_vs_pull = [
        [f, int(fam_depth.get(f, 0)), int(fam_dem.get(f, 0))]
        for f in sorted(set(fam_dem.index) | set(fam_depth.index))
    ]

    return {
        "meta": {
            "size": int(len(value)),
            "cells": int(len(cells)),
            "thin_cells": int(supply["thin_cell"].sum()),
            "german_speakers": int(value["speaks_german"].sum()),
            "people_rho": checks["people"]["value_vs_skill_count_spearman"],
        },
        "cand_cols": ["rank", "id", "family", "seniority", "years", "tags",
                      "availability", "german", "value", "pull", "scarcity",
                      "deploy", "thin", "atoms", "cell_depth"],
        "cand_rows": cand_rows,
        "cells": cell_rows,
        "supply_vs_pull": supply_vs_pull,
        "gap": gap,
    }


def build_payload(postings: pd.DataFrame, companies: pd.DataFrame, report: dict, scope: str) -> dict:
    flag, scope_label = SCOPES[scope]
    subset = postings if flag is None else postings[postings[flag]]
    subset = subset.sort_values("posting_age_days", ascending=False)

    comp_vocab, comp_idx = _dictionary(subset["company_name"])
    group_vocab, group_idx = _dictionary(subset["kldb_group"])
    level_vocab, level_idx = _dictionary(subset["kldb_level"])
    sen_vocab, sen_idx = _dictionary(subset["seniority_derived"])
    reg_vocab, reg_idx = _dictionary(subset["region_clean"])
    tech_vocab, tech_idx = _list_dictionary(subset["technologies"])

    ages = subset["posting_age_days"].tolist()
    posting_rows = [
        [t, c, g, lv, s, tt, rg, (None if a != a else int(a)), pid, bool(x)]
        for t, c, g, lv, s, tt, rg, a, pid, x in zip(
            subset["title_clean"].tolist(), comp_idx, group_idx, level_idx, sen_idx,
            tech_idx, reg_idx, ages, subset["posting_id"].tolist(),
            subset["is_competitor_posting"].tolist(),
        )
    ]

    co_cols = [
        "company_name", "company_class", "postings", "it_postings", "it_intensity",
        "median_it_age_days", "region_count", "top_technologies",
        "is_competitor", "is_noise", "needs_review",
    ]
    co = companies[companies["postings"] >= 1][co_cols]
    company_rows = [
        [
            r.company_name, r.company_class, int(r.postings), int(r.it_postings),
            float(r.it_intensity),
            None if r.median_it_age_days != r.median_it_age_days else int(r.median_it_age_days),
            int(r.region_count), list(r.top_technologies),
            bool(r.is_competitor), bool(r.is_noise), bool(r.needs_review),
        ]
        for r in co.itertuples()
    ]

    it_all = postings[postings["is_it_core"]]
    return {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "snapshot": str(report["input"]["snapshot_date"])[:10],
            "scope": scope_label,
            "postings_total": int(len(postings)),
            "postings_shown": int(len(subset)),
            "companies_total": int(len(companies)),
            "it_postings": int(len(it_all)),
            "it_companies_3plus": int(report["occupations"]["companies_with_3plus_it"]),
            "competitor_it_share": float(it_all["is_competitor_posting"].mean()),
            "median_age": int(postings["posting_age_days"].median()),
            "stale_share": float((postings["posting_age_days"] > 90).mean()),
            "entities": int(report["entity_resolution"]["resolved_entities"]),
            "raw_employers": int(report["entity_resolution"]["raw_employer_strings"]),
            "tech_coverage_it": float(report["technology"]["it_tech_coverage"]),
        },
        "dicts": {
            "companies": comp_vocab, "groups": group_vocab, "levels": level_vocab,
            "seniority": sen_vocab, "regions": reg_vocab, "tech": tech_vocab,
        },
        "postings": {
            "cols": ["title", "company", "group", "level", "seniority", "tech", "region", "age", "id", "comp"],
            "rows": posting_rows,
        },
        "companies": {"cols": co_cols, "rows": company_rows},
        "charts": build_charts(postings, companies),
        "quality": {
            "entity": report["entity_resolution"],
            "nulls": report["data_quality_null_rates"],
            "classification": report["classification"],
            "technology": report["technology"],
            "seniority": report["seniority"],
        },
        # filled by main() from whichever downstream stages have run
        "talent": None,
        "radar": None,
        "bench": None,
        "brief": None,
        "options": {
            "classes": sorted(companies["company_class"].unique().tolist()),
            "seniority": [s for s in ref.SENIORITY_ORDER if s in set(sen_vocab)],
            "regions": sorted(reg_vocab),
            "tech": sorted(tech_vocab),
        },
    }


# ---------------------------------------------------------------------------
# html
# ---------------------------------------------------------------------------

def to_json(payload: dict) -> str:
    """Compact JSON that is safe inside a <script> element.

    `</` is the one sequence that can end the tag early; `<\\/` is the same
    string to JSON.parse. `ensure_ascii=False` keeps the umlauts readable and
    the file a third smaller than escaped code points would.
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return data.replace("</", "<\\/")


def render(payload: dict, template: Path = TEMPLATE) -> str:
    """Drop the payload into the built React template."""
    if not template.exists():
        raise FileNotFoundError(
            f"{template} not found -- the UI has not been built. "
            f"Run `npm install && npm run build` in {template.parent.parent}.")
    html = template.read_text(encoding="utf-8")
    tag = DATA_TAG.search(html)
    if tag is None:
        raise RuntimeError(
            f'{template} has no <script id="opradar-data"> tag; '
            "rebuild it from ui/app.html")
    open_tag = tag.group(0)[:tag.group(0).index(">") + 1]
    return html[:tag.start()] + open_tag + to_json(payload) + "</script>" + html[tag.end():]


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="opradar.ui", description="Build the static UI.")
    p.add_argument("--data", type=Path, default=ROOT / "data" / "processed")
    p.add_argument("--out", type=Path, default=ROOT / "ui" / "index.html")
    p.add_argument("--template", type=Path, default=TEMPLATE,
                   help="built React page to fill (default: ui/dist/app.html)")
    p.add_argument("--scope", choices=list(SCOPES), default="it_extended",
                   help="which postings to embed in the postings table (default: it_extended)")
    p.add_argument("--open", action="store_true", help="open the result in a browser")
    args = p.parse_args(argv)

    postings_path = args.data / "postings.parquet"
    if not postings_path.exists():
        print(f"ERROR: {postings_path} not found. Run `python -m opradar` first.", file=sys.stderr)
        return 1
    if not args.template.exists():
        print(f"ERROR: {args.template} not found. Build the UI first: "
              f"`cd ui && npm install && npm run build`.", file=sys.stderr)
        return 1

    print("  loading parsed tables", file=sys.stderr)
    postings = pd.read_parquet(postings_path)
    companies = pd.read_parquet(args.data / "companies.parquet")
    report = json.loads((args.data / "parse_report.json").read_text(encoding="utf-8"))

    print(f"  building payload (scope={args.scope})", file=sys.stderr)
    payload = build_payload(postings, companies, report, args.scope)
    payload["talent"] = build_talent(args.data)
    payload["radar"] = build_radar(args.data)
    payload["bench"] = build_bench(args.data)
    payload["brief"] = build_brief(args.data)
    if payload["radar"]:
        print(f"  + radar: {payload['radar']['meta']['ranked']} ranked companies, "
              f"bench {payload['bench']['meta']['size']}", file=sys.stderr)
    else:
        print("  no opportunities.parquet — radar screens omitted "
              "(run `python -m opradar.score`)", file=sys.stderr)
    if payload["talent"]:
        print(f"  + talent data: {payload['talent']['meta']['candidates']:,} candidates, "
              f"{payload['talent']['meta']['skill_vocabulary']} skills", file=sys.stderr)
    else:
        print("  no candidates.parquet — talent screens omitted "
              "(run `python -m opradar.candidates`)", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(payload, args.template), encoding="utf-8")
    # the same payload as a file, so `npm run dev` in ui/ has data to show
    dev = args.out.with_name("payload.json")
    dev.write_text(to_json(payload), encoding="utf-8")
    size = args.out.stat().st_size / 1e6
    print(f"  {args.out}  ({size:.1f} MB, "
          f"{payload['meta']['postings_shown']:,} postings, "
          f"{len(payload['companies']['rows']):,} companies)", file=sys.stderr)

    if args.open:
        webbrowser.open(args.out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
