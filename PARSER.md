# Parser

Turns the raw job-postings dataset into two clean tables the algorithm layer can build on.
Product design lives in [BUILD.md](BUILD.md); the evidence behind the decisions is in
[RESEARCH.md](RESEARCH.md).

```bash
pip install -r requirements.txt
python -m opradar
```

Downloads the dataset on first run (4.5 MB, cached in `data/raw/`), then writes to
`data/processed/`:

| File | What |
| --- | --- |
| `postings.parquet` | 70,543 rows -- one per posting, normalised and enriched |
| `companies.parquet` | 18,416 rows -- one per resolved company, classified and aggregated |
| `parse_report.md` / `.json` | QA report: coverage, null rates, what worked, what to review |

Takes ~40 seconds end to end.

## Candidate parser (supply side)

```bash
python -m opradar.candidates
```

Parses `michaelozon/candidate-matching-synthetic` (MIT) into the supply-side half:

| File | What |
| --- | --- |
| `candidates.parquet` | 10,000 profiles: role, role family, seniority, experience band, industry, education, skills, skill families |
| `openings.parquet` | 2,500 synthetic openings with a **recomputed** qualified pool |
| `skill_market.parquet` | 73 skills with supply, demand and a normalised **tension** ratio |
| `role_market.parquet` | role x seniority supply vs demand |
| `candidate_report.md` | QA report, including a hard look at the shipped labels |

Takes ~4 seconds.

### Two findings you need before using it

**It does not join to the German posting data.** Only **7 of its 73 skills** have an equivalent in
our German extraction (`CI/CD, Docker, Java, JavaScript, Power BI, Python, SQL`), and those appear
in just **3.3%** of German IT postings. It contains no SAP, Azure, C#, .NET or embedded work —
which is most of the German market. Treat it as a **standalone supply-side fixture** for building
and demoing the matcher. Bridging the two vocabularies is unsolved work, not a config change.

**Its "ground truth" is not ground truth.** The dataset ships 30 relevant candidates per opening.
Recomputing the rule it documents (>=60% of must-have skills held) shows those 30 are an arbitrary
slice of a pool averaging **866** candidates — the labels cover 3.5% of the correct answers. And
they match the opening's seniority 33.6% of the time against a random baseline of 33%, so seniority
is ignored entirely. **Do not report retrieval precision against these labels**: unlabelled correct
answers are everywhere, so an honest matcher will look wrong.

### Tension

```
tension = (demand share / supply share), normalised so the market average is 1.0
```

The normalisation matters. Candidates carry ~6.5 skills and openings ask for ~4.5, so the raw ratio
has a built-in bias of 0.69 and nothing ever exceeds 1.0 — a number that looks meaningful while
being uninterpretable. Normalised, above 1.0 genuinely means the market wants a skill more than the
bench carries it. Observed spread here is only 0.85–1.18 because the generator is near-uniform; on
real data expect something much wider.

---

## Scorer

```bash
python -m opradar.score
```

The second program (ALGORITHM.md's division of labour), joined to the parser by
`postings.parquet`. Runs Pipelines A, B and C in ~12s:

| Stage | Module | Output |
| --- | --- | --- |
| Signals + Need (N1–N4) + Confidence | `signals.py`, `scoring.py` | `opportunities.parquet` — 306 ranked companies with full decomposition and clickable evidence |
| B3 bench in the German vocabulary | `bench_gen.py` (profile in `reference.py`) | `bench.parquet` — 120 synthetic consultants, deterministic |
| Supply index + German market pull | `supply.py`, `market_pull.py` | `supply_index.parquet`, `market_pull.parquet`, `tech_gap.parquet` |
| Serviceability (the join) | `match.py` | folded into opportunities |
| People value | `people_scoring.py` | `people_value.parquet` |
| V1–V3 + people checks | `validate.py` | `validation.json`, `score_report.md` |

Every tunable lives in `config.py`; the config hash is stamped into every output row.
Current run: V1 Spearman vs volume **0.47**, V2 **clean**, V3 top-20 overlap 14/20 under
±20% perturbation. The UI's Radar and Bench tabs render these outputs (with live weight
sliders); they disappear cleanly when the scorer has not been run.

## Viewer

```bash
python -m opradar.ui --open
```

Builds `ui/index.html` — one self-contained file with the data embedded. No server, no build
step, no network calls: it opens by double-click and keeps working when the venue wifi does not.
Four screens:

