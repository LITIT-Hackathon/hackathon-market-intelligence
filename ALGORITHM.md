# OpRadar — Algorithm & Code Structure

**v2, 2026-08-28.** Rewritten against the parser actually in `main`
(`opradar/`, commit `03583d1`), not the greenfield design of v1.

**Companies pipeline:** every figure below is measured against
`data/processed/postings.parquet` — the parser's own output — so the numbers
match what the code will actually see. Method and dataset caveats: `Research.txt`.
**People pipeline:** specification only. The dataset does not exist yet.

---

## 0. The spine

```
Opportunity = Need  ×  Serviceability  ×  Confidence
              (Part 1)   (Part 2)          (both)
```

| Factor | Question | Source |
|---|---|---|
| **Need** | Does this company have unmet IT hiring demand? | job postings |
| **Serviceability** | Can we actually deliver against it? | candidate pool |
| **Confidence** | How much do we trust this row? | evidence volume + identity certainty |

Multiplicative, not a weighted sum: a company with huge need we cannot serve is
worth nothing to a consultancy, and a sum would still rank it top. Before Part 2
exists, `Serviceability = 1.0` and ranking is driven by Need alone — the system
stays demoable at every point in the build.

---

## 1. Division of labour

The parser and the scorer are separate programs joined by one file.

| Owner | Modules | Responsibility |
|---|---|---|
| **Gustas** | `postings.py`, `companies.py`, `reference.py`, `text.py` | raw → clean, classified postings |
| **Jokūbas** | `signals.py`, `scoring.py`, `validate.py` | postings → ranked opportunities |
| both | `classify_llm.py` | the review queue (§4.3) |

**Interface contract — agree before writing code:**

`data/processed/postings.parquet` gains two boolean columns:

| column | meaning |
|---|---|
| `is_it_role` | the title says this is an IT job (§4.2) |
| `is_training_role` | Ausbildung / duales Studium / Werkstudent / Praktikum |

Nothing else changes. Once those column names are agreed, both halves can be
built in parallel against the existing file.

---

## 2. What the parser already provides

Do not rebuild any of this.

| Need | Column | Notes |
|---|---|---|
| identity | `company_key`, `company_name`, `name_variants` | 19,942 strings → 18,416 entities |
| classification | `company_class`, `class_confidence`, `class_rule` | 6 classes |
| IT share | `it_intensity` | recompute after §4.2 |
| occupational diversity | `kldb_sector_entropy` | better than the proxy v1 specified |
| age | `posting_age_days`, `is_fresh_30d`, `is_stale_90d/180d` | |
| tech | `technologies`, `tech_categories`, `has_tech_signal` | 12 categories |
| seniority | `seniority_derived`, `seniority_source` | sparse — see §5 |
| geography | `region_clean`, `nuts_code`, `country`, `region_population_m` | |

Three parser decisions that were better than v1's spec and stay:

- **`public_sector` as its own class.** BWI lands there correctly.
- **The review queue** — high-volume, high-breadth companies the rules cannot
  call. Extended in §4.3.
- **KldB requirement level kept as its own dimension**, after it was tested as a
  seniority source and rejected for labelling ~45% of the market senior.

---

## 3. Eligibility

Straight off `company_class`:

| class | postings | verdict |
|---|---|---|
| `end_client` | 50,502 | **prospect** |
| `public_sector` | 1,732 | **prospect** |
| `it_service_provider` | 3,293 | partner list — not ranked as prospects |
| `staffing_agency` | 14,570 | exclude |
| `training_provider` | 261 | exclude |
| `individual` | 185 | exclude |

Competitors are not merely discarded. Their IT volume is the **saturation
signal** — FERCHAU 254 IT postings, DIS AG 197 — telling a salesperson how
contested a segment already is. This was the parser's idea and it is a better
one than v1's "exclude and forget".

---

## 4. Pipeline A — Companies

### 4.1 Base set

```
eligible posting  ⟺  company_class ∈ {end_client, public_sector}
                  ∧  is_it_role
                  ∧  ¬is_training_role
```

