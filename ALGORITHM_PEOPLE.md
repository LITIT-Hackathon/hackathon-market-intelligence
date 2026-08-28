# OpRadar — People Algorithm (Pipeline B)

**v1, 2026-08-28.** Companion to `ALGORITHM.md` (companies / Pipeline A).
Read that first — the spine, the RoleAtom vocabulary and the scoring
conventions are defined there and are not repeated here.

Measured against `data/processed/candidates.parquet`,
`openings.parquet`, `skill_market.parquet`, `role_market.parquet`
(source: `michaelozon/candidate-matching-synthetic`, MIT).
The dataset audit in §2–§3 largely confirms `opradar/candidates.py`'s own
report; where this document adds numbers, they were re-measured.

---

## 0. The one thing to understand first

The two pipelines have **opposite problems**.

| | Pipeline A (companies) | Pipeline B (people) |
|---|---|---|
| data | real, messy, contaminated | clean, synthetic, near-uniform |
| difficulty | finding signal buried in noise | **there is no signal to find** |
| work | filtering, classification, entity resolution | building a bridge and a real bench |

On the company side the algorithm had to dig a real signal out of dirty data.
On the people side the data is tidy and means nothing: it is a **fixture for
building the matcher**, not a measurement of any talent market. Every design
choice below follows from that.

---

## 1. What Pipeline B is for

Two distinct jobs. Do not conflate them.

**Job 1 — the supply index.** Per RoleAtom cell: how deep is the bench, how
senior, how soon available. This is the only object Pipeline C needs, and it is
what turns `Serviceability` from a placeholder 1.0 into a real number.

**Job 2 — candidate ranking.** "Who should we have on the bench?"

```
Value(candidate) = MarketPull × Scarcity × Deployability
```

deliberately mirroring `Opportunity = Need × Serviceability × Confidence`.

Job 2 is what closes the product loop: Pipeline A says which German companies
have unfilled demand, Pipeline B says which people to hire so that demand can
actually be served. A sales lead you cannot staff is not a lead.

---

## 2. Dataset ground truth

| | |
|---|---|
| candidates | **10,000** — of which **2,949** in tech roles |
| openings | **2,500** — of which **728** tech |
| skill vocabulary | **73** |
| roles | **24**, of which **7** are tech |
| tech role × seniority cells | 21, sizes **119–168** |
| skills per candidate | 6.49 (range 5–8) |
| must-have skills per opening | 3–5 (mean 4.0), plus ~1 nice-to-have |

The 7 tech roles: Backend Engineer 456, Software Engineer 432, BI Analyst 426,
Full Stack Engineer 423, Technical Support Specialist 414, Data Analyst 404,
Technical Product Manager 394.

Distributions are uniform by construction — tech seniority splits
junior 967 / mid 1,002 / senior 980; ten industries at ~10% each.

---

## 3. Red flags

**3.1 It does not join to the German data.**
7 of 73 skills have a German equivalent (CI/CD, Docker, Java, JavaScript,
Power BI, Python, SQL), and those appear in **3.3%** of German IT postings.
Absent entirely: SAP, Cloud, Security, Embedded, Data Engineering, AI/ML,
Network — i.e. every category that carries German demand.

**3.2 The tension metrics are noise on this data.**
Skill tension spans **0.85–1.18**; role×seniority tension **0.50–1.56** over 72
cells. On a real market expect 0.2–5. A ranking built on a spread that narrow is
fabricated discrimination.

**3.3 The matching is far too loose.**
Each opening qualifies a mean of **866 candidates** (8.7% of the bench, range
643–1,436); each candidate qualifies for a mean of 217 of 2,500 openings. With a
73-skill vocabulary, 5–8 skills per profile and 3–5 must-haves per opening,
almost everyone matches almost everything.

**3.4 The shipped "ground truth" is not ground truth.**
75,000 labelled pairs, exactly 30 per opening, covering **3.5%** of the qualified
pool. Label seniority agrees with the opening's seniority **33.6%** of the time
against a ~33% random baseline — seniority is ignored entirely. Role agreement is
33.2% against a ~4% baseline, so role does carry signal.

> **Never report retrieval precision against these labels.** They are an
> arbitrary slice of a much larger correct set, so unlabelled right answers are
> everywhere and any honest matcher scores badly. This is `candidates.py`'s
> own conclusion and it is correct.

