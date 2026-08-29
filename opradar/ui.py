"""Build a self-contained static UI from the parsed tables.

    python -m opradar.ui            # writes ui/index.html, then open it
    python -m opradar.ui --open     # ...and open it in the browser
    python -m opradar.ui --scope all

One HTML file with the data embedded: no server, no build step, no network. It opens
by double-click and keeps working when the venue wifi does not.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import reference as ref
from .ui_assets import CSS, JS

SCOPES = {
    "it": ("is_it_core", "IT postings (KldB 43x)"),
    "it_extended": ("is_it_extended", "IT and adjacent engineering postings (KldB 43/41/27/25)"),
    "all": (None, "all postings"),
}


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
        "talent": None,  # filled by main() when the candidate parser has been run
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

def _opts(values, placeholder: str) -> str:
    return f'<option value="">{placeholder}</option>' + "".join(
        f'<option>{v}</option>' for v in values
    )


def _kv(d: dict, fmt=lambda v: f"{v:,}" if isinstance(v, int) else v) -> str:
    return "".join(f"<tr><td>{k}</td><td>{fmt(v)}</td></tr>" for k, v in d.items())


def _talent_replacements(payload: dict) -> dict:
    """Placeholder values for the two supply-side screens.

    When the candidate parser has not been run the screens are removed outright
    rather than rendered empty -- a nav tab leading to a blank page is worse than
    no tab at all.
    """
    t = payload.get("talent")
    if not t:
        return {}
    tm, to = t["meta"], t["options"]
    families = sorted({r[1] for r in t["skills"]["rows"]})
    gt = t["quality"]
    return {
        "__T_CAND__": f"{tm['candidates']:,}",
        "__T_TECH__": f"{tm['tech_candidates']:,}",
        "__T_OPEN__": f"{tm['openings']:,}",
        "__T_SKILLS__": f"{tm['skill_vocabulary']}",
        "__T_MEANSK__": f"{tm['mean_skills']:.1f}",
        "__T_POOL__": f"{tm['mean_pool']:,.0f}",
        "__BRIDGE_PCT__": f"{tm['bridge_pct']}",
        "__BRIDGE_COV__": f"{tm['bridge_coverage']}",
        "__OPT_SKFAM__": _opts(families, "All skill families"),
        "__OPT_CAROLE__": _opts(to["roles"], "All roles"),
        "__OPT_CASEN__": _opts(to["seniority"], "Any seniority"),
        "__OPT_CAIND__": _opts(to["industries"], "All industries"),
        "__Q_GROUNDTRUTH__": _kv({
            "Labelled pairs": gt["labelled_pairs"],
            "Labels per opening": f"{gt['labels_per_opening']['mean']:.0f} (fixed)",
            "Satisfy the documented rule": f"{gt['satisfy_documented_rule'] * 100:.1f}%",
            "Mean qualified pool": f"{gt['mean_qualified_pool']:,.0f}",
            "Share of pool that is labelled": f"{gt['labelled_share_of_pool'] * 100:.1f}%",
            "Labels matching the opening's seniority": f"{gt['same_seniority'] * 100:.1f}% (random ~33%)",
            "Labels matching the opening's role": f"{gt['same_role'] * 100:.1f}% (random ~4%)",
        }, fmt=lambda v: f"{v:,}" if isinstance(v, int) else v),
    }


def _strip_talent_screens(html: str) -> str:
    """Remove the supply-side tabs and sections when there is no candidate data."""
    for tab in ("talent", "candidates"):
        start = html.find(f'<section class="screen" id="{tab}" data-g="people">')
        if start != -1:
            end = html.find("</section>", start) + len("</section>")
            html = html[:start] + html[end:]
    # drop the nav tab only once nothing is left grouped under it
    if 'data-g="people"' not in html:
        html = html.replace(
            '    <button data-s="people" aria-selected="false">Our people</button>\n', "")
    # and the quality panel that describes it
    start = html.find('    <div class="panel span2">\n      <p class="label">Candidate dataset</p>')
    if start != -1:
        end = html.find("</div>\n    <div class=\"panel wide\">", start)
        if end != -1:
            html = html[:start] + html[end + len("</div>\n"):]
    return html


def _radar_replacements(payload: dict) -> dict:
    r, b = payload.get("radar"), payload.get("bench")
    if not r or not b:
        return {}
    v, rm, bm = r["validation"], r["meta"], b["meta"]
    # Plain-language headline numbers: totals a salesperson can act on, summed
    # across the ranked list rather than reported as pipeline internals.
    idx = {c: i for i, c in enumerate(r["cols"])}
    open_roles = sum(row[idx["it_n"]] for row in r["rows"])
    stuck = sum(row[idx["open45"]] for row in r["rows"])
    return {
        "__R_HASH__": rm["config_hash"],
        "__R_RANKED__": f"{rm['ranked']:,}",
        "__R_EXCL__": f"{rm['channels']:,}",
        "__R_OPENROLES__": f"{open_roles:,}",
        "__R_STUCK__": f"{stuck:,}",
        "__R_V1__": f"{v['v1_rho']:.2f}",
        "__R_V2__": "0" if v["v2"] == "clean" else v["v2"],
        "__R_V3__": f"{v['v3_min']}/{v['v3_k']}",
        "__B_SIZE__": f"{bm['size']}",
        "__B_CELLS__": f"{bm['cells']}",
        "__B_THIN__": f"{bm['thin_cells']}",
        "__B_DE__": f"{bm['german_speakers']}",
        "__B_RHO__": f"{bm['people_rho']:.2f}",
    }


def _strip_radar_screens(html: str) -> str:
    for tab in ("radar", "bench"):
        start = html.find(f'<section class="screen on" id="{tab}"')
        if start == -1:
            start = html.find(f'<section class="screen" id="{tab}"')
        if start != -1:
            end = html.find("</section>", start) + len("</section>")
            html = html[:start] + html[end:]
    html = html.replace(
        '    <button data-s="radar" aria-selected="true">Who to call</button>\n', "")
    if 'data-g="people"' not in html:
        html = html.replace(
            '    <button data-s="people" aria-selected="false">Our people</button>\n', "")
    # overview becomes the default again
    html = html.replace('<button data-s="companies" aria-selected="false">Companies</button>',
                        '<button data-s="companies" aria-selected="true">Companies</button>')
    html = html.replace('<section class="screen" id="overview" data-g="companies">',
                        '<section class="screen on" id="overview" data-g="companies">')
    return html


def render(payload: dict) -> str:
    m, q, o = payload["meta"], payload["quality"], payload["options"]

    review = q["classification"].get("needs_review_examples", [])
    review_rows = "".join(
        f"<tr><td>{r['company']}</td><td>{r['postings']:,} postings · "
        f"{r['sectors']} sectors · {r['regions']} regions</td></tr>"
        for r in review[:12]
    )

    variants = "".join(
        f"<tr><td>{c['company']}</td><td>{len(c['variants'])}</td></tr>"
        for c in q["entity"]["largest_variant_clusters"][:10]
    )

    html = TEMPLATE
    replacements = {
        "__CSS__": CSS,
        "__JS__": JS,
        "__DATA__": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        "__GENERATED__": m["generated"],
        "__SNAPSHOT__": m["snapshot"],
        "__SCOPE__": m["scope"],
        "__KPI_POSTINGS__": f"{m['postings_total']:,}",
        "__KPI_COMPANIES__": f"{m['entities']:,}",
        "__KPI_RAWEMP__": f"{m['raw_employers']:,}",
        "__KPI_IT__": f"{m['it_postings']:,}",
        "__KPI_ITCO__": f"{m['it_companies_3plus']:,}",
        "__KPI_COMP__": f"{m['competitor_it_share'] * 100:.0f}%",
        "__KPI_AGE__": f"{m['median_age']}d",
        "__KPI_STALE__": f"{m['stale_share'] * 100:.0f}%",
        "__POSTINGS_SHOWN__": f"{m['postings_shown']:,}",
        "__OPT_CLASS__": _opts([c.replace("_", " ") and c for c in o["classes"]], "All classes"),
        "__OPT_SEN__": _opts(o["seniority"], "Any seniority"),
        "__OPT_REG__": _opts(o["regions"], "All regions"),
        "__OPT_TECH__": _opts(o["tech"], "Any technology"),
        "__Q_ENTITY__": _kv({
            "Raw employer strings": q["entity"]["raw_employer_strings"],
            "Resolved entities": q["entity"]["resolved_entities"],
            "Collapsed": f"{q['entity']['collapse_ratio'] * 100:.1f}%",
            "Companies with >1 name variant": q["entity"]["companies_with_multiple_name_variants"],
        }),
        "__Q_NULLS__": _kv(
            {k: f"{v * 100:.2f}%" for k, v in q["nulls"].items()}, fmt=lambda v: v
        ),
        "__Q_CLASS__": _kv({
            "Competitor companies": q["classification"]["competitor_companies"],
            "Competitor postings": q["classification"]["competitor_postings"],
            "Competitor share of all postings": f"{q['classification']['competitor_posting_share'] * 100:.1f}%",
            "Noise companies": q["classification"]["noise_companies"],
            "Flagged for review": q["classification"]["needs_review"],
        }),
        "__Q_COVERAGE__": _kv({
            "Technology signal, all postings": f"{q['technology']['tech_coverage'] * 100:.1f}%",
            "Technology signal, IT postings": f"{q['technology']['it_tech_coverage'] * 100:.1f}%",
            "Seniority known": f"{(1 - q['seniority']['derived_mix'].get('unknown', 0) / max(sum(q['seniority']['derived_mix'].values()), 1)) * 100:.1f}%",
            "Dataset seniority unknown": f"{q['seniority']['raw_unknown_share'] * 100:.1f}%",
        }, fmt=lambda v: v),
        "__Q_REVIEW__": review_rows,
        "__Q_VARIANTS__": variants,
    }
    replacements.update(_talent_replacements(payload))
    replacements.update(_radar_replacements(payload))
    for key, value in replacements.items():
        html = html.replace(key, value)
    if not payload.get("talent"):
        html = _strip_talent_screens(html)
    if not payload.get("radar"):
        html = _strip_radar_screens(html)
    return html


TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opportunity Radar — Market Data</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head><body>

<header>
  <div class="bar">
    <div class="brand">
      <span class="mark">OP<b>_</b>RADAR</span>
      <span class="sub"></span>
    </div>
    <div class="stamp">
      <span class="mchip">Snapshot <b>__SNAPSHOT__</b></span>
      <span class="mchip">Parsed __GENERATED__</span>
    </div>
  </div>
  <nav>
    <button data-s="radar" aria-selected="true">Opportunities</button>
    <button data-s="companies" aria-selected="false">Companies</button>
    <button data-s="people" aria-selected="false">People</button>
    <button data-s="method" aria-selected="false">How it works</button>
  </nav>
</header>

<main>


<!-- ================= RADAR ================= -->
<section class="screen on" id="radar" data-g="radar">
  <p class="label">Opportunities &middot; demand matched to people</p>
  <h2>Who to call,<br>and why</h2>
  <p class="lede">Both halves of the product in one list. We find German companies that
    cannot fill their IT roles, then check each one against the people we could actually
    put on the work &mdash; so the top of this list is not just who is struggling, but who
    is struggling <em>with work we can take</em>. Every company scores out of 100, judged
    against the others here. Click any row for the real job ads behind it.</p>

  <div class="kpis">
    <div class="kpi hl"><p class="label">Companies worth calling</p><p class="v num" id="k-ranked">__R_RANKED__</p><p class="n">ranked below, best first</p></div>
    <div class="kpi"><p class="label">IT roles they cannot fill</p><p class="v num" id="k-roles">__R_OPENROLES__</p><p class="n">open right now across all of them</p></div>
    <div class="kpi"><p class="label">Open over 6 weeks</p><p class="v num" id="k-stuck">__R_STUCK__</p><p class="n">still not filled after six weeks</p></div>
  </div>

  <div class="controls stick">
    <input type="search" id="ra-q" placeholder="Search for a company...">
    <select id="ra-class"><option value="">Every type of company</option>
      <option value="end_client">Businesses</option>
      <option value="public_sector">Public sector</option>
      <option value="captive_it">In-house IT arms</option></select>
    <select id="ra-band"><option value="">Any amount of evidence</option>
      <option value="high">Strong evidence</option>
      <option value="medium">Some evidence</option>
      <option value="low">Thin evidence</option></select>
    <label class="chk"><input type="checkbox" id="ra-noreview"> Only externally verified</label>
    <span class="count" id="ra-count"></span>
  </div>
  <div class="tw"><table><thead id="ra-head"></thead><tbody id="ra-body"></tbody></table></div>
  <div class="pager" id="ra-pager"></div>

  <details class="adv">
    <summary>Advanced &mdash; change what counts as a good lead</summary>
    <p class="hint">Drag a slider and the ranking re-sorts instantly. Nothing is hardcoded:
      these four things are what decide the order.</p>
    <div class="sliders">
      <label>Roles they cannot fill <input type="range" id="w-unmet" min="0" max="50" value="30"><b id="wv-unmet">30</b></label>
      <label>Hiring above their own baseline <input type="range" id="w-expansion" min="0" max="50" value="15"><b id="wv-expansion">15</b></label>
      <label>One programme, not scattered backfill <input type="range" id="w-programme" min="0" max="50" value="22"><b id="wv-programme">22</b></label>
      <label>Senior roles they cannot fill <input type="range" id="w-seniority" min="0" max="50" value="15"><b id="wv-seniority">15</b></label>
      <label>How much of it we could staff <input type="range" id="w-svcsig" min="0" max="50" value="16"><b id="wv-svcsig">16</b></label>
      <label>How many people we could place at once <input type="range" id="w-dealsig" min="0" max="50" value="10"><b id="wv-dealsig">10</b></label>
      <button id="w-reset" class="resetbtn">Reset</button>
    </div>
  </details>

  <div class="note after"><b>How to read a row.</b> Each row carries two meters.
    <em>Demand</em> combines the four market signals — unfilled roles, hiring above their
    own baseline, one concentrated programme, and seniority; <em>We staff</em> is how much
    of that demand our bench could take &mdash; both how well we fit it and how many people
    we could place at once, because a one-person contract is not really a contract. The score is the two combined and then
    read as a percentile of this pool, so 87 means ahead of 87% of the companies here.
    A company with demand we cannot serve does not reach the top. Click any row for the whole
    breakdown &mdash; the four things behind Demand, what we bring against them, and the
    real job ads on arbeitsagentur.de. <em>unconfirmed</em> marks companies the keyword
    rules could not classify as customer or supplier; their confidence is already
    discounted, but check before calling.</div>
</section>
<!-- ================= COMPANIES ================= -->
<section class="screen" id="companies" data-g="companies">
  <p class="label">Companies &middot; the demand side</p>
  <h2>Every company<br>we found</h2>
  <p class="lede">All 18,416 employers, after merging the different spellings of the same company
    into one. Each is labelled by what it is &mdash; a business that might buy from us, a
    recruitment agency, an IT firm we compete with &mdash; because that label decides whether it
    can appear as a sales lead at all. <em>Review</em> marks the ones we could not tell apart
    automatically.</p>

  <div class="controls">
    <input type="search" id="co-q" placeholder="Search company…">
    <select id="co-class">__OPT_CLASS__</select>
    <select id="co-minit">
      <option value="0">Any IT volume</option>
      <option value="1">1+ IT postings</option>
      <option value="3">3+ IT postings</option>
      <option value="10">10+ IT postings</option>
    </select>
    <label class="chk"><input type="checkbox" id="co-hidecomp"> Hide competitors</label>
    <label class="chk"><input type="checkbox" id="co-hidenoise" checked> Hide noise</label>
    <span class="count" id="co-count"></span>
  </div>
  <div class="tw"><table><thead id="co-head"></thead><tbody id="co-body"></tbody></table></div>
  <div class="pager" id="co-pager"></div>
</section>
<!-- ================= OVERVIEW ================= -->
<section class="screen" id="overview" data-g="companies">
  <p class="label">Overview</p>
  <h2>What the market<br>looks like</h2>
  <p class="lede">The German job market as it stood on the snapshot date &mdash; who is hiring,
    for what, where, and how long the roles stay open. Nothing here is scored or ranked; it is
    the raw picture the sales list is built from.</p>

  <div class="kpis">
    <div class="kpi hl"><p class="label">Companies hiring IT</p><p class="v num">__KPI_ITCO__</p><p class="n">with three or more IT roles open &mdash; the market we can sell into</p></div>
    <div class="kpi"><p class="label">Roles open past 3 months</p><p class="v num">__KPI_STALE__</p><p class="n">German IT hiring is slow, and that slowness is the opening</p></div>
    <div class="kpi"><p class="label">Hiring done by agencies</p><p class="v num">__KPI_COMP__</p><p class="n">of IT roles are posted by recruiters and IT firms, not the employer</p></div>
  </div>

  <details class="more">
    <summary>More numbers about the data</summary>
    <div class="kpis">
      <div class="kpi"><p class="label">Job ads</p><p class="v num">__KPI_POSTINGS__</p><p class="n">after cleaning</p></div>
      <div class="kpi"><p class="label">Companies</p><p class="v num">__KPI_COMPANIES__</p><p class="n">from __KPI_RAWEMP__ raw employer names</p></div>
      <div class="kpi"><p class="label">IT job ads</p><p class="v num">__KPI_IT__</p><p class="n">official German occupation code 43</p></div>
      <div class="kpi"><p class="label">Typical time open</p><p class="v num">__KPI_AGE__</p><p class="n">middle of the range</p></div>
    </div>
  </details>

  <div class="grid">
    <div class="panel" style="order:4">
      <p class="label">Demand</p><h3>Occupational groups</h3>
      <p class="hint">Top 10 of 37. IT highlighted.</p>
      <div id="c-groups"></div>
    </div>
    <div class="panel" style="order:2">
      <p class="label">Supply side</p><h3>Who is posting</h3>
      <p class="hint">Postings by company class. Highlighted classes compete with us for the same placements.</p>
      <div id="c-class"></div>
    </div>
    <div class="panel" style="order:3">
      <p class="label">Stack</p><h3>Technologies in IT postings</h3>
      <p class="hint">From job titles only — roughly a third of IT postings name a technology. Descriptions would raise this.</p>
      <div id="c-tech"></div>
    </div>
    <div class="panel" style="order:5">
      <p class="label">Sector</p><h3>Market domains</h3>
      <p class="hint">Across all postings — the sector a role sits in, detected separately from the technology stack. Domain fit is a first-class matching dimension.</p>
      <div id="c-domain"></div>
    </div>
    <div class="panel" style="order:1">
      <p class="label">Scarcity</p><h3>How long postings stay open</h3>
      <p class="hint">Highlighted buckets are roles the market is failing to fill.</p>
      <div id="c-age"></div>
    </div>
    <div class="panel" style="order:6">
      <p class="label">Qualification</p><h3>Requirement level</h3>
      <p class="hint">KldB 5th digit. Present on 99.8% of postings — the reliable way to stratify by level.</p>
      <div id="c-level"></div>
    </div>
    <div class="panel wide" style="order:7">
      <p class="label">Geography</p><h3>Where the postings are</h3>
      <p class="hint" id="region-hint"></p>
      <label class="chk spaced"><input type="checkbox" id="region-norm"> Per million inhabitants</label>
      <div id="c-region"></div>
    </div>
    <div class="panel wide" style="order:8">
      <p class="label">Careful</p><h3>Postings by month posted</h3>
      <p class="hint">Last 18 months.</p>
      <div id="c-month"></div>
      <div class="note"><b>This chart is a trap.</b> It looks like the market tripled, and it did not.
        The snapshot only contains postings that were still <em>open</em> on the crawl date — older ones
        are missing because they were <em>filled</em>. This is a survival curve, not a demand curve.
        Real trend data has to come from repeated crawls or an explicit "posted in the last N days" filter.
        It is shown here so nobody rebuilds it by accident.</div>
    </div>
  </div>
</section>

<!-- ================= QUALITY ================= -->
<section class="screen" id="quality" data-g="method">
  <p class="label">How it works</p>
  <h2>How the list<br>is built</h2>
  <p class="lede">Four things about each company decide its position: how long its IT roles
    have stayed unfilled, how many are senior, whether the hiring is focused on one
    technology, and whether it is still posting. Companies are compared only against each
    other, so a score means "compared with the rest of this list". Nothing is guessed &mdash;
    every number traces to real job ads.</p>

  <div class="kpis">
    <div class="kpi"><p class="label">Not just counting job ads</p><p class="v num">__R_V1__</p>
      <p class="n">0 = completely different from ranking by number of ads, 1 = identical.
      Lower is better &mdash; anyone can count ads.</p></div>
    <div class="kpi"><p class="label">Recruiters in the list</p><p class="v num">__R_V2__</p>
      <p class="n">Staffing agencies and our own group, filtered out. Should be zero.</p></div>
    <div class="kpi"><p class="label">Ranking stability</p><p class="v num">__R_V3__</p>
      <p class="n">Of the top 20, how many stay there when the four weightings are
      nudged up or down by a fifth.</p></div>
  </div>

  <details class="more">
    <summary>More checks</summary>
    <div class="kpis">
      <div class="kpi"><p class="label">Agencies and vendors filtered out</p><p class="v num">__R_EXCL__</p>
        <p class="n">No job ad posted in 90 days &mdash; probably abandoned listings.</p></div>
    </div>
  </details>

  <p class="hint spaced">Same data in, same list out &mdash; settings
    fingerprint <code>__R_HASH__</code>.</p>

  <h3 class="tight">What to distrust</h3>
  <p class="lede">The parser reports its own weak spots. Read this before quoting any number
    from the other screens.</p>

  <div class="q">
    <div class="panel">
      <p class="label">Entity resolution</p><h3>Name → company</h3>
      <p class="hint">Exact grouping on the normalised name. Fuzzy merging is off by default —
        over-merging invents companies that do not exist.</p>
      <table class="kv">__Q_ENTITY__</table>
    </div>
    <div class="panel">
      <p class="label">Classification</p><h3>Client vs competitor</h3>
      <p class="hint">Keyword rules. Precision has not been measured against hand labels yet.</p>
      <table class="kv">__Q_CLASS__</table>
    </div>
    <div class="panel">
      <p class="label">Coverage</p><h3>How much signal exists</h3>
      <p class="hint">Titles name roles, not stacks. These numbers rise once job descriptions are fetched.</p>
      <table class="kv">__Q_COVERAGE__</table>
    </div>
    <div class="panel">
      <p class="label">Completeness</p><h3>Null rates by column</h3>
      <table class="kv">__Q_NULLS__</table>
    </div>
    <div class="panel span2">
      <p class="label">Review queue</p><h3>The rules could not decide</h3>
      <p class="hint">High volume across unrelated sectors and many regions, but no agency keyword in the
        name. That is the fingerprint of a staffing firm — and of a large diversified employer.
        Flagged rather than guessed.</p>
      <table class="kv">__Q_REVIEW__</table>
    </div>
    <div class="panel">
      <p class="label">Merges</p><h3>Largest name-variant clusters</h3>
      <p class="hint">Worth spot-checking: these are the entities where resolution did the most work.</p>
      <table class="kv">__Q_VARIANTS__</table>
    </div>
    <div class="panel span2">
      <p class="label">Candidate dataset</p><h3>Its "ground truth" is not ground truth</h3>
      <p class="hint">The benchmark ships 30 relevant candidates per opening. Recomputing the
        rule it documents shows those 30 are an arbitrary slice of a far larger qualified set,
        and that seniority is ignored completely.</p>
      <table class="kv">__Q_GROUNDTRUTH__</table>
      <div class="note after"><b>Do not report retrieval precision against
        these labels.</b> Unlabelled correct answers are everywhere, so an honest matcher will
        look wrong.</div>
    </div>
    <div class="panel wide">
      <p class="label">Known limits</p><h3>Read before quoting anything</h3>
      <ul class="lim">
        <li><b>Posting-date trends are meaningless.</b> The snapshot is a stock of open postings, not a
          flow. Counting by month produces a survival curve. See the note on the Overview screen.</li>
        <li><b>Posting age is length-biased.</b> Long-lived postings are over-sampled by construction.
          Valid for ranking companies against each other; invalid as an absolute time-to-fill.</li>
        <li><b>Technology coverage is low</b> because job descriptions are not in this dataset.
          The same extraction runs over descriptions once they are fetched.</li>
        <li><b>ESCO tags are noisy.</b> The skill list is a top-5 nearest-neighbour assignment rather
          than extraction, and the occupation mapping is visibly wrong on a material share of rows.
          Passed through as a weak prior only.</li>
        <li><b>Regional counts reflect crawl coverage</b> as much as labour demand. Use the per-capita
          toggle before comparing regions.</li>
        <li><b>Seniority is mostly unknown</b> and deliberately so — it is only filled where a title
          states it. Stratify on requirement level instead.</li>
        <li><b>The candidate data is synthetic.</b> Near-uniform distributions, a 73-skill
          vocabulary, and no overlap worth speaking of with German demand. It is a fixture for
          building the matcher, not evidence about anyone's talent pool.</li>
        <li><b>This is a sample, not a census.</b> One source, one crawl window, and it under-represents
          hiring that runs through company career pages and LinkedIn.</li>
      </ul>
    </div>
  </div>
</section>

<!-- ================= POSTINGS ================= -->
<section class="screen" id="postings" data-g="method">
  <p class="label">Postings</p>
  <h2>The evidence<br>layer</h2>
  <p class="lede">Showing __POSTINGS_SHOWN__ __SCOPE__. Every title links to the live posting on
    arbeitsagentur.de — this is what any score has to be traceable back to.</p>
  <div class="note"><b>Sorted by how long each posting has been open.</b>
    The extreme tail is real but not useful: postings older than roughly two years are records the
    source never delisted, not live demand. The scarcity signal worth acting on sits in the
    90–400 day band — use the age filter.</div>

  <div class="controls">
    <input type="search" id="po-q" placeholder="Search title or company…">
    <select id="po-sen">__OPT_SEN__</select>
    <select id="po-tech">__OPT_TECH__</select>
    <select id="po-reg">__OPT_REG__</select>
    <select id="po-age">
      <option value="0">Any age</option>
      <option value="30">Open 30+ days</option>
      <option value="90">Open 90+ days</option>
      <option value="180">Open 180+ days</option>
    </select>
    <label class="chk"><input type="checkbox" id="po-hidecomp"> Hide competitor postings</label>
    <span class="count" id="po-count"></span>
  </div>
  <div class="tw"><table><thead id="po-head"></thead><tbody id="po-body"></tbody></table></div>
  <div class="pager" id="po-pager"></div>
</section>


<!-- ================= BENCH ================= -->
<section class="screen" id="bench" data-g="people">
  <p class="label">Bench &middot; people scoring</p>
  <h2>Who we can<br>deploy</h2>
  <p class="lede">A <b>synthetic</b> delivery bench of __B_SIZE__ consultants, generated in the
    German tech vocabulary (option B3) so matching against real demand is a join, not a guess.
    Each consultant is scored <b>Value = MarketPull &times; Scarcity &times; Deployability</b>
    &mdash; and MarketPull comes from the <em>real German postings</em>, never from synthetic
    openings.</p>

  <div class="note"><b>Every person on this screen is synthetic.</b>
    The bench profile is a deliberate model of a Lithuanian nearshore consultancy &mdash; strong in
    modern software delivery, thin in SAP/embedded &mdash; so the gap against German demand is
    visible instead of flattered away. Swap in the real bench and every number recomputes.</div>

  <div class="kpis">
    <div class="kpi hl"><p class="label">People on the bench</p><p class="v num">__B_SIZE__</p><p class="n">who we could put on a project</p></div>
    <div class="kpi"><p class="label">Speak German</p><p class="v num">__B_DE__</p><p class="n">the hard limit on how much German work we can take</p></div>
    <div class="kpi"><p class="label">Thin skill groups</p><p class="v num">__B_THIN__</p><p class="n">fewer than 5 people &mdash; we flag these rather than promise them</p></div>
  </div>

  <details class="more">
    <summary>More numbers about the bench</summary>
    <div class="kpis">
      <div class="kpi"><p class="label">Skill groups</p><p class="v num">__B_CELLS__</p><p class="n">role type &times; seniority</p></div>
      <div class="kpi"><p class="label">Not just the longest CV</p><p class="v num">__B_RHO__</p><p class="n">how little our ranking agrees with simply counting skills; near zero is good</p></div>
    </div>
  </details>

  <div class="grid">
    <div class="panel wide">
      <p class="label">The gap</p><h3>German demand vs bench capability</h3>
      <p class="hint">Bench consultants carrying each tech category (violet) against eligible
        German postings naming it (dark). Where dark towers over violet &mdash; SAP/erp, embedded,
        security &mdash; is exactly what the bench cannot serve. This chart is the honest version
        of Serviceability.</p>
      <div id="b-gap"></div>
    </div>
    <div class="panel">
      <p class="label">Demand</p><h3>Unfilled German demand by role family</h3>
      <p class="hint">Postings open &gt;45 days in the eligible pool &mdash; the MarketPull input.</p>
      <div id="b-pull"></div>
    </div>
    <div class="panel">
      <p class="label">Supply</p><h3>Bench by role family</h3>
      <p class="hint">Where our capacity actually sits.</p>
      <div id="b-supply"></div>
    </div>
    <div class="panel wide">
      <p class="label">Cells</p><h3>Supply index &mdash; the Pipeline C hand-off</h3>
      <p class="hint">One row per role family &times; seniority. Thin cells (&lt;5 people) are
        flagged: scarcity = 1/depth explodes there, so they are never ranked &mdash; dead code on
        a 120-person bench in some cells, load-bearing the moment the real bench arrives.</p>
      <div class="tw" style="max-height:44vh"><table><thead id="ce-head"></thead><tbody id="ce-body"></tbody></table></div>
      <div class="pager" id="ce-pager"></div><span class="count" id="ce-count" style="display:none"></span>
    </div>
    <div class="panel wide">
      <p class="label">People ranking</p><h3>Bench value</h3>
      <p class="hint">Value = MarketPull &times; Scarcity &times; Deployability, all percentiled.
        Multiplicative: a candidate nobody wants, or one we have forty of, is not valuable
        regardless of the other factors.</p>
      <div class="controls">
        <input type="search" id="be-q" placeholder="Search family or tag...">
        <select id="be-fam"><option value="">All families</option>
          <option>dev</option><option>data</option><option>ops</option><option>qa</option>
          <option>analyst</option><option>architect</option><option>security</option><option>support</option></select>
        <label class="chk"><input type="checkbox" id="be-avail"> Available now / 30d only</label>
        <span class="count" id="be-count"></span>
      </div>
      <div class="tw" style="max-height:56vh"><table><thead id="be-head"></thead><tbody id="be-body"></tbody></table></div>
      <div class="pager" id="be-pager"></div>
    </div>
  </div>
</section>
<!-- ================= TALENT ================= -->
<section class="screen" id="talent" data-g="people">
  <p class="label">Talent &middot; supply side</p>
  <h2>Who is<br>available</h2>
  <p class="lede">The other half of the market: 10,000 candidate profiles and 2,500 openings from a
    synthetic benchmark dataset. Same treatment as the demand side &mdash; normalised, aggregated,
    and honest about what it can and cannot tell you.</p>

  <div class="note"><b>Two things to know before reading any of this.</b>
    The dataset is <em>synthetic and LLM-generated</em>, so the near-uniform distributions below
    measure the generator, not a labour market. And it <em>does not join to the German posting
    data</em>: only __BRIDGE_PCT__% of its skill vocabulary has an equivalent in our German
    extraction, covering __BRIDGE_COV__% of German IT postings. Use it to build and demo the
    matcher, not to claim anything about Germany.</div>

  <details class="more">
    <summary>Numbers about this candidate dataset</summary>
    <div class="kpis">
      <div class="kpi"><p class="label">Candidate profiles</p><p class="v num">__T_CAND__</p><p class="n">all synthetic</p></div>
      <div class="kpi"><p class="label">In tech roles</p><p class="v num">__T_TECH__</p><p class="n">engineering, data, technical</p></div>
      <div class="kpi"><p class="label">Openings</p><p class="v num">__T_OPEN__</p><p class="n">also synthetic</p></div>
      <div class="kpi"><p class="label">Different skills</p><p class="v num">__T_SKILLS__</p><p class="n">__T_MEANSK__ per candidate</p></div>
      <div class="kpi"><p class="label">Match too loose</p><p class="v num">__T_POOL__</p><p class="n">candidates qualify for a typical opening &mdash; far too many to be realistic</p></div>
    </div>
  </details>

  <div class="grid">
    <div class="panel wide">
      <p class="label">The core question</p><h3>Skill supply vs demand</h3>
      <p class="hint">Share of candidates holding each skill (violet) against share of openings
        asking for it (dark). Where dark outruns violet, the market wants more than the bench
        carries.</p>
      <div id="t-supplydemand"></div>
    </div>
    <div class="panel">
      <p class="label">Scarcity</p><h3>Highest tension</h3>
      <p class="hint">Demand share divided by supply share, normalised so the market average is 1.0.
        The spread is narrow because the generator is close to uniform &mdash; on real data expect
        a far wider range.</p>
      <div id="t-tensiontop"></div>
    </div>
    <div class="panel">
      <p class="label">Oversupply</p><h3>Lowest tension</h3>
      <p class="hint">More bench than market. On a real bench these are the hardest people to place.</p>
      <div id="t-tensionbot"></div>
    </div>
    <div class="panel">
      <p class="label">Shape</p><h3>Role families</h3>
      <p class="hint">Candidates by role family. Engineering and data are the tech-facing ones.</p>
      <div id="t-rolefam"></div>
    </div>
    <div class="panel">
      <p class="label">Demand</p><h3>Most requested roles</h3>
      <p class="hint">Openings by title.</p>
      <div id="t-roledemand"></div>
    </div>
    <div class="panel">
      <p class="label">Level</p><h3>Seniority and experience</h3>
      <p class="hint">Note the near-perfect thirds. That is the generator, not a talent pool.</p>
      <div id="t-seniority"></div>
      <div class="stack"></div>
      <div id="t-experience"></div>
    </div>
    <div class="panel">
      <p class="label">Background</p><h3>Industry and education</h3>
      <p class="hint">Ten industries at roughly 10% each, five education levels at roughly 20% each.</p>
      <div id="t-industry"></div>
      <div class="stack"></div>
      <div id="t-education"></div>
    </div>
    <div class="panel wide">
      <p class="label">Skill market</p><h3>Every skill, supply against demand</h3>
      <p class="hint">Sort any column. Tension above 1.0 means demand outruns supply.</p>
      <div class="controls">
        <input type="search" id="sk-q" placeholder="Search skill...">
        <select id="sk-fam">__OPT_SKFAM__</select>
        <span class="count" id="sk-count"></span>
      </div>
      <div class="tw" style="max-height:52vh"><table><thead id="sk-head"></thead><tbody id="sk-body"></tbody></table></div>
      <div class="pager" id="sk-pager"></div>
    </div>
  </div>
</section>



<!-- ================= CANDIDATES ================= -->
<section class="screen" id="candidates" data-g="people">
  <p class="label">Candidates</p>
  <h2>The bench</h2>
  <p class="lede">All __T_CAND__ parsed profiles. <em>Qualified for</em> counts how many of the
    __T_OPEN__ openings each candidate meets the must-have threshold for &mdash; recomputed here,
    not taken from the dataset's own labels.</p>

  <div class="controls">
    <input type="search" id="ca-q" placeholder="Search role, industry or skill...">
    <select id="ca-role">__OPT_CAROLE__</select>
    <select id="ca-sen">__OPT_CASEN__</select>
    <select id="ca-ind">__OPT_CAIND__</select>
    <label class="chk"><input type="checkbox" id="ca-tech"> Tech roles only</label>
    <span class="count" id="ca-count"></span>
  </div>
  <div class="tw"><table><thead id="ca-head"></thead><tbody id="ca-body"></tbody></table></div>
  <div class="pager" id="ca-pager"></div>
</section>


</main>

<footer>
  Opportunity Radar — parser output viewer. Job posting data ©&nbsp;Bundesagentur für Arbeit,
  <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC&nbsp;BY&nbsp;4.0</a>.
  Snapshot __SNAPSHOT__ · built __GENERATED__.
</footer>

<script>window.__OPRADAR__ = __DATA__;</script>
<script>__JS__</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="opradar.ui", description="Build the static UI.")
    p.add_argument("--data", type=Path, default=root / "data" / "processed")
    p.add_argument("--out", type=Path, default=root / "ui" / "index.html")
    p.add_argument("--scope", choices=list(SCOPES), default="it_extended",
                   help="which postings to embed in the postings table (default: it_extended)")
    p.add_argument("--open", action="store_true", help="open the result in a browser")
    args = p.parse_args(argv)

    postings_path = args.data / "postings.parquet"
    if not postings_path.exists():
        print(f"ERROR: {postings_path} not found. Run `python -m opradar` first.", file=sys.stderr)
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
    args.out.write_text(render(payload), encoding="utf-8")
    size = args.out.stat().st_size / 1e6
    print(f"  {args.out}  ({size:.1f} MB, "
          f"{payload['meta']['postings_shown']:,} postings, "
          f"{len(payload['companies']['rows']):,} companies)", file=sys.stderr)

    if args.open:
        webbrowser.open(args.out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
