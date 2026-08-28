"""QA report.

The point of this file is that the parser tells you what it did and where it is
weak, every run. A parser that silently produces a clean-looking table is how you
end up demoing a number nobody can defend.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd


def _top(series: pd.Series, n: int = 15) -> dict:
    return {str(k): int(v) for k, v in series.value_counts().head(n).items()}


def build_stats(
    *,
    raw: pd.DataFrame,
    postings: pd.DataFrame,
    companies: pd.DataFrame,
    raw_distinct_employers: int,
    resolved_entities: int,
    unattributed_rows: int,
    fuzzy_merges: list,
    options,
    elapsed_s: float,
) -> dict:
    it = postings[postings["is_it_core"]]

    tech_counter: Counter = Counter()
    for techs in postings["technologies"]:
        tech_counter.update(techs)

    null_rates = {
        col: round(float(postings[col].isna().mean()), 4)
        for col in [
            "company_key", "title_clean", "kldb_code", "kldb_level",
            "region_clean", "posted_date", "esco_occupation_label",
            "salary_min_eur",
        ]
        if col in postings.columns
    }

    it_companies = companies[companies["it_postings"] > 0]

    return {
        "elapsed_s": elapsed_s,
        "options": {
            "fuzzy": options.fuzzy,
            "fuzzy_threshold": options.fuzzy_threshold,
            "loose_keys": options.loose_keys,
        },
        "input": {
            "raw_rows": int(len(raw)),
            "raw_columns": int(len(raw.columns)),
            "snapshot_date": str(postings["snapshot_date"].iloc[0]) if len(postings) else None,
            "fetched_at_min": str(pd.to_datetime(raw["fetched_at"]).min()),
            "fetched_at_max": str(pd.to_datetime(raw["fetched_at"]).max()),
            "posted_date_min": str(pd.to_datetime(raw["posted_date"]).min()),
            "posted_date_max": str(pd.to_datetime(raw["posted_date"]).max()),
        },
        "output": {
            "postings": int(len(postings)),
            "companies": int(len(companies)),
            "unattributed_rows": int(unattributed_rows),
        },
        "entity_resolution": {
            "raw_employer_strings": raw_distinct_employers,
            "resolved_entities": resolved_entities,
            "collapse_ratio": round(1 - resolved_entities / max(raw_distinct_employers, 1), 4),
            "companies_with_multiple_name_variants": int(
                (companies["name_variant_count"] > 1).sum()
            ),
            "fuzzy_merge_pairs": len(fuzzy_merges),
            "fuzzy_merge_examples": [list(m) for m in fuzzy_merges[:20]],
            "largest_variant_clusters": [
                {"company": r.company_name, "variants": r.name_variants}
                for r in companies.nlargest(10, "name_variant_count").itertuples()
                if r.name_variant_count > 1
            ],
        },
        "classification": {
            "by_class": _top(companies["company_class"], 10),
            "postings_by_class": _top(postings["company_class"], 10),
            "competitor_companies": int(companies["is_competitor"].sum()),
            "competitor_postings": int(postings["is_competitor_posting"].sum()),
            "competitor_posting_share": round(
                float(postings["is_competitor_posting"].mean()), 4
            ),
            "noise_companies": int(companies["is_noise"].sum()),
            "needs_review": int(companies["needs_review"].sum()),
            "needs_review_examples": [
                {"company": r.company_name, "postings": int(r.postings),
                 "sectors": len(r.kldb_sectors), "regions": int(r.region_count),
                 "breadth": float(r.agency_breadth_score)}
                for r in companies[companies["needs_review"]].nlargest(15, "postings").itertuples()
            ],
            "it_postings_by_class": _top(it["company_class"], 10),
        },
        "occupations": {
            "it_core_postings": int(len(it)),
            "it_core_share": round(len(it) / max(len(postings), 1), 4),
            "it_extended_postings": int(postings["is_it_extended"].sum()),
            "companies_with_it": int(len(it_companies)),
            "companies_with_3plus_it": int((companies["it_postings"] >= 3).sum()),
            "companies_with_10plus_it": int((companies["it_postings"] >= 10).sum()),
            "top_kldb_groups": _top(postings["kldb_group"], 12),
            "kldb_level_mix": _top(postings["kldb_level"], 6),
            "kldb_unparsed": int(postings["kldb_code"].isna().sum()),
        },
        "seniority": {
            "derived_mix": _top(postings["seniority_derived"], 8),
            "source_mix": _top(postings["seniority_source"], 6),
            "raw_unknown_share": round(
                float((raw["seniority"].fillna("unknown") == "unknown").mean()), 4
            ),
        },
        "technology": {
            "postings_with_tech_signal": int(postings["has_tech_signal"].sum()),
            "tech_coverage": round(float(postings["has_tech_signal"].mean()), 4),
            "it_tech_coverage": round(float(it["has_tech_signal"].mean()), 4)
            if len(it)
            else 0.0,
            "top_technologies": {k: int(v) for k, v in tech_counter.most_common(20)},
        },
        "geography": {
            "by_country": _top(postings["country"], 6),
            "top_regions": _top(postings["region_clean"], 18),
            "region_missing": int(postings["region_clean"].isna().sum()),
        },
        "recency": {
            "median_age_days": float(postings["posting_age_days"].median()),
            "fresh_30d": int(postings["is_fresh_30d"].sum()),
            "stale_90d": int(postings["is_stale_90d"].sum()),
            "stale_180d": int(postings["is_stale_180d"].sum()),
            "by_month": {
                str(k): int(v)
                for k, v in postings["posted_year_month"].value_counts().sort_index().tail(18).items()
            },
        },
        "data_quality_null_rates": null_rates,
        "top_it_employers_non_competitor": [
            {
                "company": r.company_name,
                "class": r.company_class,
                "it_postings": int(r.it_postings),
                "it_intensity": float(r.it_intensity),
                "median_it_age_days": r.median_it_age_days,
            }
            for r in companies[~companies["is_competitor"] & ~companies["is_noise"]]
            .nlargest(20, "it_postings")
            .itertuples()
        ],
        "top_it_employers_competitor": [
            {"company": r.company_name, "class": r.company_class, "it_postings": int(r.it_postings)}
            for r in companies[companies["is_competitor"]].nlargest(10, "it_postings").itertuples()
        ],
    }


def _table(d: dict, key_header: str, value_header: str = "count") -> str:
    lines = [f"| {key_header} | {value_header} |", "| --- | ---: |"]
    lines += [f"| {k} | {v:,} |" if isinstance(v, int) else f"| {k} | {v} |" for k, v in d.items()]
    return "\n".join(lines)


def render_markdown(s: dict) -> str:
    er = s["entity_resolution"]
    cl = s["classification"]
    oc = s["occupations"]
    tech = s["technology"]

    out = [
        "# Parse report",
        "",
        f"Generated by `opradar` in {s['elapsed_s']}s. "
        f"Options: fuzzy={s['options']['fuzzy']}, loose_keys={s['options']['loose_keys']}.",
        "",
        "## Input",
        "",
        f"- Raw rows: **{s['input']['raw_rows']:,}** ({s['input']['raw_columns']} columns)",
        f"- Crawl window: `{s['input']['fetched_at_min']}` -> `{s['input']['fetched_at_max']}`",
        f"- Posted dates span: `{s['input']['posted_date_min']}` -> `{s['input']['posted_date_max']}`",
        "",
        "> This is a **stock** of postings still open at crawl time, not a **flow** of",
        "> postings created over time. Counting by `posted_date` produces a fake growth",
        "> curve -- older postings are missing because they were filled. See RESEARCH.md 3.1.",
        "",
        "## Output",
        "",
        f"- `postings.parquet`: **{s['output']['postings']:,}** rows",
        f"- `companies.parquet`: **{s['output']['companies']:,}** rows",
        f"- Unattributed rows dropped (no employer): {s['output']['unattributed_rows']:,}",
        "",
        "## Entity resolution",
        "",
        f"- {er['raw_employer_strings']:,} raw employer strings -> "
        f"**{er['resolved_entities']:,}** entities "
        f"({er['collapse_ratio'] * 100:.1f}% collapsed)",
        f"- Companies with more than one name variant: {er['companies_with_multiple_name_variants']:,}",
        f"- Fuzzy merge pairs: {er['fuzzy_merge_pairs']:,}",
        "",
        "Largest name-variant clusters (spot-check these -- over-merging is worse than under-merging):",
        "",
    ]
    for cluster in er["largest_variant_clusters"]:
        out.append(f"- **{cluster['company']}** -- {', '.join(cluster['variants'][:6])}")

    out += [
        "",
        "## Classification",
        "",
        _table(cl["by_class"], "company class", "companies"),
        "",
        f"- Competitor companies (staffing + IT services): **{cl['competitor_companies']:,}**",
        f"- Competitor postings: **{cl['competitor_postings']:,}** "
        f"({cl['competitor_posting_share'] * 100:.1f}% of all postings)",
        f"- Noise companies (training providers, individuals): {cl['noise_companies']:,}",
        f"- **Flagged for review**: {cl['needs_review']:,} high-volume, high-breadth companies "
        "with no agency keyword in the name. The rules cannot tell a staffing firm from a "
        "large diversified employer here -- this is the queue for the LLM/human pass.",
        "",
        _table(
            {e["company"]: f"{e['postings']} postings, {e['sectors']} sectors, "
                           f"{e['regions']} regions" for e in cl["needs_review_examples"]},
            "flagged company", "profile",
        ),
        "",
        "IT postings by company class:",
        "",
        _table(cl["it_postings_by_class"], "class", "IT postings"),
        "",
        "## Occupations",
        "",
        f"- IT core (KldB 43x): **{oc['it_core_postings']:,}** ({oc['it_core_share'] * 100:.1f}%)",
        f"- IT extended (43/41/27/25): {oc['it_extended_postings']:,}",
        f"- Companies with any IT posting: {oc['companies_with_it']:,} "
        f"| 3+: {oc['companies_with_3plus_it']:,} | 10+: **{oc['companies_with_10plus_it']:,}**",
        f"- Unparsed KldB codes: {oc['kldb_unparsed']:,}",
        "",
        _table(oc["top_kldb_groups"], "KldB group", "postings"),
        "",
        "Requirement level (KldB 5th digit) -- the reliable seniority proxy:",
        "",
        _table(oc["kldb_level_mix"], "level", "postings"),
        "",
        "## Seniority",
        "",
        f"- Raw dataset `seniority` unknown share: **{s['seniority']['raw_unknown_share'] * 100:.1f}%**",
        "",
        _table(s["seniority"]["derived_mix"], "seniority_derived", "postings"),
        "",
        _table(s["seniority"]["source_mix"], "resolved from", "postings"),
        "",
        "## Technology signal",
        "",
        f"- Postings with a technology in the title: **{tech['postings_with_tech_signal']:,}** "
        f"({tech['tech_coverage'] * 100:.1f}%); within IT: {tech['it_tech_coverage'] * 100:.1f}%",
        "",
        "> Low coverage is expected: German job titles name a role, not a stack.",
        "> Real technology signal requires the job description text.",
        "",
        _table(tech["top_technologies"], "technology", "postings"),
        "",
        "## Geography",
        "",
        _table(s["geography"]["by_country"], "country", "postings"),
        "",
        _table(s["geography"]["top_regions"], "region", "postings"),
        "",
        "> Regional counts reflect crawl coverage as much as labour demand. Normalise",
        "> before presenting any regional comparison.",
        "",
        "## Recency",
        "",
        f"- Median posting age: **{s['recency']['median_age_days']:.0f} days**",
        f"- Fresh (<=30d): {s['recency']['fresh_30d']:,} "
        f"| Stale (>90d): {s['recency']['stale_90d']:,} "
        f"| Very stale (>180d): {s['recency']['stale_180d']:,}",
        "",
        "## Data quality -- null rates",
        "",
        _table(s["data_quality_null_rates"], "column", "null rate"),
        "",
        "## Top IT employers, competitors excluded",
        "",
        "| company | class | IT postings | IT intensity | median IT age (d) |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for r in s["top_it_employers_non_competitor"]:
        age = f"{r['median_it_age_days']:.0f}" if r["median_it_age_days"] is not None else "-"
        out.append(
            f"| {r['company']} | {r['class']} | {r['it_postings']} | "
            f"{r['it_intensity'] * 100:.0f}% | {age} |"
        )

    out += [
        "",
        "## Top IT employers among competitors (the saturation signal)",
        "",
        _table(
            {r["company"]: r["it_postings"] for r in s["top_it_employers_competitor"]},
            "competitor",
            "IT postings",
        ),
        "",
    ]
    return "\n".join(out)