**3.5 Fields a matcher needs are absent.**
No location, no availability, no languages, no cost. `industry_domain` is
**49.6% null**. Nothing here supports a realistic staffing decision.

**3.6 Current demand is measured against the wrong universe.**
`skill_market` and `role_market` compute supply and demand *both* from the
synthetic dataset — 10,000 candidates against 2,500 synthetic openings. That is
a closed loop. It says nothing about Germany, and its output cannot feed
`Serviceability` for any real company.

---

## 4. The bridge — the make-or-break stage

The company pipeline's decisive stage was classification. Pipeline B's is the
**vocabulary bridge**. Everything downstream is arithmetic; this is the part
that can quietly make the product meaningless.

Two vocabularies that do not meet: 73 candidate skills against the German side's
13 `tech_categories`; 7 tech roles at 3 seniorities (21 cells) against 13
categories at 4 seniorities (52 cells).

| | approach | cost | verdict |
|---|---|---|---|
| B1 | hand-map 73 skills → 13 tech categories | ~1h | lossy — only 7 map cleanly, the rest go through family guesses |
| B2 | join at role level only | minutes | works today, very coarse; ignores skills entirely |
| B3 | **regenerate the bench in the German vocabulary** | ~half a day | **recommended** — join exact by construction |

**B3 in detail.** The bench is synthetic either way, so generate it from
`reference.py`'s technology map instead of an unrelated 73-skill vocabulary.
Every candidate then carries `tech_categories` values that already exist on the
demand side, and Pipeline C becomes a join rather than a research project.

> **The trap in B3.** Do **not** sample supply from the demand distribution. A
> bench that mirrors German demand matches everything perfectly and the product
> has nothing to say. Define a **bench profile** — what LITIT is actually good at
> — that deliberately differs from demand. The gap between the two is the entire
> insight the product exists to surface.

B2 is the fallback if time runs out: it produces a working, honest, coarse match.
B1 is the worst of both — real effort for a lossy result.

---

## 5. The cascade

**P0 — Ingest & validate.** Reject any profile that cannot produce a RoleAtom.
Do not filter on `industry_domain` (49.6% null).

**P1 — Normalise to RoleAtom.** Same structure as the demand side:
`role_family`, `tech_tags`, `seniority`, `region`. Restrict to `is_tech_role`
→ **2,949 candidates, 728 openings**. The other 7,051 are marketing, sales and
finance profiles, irrelevant to an IT consultancy.

**P2 — Bridge** (§4). Emit `tech_tags` drawn from the demand-side vocabulary.

**P3 — Supply index.** Per RoleAtom cell:
```
depth        = candidates in cell
seniority_mix= junior / mid / senior / lead split
readiness    = share available now vs within 90d
```
This is the hand-off object for Pipeline C.

**P4 — Market pull.** Computed from **the real German postings** — the 4,168
eligible IT postings from Pipeline A — **not** the 2,500 synthetic openings.
Reuse N1: unfilled demand (vacancies open past 45 / 90 days) aggregated per
RoleAtom cell. This is the correction to §3.6 and the single most important
change to what is currently built.

**P5 — Scoring.** All components percentile-ranked within the tech pool:
```
MarketPull    = pct(German unfilled demand for this cell)        ← real data
Scarcity      = pct(1 / bench depth for this cell)
Deployability = 0.5·pct(seniority) + 0.3·readiness + 0.2·pct(skill breadth)

Value = MarketPull × Scarcity × Deployability
```
Multiplicative for the same reason as Pipeline A: a candidate nobody wants, or
one we have forty of, is not valuable regardless of how good the other two
factors look.

**P6 — Guardrails.** Suppress cells below ~5 candidates rather than ranking them
— scarcity is `1/depth` and explodes on thin cells.

> On *this* fixture the guardrail never fires: the 21 tech cells hold 119–168
> candidates each. It matters for a **real** bench: LITIT at ~100 specialists
> spread over 21+ cells averages ~5 per cell, which is exactly where `1/depth`
> becomes unstable. Build the guard now; it is dead code today and load-bearing
> the moment real data arrives.

**P7 — Explanation.** Deterministic template first; the LLM only rewrites it as
prose and never sources a fact. Identical discipline to Pipeline A §4.7.

---

## 6. Pipeline C — the join