**Measured pool:** 1,498 companies have ≥1 eligible IT posting (4,168 postings
in total). Applying `it_n ≥ 3` gives **327 companies holding 2,142 postings** —
that is the pool every percentile in §4.4 is computed over. 151 companies reach
≥5, and 70 reach ≥8.

**Why training roles are excluded.** A company hiring Azubis is building
capability in-house — the opposite of an outsourcing trigger. Counting them
inflates exactly the wrong companies.

> `seniority_derived` cannot do this filtering. Ausbildung and Werkstudent
> postings split across `entry` (3,957) and `intern` (1,661), so excluding
> `intern` alone leaves ~4,000 apprenticeships in the pool. This is why
> `is_training_role` must be its own column.

### 4.2 The IT definition — title-primary

**`is_it_role` = the cleaned title matches the IT pattern.** `is_it_core`
(KldB) becomes *corroboration*, feeding Confidence — not a gate.

The parser's current `is_it_core` is KldB-only. Measured against title evidence
on its own output:

| | title looks IT | title looks non-IT |
|---|---|---|
| `is_it_core` = true | 4,589 | **2,542** |
| `is_it_core` = false | **2,061** | 61,351 |

36% of the KldB "IT" set has no IT signal in the title — "Kaufmännischer
Mitarbeiter", "Leitende Rezeptionskraft / Front Office-Manager",
"Gruppenleitung Order Management" are all coded KldB 43. Meanwhile 2,061 real
IT jobs are missed: "Junior Java Entwickler" (coded 83113, social work),
"Fullstack Developer" (25112, vehicle engineering), "DevOps Engineer" (28102,
textiles).

**The two error types are not symmetric, which is the whole point.** A title
reading "Java Entwickler" is direct evidence. A KldB code reading 43 while the
title reads "Rezeptionskraft" is simply wrong. So the title decides, and KldB
agreement raises confidence.

> **Rejected: `is_it_core AND title_match`.** An earlier version of this
> document proposed the intersection as "agreement = evidence". It is wrong:
> it discards the 2,061 genuine IT jobs whose KldB code is broken, shrinking
> the pool from 327 companies to 212 and losing precisely the miscoded
> developer roles. Symmetry was assumed rather than tested.

Impact on ranking, from the parser's own top-IT table — share of counted IT
postings with no title evidence: Deutsche Bahn 20 of 27 (74%), TÜV SÜD 12 of 19,
Vodafone 15 of 25, Siemens Energy 23 of 39, Rheinmetall 30 of 63. BMW runs the
other way: 36 by KldB, 48 by title.

### 4.3 Review queue (Stage 3c)

Two triggers, not one.

