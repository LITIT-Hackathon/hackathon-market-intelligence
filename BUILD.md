# Opportunity Radar — What We're Building

> Short version. Evidence, data profiling and API details in [RESEARCH.md](RESEARCH.md).
> **Framing (confirmed): a recruiter / staffing-side tool.** We analyse the job market from the
> *people* angle — which profiles are in demand, which are scarce, which are contested — and then
> rank the opportunities our candidates can actually be placed into.

---

## 1. The product in one paragraph

A radar for a **staffing / recruitment business**. It reads the open job market, works out where
demand is real and talent is thin, measures **how many rival agencies are already chasing each
lane**, and produces two things: a **market picture** of where to aim, and a **ranked list of
opportunities** matched to specific candidate profiles — each with the postings that prove it.

The question it answers:
> *"Which mandates are worth chasing, which of our people can fill them, and who else is competing?"*

---

## 2. Three layers, one pipeline

| Layer | Unit | Question | Output |
| --- | --- | --- | --- |
| **1. Market** | role × skill × seniority × region *cell* | Where is demand real, talent scarce, competition thin? | **Lane score** |
| **2. Opportunity** | company | Which companies have mandates we could win *and fill*? | **Opportunity score** |
| **3. Match** | candidate × posting | Which of our people fit, and would they rank well? | **Placeability score** |

Layer 2 is the headline deliverable. Layer 1 explains *why* it's ranked that way. Layer 3 is the
proof we can actually deliver. They share one pipeline and one vocabulary.

---

## 3. Three ideas that make this work with only job-posting data

**1. A candidate profile is a job posting with the arrow reversed.**
Same schema on both sides — skills, occupation code, seniority, region, remote-OK. So matching is
symmetric over one shared vocabulary, we need no second data model, and demo profiles can be
bootstrapped by sampling real postings. *This is why "we have no candidate database" is not a
blocker.*

**2. Scarcity is measurable from the demand side.**
We can't observe people, but we can observe **failure to hire**. A role open five months, reposted
twice, with loosening requirements, *is* a measurement of how few of those people exist.
**Time-on-market is a supply signal wearing a demand-side costume.**

**3. Competition is directly observable — and it's our differentiator.**
Staffing agencies post into this market too, and they're identifiable (name patterns plus official
temp-work / placement-agency flags on the source data). So for any lane we can count how many
distinct rivals are chasing it. Everyone else will treat agencies as noise to delete. We treat them
as the competitive-intelligence layer.

```
Lane score = Demand × Scarcity × (1 − Agency saturation)
```

| Demand | Scarcity | Saturation | Verdict |
| --- | --- | --- | --- |
| high | high | **low** | **Open lane — go here** |
| high | high | high | Hard and crowded — only with a differentiated bench |
| high | low | high | Commodity grinder — avoid |
| low | high | low | Niche — worth it only if we already have the person |

---

## 4. The core loop

```
   1. INGEST     dataset for development; live market feed for the real thing
   2. NORMALISE  role taxonomy, seniority, region, skills → one vocabulary
   3. CLASSIFY   end client / IT provider / staffing agency / public / noise
   4. CELL-UP    aggregate into role × seniority × region cells
   5. MEASURE    demand · scarcity · saturation · trend        → Lane score
   6. ROLL-UP    cells → companies with winnable mandates      → Opportunity score
   7. MATCH      candidate profiles × open postings            → Placeability score
   8. EXPLAIN    LLM narrative, grounded in cited postings
   9. SERVE      market dashboard + matcher + export + alerts
```

Step 3 is load-bearing in **both** directions now: agencies are excluded from "who can we sell to"
*and* counted as "who are we competing with." Same classification, two uses.

---

## 5. What we must build (MVP)

| # | Thing | Why |
| --- | --- | --- |
| 1 | **Ingest + normalise** into one posting schema | Everything downstream depends on it |
| 2 | **Role / skill / seniority taxonomy** | The shared vocabulary both sides match on. Non-negotiable — it's the join key of the whole product |
| 3 | **Company classification** | Client vs competitor. Feeds both the opportunity list and the saturation metric |
| 4 | **Market cells + Lane score** | Demand, scarcity, saturation per cell |
| 5 | **Opportunity score per company** | The headline deliverable |
| 6 | **Candidate profile input + matcher** | Even with hand-entered profiles — the matcher must exist |
| 7 | **Grounded explanations** | Every claim cites specific postings, clickable |
| 8 | **Two-tab dashboard** | Market view + matcher, sharing state |
| 9 | **Export** (CSV/JSON) | So it can leave the screen |

## 6. Should have (cheap, high impact)

- **Tunable weights** — sliders that re-rank live. Answers "why is this #3?" better than any prose.
- **Reverse matcher** — pick a hot lane, get a **sourcing brief**: "go find 4 of these people."
- **Open-lane report** — the single most useful screen for a recruiting manager: high demand,
  high scarcity, low competition, ranked.
