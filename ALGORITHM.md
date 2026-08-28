# OpRadar — Algorithm & Code Structure

**Status:** design spec, v1. Written 2026-08-28.
**Companies pipeline:** every threshold and figure below was measured against
`data/postings.parquet` (see `Research.txt` for method).
**People pipeline:** specification only. The dataset does not exist yet — this
document defines what it must contain so that Part 3 is possible at all.

---

## 0. How to read this

The three parts of the product are not three separate systems. They are three
factors of one number:

```
Opportunity = Need  ×  Serviceability  ×  Confidence
              (Part 1)   (Part 2)          (both)
```

| Factor | Question it answers | Source |
|---|---|---|
| **Need** | Does this company have unmet IT hiring demand? | job postings |
| **Serviceability** | Can we actually deliver against it? | candidate pool |
| **Confidence** | How much do we trust this row? | evidence volume + entity certainty |

Why multiplicative and not a weighted sum: a weighted sum lets a company with
enormous need but zero serviceability outrank a perfect match. That is exactly
the wrong answer for a consultancy. Multiplication makes an unservable
opportunity worth nothing, which is the truth.

Before Part 2 exists, `Serviceability = 1.0` for everyone and the ranking is
driven purely by Need. The system degrades gracefully and stays demoable at
every stage of the build.

---

## 1. What the product is

For a LITIT salesperson:

> Which DACH company should I contact, why, what do I pitch them,
> and what evidence backs it?

Output is a ranked list of companies. Each row carries a score, a full
decomposition of that score, a named opportunity type, and 3–8 real job
postings with live `arbeitsagentur.de` links.

---

## 2. The shared vocabulary (build this FIRST)

This is the single most important design decision in the project. Both
pipelines must emit the same canonical unit, or Part 3 is impossible.

### RoleAtom

The atom of both demand and supply.

```
RoleAtom {
  role_family : dev | ops | data | security | qa | architect | analyst | support
  tech_tags   : set of {sap, java, dotnet, cloud, data_bi, security,
                        network, web, erp_crm, ai, other}
  seniority   : junior | mid | senior | lead
  region      : NUTS code (DE1, DE2, ... )
}
```

A **job posting** normalises into a RoleAtom = one unit of demand.
A **candidate** normalises into a RoleAtom = one unit of supply.
Part 3 joins them on this structure. Nothing else needs to match.

Both pipelines import the same module (`common/taxonomy.py`). If the people
pipeline invents its own skill vocabulary, the project fails at integration —
this is the number one integration risk and it costs nothing to avoid.

### Measured tech distribution (companies side, 6,902 IT postings)

| family | postings |
|---|---|
| data_bi | 811 |
| sap | 516 |
| web | 273 |
| cloud | 257 |
| security | 241 |
| network | 220 |
| java | 211 |
| ai | 178 |
| erp_crm | 143 |
| dotnet | 133 |

Only ~45% of IT postings carry any identifiable tech token. **Tech tags are
sparse evidence, never a required field.** Any logic that assumes a stack is
known will silently drop half the data.

---

## 3. PIPELINE A — Companies (demand)

### Stage 0 — Hygiene

- Drop 41 rows with null employer.
- Collapse 858 exact-duplicate groups (`employer`,`title`,`posted_date`) = 1,338 redundant rows.
- `vacancy_age_days = snapshot_date − posted_date`, snapshot_date = 2026-06-06.
- Normalise every title once, centrally:
  `' ' + re.sub('[^a-z0-9äöüß#+]+',' ', title.lower()) + ' '`

> **Trap:** DuckDB uses RE2, which silently ignores `\b`. `\bsap\b` matches
> zero rows while `sap` matches 525. Never use `\b` in this codebase. Match
> against the space-padded token string instead. This bug cost us a full round
> of wrong numbers.

### Stage 1 — Entity resolution

Normalise: casefold → fold umlauts → strip legal forms
(`GmbH`, `AG`, `SE`, `KG`, `GmbH & Co. KG`, `mbH`, `oHG`, `e.K.`) →
collapse whitespace. Handle the doubled-suffix case explicitly
(`PerZukunft … GmbH&Co.KG GmbH & Co. KG` — merges 904 postings).

**Do not strip** `Group`, `Holding`, `Services`, `Deutschland`, `Niederlassung`
— they carry meaning and stripping them collapses distinct subsidiaries.

Blocking on the normalised first token keeps matching O(n·k) rather than O(n²)
over 19,942 names. Keep branches distinct, assign a shared `group_id`
(all `FERCHAU Niederlassung *`, all `DIS AG *`, all `NTT *`). Classification
runs at group level; evidence stays at branch level.