| Screen | |
| --- | --- |
| **Overview** | KPIs and eight charts: occupational mix, who is posting, technologies, domains, posting-age distribution, requirement level, geography (with a per-capita toggle), and the posted-by-month chart with its survivorship warning |
| **Companies** | All 18,416 entities. Sort any column; filter by class, IT volume, competitor and noise |
| **Postings** | The evidence layer. Every title links to the live posting on arbeitsagentur.de |
| **Talent** | Supply side: skill supply vs demand, tension ranking, role families, seniority, industry, education, and the full 73-skill market table |
| **Candidates** | All 10,000 profiles. Filter by role, seniority, industry, tech-only; search by skill |
| **Data quality** | Entity resolution, classification, coverage, null rates, review queue, ground-truth audit, known limits |

The Talent and Candidates screens appear only when `python -m opradar.candidates` has been run;
otherwise the tabs are removed rather than rendered empty.

`--scope it` (7,131 rows) / `it_extended` (11,288, default) / `all` (70,543) controls how many
postings are embedded in the postings table. `all` produces a noticeably larger file.

```bash
python -m opradar --fuzzy        # blocked fuzzy merge of company names (off by default)
python -m opradar --loose-keys   # also strip Deutschland/Group/Holding when grouping
python -m opradar --duckdb       # also write data/processed/opradar.duckdb
python tests/test_parser.py      # normalisation self-checks
```

---

## What it does

**Postings**
- Derives the two **interface-contract columns** for the scorer (ALGORITHM.md §1):
  `is_it_role` (title-primary IT detection — the title decides, KldB corroborates) and
  `is_training_role` (Ausbildung / duales Studium / Werkstudent / Praktikum).
  Both lexicons live in `reference.py` — the single source; do not re-implement downstream
- Flattens the nested ESCO occupation/skill structs
- Decodes `kldb_2010` into sector, group, subgroup and **requirement level** (5th digit)
- Cleans titles: strips `(m/w/d)` variants, `*innen`/`:innen`, internal reference codes, trailing boilerplate
- Extracts **technologies** (~55 patterns) and **market domains** (11) from the title
- Derives seniority from title keywords, falling back to the dataset column
- Computes posting age, freshness and staleness against the crawl date
- Normalises region, fills gaps from NUTS, tags country, attaches regional population

**Companies**
- Resolves ~19.9k raw employer strings to 18.4k entities
- Picks a clean display name per entity
- Classifies into `end_client` / `it_service_provider` / `staffing_agency` / `public_sector` / `training_provider` / `individual`
- Flags `is_competitor` and `is_noise`
- Aggregates volume, IT intensity, region spread, seniority mix, top technologies, posting-age stats
- Flags ~60 companies as `needs_review` where the rules genuinely cannot decide

---

## The decisions worth knowing about

**Entity resolution cuts at the first legal-form token.** `"DIS AG Personaldienstleistungen"`,
`"DIS AG Germany"` and `"DIS AG FB Office & Management"` all reduce to `dis`. This one rule
removes divisions, branches and duplicated suffixes in a single step, and it collapses FERCHAU's
61 branch listings into one company. Exact grouping only by default -- **fuzzy merging is opt-in
because over-merging invents companies that do not exist**, which is worse for a placement list
than leaving two records unmerged.

**Agencies are classified, not deleted.** 28.4% of IT postings come from competitors (staffing
agencies + IT service providers). For a recruiter-side product that is not noise to filter out --
it is the market-saturation signal. `is_competitor` marks them so downstream code can exclude them
from the opportunity list *and* count them for the competition metric.

**Product companies are end clients, not competitors.** The IT-services rule is deliberately
narrow: generic words like *software*, *informatik*, *digital*, *systems*, *data* describe product
companies just as often as service companies. Including them classified Finanz Informatik -- a
captive banking IT arm and the single largest non-agency IT employer in the data -- as a
competitor, and dropped it off the leaderboard entirely.

**Seniority stays honest at ~16% known.** An earlier version filled it from the KldB requirement
level and reported 45% of the German labour market as "senior". Anforderungsniveau 4 means
"requires a degree", which is true of every graduate hire -- it is a *qualification* level, not a
career stage. It is now exposed as `kldb_level` (99.8% coverage) and never mapped to seniority.
**For stratification, use `kldb_level`. Use `seniority_derived` only where it is populated.**

**Technology patterns run against folded text.** Patterns are written in ASCII
(`steuergeraet`, `kuenstliche intelligenz`), so they are matched against a lowercased,
umlaut-expanded title. Before this, every German pattern in the dictionary silently never fired.