- **Baseline comparison** — our ranking vs a naive "most vacancies" ranking, with named movers and
  reasons. The most convincing artefact you can produce.
- **Negative controls** — prove that saturated commodity lanes and training providers rank *low*.
- **Live trend** — which lanes are heating up week over week.

## 7. Nice to have

Skill co-occurrence graph ("who asks for X also asks for Y" → adjacent placements) · salary/price
signal per lane · "candidates like this one" clustering · geographic supply-vs-demand gap map ·
scheduled monitoring with alerts · confidence intervals rather than point scores.

## 8. Do NOT build

Automated outreach · CRM write-back · full-web crawling · **scraping personal profiles or CVs from
the web** (personal data, no legitimate-interest story, actively litigated) · a custom-trained
model (no labels) · auth/multi-tenancy · perfect entity resolution.

---

## 9. The scores

### Lane score (market layer)
```
Lane = Demand^0.5  ×  Scarcity  ×  (1 − Saturation)  ×  Trend
```
- **Demand** — open postings in the cell, log-scaled
- **Scarcity** — median days open, share open >90 days, repost rate
- **Saturation** — agency postings ÷ total postings; distinct competing agencies
- **Trend** — new-in-7d vs new-in-28d rate

### Opportunity score (company layer — the headline)
```
Opportunity = (0.30·Demand + 0.30·Unfilled + 0.20·Fillability + 0.20·Uncontested) × Confidence
```
- **Demand** — volume and concentration of their open roles
- **Unfilled** — how long their roles have been sitting → they need help
- **Fillability** — **do we have candidates who match?** ← the layer-3 feedback that makes this
  better than a generic lead list
- **Uncontested** — how few agencies are already working this account
- **Confidence** — evidence volume, entity certainty, taxonomy match quality

### Placeability score (match layer)
```
Placeability = Fit × Scarcity × (1 − Competition) × Freshness × Accessibility
```
- **Fit** — skill and seniority overlap, profile ↔ posting
- **Scarcity** — how few comparable people exist *(this is what makes them rank well, not just qualify)*
- **Competition** — how many agencies are chasing this exact role
- **Freshness** — recently posted, still open
- **Accessibility** — remote-friendly, contract type, location, language

**The insight the whole product rests on:** you place people where demand is high and comparable
supply is thin. A perfect-fit role with 400 applicants is worth less than an 80%-fit role with 4.

**Three implementation rules that matter more than the weights:**
- **Log-scale every count**, or the largest employer wins everything and you've rebuilt a vacancy
  counter with extra steps.
- **Rank within peer group** (comparable cell size), not globally.
- **Multiply by confidence, don't filter on it.** Thin-evidence rows rank lower with a visible
  badge; they don't silently vanish.

---

## 10. Where the LLM goes

**Use it for:**
- Reading job text → structured `{skills, technologies, seniority, must-have vs nice-to-have, contract shape}`
- **Semantic matching** where the taxonomy fails — "Fachinformatiker Systemintegration" ≈ "IT Systems Administrator"
- Classifying company type from name + role mix
- Writing the narrative: why this lane, why this company, why this candidate
- Generating the sourcing brief for the reverse matcher

**Never for:** producing a score, aggregating counts, or anything you'd have to re-run to reproduce
a number on stage.

**Grounding rules — this is what makes it defensible:**
- Every claim cites posting IDs, rendered as links to the live posting.
- Closed-world prompt: *"use only the postings provided; say 'insufficient evidence' otherwise; do
  not infer company size, revenue, headcount, or unlisted technologies."*
- Structured output (JSON schema) so parsing never fails.
- **Post-validate** — check every cited posting exists and belongs to that company, and every named
  skill actually appears in the cited text. Drop unsupported claims. Cheap string matching, and it
  turns "we used AI" into "we used AI and verified it."
- Cache by content hash. You'll re-run 20 times; pay once, and keep the demo working offline.

---

## 11. Architecture

```
ingest (dataset now, live feed for production)
   └→ normalised postings (one schema, one vocabulary)
        └→ classify companies  ─────────────┐
             └→ market cells                │ same classification
                  └→ lane scores            │ feeds saturation
                       └→ company roll-up ◄─┘
                            └→ candidate matcher (profiles × postings)
                                 └→ explain (LLM, grounded + validated)
                                      └→ market tab · matcher tab · export
```

**Stack: keep it boring.** This is a laptop-scale problem.

- **DuckDB over parquet** for storage and compute
- **One numbered Python script per stage**, parquet between stages — idempotent, so you can re-run
  stage 6 without re-doing stage 1
- **Gemini Flash**, structured output, batched
- **FastAPI** + **Streamlit** (fast) or Next.js (prettier, riskier — only if someone owns it)
- **Disk cache keyed by content hash** — non-negotiable
- **Ship a static JSON fallback** of the final results. If the venue wifi dies, the demo must still
  render. This has saved more demos than any architectural decision.