### Stage 2 — Role tagging

The dataset's own `esco_occupation`, `esco_skills`, `kldb_2010` and `seniority`
fields are unreliable (Research.txt §3.2–3.5) and are **not used**. Everything
is derived from the title:

- **is_IT** — keyword match → 6,902 postings, 2,691 employers
- **tech_tags** — see §2
- **seniority** — senior 655, lead 268, architect 495, junior 188
- **role_family**

**Exclude apprentices, dual-study and Werkstudenten from demand counting**
(310 + 196 IT postings). A company hiring Azubis is building capability
in-house — the opposite of an outsourcing trigger. Counting them inflates
precisely the wrong companies.

> **Rejected:** LLM classification per posting. Measured 57,564 distinct titles
> across 70,584 rows; the top 2,000 titles cover only 18% of rows. There is no
> head to exploit — per-title LLM calls cost nearly as much as per-row and buy
> nothing over keywords. LLM is used at company level only (§Stage 3), where
> there are ~377 decisions instead of ~70,000.

### Stage 3 — Classification gate

**The stage that decides whether the project succeeds.** Filtering is separate
from scoring: a company is ruled eligible first, ranked second.

**3a — deterministic exclusion (high precision, no judgement)**

| class | removed | detection |
|---|---|---|
| intermediary | 1,720 companies / 1,487 IT postings | name lexicon: `personaldienst`, `zeitarbeit`, `arbeitsvermittlung`, `staffing`, plus brand list (DIS AG, Hays, Michael Page, Manpower, Randstad, Adecco, Akkodis, FERCHAU, Orizon, Amadeus Fire, Brunel, GULP…) |
| training provider | 52 / 54 | `bildungszentrum`, `akademie`, `alfatraining`, `umschulung` |
| own group | 5 / 118 | `NTT`, `Reiz Tech` |

**3b — features**

`it_share = it_postings / total_postings`, total volume, occupational
diversity, region spread, count open >90d, age profile shape.

**3c — LLM classification (~377 companies)**

The name lexicon alone leaks badly — after 3a the top of the list was still
Deloitte, Computacenter, BridgingIT, ALTEN, EY, secunet, SINTEC. All
competitors.

`it_share` is the strong discriminator. Filtering to <30% IT share yields
Siemens Energy, Deutsche Bahn, BMW, AXA, Deutsche Telekom, REWE, HUK-COBURG,
Rossmann, Vodafone — unmistakably end clients. The logic: a company that also
hires nurses, drivers and accountants is a company *with* an IT department,
not an IT company.

Distribution over the 377 companies with ≥3 IT postings:

| IT share | companies |
|---|---|
| <10% | 39 |
| 10–25% | 56 |
| 25–50% | 77 |
| 50–80% | 108 |
| ≥80% | 97 |

So ~205 of 377 are IT firms. The genuine prospect pool is **95–170 companies**.

