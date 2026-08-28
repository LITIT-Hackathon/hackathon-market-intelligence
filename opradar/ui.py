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
    for key, value in replacements.items():
        html = html.replace(key, value)
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
      <span class="sub">German IT labour market</span>
    </div>
    <div class="stamp">
      Snapshot <b>__SNAPSHOT__</b><br>Parsed __GENERATED__
    </div>
  </div>
  <nav>
    <button data-s="overview" aria-selected="true">Overview</button>
    <button data-s="companies" aria-selected="false">Companies</button>
    <button data-s="postings" aria-selected="false">Postings</button>
    <button data-s="quality" aria-selected="false">Data quality</button>
  </nav>
</header>

<main>

<!-- ================= OVERVIEW ================= -->
<section class="screen on" id="overview">
  <p class="label">Overview</p>
  <h2>What the market<br>looks like</h2>
  <p class="lede">Everything below comes from the parsed snapshot. No scores, no ranking yet —
    this is the raw shape of demand the algorithm layer will be built on.</p>

  <div class="kpis">
    <div class="kpi"><p class="label">Postings</p><p class="v num">__KPI_POSTINGS__</p><p class="n">after parsing</p></div>
    <div class="kpi"><p class="label">Companies</p><p class="v num">__KPI_COMPANIES__</p><p class="n">from __KPI_RAWEMP__ raw strings</p></div>
    <div class="kpi"><p class="label">IT postings</p><p class="v num">__KPI_IT__</p><p class="n">KldB group 43</p></div>
    <div class="kpi"><p class="label">IT employers</p><p class="v num">__KPI_ITCO__</p><p class="n">with 3+ IT roles</p></div>
    <div class="kpi hl"><p class="label">Competitor share</p><p class="v num">__KPI_COMP__</p><p class="n">of IT postings, from agencies &amp; IT services</p></div>
    <div class="kpi"><p class="label">Median age</p><p class="v num">__KPI_AGE__</p><p class="n">days a posting has been open</p></div>
    <div class="kpi"><p class="label">Open &gt; 90 days</p><p class="v num">__KPI_STALE__</p><p class="n">the scarcity signal</p></div>
  </div>

  <div class="grid">
    <div class="panel">
      <p class="label">Demand</p><h3>Occupational groups</h3>
      <p class="hint">Top 10 of 37. IT highlighted.</p>
      <div id="c-groups"></div>
    </div>
    <div class="panel">
      <p class="label">Supply side</p><h3>Who is posting</h3>
      <p class="hint">Postings by company class. Highlighted classes compete with us for the same placements.</p>
      <div id="c-class"></div>
    </div>
    <div class="panel">
      <p class="label">Stack</p><h3>Technologies in IT postings</h3>
      <p class="hint">From job titles only — roughly a third of IT postings name a technology. Descriptions would raise this.</p>
      <div id="c-tech"></div>
    </div>
    <div class="panel">
      <p class="label">Sector</p><h3>Market domains</h3>
      <p class="hint">Across all postings — the sector a role sits in, detected separately from the technology stack. Domain fit is a first-class matching dimension.</p>
      <div id="c-domain"></div>
    </div>
    <div class="panel">
      <p class="label">Scarcity</p><h3>How long postings stay open</h3>
      <p class="hint">Highlighted buckets are roles the market is failing to fill.</p>
      <div id="c-age"></div>
    </div>
    <div class="panel">
      <p class="label">Qualification</p><h3>Requirement level</h3>
      <p class="hint">KldB 5th digit. Present on 99.8% of postings — the reliable way to stratify by level.</p>
      <div id="c-level"></div>
    </div>
    <div class="panel wide">
      <p class="label">Geography</p><h3>Where the postings are</h3>
      <p class="hint" id="region-hint"></p>
      <label class="chk" style="margin-bottom:14px"><input type="checkbox" id="region-norm"> Per million inhabitants</label>
      <div id="c-region"></div>
    </div>
    <div class="panel wide">
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

<!-- ================= COMPANIES ================= -->
<section class="screen" id="companies">
  <p class="label">Companies</p>
  <h2>Every resolved<br>company</h2>
  <p class="lede">One row per entity after name resolution. Class comes from keyword rules over the
    company name — <em>review</em> marks the ones the rules could not decide.</p>

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

<!-- ================= POSTINGS ================= -->
<section class="screen" id="postings">
  <p class="label">Postings</p>
  <h2>The evidence<br>layer</h2>
  <p class="lede">Showing __POSTINGS_SHOWN__ __SCOPE__. Every title links to the live posting on
    arbeitsagentur.de — this is what any score has to be traceable back to.</p>
  <div class="note" style="margin:-16px 0 26px"><b>Sorted by how long each posting has been open.</b>
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

<!-- ================= QUALITY ================= -->
<section class="screen" id="quality">
  <p class="label">Data quality</p>
  <h2>What to<br>distrust</h2>
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
        <li><b>This is a sample, not a census.</b> One source, one crawl window, and it under-represents
          hiring that runs through company career pages and LinkedIn.</li>
      </ul>
    </div>
  </div>
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