**German compounds need asymmetric boundaries.** `netzwerk` uses a left boundary only, so
"Netzwerkadministrator" matches. `security` needs both, so "Sicherheitsmitarbeiter" (a security
guard) does not. Bare `sicherheit` was matching occupational-safety jobs and inflating the security
count by ~3x. `C` as a language was removed entirely: it matched truck licence classes
("Klasse C", "C/CE") far more often than the language.

**Domains are separate from technologies.** "Automotive" is the client's sector, not a stack. Left
in the technology list it ranked #1, above SAP. It is now its own field -- and domain fit is a
first-class matching dimension for placement anyway.

---

## Key output columns

`postings.parquet`

| Column | Note |
| --- | --- |
| `posting_id`, `source_url` | Evidence link -- every claim downstream should cite these |
| `company_key`, `company_name`, `company_class` | Resolved entity |
| `title_clean` | Gender markers and reference codes removed |
| `kldb_code` / `_sector` / `_group` / `_level` | **`kldb_level` is the reliable stratification field** |
| `is_it_core`, `is_it_extended` | KldB `43x`, and `43/41/27/25` — corroboration, not a gate |
| **`is_it_role`**, **`is_training_role`** | **The scorer's interface contract.** Eligible posting = prospect class ∧ `is_it_role` ∧ ¬`is_training_role` |
| `technologies`, `tech_categories` | ~7% coverage from titles; run again on descriptions for real coverage |
| `domains` | Market sector |
| `seniority_derived`, `seniority_source` | ~16% known, honestly |
| `posting_age_days`, `is_stale_90d`, `is_stale_180d` | **The scarcity signal** |
| `region_clean`, `country`, `region_population_m` | Normalise before any regional comparison |
| `is_competitor_posting` | For the saturation metric |

`companies.parquet`

| Column | Note |
| --- | --- |
| `company_key`, `company_name`, `name_variants` | Spot-check large variant clusters |
| `company_class`, `class_confidence`, `class_rule` | `class_rule` shows *which* keyword fired |
| `is_competitor`, `is_noise`, `needs_review` | |
| `postings`, `it_postings`, `it_intensity` | **Now title-based** (`is_it_role` ∧ ¬training), per ALGORITHM.md §2 |
| `it_core_postings`, `training_postings`, `it_corroboration` | KldB count, training count, share of IT postings where KldB agrees (Confidence input) |
| `needs_review_t2` | ALGORITHM.md §4.3 T2: small IT-dense `end_client` — the LLM-pass queue alongside `needs_review` (T1) |
| `median_age_days`, `p90_age_days`, `median_it_age_days`, `stale_90d_share` | Time-on-market |
| `region_count`, `regions`, `primary_region` | |
| `kldb_sector_entropy`, `agency_breadth_score`, `agency_likelihood` | Behavioural agency fingerprint |
| `top_technologies`, `seniority_mix`, `kldb_level_mix` | |

---

## Known limits

- **`posted_date` trends are meaningless.** The dataset is a *stock* of postings still open at
  crawl time, not a *flow*. Older postings are missing because they were filled, so counting by
  month produces a fake exponential curve. `posting_age_days` is also length-biased: valid for
  ranking companies against each other, invalid as an absolute time-to-fill.
- **Technology coverage is ~7%** (36% within IT). Titles name roles, not stacks. Real coverage
  needs the job description text, which this dataset does not contain.
- **ESCO fields are noisy.** `esco_skills` is a top-5 nearest-neighbour assignment, not extraction,
  and `esco_occupation` is visibly wrong on a material share of rows. Passed through unchanged as a
  weak prior; do not trust them over `kldb_code` + title.
- **Regional counts reflect crawl coverage** as much as labour demand.
- **Company classification is keyword rules.** Precision has not been measured against hand labels
  yet -- that is the next thing worth doing, and `needs_review` is where to start.
- The dataset contains 355 Austrian and 2 Swiss rows despite the "German" framing; `country` marks them.

---

## Extending it

- **New technology or domain**: add one line to `TECH_PATTERNS` / `DOMAIN_PATTERNS` in
  `reference.py`, then add a case to `tests/test_parser.py`. Watch the German-compound boundary
  rules described above.
- **New company classification rule**: `CLASS_PATTERNS` in `reference.py`, evaluated in order,
  first hit wins.
- **Descriptions**: `extract_technologies()` and `extract_domains()` take a column argument. Point
  them at a description column once you have one; nothing else changes.
- **Live data**: keep this same output schema. The live source publishes a stable employer hash
  that beats every string heuristic here -- see RESEARCH.md section 4.2.

---

*Job posting data © Bundesagentur für Arbeit, CC-BY-4.0 — attribution required in any UI.*