**But `it_share` alone gets one important class exactly wrong.**
`Finanz Informatik` (70 IT postings — the Sparkassen group's IT arm),
`BWI GmbH` (54 — Bundeswehr IT), `Bundesdruckerei` are all high-IT-share, so
share-based logic discards them as competitors. They are in fact *captive IT
subsidiaries*: in-house IT providers who buy external delivery capacity as a
matter of routine. They are among the **best** prospects.

A commercial IT vendor and a captive IT subsidiary are near-identical in this
data. Telling them apart requires knowing *who the company serves* — world
knowledge the features cannot supply. **This is the one decision that
genuinely requires the LLM**, and the reason it is in the design.

Classes emitted:

| class | verdict |
|---|---|
| non-IT enterprise with IT dept | prospect |
| captive / in-house IT subsidiary | **prime prospect** |
| commercial IT services vendor | competitor → partner list |
| missed intermediary | exclude |

Input to the model: company name, IT share, total postings, top 15 job titles,
region spread. Output: class + one-sentence justification, both stored.
Temperature 0. Cache by company name.

### Stage 4 — Need signals

Computed only over eligible companies, only from trusted fields.

**N1 — Unmet demand (weight 35)**
```
open_over_90   = count(IT vacancies with age > 90d)
open_over_180  = count(IT vacancies with age > 180d)
N1 = 0.6·pct(open_over_90) + 0.4·pct(open_over_180)
```
> **Changed in v1 after testing.** The first version used *median vacancy age*.
> That is confounded: a company posting many fresh ads shows a low median
> regardless of how hard its roles are to fill. Median age measures posting
> cadence, not difficulty. A **count** of vacancies still open past 90 days is
> a direct observation and survives the confound. Median age is retained for
> display only.

**N2 — Seniority pressure (weight 25)**
```
N2 = 0.6·pct(senior_lead_architect_count) + 0.4·pct(senior_share)
```
Senior roles are the hardest to hire and the strongest trigger for buying
external capacity. This discriminates independently of volume: Deutsche
Telekom shows 15 senior/lead roles of 27; Rossmann shows 0 of 12. Similar
size, completely different opportunity.

**N3 — Coherence (weight 20)**
```
HHI = Σ (share of tech family)²        over the company's IT postings
N3  = pct(HHI) · min(1, it_count / 5)
```
Nine SAP roles is a programme with a nameable pitch. Nine scattered roles is
business-as-usual backfill. The volume damper stops a 3-posting company
scoring 1.0 on concentration by accident.

**N4 — Momentum (weight 20)**
```
N4 = pct(postings_last_30d / postings_last_180d)
```
Proves the company is *still* hiring rather than sitting on abandoned ads.
This is the main defence against dead listings.

**Context only — never scored:** total IT volume, median vacancy age, region
count, market scarcity per tech family.

> **Rejected: market scarcity as a scored signal.** Intended as "how hard is
> this skill to fill market-wide". Measured median vacancy age by family: SAP
> 14d (lowest), web 30d (highest). That does not mean SAP is easy — it means
> SAP ads are posted more recently and churn faster. A single snapshot cannot
> separate "posted recently" from "filled quickly"; that needs two snapshots
> and a duration model. Kept as displayed context with an explicit caveat.
> **If we pull a second snapshot from the live BA API, this becomes properly
> measurable and is the single highest-value upgrade available.**

**Normalisation.** Every signal → percentile rank *within the eligible pool*.
Percentiles resist outliers, remove unit problems, and speak the language of
the user: "top 6% for unfilled senior demand". Percentiles computed over the
contaminated pool would be meaningless, so this must run strictly after
Stage 3.

```
Need = Σ wᵢ · Nᵢ    (weights sum to 100, output 0–100)
```

### Stage 5 — Confidence
```
Confidence = 0.5·evidence_factor + 0.3·recency_factor + 0.2·identity_factor

evidence_factor = min(1, it_count / 8)          # thin evidence → low trust
recency_factor  = 1 if posting in last 30d, 0.7 if 90d, 0.4 otherwise
identity_factor = 1.0 clean match | 0.7 fuzzy merge | 0.5 ambiguous
```

Reported next to the score, never hidden inside it: *"score 81, confidence
medium — based on 4 postings"*. This is more honest than shrinkage and far
easier to defend when a judge asks why a small company ranks highly.

### Stage 6 — Guardrails

- ≥3 eligible IT postings (pool: 742 companies at ≥2, 377 at ≥3, 187 at ≥5)
- ≥1 posting within the last 90 days → 335 companies survive both
- flag contradictory signals rather than averaging them away

### Stage 7 — Explanation

1. Compute a deterministic template containing the real numbers.
2. The LLM **rewrites that template into prose**. It receives only the computed
   facts. It never sees raw data and never sources a claim.
3. Attach 3–8 evidence postings with live `source_url`s.

Any architecture where the LLM can invent a signal is disqualifying: one
hallucinated fact discovered live destroys the credibility of every number on
screen.

### Stage 8 — Output

Ranked prospects with score, decomposition, opportunity type (derived from
dominant tech family — "SAP delivery capacity", "cloud migration team"),
evidence, and confidence. Plus the partner list, and the naive volume ranking
retained as the comparison exhibit.

---

## 4. PIPELINE B — People (supply)

**Not yet measured — this is a specification.** Its purpose is to define what
the dataset must contain. Build the dataset to this shape and Part 3 is nearly
free; build it to a different shape and Part 3 becomes the whole hackathon.

### Required per candidate

```
Candidate {
  candidate_id
  role_atom        : RoleAtom            # SAME structure as demand, §2
  years_experience : int
  availability     : available_now | in_30d | in_90d | unavailable
  languages        : set                 # German matters — see below
  location         : region + remote_ok
  source           : synthetic | consented   # MUST be labelled
}
```

### Stages

**P0 — Ingest & validate.** Reject any profile that cannot produce a RoleAtom.

**P1 — Normalise to RoleAtom.** Reuses `common/taxonomy.py` unchanged. This is
the integration contract.

**P2 — Supply signals, per (role_family, tech, seniority) cell:**
- `depth` — how many candidates
- `readiness` — share available now vs in 90 days
- `bench_pressure` — unallocated capacity, if the notion applies

**P3 — Supply index.** A lookup from RoleAtom cell → depth, readiness. This is
the only object Part 3 needs from Pipeline B.

### Two constraints that must be honoured

**Synthetic data must be labelled as synthetic in the UI.** A judge who
suspects generated people are being passed off as real applicants will
discount every other number on screen. Labelling it costs one line and buys
credibility.

**German language capability is a real constraint on nearshore delivery** and
belongs in the candidate schema. We cannot detect a German-language
requirement from job titles, so this stays a stated limitation on the demand
side — but the supply side should carry it.

---

## 5. PIPELINE C — Match

For company `C` with demand atoms `D`, and supply index `S`:

```
for each demand atom d in D:
    coverage(d) = 1 if S has ≥1 candidate matching
                    (role_family, tech ∩ ≠ ∅, seniority ≥ d.seniority − 1)
                  else partial credit for adjacent seniority
    depth(d)    = min(1, matching_candidates / 3)

Serviceability(C) = Σ wᵈ · (0.7·coverage(d) + 0.3·depth(d)) / Σ wᵈ
```

where `wᵈ` weights each demand atom by its own unmet-demand contribution — an
unfilled senior role we can staff counts for far more than a junior role we
cannot.

```
Opportunity(C) = Need(C) × Serviceability(C) × Confidence(C)
```

**Output framing for sales:** *"AXA has 4 IT roles open over 90 days, 3 of
them senior, concentrated in data/BI. We have 5 matching data engineers
available within 30 days."* Demand pain is a lead. Demand pain matched to
available supply is a deal.

**Degradation:** with no supply data, `Serviceability = 1.0` and the ranking
falls back to pure Need. Nothing breaks.

---

## 6. Output artifact (the contract between pipeline and UI)

The pipeline is a **batch job producing a file**. The API only reads that file.
Scoring never runs inside a request handler — a bad data edge case must never
be able to take down a live demo.

SQLite, `data/opradar.db`:

```
companies(company_id, canonical_name, group_id, class, class_reason,
          total_postings, it_postings, it_share, regions, archetype)

scores(company_id, need, serviceability, confidence, opportunity,
       n1_unmet, n2_seniority, n3_coherence, n4_momentum,
       rank, rank_naive_volume)

evidence(company_id, posting_id, title, posted_date, age_days,
         tech_tags, seniority, region, source_url)

narratives(company_id, opportunity_type, summary_text, generated_at)

supply_index(role_family, tech, seniority, depth, readiness)   -- Part 2

matches(company_id, coverage, depth, serviceability)           -- Part 3

meta(key, value)   -- snapshot_date, weights hash, pipeline version
```

Agree this schema before either of you writes a line. Commit a hand-written
fake `opradar.db` immediately so the UI can be built against real-shaped data
before the pipeline produces any.

---

## 7. Validation without ground truth

There are no labels, so "accuracy" is unavailable. Three checks that are honest
and demoable:

**V1 — Divergence from volume, measured.** Spearman rank correlation between
our ranking and pure vacancy count. It must be **low**. If our top 20 is
largely the volume top 20, we have failed the brief's central constraint.
Reporting this number converts "we don't rank by volume" from a claim into
evidence. Store it in `meta`.

**V2 — Adversarial check.** No intermediary, no competitor, no NTT entity may
appear in the customer list. Each one that does is a named, countable defect.
Invite judges to hunt for one.

**V3 — Sensitivity.** Perturb weights ±20% and check whether the top 20 holds.
If small changes reshuffle the leaderboard, the weights are doing the work
rather than the signals — and "why 35 and not 30?" becomes an unanswerable
question on stage.

---

## 8. Code structure

```
OpRadar/
├── ALGORITHM.md
├── Research.txt
├── config/
│   ├── weights.yaml                 # all tunables, nothing hardcoded
│   └── lexicons/
│       ├── intermediaries.txt       # agency names + brands
│       ├── training.txt
│       ├── own_group.txt
│       ├── legal_forms.txt
│       ├── tech_taxonomy.yaml       # tech family → keywords
│       ├── role_families.yaml
│       └── seniority.yaml
├── data/                            # gitignored: parquet in, opradar.db out
├── src/opradar/
│   ├── common/
│   │   ├── taxonomy.py       # RoleAtom, tag_tech, tag_seniority, tag_role
│   │   │                     # ← BOTH pipelines import this. Build first.
│   │   ├── text.py           # tokenize_title, normalize_company, fold_umlauts
│   │   ├── stats.py          # percentile_rank, hhi, weighted_sum
│   │   └── db.py             # artifact read/write
│   ├── companies/
│   │   ├── s0_ingest.py      # load parquet, dedupe, ages
│   │   ├── s1_entities.py    # normalize + block + merge → company_id
│   │   ├── s2_roles.py       # postings → RoleAtoms
│   │   ├── s3_classify.py    # 3a lexicon, 3b features
│   │   ├── s3_llm.py         # 3c LLM classifier, cached, temp 0
│   │   ├── s4_signals.py     # N1..N4 + context metrics
│   │   ├── s5_score.py       # percentiles, Need, Confidence
│   │   ├── s6_guards.py      # thresholds, contradiction flags
│   │   └── s7_explain.py     # template → LLM prose → evidence
│   ├── people/
│   │   ├── p0_ingest.py
│   │   ├── p1_profiles.py    # → RoleAtoms via common.taxonomy
│   │   └── p2_supply.py      # supply_index
│   ├── match/
│   │   └── m1_match.py       # coverage, depth, Serviceability
│   ├── validate/
│   │   └── checks.py         # V1 V2 V3
│   ├── api/
│   │   └── main.py           # FastAPI, READ-ONLY over opradar.db
│   └── cli.py                # opradar build | validate | serve
├── web/                      # leaderboard, company detail, evidence
└── tests/
    ├── test_text.py          # incl. the RE2 \b regression
    ├── test_entities.py      # PerZukunft merge case
    └── test_scoring.py
```

### Design rules

1. **Every stage reads a file and writes a file.** Any stage can be re-run
   alone. Debugging at hour 20 depends on this.
2. **No tunable is hardcoded.** All weights and thresholds live in
   `weights.yaml`, hashed into `meta` so any result is reproducible.
3. **The API never computes a score.** It reads `opradar.db`. A broken
   pipeline run then costs you yesterday's data, not the demo.
4. **LLM calls are cached to disk and run at temperature 0.** Two runs must
   produce the same leaderboard, or the demo is a coin flip.
5. **`common/taxonomy.py` is the integration contract.** Neither pipeline may
   define its own skill vocabulary.

### Build order

```
common/taxonomy.py + text.py     ← both people depend on this; do it together
        ↓
s0 → s1 → s2 → s3 → s4 → s5 → s6 → s7      artifact exists, demo is possible
        ↓
web + api against the artifact              ← parallel, different owner
        ↓
validate/checks.py                          ← V1 is a demo slide, not a test
        ↓
people/ → match/                            ← only after companies is shippable
```

Part 1 alone satisfies every minimum requirement in the challenge README.
Parts 2 and 3 are the differentiator, but they are worth nothing if Part 1 is
not finished and demoable. Cut Part 3 down, never Part 1.

---

## 9. Known limitations (state these before a judge finds them)

1. **Single snapshot.** All postings scraped in one ~2h window on 2026-06-06.
   No true time series exists, so no hiring-velocity claim is made anywhere in
   this system. Month-over-month counts from this file measure vacancy
   survival, not hiring demand.
2. **Survivorship bias.** Older months contain only postings still unfilled
   today. This is why Need uses counts of currently-open vacancies rather than
   historical rates.
3. **One source.** 100% Bundesagentur für Arbeit. Companies that do not post
   there are invisible — likely biasing against startups and senior/executive
   hiring.
4. **DACH is really DE.** 355 Austrian rows, 2 Swiss, out of 70,584.
5. **No firmographics.** No revenue, headcount or industry. Company size is
   proxied by total posting volume, which is weak.
6. **No job description text.** `description_derived` is 100% null, so tech
   stack comes from titles alone and is present for only ~45% of IT postings.
7. **Dataset's own enrichment fields are unreliable** and deliberately unused
   (Research.txt §3.2–3.5).
8. **Entity resolution is approximate.** Explicitly permitted by the README.
9. **Abandoned listings.** A very old open posting may be neglected rather than
   unfilled. Mitigated by the momentum signal and the 90-day recency guard,
   not eliminated.
10. **Language requirement invisible.** A German-language-mandatory role is
    harder to serve from Lithuania, and titles do not reveal it.

---

## 10. Open questions

| # | Question | Blocks |
|---|---|---|
| Q1 | Competitors — exclude, or surface as a partner list? | Stage 3 output shape |
| Q2 | May we call the live BA API? Enables a second snapshot (→ real duration analysis) and full description text | N-signal upgrade, stretch goal |
| Q3 | LITIT's actual delivery stack | turns "hiring IT" into "hiring OUR stack" |
| Q4 | People dataset — bench, or open candidate pool? | Pipeline B semantics |
| Q5 | Judging rubric weightings | effort allocation |