**T1 — high volume, high breadth** (the parser's existing rule): 61 companies,
including Siemens Energy, GOLDBECK, Office People, Bankpower. Rules cannot
separate a staffing firm from a large diversified employer.

**T2 — small, IT-dense, classified `end_client`** — NEW:
```
it_intensity > 0.5  ∧  it_n ≥ 3  ∧  company_class = 'end_client'
```
T1 only catches large companies. Ranking the current pool by unfilled demand
surfaces inovex GmbH, EMOS Software, BCM Solutions, WBS IT-Service, SmartTECS
Engineers and zollsoft near the top — all IT service providers sitting in
`end_client` because they are small and their names carry no agency keyword.
Without T2 the leaderboard fills with competitors.

**LLM pass** on both queues. Input: name, `it_intensity`, `postings`,
`kldb_sector_entropy`, top 15 titles, `region_count`. Output: class +
one-sentence justification, both persisted. Temperature 0, cached by
`company_key`.

The one decision that genuinely needs a model: **captive IT subsidiary vs
commercial IT vendor.** `Finanz Informatik` (Sparkassen IT, 95 IT postings),
`BWI` (Bundeswehr IT), `Bundesdruckerei` are all IT-dense, so intensity logic
files them as competitors. They are in-house IT providers who buy external
delivery capacity as routine — among the best prospects available. Telling them
apart requires knowing *who the company serves*, which no feature in this
dataset encodes.

### 4.4 Need signals

> **Superseded.** The shipped scorer replaced this weighted sum of
> percentiles with a weighted geometric mean of six named signals, and the
> printed score with an absolute one. See [§11](#11-revision--what-the-scored-number-is-now)
> and `opradar/scoring.py`, which carry the current definitions. Kept here
> because the threshold measurements below are still the reason the
> current signals look the way they do.

Percentile-ranked within the eligible pool, then weighted.

**N1 — unmet demand (35)**
```
it_open_45 = count(posting_age_days > 45)
it_open_90 = count(posting_age_days > 90)
N1 = 0.6·pct(it_open_45) + 0.4·pct(it_open_90)
```

> **Thresholds are chosen by measurement, not convention.** Companies in the
> 327-company pool scoring zero on each candidate threshold:
>
> | threshold | companies at zero | share of pool |
> |---|---|---|
> | > 45 days | 113 | 35% |
> | > 90 days | 185 | 57% |
> | > 120 days | 196 | 60% |
>
> A threshold where most of the pool ties at zero cannot rank that pool. 45 days
> is the only candidate that separates a majority, so it carries the heavier
> weight; 90 days rides along at 0.4 to reward genuinely long-unfilled roles.
> 120 days was tested and dropped — it is barely more discriminating than 90.
>
> No claim is made here about German average time-to-hire. These thresholds are
> justified by how they behave on this pool, nothing else. Re-measure if the
> pool definition changes.

**N2 — seniority pressure (25)**
```
it_senior_n = count(seniority_derived ∈ {senior, lead})
N2 = 0.6·pct(it_senior_n) + 0.4·pct(it_senior_n / it_n)
```
Senior roles are hardest to hire and the strongest trigger for buying external
capacity. Discriminates independently of size: BWI shows 44 senior/lead of 52 IT
postings; shoob.de shows 0 of 29.

**N3 — coherence (20)**
```
HHI = Σ (share of tech_category)²   over postings where has_tech_signal
N3  = pct( HHI · min(1, it_n/5) · min(1, tech_covered_n/3) )
```
Nine SAP roles is a programme with a nameable pitch; nine scattered roles is
backfill. Two dampers because both counts are small.

> Damping is applied **before** the percentile, not after. Percentile-then-damp
> would leave N3 on a different scale from N1, N2 and N4 and quietly distort the
> weighted sum. Every Nᵢ must be a percentile over the same pool.

**N4 — momentum (20)**
```
N4 = pct( count(is_fresh_30d) / count(posting_age_days ≤ 180) )
```
Proves the company is *still* hiring rather than sitting on abandoned ads.

> N4 reduces dead-listing companies but does not eliminate them: a company
> scoring 0 on N4 still collects up to 35 points from N1, because old vacancies
> score highly on exactly the signal N1 measures. The **recency guard in §4.6 is
> what actually removes them.** shoob.de is the worked example — 29 IT postings,
> zero within 90 days, zero within 30, median age 466 days. It ranks near the top
> on unfilled demand and is excluded by the guard, not by N4.

**Context only, never scored:** `it_postings` (volume), `median_it_age_days`,
`p90_age_days`, `region_count`, competitor saturation.

> **Rejected: market scarcity per technology.** Measured median vacancy age by
> family: SAP 14d (lowest), web 30d (highest). That does not mean SAP is easy to
> fill — it means SAP ads are posted more recently and churn faster. One
> snapshot cannot separate "posted recently" from "filled quickly"; that needs
> two snapshots and a duration model. A second crawl from the live BA API is the
> single highest-value upgrade available.

**Normalisation.** Percentile rank *within the eligible pool*, computed strictly
after §3 — percentiles over a contaminated pool are meaningless. Percentiles
resist outliers, remove unit mismatches, and speak the user's language: "top 6%
for unfilled senior demand".

```
Need = Σ wᵢ·Nᵢ ,  Σwᵢ = 100
```

### 4.5 Confidence
```
evidence = min(1, it_n / 8)                       # 70 of 327 companies reach 8
recency  = 1.0 if any is_fresh_30d
           0.7 if any posting ≤ 90d
           0.4 otherwise
identity = 1.0 if name_variant_count = 1
           0.8 if merged variants and class_confidence high
           0.5 if in the review queue
corrob   = share of the company's IT postings where is_it_core agrees
                                                  # pool average 69.7%

Confidence = 0.40·evidence + 0.25·recency + 0.20·identity + 0.15·corrob
```

> **Caveat on `corrob`.** It rewards agreement between two independent signals,
> which is real information — but the disagreement is usually the *dataset's*
> fault, not the company's. A software house whose developer roles are miscoded
> under textiles gets a lower confidence for a defect it did not cause. Held at
> the lowest weight for that reason. Drop it entirely if it correlates with
> anything we care about.

Reported beside the score, never folded into it: *"81, confidence medium — 4
postings"*. More honest than shrinkage and far easier to defend than a number
that has been quietly pulled toward the mean.

### 4.6 Guardrails

- `it_n ≥ 3` → 327 companies
- **at least one posting within 90 days** → removes a further 30, leaving **297
  ranked companies**. This is the guard that eliminates abandoned listing sets;
  N4 alone does not (see N4 above).
- flag contradictory signals rather than averaging them away

### 4.7 Explanation

1. Build a deterministic template containing the real numbers.
2. The LLM **rewrites that template as prose**. It receives only computed facts.
   It never sees raw rows and never sources a claim.
3. Attach 3–8 evidence postings with their live `source_url`.

Any design where the model can invent a signal is disqualifying: one
hallucinated fact found on stage discredits every number on the screen.

---

## 5. Signal coverage — state these when presenting

Measured inside the ranked pool itself — 327 companies, 2,142 postings:

| signal | coverage | consequence |
|---|---|---|
| age (N1, N4) | 100% | reliable |
| `seniority_derived` ∈ {senior, lead} (N2) | 564 postings, **26.3%** | directional; report coverage |
| `has_tech_signal` (N3) | 1,130 postings, **52.8%** | HHI over half the evidence |
| `is_it_core` corroboration | 1,493 postings, **69.7%** | Confidence input only |

N1 and N4 carry near-complete coverage; N2 and N3 do not. If the sensitivity
check (§7) shows the top 20 moving under small weight changes, shift weight
toward N1 and N4 rather than tuning the thin signals.

`tech_categories` vocabulary and volumes: data 975, erp 611, language 537,
embedded 307, quality 277, cloud 253, security 245, backend 237, network 220,
devops 135, platform 135, frontend 85.

---

## 6. Pipelines B and C — People and Match

**Moved.** The people pipeline, the vocabulary bridge and the match formula now
live in **`ALGORITHM_PEOPLE.md`**, written against the candidate data actually in
the repo. This section keeps only the contract the two pipelines share.

### The shared vocabulary — the integration contract

Both sides must emit the same unit:

```
RoleAtom {
  role_family : dev | ops | data | security | qa | architect | analyst | support
  tech_tags   : subset of the tech_categories above
  seniority   : junior | mid | senior | lead
  region      : NUTS code
}
```

Demand: one posting → one RoleAtom. Supply: one candidate → one RoleAtom.

**`reference.py` is the single technology map. Neither pipeline may define a
second one** — that rule is the whole reason Pipeline C can be a join rather
than a research project. The candidate fixture currently in the repo breaks it:
7 of its 73 skills have a German equivalent, covering 3.3% of German IT
postings. `ALGORITHM_PEOPLE.md` §4 sets out the three ways to fix that and
recommends one.

Until the bridge lands, `Serviceability = 1.0` and the company ranking is driven
by Need alone.

---

## 7. Validation without ground truth

No labels exist, so accuracy is unavailable. Three checks that are honest and
demoable:

**V1 — divergence from volume, measured.** Spearman correlation between the
final ranking and `it_postings`. It must be **low**. If our top 20 is largely
the volume top 20 we have failed the brief's central constraint. Persist it and
put it on a slide: it turns "we don't rank by volume" from a claim into a number.

**V2 — adversarial.** No staffing agency, no IT service provider, no NTT entity
may appear in the prospect list. Each one that does is a named, countable defect.
Invite judges to hunt for one.

**V3 — sensitivity.** Perturb weights ±20%; check whether the top 20 holds. If
small changes reshuffle it, the weights are doing the work the signals should be
doing — and "why 35 and not 30?" becomes unanswerable on stage.

---

## 8. Code structure

Extends the existing package; nothing is restructured.

```
opradar/
  reference.py      lexicons, KldB maps, technology map      [exists]
  text.py           folding, legal forms, title cleaning     [exists]
  loading.py        raw ingest                               [exists]
  postings.py       MODIFY: add is_it_role, is_training_role
  companies.py      MODIFY: it_intensity from is_it_role
  classify_llm.py   NEW: review queues T1+T2, cached, temp 0
  signals.py        NEW: per-company IT-restricted aggregates
  scoring.py        NEW: percentiles, Need, Confidence, Opportunity
  validate.py       NEW: V1, V2, V3
  pipeline.py       MODIFY: wire the new stages
  report.py         extend: score decomposition
  ui.py             extend: decomposition + evidence links
```

### Rules

1. **Every stage reads a file and writes a file.** Any stage re-runnable alone —
   this is what makes debugging at hour 20 possible. The parser already does this.
2. **No tunable hardcoded.** Weights and thresholds in one config, hashed into
   the output so any result is reproducible.
3. **The UI never computes a score.** It reads the artifact. A broken pipeline
   run costs yesterday's data, not the demo.
4. **LLM calls cached to disk, temperature 0.** Two runs must produce the same
   leaderboard or the demo is a coin flip.
5. **`reference.py` is the shared vocabulary.** Neither pipeline defines a
   second technology map.
6. **Do not commit generated parquet.** `postings.parquet` (8.2 MB) and
   `companies.parquet` (1.7 MB) are currently tracked; `.gitignore` does not
   apply to already-tracked files. `git rm --cached data/processed/*.parquet`.
   Keep `parse_report.md` tracked — it is worth diffing between runs.

### Build order

```
is_it_role + is_training_role         ← unblocks everything; do first
        ↓
signals.py → scoring.py               ← artifact exists, demo possible
        ↓
classify_llm.py (T1+T2)               ← removes competitors from the top
        ↓
ui.py + report.py                     ← parallel, different owner
        ↓
validate.py                           ← V1 is a demo slide, not just a test
        ↓
people/ → match/                      ← only after Part 1 is shippable
```

Part 1 alone satisfies every minimum requirement in the challenge README. Parts 2
and 3 are the differentiator but are worth nothing if Part 1 is not demoable.
Cut Part 3 down, never Part 1.

---

## 9. Known limitations

1. **Single snapshot** — all postings crawled in one ~2h window on 2026-06-06.
   No true time series exists, so this system makes no hiring-velocity claim
   anywhere. Counting by `posted_date` measures vacancy survival, not demand.
2. **Survivorship bias** — older months contain only what is still unfilled.
   Hence counts of currently-open vacancies, never historical rates.
3. **One source** — 100% Bundesagentur für Arbeit. Companies that do not post
   there are invisible, likely biasing against startups and executive hiring.
4. **DACH is really DE** — 355 Austrian rows, 2 Swiss, of 70,543.
5. **No firmographics** — no revenue, headcount or industry. Size is proxied by
   posting volume, which is weak.
6. **No job description text** — `description_derived` is 100% null, so
   technology comes from titles alone: ~52% coverage inside the eligible pool.
7. **The dataset's own enrichment is unreliable** — ESCO labels are wrong at row
   level ("DevOps Engineer" → *knitting machine supervisor*), `esco_skills` is a
   fixed top-5 for 99.99% of rows, `seniority` is 88% unknown. None is used as
   ground truth.
8. **Entity resolution is approximate.** Explicitly permitted by the README.
9. **Abandoned listings** — a very old posting may be neglected rather than
   unfilled. Mitigated by N4 and the recency guard, not eliminated.
10. **Language requirement invisible** — a German-mandatory role is harder to
    serve from Lithuania, and titles do not reveal it.
11. **Regional counts reflect crawl coverage** as much as labour demand
    (parser's own caveat). Normalise before any regional comparison.

---

## 10. Open questions

| # | Question | Blocks |
|---|---|---|
| Q1 | Competitors — partner list, or plain exclusion? | §3 output shape |
| Q2 | May we call the live BA API? Enables a second snapshot → real duration analysis, and full description text | N-signal upgrade, stretch goal |
| Q3 | LITIT's actual delivery stack | turns "hiring IT" into "hiring OUR stack" |
| Q4 | People dataset — bench, or open candidate pool? | Pipeline B semantics |
| Q5 | Judging rubric weightings | effort allocation |

---

## 11. Revision — what the scored number is now

> **§4.4 above describes a superseded model.** The shipped scorer replaced the
> weighted sum of percentiles (N1..N4) with a weighted **geometric** mean of six
> named signals; `opradar/scoring.py` and `opradar/config.py` carry the current
> definitions and every justification. This section records the last change to
> what the number *means*, because that is the part a reader is most likely to
> quote.

### 11.1 The score is absolute, and 100 is unreachable

`opportunity` used to be a percentile of the pool. Three things were wrong with
that, all measured on the 142-company pool:

| symptom | measurement |
|---|---|
| the head printed 100 whatever it scored | the best company reached **0.46** of the model's own maximum |
| the spacing was uniform, the reality was not | rank 1→2 is a **7.1%** drop in `pressure`; rank 20→21 is **0.2%**; both printed 0.7 points |
| a company's score moved when an unrelated company joined the pool | by construction |

Every effective signal lives in `[log_floor, 1]`, so their weighted geometric
mean `pressure` does too, and both ends are meanings: the floor is a company
that fails every dimension as hard as the model allows, `1.0` is one that maxes
all six at once. The score is the position between them, on the log scale the
model actually multiplies in:

```
opportunity = 100 · (1 + ln(pressure) / −ln(log_floor))
```

**Nobody can reach 100, and it is not capped.** `unmet`, `seniority` and
`programme` are geometric means of saturating terms and `expansion` is a
logistic; all four approach 1 without arriving, so `pressure = 1` describes no
finite company. On the shipped pool the board runs **30.8 – 86.6**. A company at
the bottom of it is still not the worst company the model can imagine, and
saying so is the point. `percentile` keeps the pool-relative reading beside the
score, correctly labelled.

The six `points_*` columns decompose it: each signal's weight **is** its point
budget (unmet 27, programme 20, serviceability 16, expansion 14, seniority 13,
dealsize 10), and each awards the share of its budget equal to its own position
on the same scale. They sum to `opportunity` exactly.

### 11.2 A signal built from several legs is a geometric mean too

The file argues at the top that a conjunction must be a geometric mean rather
than a raw product, so that requiring every dimension to be non-trivial does not
also collapse the scale. The signals were not obeying it internally:

| signal | pool max, before | after |
|---|---|---|
| `programme` = burst × concentration × shape | **0.211** | 0.595 |
| `unmet` = rate × magnitude | 0.867 | 0.931 |
| `seniority` = rate × magnitude | 0.919 | 0.959 |

A signal whose maximum is 0.211 cannot spend a 0.20 weight. Measured share of
the ranking's variance: `programme` **2.5%** before, against `serviceability`'s
37.5% — the second-heaviest stated weight was deciding a fortieth of the board.

### 11.3 Two things the model was scoring that were not about the company

**The absence of a burst.** Two of S3's three legs carried a floor, stated as
"keep the three-way product from zeroing on one weak leg". The burst leg had
none, so a company whose largest 21-day cluster was two roles — ordinary
scattered backfill — was scored exactly as hard as a company with no demand at
all. It now has the same floor as the concentration leg. A shape claim also
needs enough advertisements to be a claim: with three ads in hand the largest
possible cluster is three, so `programme`'s evidence weight is now the weaker of
its stack coverage and `it_n / 8`.

> [measured] Schwarz Digits — 3 ads in the June crawl, **85** IT roles on the
> board today and **79** of them open past a month, the highest unmet-demand
> score in the pool — scored 0 on `programme` because two of its three ads
> landed in the same window.

**The age of our own crawl.** Both bench signals were computed over vacancies
still live, and scored 0 when none survived. That floored **77 companies** on
0.26 of the total weight — and it is one fact counted twice: r(log
serviceability, log dealsize) = **0.88**, and the same 79 rows were floored on
both. 48 of those 77 have IT roles open on today's board; the board reports
counts, not roles, so it cannot say what they are. That is missing evidence.

> [measured] Deutsche Telekom — **37** IT roles open today, **32** of them open
> past a month — sat at rank 42. The top 40 contained *no* company whose ads had
> aged out, which made a 0.26-weight signal behave as a hard gate.

**Serviceability** now falls back to the same arithmetic over the vacancies we
do hold. **Dealsize does not**, and the split is measured rather than argued:
serviceability is a *rate* and survives its ads expiring (June sits +0.004 from
the live reading over the 65 paired companies, and is the higher of the two on
only 23 of them); dealsize is a *count* and does not (+0.268, because June still
contains every role since filled). Carrying the count would credit the size of a
deal that no longer exists, so it is left unobserved and the pool prior stands
in for it.

How far to trust the rate is **fitted at run time**, not chosen — the textbook
shrinkage weight `var(signal) / (var(signal) + var(noise))`, estimated on the
companies carrying both readings, exactly as the Beta priors above are fitted.
It comes out at **0.79** on this pool. The 0.5 that had been copied from S1's
proxy was wrong in the direction that matters: June's rate has a mean absolute
error of 0.065 against the pool prior's 0.163, so shrinking halfway to the prior
threw away the better estimate in favour of one that happens to sit high — which
flattered exactly the companies we can see least. Raising the weight to its
fitted value *demotes* them.

Confidence was also blind to all this. Its observability term listed only the
four market signals, from when the two bench evidence weights were the constant
1.0; it now covers all six, weighted by how much of the score each carries.

### 11.4 What it did to the board

| check | before | after |
|---|---|---|
| rows printing 100 | 1 | **0** |
| Spearman(score, `it_n`) — V1 divergence, lower is better | 0.414 | **0.324** |
| Spearman(score, roles open past a month on the board) | — | **0.910** |
| companies floored on both bench signals | 79 | **2** (both with live roles we genuinely cannot cover) |
| V3 weight-perturbation overlap @20 | 19/20 | 18/20 |
| V4 jackknife overlap @20 | 16/20 | 16/20 |

The ranking became *less* correlated with raw ad volume and much more correlated
with the board's own count of roles open past a month, which is what the product
claims to rank on.

### 11.5 What a signal is allowed to decide

A weight is an elasticity, not a share of the outcome — a signal only moves the
board over the range it actually varies. Measured across the pool:

| signal | budget | awards | why |
|---|---:|---|---|
| `unmet` | 27 | 0.0 – 26.4 | 44 companies have nothing open past a month; the definitional gate does its job |
| `serviceability` | 16 | 0.0 – 16.0 | two companies have live roles we cannot cover |
| `dealsize` | 10 | 0.0 – 10.0 | |
| `programme` | 20 | 10.4 – 16.5 | only measurable on companies with enough ads; quiet elsewhere by design |
| `expansion` | 14 | 7.7 – 13.1 | standardised against the pool's own median change, most companies **are** at parity |
| `seniority` | 13 | 8.8 – 12.8 | observed on 24% of postings, so mostly shrunk to the prior |

Among the 98 companies that clear the unmet gate — the ranking that actually
matters — the shares are `unmet` 60%, `dealsize` 18%, `serviceability` 15%,
`programme` 4%, `seniority` 2%, `expansion` 1%.