```
for each demand atom d of company C:
    coverage(d) = 1 if ≥1 candidate matches (role_family,
                       tech_tags ∩ ≠ ∅, seniority ≥ d.seniority − 1)
                  partial credit for adjacent seniority
    depth(d)    = min(1, matching_candidates / 3)

Serviceability(C) = Σ wᵈ·(0.7·coverage(d) + 0.3·depth(d)) / Σ wᵈ
```
`wᵈ` weights each demand atom by its own N1 contribution — an unfilled senior
role we can staff matters far more than a junior role we cannot.

Sales output: *"Siemens Energy has 11 IT roles open past 90 days, 3 senior,
concentrated in data. We have 5 matching data engineers free within 30 days."*

---

## 7. Validation

Mirrors Pipeline A §7.

**V1 — divergence.** Rank correlation between candidate Value and raw
`skill_count` must be **low**. "Most skills wins" is the people-side equivalent
of ranking companies by vacancy volume, and it is equally wrong.

**V2 — adversarial.** No non-tech candidate may appear in an IT supply cell. No
supply cell may claim depth for a `tech_tag` that no candidate actually holds.

**V3 — sensitivity.** Perturb weights ±20%; the top 20 should hold.

**V4 — prohibition.** No precision/recall claim against the dataset's shipped
labels, for the reason in §3.4. If a retrieval metric is needed for the demo,
state it against a hand-checked sample instead and say the sample size.

---

## 8. What a real bench record must carry

The B3 generator should emit these; the current dataset has none of them.

```
Candidate {
  candidate_id, role_atom, years_experience
  region + remote_ok      — where they can work
  availability            — now | 30d | 90d | unavailable
  languages               — German capability is a hard nearshore constraint
  cost_band               — optional; it is what makes an opportunity real
  source                  — synthetic | consented     ← MUST be labelled in the UI
}
```

**Two constraints.** Synthetic candidates must be visibly labelled synthetic on
screen — a judge who suspects generated people are being presented as real
applicants discounts every other number in the demo. And if real candidate data
is ever introduced, it is EU personal data: consented only, and say so on the
limitations slide.

---

## 9. Code structure

```
opradar/
  candidates.py       [exists] ingest + normalise the synthetic fixture
  bench_gen.py        NEW  B3 generator — bench in the German vocabulary
  supply.py           NEW  P3 supply index
  market_pull.py      NEW  P4 demand per RoleAtom, from German postings
  people_scoring.py   NEW  P5 Value = MarketPull × Scarcity × Deployability
  match.py            NEW  Pipeline C, Serviceability per company
  validate.py         extend with V1–V4
```

`reference.py` stays the single shared vocabulary. Neither pipeline may define a
second technology map — that rule is what makes Pipeline C a join.

### Build order

```
bench_gen.py (B3)              ← unblocks everything; B2 fallback if time is short
      ↓
supply.py → market_pull.py     ← needs Pipeline A's eligible postings
      ↓
people_scoring.py              ← candidate ranking, demoable alone
      ↓
match.py                       ← Serviceability enters the company score
```

Pipeline A must be shippable before any of this starts. Pipeline B and C are the
differentiator; they are worth nothing if Part 1 is not finished.

---

## 10. Known limitations

1. **The supply data is synthetic and near-uniform.** Nothing here measures a
   real talent market. Say so on screen and on the slide.
2. **Skill vocabularies do not currently join** — 7 of 73, covering 3.3% of
   German IT postings (§3.1). Until B3 or B2 lands, `Serviceability` is a
   placeholder.
3. **Current tension metrics are a closed loop** — synthetic supply against
   synthetic demand (§3.6). They must be recomputed against German postings.
4. **The shipped labels cannot validate anything** (§3.4).
5. **No location, availability, language or cost** in the source data (§3.5).
6. **Seniority granularity mismatch** — 3 levels on the supply side, 4 on the
   demand side. Map explicitly; do not let it happen implicitly.
7. **`industry_domain` is 49.6% null** and its ten values are synthetic
   categories that do not correspond to the German companies' actual sectors.

---

## 11. Open questions

| # | Question | Blocks |
|---|---|---|
| P1 | Bench or open candidate market? Bench = we sell delivery capacity; market = we place people, which makes us a competitor to the agencies Pipeline A filters out | the meaning of Value, and of Serviceability |
| P2 | B3 or B2 — regenerate the bench, or accept a coarse role-level join? | §4, and the whole Pipeline C timeline |
| P3 | LITIT's real delivery stack — needed to define the bench profile in B3 without mirroring demand | §4 trap |
| P4 | Realistic bench size? 100 specialists behaves very differently from 10,000 | §6 guardrail |