**Core tables:** `postings` · `companies` (with class) · `cells` (role × seniority × region, with
demand/scarcity/saturation) · `profiles` (candidates — same schema as postings) · `matches`
(profile × posting) · `opportunities` (scored company output, with `weights_version`).

---

## 12. Design rules

1. **Never infer trends from posting dates in a single snapshot.** A snapshot only holds roles still
   *open* — the old ones are missing because they got **filled**. The resulting "growth curve" is
   survivorship bias and it points the wrong way. Trends come from repeated pulls or an explicit
   "posted in last N days" filter. Nothing else.
2. **Long-open roles mean two different things — say which.** For scarcity: hard to fill. For
   opportunity: an easy mandate to win, but a hard one to deliver. Don't let one number carry both
   meanings silently.
3. **Days-open in a snapshot is length-biased.** You oversample long-lived postings by construction.
   Fine for *ranking cells against each other*; wrong as an absolute "average time to fill."
4. **Agencies are competitors, not noise.** Classify them, don't delete them. Their postings are the
   saturation signal.
5. **Job titles barely mention technology.** Real skill signal needs the job description text.
   Budget for it.
6. **Word-boundary regex, always.** Naive substring matching finds "AI" and "KI" inside hundreds of
   German words and will have you reporting a boom that doesn't exist.
7. **Normalise regional counts.** Crawl coverage is uneven by region; raw regional heatmaps are
   artefacts, not market facts.
8. **The auto-assigned skill/occupation tags are noisy.** Cross-check against the official
   occupation code and the title before trusting them — see RESEARCH.md §3.4.
9. **Report measured error rates, not claims.** "Matcher precision 0.84 on a 50-pair audit" beats
   "our matching works," every time.
10. **We handle candidate data — that's personal data.** Anonymise anything shown on screen, keep it
    local, and say on slide 1 that we do not scrape personal profiles.

---

## 13. How we prove it works

1. **Hand-audit the top 25 opportunities.** "Would a recruiter chase this?" Report the hit rate
   honestly — 20/25 with 5 explained misses is more credible than a claim of perfection.
2. **Hand-audit 50 matches.** "Would you put this CV forward for this role?" → matcher precision.
3. **Negative controls.** Saturated commodity lanes, training providers and one-role employers must
   rank low. A real, checkable correctness test that costs nothing.
4. **Ablation.** Remove each signal; show how the top 20 moves. Proves nothing is decoration.
5. **Baseline.** Rank correlation vs a naive vacancy-count ranking, with 3 named movers and the
   reason each moved.

---

## 14. Build order

| Order | Build | Note |
| --- | --- | --- |
| 0 | **Agree the taxonomy and schema** | Both sides match on it — get it wrong and everything downstream is wrong |
| 1 | Ingest + normalise | |
| 2 | Company classification | Feeds opportunities *and* saturation |
| 3 | Market cells + lane scores | First demoable artefact — **the market tab can ship alone** |
| 4 | Company opportunity scores | The headline deliverable |
| 5 | Profile input + matcher | Start with exact taxonomy match; add semantic matching after |
| 6 | LLM enrichment (skills from job text) | **First thing to cut if time runs out** |
| 7 | Explanations | Template fallback if the LLM stage is cut |
| 8 | Dashboard + export | Build against fixtures from step 1 — never let the UI wait on the pipeline. A read-only viewer of the parsed data already exists (`python -m opradar.ui`); the scored screens go on top of it |
| 9 | Evaluation + baseline | Don't skip — it's the most convincing part |

**Freeze the schema early** and have the frontend build against fixture data immediately.

**The cut line:** if there's no end-to-end path from ingest → ranked list → dashboard by the
two-thirds mark, cut LLM enrichment and semantic matching entirely. Ship taxonomy matching +
deterministic scoring + template explanations. A complete simple system demos far better than a
sophisticated broken one.

---

## 15. The demo

**Narrative, 5 minutes:**

1. *"Where should our recruiters aim next month?"* → **Market tab.** Open lanes: high demand, thin
   talent, few competitors. Name one.
2. *"Who in that lane has mandates we could win?"* → **Opportunity list.** Click a company → score
   breakdown → the actual postings.
3. *"Can we fill it?"* → **Matcher.** Load a profile → ranked placeable roles with reasons.
4. Move a weight slider, re-rank live.
5. *"And here's who we'd be competing against"* → the saturation view.
6. Limitations, honestly. 30 seconds. It buys more credibility than it costs.

**The moment that wins it:** clicking from a score, through the signals, to a real job posting that
a judge can open in a browser tab.

---

*Job posting data © Bundesagentur für Arbeit, CC-BY-4.0 — attribution required in the UI.*
