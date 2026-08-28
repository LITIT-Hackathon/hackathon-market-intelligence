# Opportunity Radar — Research, Architecture & Build Plan

> Working research document for the LITIT hackathon challenge in [README.md](README.md).
> Everything marked **[measured]** was verified by me directly against the actual dataset
> and the live Bundesagentur API on 2026-08-28. Everything marked **[researched]** comes
> from web sources listed in Appendix C.

---

## ⚠️ Framing update — read this first

This document was written for an earlier framing: *a nearshore IT vendor looking for German
clients*. **The confirmed framing is now a recruiter / staffing-side tool** — see
[BUILD.md](BUILD.md) for the current product definition.

**All measured evidence below remains valid.** The data profiling, the API findings and the traps
are facts about the data, not about the framing. What changes is what you *do* with them:

| Section | Status under the new framing |
| --- | --- |
| §2 What the data is · §3 The five traps · §4 Data strategy · App. A/B/C | **Fully valid.** Unchanged. |
| §3.2 Staffing agencies | **Re-read with the opposite sign.** Agencies are no longer noise to remove — they are the **competition signal**. Classification still essential; its purpose flips. |
| §3.5 No tech in titles · §3.4 Noisy ESCO | **More important now,** not less. These are the matching vocabulary; their noise is now a matching-quality problem, not just a reporting one. |
| §3.1 Survivorship bias | **Still bites, identically** — plus a new nuance: days-open in a snapshot is *length-biased*. Fine for ranking cells against each other; wrong as an absolute time-to-fill. |
| §1 Who is the customer · §5 Signal taxonomy · §6 Classification · §7 Scoring · §13 Demo | **Superseded by BUILD.md.** The unit of analysis moved from *company* to *role × skill × seniority × region cell*, and scoring gained a matcher layer. |
| §8 LLM usage · §10 Must/should/nice · §11 Difficulty · §12 Evaluation · §15 Limitations | **Directionally valid;** BUILD.md carries the current version. |

**One addition the new framing makes possible, which nothing below covers:** because staffing
agencies are present and identifiable in this data, **rival competition per lane is directly
measurable**. That is the product's main differentiator and it exists precisely *because* of the
data-quality problem described in §3.2.

---

## 0. TL;DR — the thesis

**The provided dataset is a snapshot of open vacancies, not a history of hiring.** Almost every
team will compute "hiring growth" from `posted_date`, see a beautiful exponential curve, and ship a
ranking that is 100% survivorship artifact. The dataset was fetched in a **2-hour window** on
2026-06-05/06 **[measured]**; older postings are missing not because hiring was slower, but because
those roles got filled and delisted.

**The winning move is threefold:**

1. **Name the trap and correct for it.** Treat the snapshot as a cross-sectional *stock* of demand.
   Get the *flow* (new postings per period) from the live API, which is free, unauthenticated, and
   gives per-company 7-day / 28-day counts in a single request **[measured]**.
2. **Classify companies before ranking them.** The top of the naive leaderboard is entirely
   staffing agencies — Arbitex, PerZukunft, ARWA, DIS AG, Hays, Manpower **[measured]**. A vacancy
   count ranking produces a lead list of recruiters. Segmenting into *end client / IT service
   provider / staffing agency / public sector / training provider* converts that noise into the
   README's "competitor vs. partner classification" stretch goal, for free.
3. **Score with arithmetic, explain with an LLM.** A deterministic score is reproducible, tunable
   and defensible; an LLM that invents scores is neither. Use the model where it is genuinely
   better than code: reading job descriptions, classifying company type, naming the programme
   behind a hiring cluster, and writing the sales narrative — always grounded in cited postings.

The demo that wins is not the prettiest dashboard. It is the one where a judge asks *"why is this
company number 3?"* and you drill from score → signals → weights → the six specific job postings
that produced it, with links to arbeitsagentur.de.

---

## 1. Reading the brief properly

### 1.1 Who is the customer?

The README never says, and that is the first decision you must make and state out loud. Given a
Lithuanian IT hackathon and a German dataset, the highest-value framing is:

> **A Lithuanian/Baltic IT services company (nearshore delivery, team augmentation, project
> outsourcing) looking for German clients.**

This framing is worth choosing explicitly because it makes every downstream decision concrete:

| Question | Answer once you fix the ICP |
| --- | --- |
| What is an "opportunity"? | A German company whose IT delivery demand exceeds what it can hire locally. |
| What is a good signal? | Unfilled IT roles, long time-to-fill, concentrated tech stacks, multi-site hiring. |
| What is a bad lead? | A staffing agency (intermediary), a training centre (not hiring), a 1-role SME. |
| Who is a competitor? | Ferchau, Akkodis, Orizon, Guldberg — *and also a channel partner to subcontract to*. |
| Why now? | Bitkom: ~109,000 unfilled IT roles in Germany; ~30% of the IT workforce retiring; demand for ~630k roles by 2040 vs ~120k new entrants **[researched]**. |

State the ICP on slide 1. Judges reward teams that know who they are selling to.

### 1.2 The line that decides the scoring design

> *"The system should not simply rank companies by number of vacancies."*

This is the actual grading criterion hiding in the brief. Everything in §7 exists to satisfy it.
The test is simple: **if your top-10 list correlates ~1.0 with a raw posting-count top-10, you
have failed the challenge regardless of how good the UI is.** Compute and show that correlation
(Spearman ρ) as a slide — a low ρ with a *defensible* reason for each re-ranking is a strong
result.

---

## 2. What the data actually is **[measured]**

I downloaded the parquet (4.5 MB) and profiled it. This section is the single most useful part of
this document — read it before designing anything.

### 2.1 Shape

| Property | Value |
| --- | --- |
| Rows | **70,584** |
| Unique employers | **19,943** |
| Source | Bundesagentur für Arbeit, Jobsuche API v4 (single source, `source = "bundesagentur"`) |
| License | CC-BY-4.0 (attribution required — put it in the footer) |
| `fetched_at` range | **2026-06-05 23:41 → 2026-06-06 01:40** — a single 2-hour crawl |
| `posted_date` range | 2015-10-20 → 2026-06-06 |
| Columns | 19, of which 4 are constants (`source`, `license`, `provenance`, `lang`) |

### 2.2 The fields, honestly assessed

| Field | Fill | Verdict |
| --- | --- | --- |
| `id` / `source_url` | 100% | Good. `id` == BA `referenznummer`; URL is your evidence link. |
| `employer` | 99.94% (41 null) | **Raw, unnormalized string.** The entire entity-resolution problem lives here. |
| `title` | 100% | Your richest usable text. Median 46 chars. Contains role, seniority, sometimes tech. |
| `description_derived` | **0% — null in all 70,584 rows** | **Dead field.** No job descriptions in this dataset. This is the biggest constraint on the whole challenge. |
| `posted_date` | 100% | Trustworthy *per row*, dangerous *in aggregate* (see §3.1). |
| `region` | 99.8% | 27 values — includes **357 Austrian/Swiss rows** (Wien, Zürich, Tirol…). Not purely German. |
| `nuts_code` | 99.3% | NUTS-1 only (DE1–DEF). State level, not city. No coordinates, no postcode. |
| `kldb_2010` | 99.8% | **The best classifier in the dataset.** Official BA taxonomy, 360 distinct codes. |
| `esco_occupation` | ~100% | **Noisy.** Machine-mapped, visibly wrong on a material share of rows. |
| `esco_skills` | 100% | **Top-5 capped** (mean 4.98, median 5, max 5) → similarity-based, not extracted. Generic, not technological. |
| `seniority` | 100% | **88.0% "unknown"**. 6 values incl. a single `mid` row. Effectively unusable as-is. |
| `salary_range` | ~0% | Effectively empty. The live API confirms `verguetungsangabe: KEINE_ANGABEN` almost always. |
| `is_green` | 100% | 5,031 true (7.1%). Interesting for an ESG/energy angle, irrelevant otherwise. |

### 2.3 The occupational mix

`kldb_2010` first two digits (Berufsgruppe). Digit 1 = sector, digits 2–4 = increasing specificity,
**digit 5 = Anforderungsniveau (skill level 1–4)** — 1 Helfer, 2 Fachkraft, 3 Spezialist,
4 Experte/akademisch **[researched]**. That fifth digit is a free, reliable seniority proxy and is
**far better than the 88%-unknown `seniority` column**.

| KldB | Meaning | Rows | Share |
| --- | --- | --- | --- |
| 26 | Mechatronik, Energie, Elektro | 8,764 | 12.4% |
| 61 | Einkauf, Vertrieb, Handel | 7,397 | 10.5% |
| **43** | **Informatik / IKT** | **7,136** | **10.1%** |
| 21 | Rohstoffe, Glas, Keramik | 5,763 | 8.2% |
| 51 | Verkehr, Logistik | 5,208 | 7.4% |
| 81 | Medizin, Gesundheit | 4,361 | 6.2% |

**Your addressable slice is `kldb_2010 LIKE '43%'` → 7,136 postings, 3,001 employers.**
Adjacent codes worth including: `25` (Maschinenbau/Automatisierung, embedded), `27` (Technische
Forschung & Entwicklung), `71`/`72` (Unternehmensberatung, Finanzdienstleistungen — for
digitalization programmes). Decide and document your filter.

IT depth per company is thin:

| IT postings per employer | Employers |
| --- | --- |
| ≥ 3 | 491 |
| ≥ 5 | 242 |
| ≥ 10 | **93** |

**Design consequence: your real leaderboard universe is ~250–500 companies, not 20,000.** That is
small enough to run an LLM over *every* candidate, and small enough to hand-audit the top 30. Both
are enormous advantages — use them.

### 2.4 Regional skew

NRW 19,479 (27.6%), Bayern 10,205, Sachsen 7,915, Berlin 5,889, BW 5,415, Niedersachsen 5,403,
Hessen 4,963, Hamburg 4,574, **Bremen 3,429**, Schleswig-Holstein 814, Rheinland-Pfalz 316.

Bremen (0.8% of German population) has 4× the postings of Rheinland-Pfalz (4.9%). Baden-Württemberg
is under-represented relative to its economy. **This is a crawl artifact, not a labour-market
fact.** Never present a "regional hiring heatmap" from raw counts — normalize per region, or
present regional shares *within* a company, not across the market.

Cross-check: the live API currently reports **820,657 open postings** across all fields, of which
~23,300 are core IT **[measured]**. The 70,584-row dataset is therefore a **~8.6% sample of the BA
stock, capturing ~30% of live IT postings** — a sample, not a census. Say so in your limitations
slide before a judge says it for you.

---

## 3. The five traps

### 3.1 Trap 1 — Survivorship bias in `posted_date` (the big one)

Monthly `posted_date` counts in the snapshot **[measured]**:

| Month | Postings | vs prior |
| --- | --- | --- |
| 2025-09 | 1,496 | |
| 2025-12 | 1,560 | |
| 2026-01 | 2,608 | +67% |
| 2026-02 | 2,959 | +13% |
| 2026-03 | 5,156 | +74% |
| 2026-04 | 7,522 | +46% |
| **2026-05** | **22,141** | **+194%** |
| 2026-06 (6 days) | 15,760 | — |

A naive reading: "the German job market tripled in May 2026." The truth: **the snapshot only
contains postings still open on 2026-06-06.** A January posting survives into the snapshot only if
it was *still unfilled* five months later. What you are looking at is a survival curve, not a
demand curve.

**Consequences, in order of severity:**

- Any "hiring velocity", "growth vs. baseline", or "acceleration" metric computed from
  `posted_date` alone is **backwards**: it rewards recency of crawl, and it systematically
  *penalizes* companies whose roles are hard to fill — which are exactly the companies that need
  an outsourcing partner.
- Trend lines, month-over-month charts, and "hiring surge detected" badges built on this are all
  wrong. They will look great and be indefensible.

**How to handle it (pick one and say which):**

| Option | Effort | Honesty |
| --- | --- | --- |
| **A. Cross-sectional only.** Treat the snapshot as a photo of *current open demand*. Compare companies against each other at one instant. No time series at all. | Low | Fully honest. Recommended baseline. |
| **B. Invert the bias into a feature.** Posting age = `snapshot_date − posted_date` becomes **time-on-market**. A 6-month-old open IT role is a *strong* signal of a role the company cannot fill locally. This is a nearshoring vendor's single best buying signal. | Low | Honest and clever. **Do this.** |
| **C. Get real flow from the live API.** `veroeffentlichtseit=7` / `=28` gives genuine new-posting counts per company (§4.2). Two extra API calls. | Low | Fully honest, and it unlocks the velocity stretch goal. |
| **D. Survival-corrected estimate.** Model fill hazard by occupation, divide observed stock by survival probability to estimate true inflow. | High | Rigorous, but a research project. Mention it, don't build it. |

**Do B + C, present A as the fallback.** Trap 1 is the strongest single talking point available to
you. A slide titled *"Why the obvious trend line is wrong"* with this table will separate you from
every other team.

### 3.2 Trap 2 — The leaderboard is full of recruiters

Top employers by raw posting count **[measured]**:

| Employer | Postings | What it is |
| --- | --- | --- |
| Deutsche Bahn AG | 816 | Real end client |
| Jan Schreiner Private Arbeitsvermittlung Arbitex | 571 | **Placement agency** |
| PerZukunft Arbeitsvermittlung GmbH&Co.KG | 544 | **Placement agency** |
| Pflegia GmbH | 362 | **Care-sector recruiter** |
| PerZukunft … GmbH&Co.KG **GmbH & Co. KG** | 360 | **Same company, duplicated legal-form suffix** |
| ARWA Personaldienstleistungen GmbH | 336 | **Temp agency** |
| DIS AG Germany | 309 | **Staffing** |
| Akkodis Germany Tech Experts GmbH | 295 | **IT engineering services** |
| TimePartner, Hays, Michael Page, Manpower, puro, I.K. Hofmann, SYNERGIE… | 100–300 each | **Staffing** |

In the IT slice specifically, **the #1, #3, #4, #6 employers are all agencies**. A regex over
agency name patterns flags **21.3% of IT postings** **[measured]** — and that regex is a floor, not
a ceiling.

Also present: **alfatraining Bildungszentrum GmbH** (150 postings) — a training provider whose
"vacancies" are course listings, and private individuals as employers (`Ängel, Ahmet`, 162
postings).

**This is not a filter, it is a segmentation.** For a nearshore vendor:

- Agencies are **not** end clients — but Ferchau/Akkodis/Orizon/Guldberg **are subcontracting
  channels**, often an easier first sale than a direct enterprise deal.
- Training providers are pure noise — drop them.
- Public sector (BWI, Bundeskriminalamt, Bundesverwaltungsamt, Deutsche Rentenversicherung) is real
  demand but bound by procurement law — a different, slower motion.

Filtering agencies out changes the IT leaderboard completely **[measured]**:

| Rank | Employer | IT postings | Segment |
| --- | --- | --- | --- |
| 1 | Finanz Informatik GmbH & Co. KG | 82 | End client (banking IT) |
| 2 | Rheinmetall AG | 63 | End client (defence) |
| 3 | BWI GmbH | 61 | Public sector (Bundeswehr IT) |
| 4 | Deloitte GmbH | 57 | Consultancy (competitor *and* partner) |
| 5 | NTT DATA Deutschland SE | 45 | IT service provider (partner) |
| 6 | Siemens Energy Global | 38 | End client |
| 7 | prognum Automotive GmbH | 36 | End client (automotive engineering) |
| 8 | BMW AG | 36 | End client |
| 9 | Deutsche Telekom AG | 29 | End client |
| 10 | OHB-System AG | 28 | End client (space) |

That is a *credible sales list*. Show the before/after as a slide.

### 3.3 Trap 3 — Entity resolution

`employer` is a free-text string with no ID. Real examples from the data **[measured]**:

- `DIS AG` / `DIS AG Germany` / `DIS AG Personaldienstleistungen` / `DIS AG Office & Management` /
  `DIS AG FB Office & Management` — one company, five strings.
- `FERCHAU GmbH Niederlassung Bremen City` / `… Hamburg-City` / `… Nürnberg City` — branch suffixes.
- `PerZukunft Arbeitsvermittlung GmbH&Co.KG` vs `… GmbH&Co.KG GmbH & Co. KG` — duplicated suffix.
- `NTT DATA Deutschland SE` vs `NTT DATA Business Solutions Global Managed Services GmbH` — group
  vs subsidiary. **Do you merge them?** For a sales list: probably not — different buying centres.
  Model a `company` and a `company_group` and let the UI roll up.

The README explicitly says *perfect entity resolution is not required*. So don't build a
state-of-the-art system. Build this ladder and stop when it's good enough:

1. **Normalize**: lowercase; expand German umlauts (ä→ae, ö→oe, ü→ue, ß→ss) **and** strip-accent
   variants; `&` → `und`; collapse whitespace/punctuation.
2. **Strip legal forms** into a separate field: `gmbh & co. kg`, `gmbh`, `ag`, `se`, `kgaa`, `ohg`,
   `ug (haftungsbeschränkt)`, `e.v.`, `e.k.`, `kdör`, `mbh`. Apply **repeatedly** — the PerZukunft
   row proves suffixes stack.
3. **Strip branch markers**: `niederlassung X`, `standort X`, `filiale X`, `nl X`, `region X`,
   plus a trailing German city name.
4. **Block + fuzzy match** within blocks (first token, or first 4 chars + region) using
   token-set-ratio ≥ 92. Blocking keeps it O(n·k) instead of O(n²) on 20k names.
5. **Free win — use the API's own key.** The live BA API returns
   `arbeitgeberKundennummerHash` on **77% of postings** **[measured]**, and it is stable across
   postings for the same employer (verified: Siemens Energy returned the identical hash on two
   different postings). **This is a gift.** Where present, it beats any string matching. Where
   absent, fall back to the ladder above.

Expected outcome: ~20,000 raw strings → ~17,000 entities, with the top 500 (the ones that matter)
close to clean. Report a resolution-quality number: sample 50 merges, count errors, publish the
rate. Judges love a measured error rate far more than a claim of perfection.

### 3.4 Trap 4 — ESCO is not what you think it is

`esco_skills` is capped at exactly 5 entries (mean 4.98) **[measured]** — it is a top-5 nearest-
neighbour assignment against the ESCO skill vocabulary, not extraction from a job description
(there are no descriptions). The labels are generic competences, not technologies:

> `create software design` (933), `software UI design patterns` (642), `use software design
> patterns` (584), `operate open source software` (500), `data engineering` (430)

**You cannot get "Java + Azure" out of `esco_skills`.** The README's own worked example ("strong
concentration of Java and Azure roles") is *not achievable from the provided dataset alone*. That
is a deliberate gap, and closing it is where you win points.

`esco_occupation` is likewise machine-mapped and visibly wrong **[measured]**:

| Actual title | ESCO says |
| --- | --- |
| `Betreuungskraft / Alltagsbegleiter/in` (care worker) | **furniture specialised seller** |
| `Teamleitung Techniker/in - Meister Mechanische Werkstatt` | **chief technology officer** |
| `Prozessmanager Logistik für Siemens` | ICT operations manager |
| `Software Test Engineer / QA Engineer` | software tester ✅ |

`chief technology officer` is assigned to 412 IT rows and `commercial director` to 258 — clear
over-assignment. **Treat ESCO as a weak prior. Trust `kldb_2010` + `title` instead**, and use ESCO
only for coarse role families or as one vote in an ensemble.

### 3.5 Trap 5 — Technology signals barely exist in titles

Word-count of tech keywords across all 70,584 titles **[measured]**:

| Tech | Hits | Tech | Hits |
| --- | --- | --- | --- |
| SAP | 525 | .NET | 81 |
| Cloud | 228 | Linux | 62 |
| Java | 219 | Frontend | 58 |
| Security | 225 | Dynamics | 39 |
| Embedded | 211 | Python | 36 |
| DevOps | 115 | Azure | 36 |
| C# | 98 | ServiceNow | 25 |
| Backend | 92 | AWS | 18 |
| Fullstack | 86 | Kubernetes | 7 |

Titles yield a technology mention for maybe **5–8% of postings**. (Beware: naive substring matching
gives "AI" 1,916 hits and "KI" 1,123 hits — nearly all false positives from inside German words.
**Use word-boundary regex**, or you will confidently report an AI boom that isn't there.)

**SAP at 525 is the standout real finding** — it dwarfs every other named technology and is a
classic nearshore-outsourcing wedge. An "SAP transformation radar" is a viable, defensible product
narrative from this data alone.

**The fix for everything else: fetch the descriptions.** See §4.2.

---

## 4. Data strategy

### 4.1 Layer 0 — the provided dataset

Ingest the parquet directly (4.5 MB, one file):

```
https://huggingface.co/datasets/mischeiwiller/german-job-postings/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet
```

Everything fits in memory. **Do not stand up Spark/Dataflow for 70k rows.** DuckDB or pandas will
do the entire job in seconds, and BigQuery is a one-command load if you want SQL + a hosted demo.

Good news you don't have to solve: **there are zero exact duplicates** on
`(employer, title, region)` **[measured]** — the dataset is already deduplicated. Near-duplicates
(same role across cities) exist and are *signal*, not noise: multi-site posting of the same role
means a distributed programme.

### 4.2 Layer 1 — the live Bundesagentur API (the unlock)

**I verified this end-to-end. It works, it is free, and it needs no registration.** Auth is a single
static header: `X-API-Key: jobboerse-jobsuche`. Disable TLS verification (their cert chain is
broken) **[measured]**.

**Search endpoint (v6 — note: v4/app/jobs is dead, returns 403):**

```
https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
```

List items already carry almost everything you need — **no per-job detail call required for the
aggregate layer** **[measured]**:

`stellenangebotsTitel`, `firma`, **`arbeitgeberKundennummerHash`**, `hauptberuf` (BA-normalized
occupation), `alleBerufe`, `stellenlokationen` (PLZ + **city + lat/lon**), `referenznummer`,
`datumErsteVeroeffentlichung`, `aenderungsdatum`, `veroeffentlichungszeitraum`,
`eintrittszeitraum`, `vertragsdauer`, `verguetungsangabe`, `arbeitszeitVollzeit`.

Note `stellenlokationen` gives **city-level coordinates** — the provided dataset only has NUTS-1
states. Live data is strictly richer.

**Key parameters:**

| Param | Effect |
| --- | --- |
| `berufsfeld=Informatik` | Occupational field filter (144 fields exist) |
| `zeitarbeit=false` | **Excludes temp-work agencies** |
| `pav=false` | **Excludes private placement agencies** |
| `veroeffentlichtseit=0\|1\|7\|14\|28` | Published within N days — **this is your flow measure** |
| `wo` + `umkreis` | Location + radius km |
| `arbeitszeit=ho` | Home-office capable |
| `size` (≤100), `page` | Paging — **max ~page 50 (≈5,000 results); page 100 fails** |

**Facets are the killer feature.** Every response includes aggregate counts without extra calls:
`arbeitgeber` (company → count, top 100), `branche` (industry), `beruf`, `arbeitsort`,
`arbeitsort_plz`, `zeitarbeit`, `pav`, `homeoffice`, `veroeffentlichtseit`, `befristung`,
`verguetung`, `eintrittsdatum`.

**Three requests give you a real per-company velocity table** — no waiting weeks for a time series.
Actual output from `berufsfeld=Informatik&angebotsart=1&zeitarbeit=false&pav=false` **[measured,
2026-08-28]**:

| Company | Open now | New in 28d | New in 7d | Burst ratio (28d/open) |
| --- | --- | --- | --- | --- |
| BWI GmbH | 115 | 62 | 22 | 0.54 |
| **CGM** | 33 | 33 | 33 | **1.00 — entire portfolio posted this week** |
| Finanz Informatik | 70 | 28 | 9 | 0.40 |
| ALTEN GmbH München | 26 | 26 | 11 | 1.00 |
| SAP | 37 | 24 | 5 | 0.65 |
| ]init[ AG | 24 | 24 | 11 | 1.00 |
| Siemens AG | 46 | 22 | 9 | 0.48 |
| KNDS Deutschland | 15 | 15 | 3 | 1.00 |
| E.ON Grid Solutions | 14 | 14 | 0 | 1.00 |
| HENSOLDT Sensors | 12 | 12 | 7 | 1.00 |
| blackned GmbH | 12 | 12 | 0 | 1.00 |

A burst ratio of 1.00 means *the company's entire open IT portfolio appeared inside 28 days* — a
brand-new programme, and the hottest possible outbound trigger. A ratio of 0.4–0.5 with high volume
(BWI, Finanz Informatik) means a large, steady, long-running programme — a different sales motion
(framework agreements, not project pitches). **Two numbers, two distinct plays.** Note also the
visible defence/public-sector cluster (KNDS, HENSOLDT, blackned, BWI) — a real, nameable market
trend you found in live data.

Aggregate market context **[measured]**: `berufsfeld=Informatik` returns 7,571 open; adding
`zeitarbeit=false&pav=false` drops it to **4,977 — 34% of IT postings are agency-mediated**.
Facets: `zeitarbeit=true` 1,775 (23.4%), `pav=true` 819 (10.8%). Core IT across all IT-ish fields
≈ 23,300 of 820,657 total open postings.

**Detail endpoint (for descriptions):**

```
GET /jobboerse/jobsuche-service/pc/v4/jobdetails/{base64(referenznummer)}
```

Returns `stellenangebotsBeschreibung` — **mean 3,063 chars, median 2,945** **[measured]** — plus:

| Field | Why it matters |
| --- | --- |
| **`istArbeitnehmerUeberlassung`** | **Official temp-work flag. Ground truth for Trap 2 — verified True for DIS AG and Guldberg, False for Siemens Energy and Rheinmetall.** |
| **`istPrivateArbeitsvermittlung`** | Official placement-agency flag. |
| `arbeitgeberKundennummerHash` | Stable employer key (Trap 3). |
| `datumErsteVeroeffentlichung` + `aenderungsdatum` | **Time-on-market.** I found an ENERCON role first published 2025-03-11 and *still open* — 17 months. That is a screaming "we cannot fill this" signal. |
| `homeofficemoeglich` | Remote-friendly → far more receptive to a nearshore team. |
| `hauptberuf` | BA-normalized occupation, cleaner than the raw title. |
| `stellenlokationen` | PLZ + city + coordinates. |

**Two caveats, both important:**

1. **Retro-enrichment hit rate is only ~25%** **[measured, 44 sampled]** — 75% of the June snapshot's
   postings had already expired by late August. Plan around it: enrich only the postings belonging
   to your top ~100 candidate companies, and lean on live data for the rest.
2. **Reference-number format changed between June and August 2026.** Snapshot IDs look like
   `17102-44225539-65-S`; live ones look like `13669-YHFM6UDDIG6TAMA6-S` (only 1 of 100 live refnrs
   was numeric-style) **[measured]**. **Join snapshot ↔ live on the employer hash, not the refnr.**

Throughput: ~0.19 s per detail request single-threaded **[measured]**. 7,136 IT postings ≈ 23 min
serial, ~2–3 min with 8–16 workers. Be polite: cap concurrency, cache aggressively to disk, respect
their service.

### 4.3 Layer 2 — enrichment (optional, and use it sparingly)

| Source | Gives you | Cost | Verdict |
| --- | --- | --- | --- |
| **KldB 2010 reference table** (BA / destatis) | Code → German occupation label, sector, **Anforderungsniveau** | Free, static file | **Must have.** Turns opaque `43102` into "IT, Fachkraft-Niveau". |
| **ESCO v1.2.1 download** (CSV/RDF, 3,039 occupations / 13,939 skills) | Skill hierarchy, ISCO mapping, DE labels | Free | Nice to have. Only if you build a skill-family rollup. |
| **NUTS ↔ Bundesland ↔ population/GDP** (Eurostat) | Regional normalization, fixing the Bremen skew | Free | Nice to have, cheap, and defuses a likely judge question. |
| **Company website / domain** (search or the BA `allianzpartnerUrl` field) | Domain for CRM export, logo | Free-ish | Nice to have. A domain makes the export feel real. |
| **GLEIF LEI API** | Legal entity IDs, parent/child hierarchy for larger firms | Free API | Nice to have. Best available free answer to "is NTT DATA Deutschland the same group as NTT DATA Business Solutions?" |
| **OffeneRegister.de / OpenCorporates DE dump** | Handelsregister entities, legal form, address | Free bulk | Difficult. Germany's register is **~150 separate court databases**; `HRB 12345` is unique only within one Amtsgericht **[researched]**. High effort, low hackathon payoff. |
| **Commercial (ZoomInfo, Coresignal, PredictLeads, TheirStack)** | Firmographics, headcount, technographics | Paid | Skip. But **do** name them in the competitive-positioning slide — TheirStack indexes ~210M postings across 195 countries and charges 3 credits per company lookup; PredictLeads starts at $40/mo **[researched]**. Positioning yourself against a known market beats claiming novelty. |

**Recommendation: KldB table + NUTS normalization + a domain lookup for the top 30 only.** Every
extra source multiplies join bugs and eats demo time.

---

## 5. What counts as a meaningful hiring signal

The core intellectual work of the challenge. Here is the full menu — the point is that only ~4 of
these are volume-based, and the interesting ones aren't.

Legend: **S** = computable from the provided snapshot, **L** = needs the live API, **D** = needs job
descriptions.

### 5.1 Scale & capacity

| # | Signal | How | Src |
| --- | --- | --- | --- |
| 1 | **IT vacancy stock** | Count of open `43%` postings | S |
| 2 | **IT intensity** | IT postings ÷ total postings for that company. *Isolates companies whose growth is specifically technological* — Deutsche Bahn has 816 postings but only 27 IT (3%); prognum Automotive has 36 of 36 (100%). **This one metric alone beats raw counts and is trivial to compute.** | S |
| 3 | **Seniority pyramid** | Distribution of KldB 5th digit. Many Experten (4) + few Helfer (1) = architecture/greenfield work. Many level-2 = volume delivery — the nearshore sweet spot. | S |
| 4 | **Multi-site footprint** | Distinct regions with IT postings. BWI hires IT in 6 states; prognum in 2. Distributed = already used to distributed delivery = receptive to nearshore. | S |

### 5.2 Timing & momentum

| # | Signal | How | Src |
| --- | --- | --- | --- |
| 5 | **Burst ratio** | New-in-28d ÷ open. 1.00 = brand-new programme (project pitch). 0.4 = steady large programme (framework deal). | L |
| 6 | **Acceleration** | 7d-rate vs 28d-rate, per company. Needs a Poisson/EWMA baseline, not a raw ratio — small companies produce huge fake z-scores **[researched]**. | L |
| 7 | **Time-on-market** | `snapshot_date − datumErsteVeroeffentlichung`. Long-open roles = **local hiring has failed** = the exact moment a nearshore vendor is relevant. **The highest-conviction signal in this whole list for the chosen ICP.** | S/L |
| 8 | **Repost detection** | Same role reappearing under a new refnr = failed to fill, tried again. Strongest possible pain signal. | L |

### 5.3 Composition & intent (what they're actually building)

| # | Signal | How | Src |
| --- | --- | --- | --- |
| 9 | **Technology concentration** | Herfindahl index over extracted tech. SAP-heavy vs cloud-heavy vs embedded-heavy → completely different pitches. | D (partly S via titles) |
| 10 | **Programme archetype** | Cluster a company's roles into a named programme: *cloud migration* (Cloud Architect + DevOps + SRE + Security), *SAP S/4 transition* (SAP consultants + ABAP + Basis), *data platform* (Data Engineer + Analyst + Platform), *product build* (PO + FE + BE + QA). **This is the "opportunity", not the vacancy count.** | D |
| 11 | **Role-mix completeness** | A full squad shape (PO + architect + 3 devs + QA) = a project starting now → *we can staff a pod*. Scattered singletons = BAU backfill → low value. Excellent, cheap, and almost nobody will do it. | S |
| 12 | **Adjacent-function hiring** | IT roles alongside `61` (Vertrieb) or `71` (Unternehmensorganisation) = business expansion, not just IT replacement. | S |
| 13 | **Contract/remote posture** | `homeofficemoeglich=true`, `vertragsdauer=BEFRISTET`, "Projekt"/"befristet" in title → already comfortable with flexible/external delivery. | L/S |

### 5.4 Qualifiers & disqualifiers

| # | Signal | Effect |
| --- | --- | --- |
| 14 | **Company type** (§6) | Gate, not a score component. |
| 15 | **Public sector** | Real demand, procurement-bound → separate track, don't mix into the main ranking. |
| 16 | **Confidence** | Low posting count, unresolved entity, no descriptions fetched → **shrink the score toward the mean, don't hide the lead.** |
| 17 | **Region fit** | Optional ICP filter (e.g. prefer NRW/Bayern/Berlin/Hamburg for German-market nearshore). |

**Pick 6–9 and implement them properly. Signals 2, 3, 7, 5, 11 and 10 are the highest
value-per-hour on this list.**

---

## 6. Company classification — the segmentation that makes the list usable

Six classes, and the README's "competitor vs. partner classification" stretch goal falls out for
free:

| Class | Examples in the data | Sales meaning |
| --- | --- | --- |
| **End client** | Finanz Informatik, Rheinmetall, BMW, Siemens Energy, prognum, zollsoft | **Primary target.** Direct delivery/augmentation. |
| **IT service provider** | NTT DATA, Bechtle, Computacenter, BridgingIT, SoftwareOne, ]init[ | **Partner or competitor.** Subcontracting is often the fastest first deal. |
| **Staffing / AÜ** | DIS AG, Hays, ARWA, puro, Orizon, FERCHAU, Akkodis | **Channel, not client.** Separate track or excluded. |
| **Public sector** | BWI, Bundeskriminalamt, Bundesverwaltungsamt, Deutsche Rentenversicherung | Real, slow, procurement-bound. Own track. |
| **Training provider** | alfatraining Bildungszentrum | **Noise. Drop.** |
| **Individual / micro** | `Ängel, Ahmet`, single-posting employers | Drop below a minimum-volume threshold. |

**How to classify, cheapest first:**

1. **`istArbeitnehmerUeberlassung` / `istPrivateArbeitsvermittlung` from the API** — official ground
   truth, free, no ML. **Start here.**
2. **Name regex** — `Personaldienst|Personalservice|Arbeitsvermittlung|Zeitarbeit|Recruit|Staffing|
   Personalmanagement|Bildungszentrum|Akademie` catches 21.3% of IT postings **[measured]** and is
   a 10-minute job.
3. **Behavioural fingerprint** — agencies post *many roles across unrelated occupational sectors in
   many regions*. Compute KldB-sector entropy per company: high entropy + high volume + many
   regions ≈ agency, even without a matching name. This catches the ones the regex misses and is a
   genuinely nice touch.
4. **LLM classification** on the ~500 companies that survive the volume threshold, given name +
   top-10 titles + sector spread, returning `{class, confidence, rationale}` as structured output.
   500 calls ≈ cents. **This is where an LLM is clearly better than a regex** — and the population
   is small enough to make it cheap and auditable.

Then: **hand-label 100 companies yourself** and report classifier precision/recall. A measured 0.88
beats an unmeasured "it works" every time.

---

## 7. Scoring architecture

### 7.1 Principle: deterministic score, LLM narrative

Do **not** ask an LLM to output "87/100". It is unstable across runs, unauditable, and untunable —
and the first judge who asks "why 87 and not 82?" ends the demo. Instead:

```
signals (arithmetic, reproducible)
   → sub-scores (0–100, each independently explainable)
      → weighted total × confidence
         → LLM writes the narrative from the computed signals, citing postings
```

The LLM never sees a blank page and never invents a number. It explains numbers that already exist.

### 7.2 A four-factor model

```
Opportunity = (0.35·Demand + 0.30·Pain + 0.20·Fit + 0.15·Timing) × Confidence
```

| Factor | Composed of | Intuition |
| --- | --- | --- |
| **Demand** | IT stock (log-scaled), IT intensity, role-mix completeness | Is there enough work to be worth a conversation? |
| **Pain** | Time-on-market, reposts, seniority skew toward scarce profiles, region scarcity | Are they *failing* to hire? This is what you actually monetize. |
| **Fit** | Tech overlap with your bench, company class, size band, remote posture | Can *we specifically* deliver this? |
| **Timing** | Burst ratio, acceleration, new-programme detection | Is the buying window open now? |
| **Confidence** | Evidence volume, entity-resolution certainty, description coverage | How much should we believe the above? |

**Three implementation rules that matter more than the weights:**

- **`log1p` all count-based inputs.** Otherwise Deutsche Bahn's 816 postings dominate everything and
  you have rebuilt the naive ranking with extra steps.
- **Percentile-rank within peer group** (same class × similar size band), not globally. A 12-role
  Mittelstand burst is a bigger deal than 40 roles at Siemens.
- **Multiply by confidence, don't gate on it.** A high-signal, low-evidence company should appear
  ranked lower with a visible "thin evidence" badge — not silently vanish.

### 7.3 Make the weights visible and tunable

Put the weights in a YAML/JSON config, expose sliders in the UI, and re-rank live. When a judge
says *"we care more about SAP than cloud"*, you change it on stage. **This single feature makes the
demo feel like a product instead of a notebook**, and it directly answers "the scoring approach is
up to the team" by showing the approach is a *parameter*, not a hardcode.

### 7.4 Prove you beat the naive baseline

Compute Spearman ρ between your ranking and a pure posting-count ranking. Show the top 5 companies
that **moved up** and the top 5 that **dropped out**, each with a one-line reason:

> *"ARWA Personaldienstleistungen: rank 6 → excluded. Reason: `istArbeitnehmerUeberlassung = true`,
> KldB-sector entropy 0.91 across 14 occupational sectors. Staffing agency, not an end client."*

> *"prognum Automotive: rank 47 → rank 7. Reason: 36 of 36 postings are IT (100% intensity),
> concentrated in data/AI + automotive embedded across 2 sites, 8 senior-level roles."*

This slide *is* the answer to "the system should not simply rank by number of vacancies."

---

## 8. Where AI actually earns its place

**Use an LLM for (high value):**

| Task | Why the LLM wins | Scale |
| --- | --- | --- |
| **Tech & seniority extraction from descriptions** | 3,000-char German prose → structured `{technologies, seniority, project_context, team_size_hints, contract_type}`. Regexes are brittle across German phrasing; this is exactly what LLMs are for. | ~5–10k calls, batched |
| **Programme archetype naming** | "These 14 roles constitute an S/4HANA migration with a parallel data-platform build." No heuristic produces that sentence. | ~500 calls |
| **Company classification** | Client vs provider vs agency from name + role mix (§6). | ~500 calls |
| **Sales narrative + suggested approach** | The README's "Reasoning" field, plus the stretch goal "suggested sales approach". | Top ~100 only |
| **Entity-resolution tie-breaks** | Only for the ~50 fuzzy pairs the deterministic ladder can't decide. | ~50 calls |

**Do NOT use an LLM for:**

- Producing the score (§7.1).
- Aggregating counts — that's SQL.
- Anything you'd have to re-run to reproduce a number in your demo.

**Grounding rules (this is what makes the output defensible):**

- Every generated claim must cite `posting_id`s. Render them as clickable `source_url` links.
- Prompt with a **closed-world instruction**: *"Use only the postings provided. If the evidence does
  not support a claim, say 'insufficient evidence'. Do not infer company size, revenue, funding, or
  technologies not present in the text."*
- Use **structured output / JSON schema** (Vertex AI `responseSchema`) so parsing never fails.
- **Post-validate**: check every cited `posting_id` exists and belongs to that company; check every
  named technology appears in at least one cited description. Drop or flag unsupported claims. This
  is cheap string matching and it turns "we used AI" into "we used AI and verified it"
  **[researched: atomic-claim decomposition + citation-resolvability checking]**.
- **Cache by content hash.** You will re-run the pipeline 20 times during the hackathon; don't pay
  for the same generation twice, and keep the demo reproducible offline.

**Model/infra notes [researched]:** batch prediction accepts up to 30,000 prompts per job from GCS
or BigQuery and is ~50% cheaper than online; `gemini-embedding-001` is $0.15/1M input tokens online,
$0.075/1M batched. For 10k descriptions × ~800 tokens ≈ 8M tokens — cents on a Flash-class model.
The $300 GCP credit is not a real constraint here; **your constraint is wall-clock time, so batch
early and cache everything.**

**Embeddings — one genuinely good use:** embed job titles (or descriptions), cluster per company,
and let cluster structure define "programmes". Also enables *"find companies similar to our best
existing client"* — a killer demo moment that takes ~20 lines with a vector index over ~500
company profile vectors.

---

## 9. System architecture

### 9.1 Pipeline

```
┌─ ingest ──────────────────────────────────────────────────────┐
│ HF parquet (70,584 rows)   +   live BA API (v6 search)        │
│ KldB reference table       +   NUTS/population lookup         │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ normalize ───────────────────────────────────────────────────┐
│ employer → normalized name + legal form + branch              │
│ entity resolution (hash-first, then fuzzy blocking)           │
│ KldB decode → sector + Anforderungsniveau                     │
│ posting age, region normalization                             │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ enrich (LLM, batched, cached) ───────────────────────────────┐
│ fetch descriptions for candidate companies (~25% retro hit)   │
│ extract {tech[], seniority, project_context, contract}        │
│ classify company type                                         │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ aggregate ───────────────────────────────────────────────────┐
│ company × signal matrix (§5) + peer-group percentiles         │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ score ───────────────────────────────────────────────────────┐
│ deterministic sub-scores → weighted total × confidence        │
│ weights from config, hot-reloadable                           │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ explain (LLM, grounded + validated) ─────────────────────────┐
│ programme archetype, narrative, suggested approach, citations │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─ serve ───────────────────────────────────────────────────────┐
│ FastAPI  +  Streamlit/Next.js dashboard  +  CSV/JSON export   │
└───────────────────────────────────────────────────────────────┘
```

### 9.2 Stack recommendation

**Keep it boring. 70k rows is a laptop-scale problem.**

| Layer | Pick | Why |
| --- | --- | --- |
| Storage/compute | **DuckDB** over parquet | Zero infra, full SQL, sub-second on this data. Mirror to **BigQuery** only if you want a hosted demo or want to show GCP usage. |
| Orchestration | **A numbered Python script per stage** writing parquet between stages | Airflow/Dagster is theatre at this scale. Idempotent stages let you re-run stage 4 without re-fetching stage 1. |
| LLM | **Vertex AI Gemini Flash**, structured output, batch mode | Fast, cheap, on the provided credits. |
| API | **FastAPI** | `/companies`, `/companies/{id}`, `/signals`, `/export.csv` |
| UI | **Streamlit** (safe) or **Next.js** (impressive, riskier) | Streamlit gets you a working drill-down in ~2 hours. Only go Next.js if someone owns it full-time. |
| Cache | Local disk keyed by content hash | Non-negotiable. Protects the demo from network failure. |

**Ship a static JSON fallback of the final results.** If the venue wifi dies during your demo, the
dashboard must still render. This has saved more hackathon demos than any architectural decision.

### 9.3 Data model

```sql
-- postings (fact)
posting_id, company_id, raw_employer, title, hauptberuf, posted_date,
first_published, last_modified, days_open, region, nuts, plz, lat, lon,
kldb, kldb_sector, kldb_level, esco_occupation, esco_skills[],
technologies[], seniority_derived, is_remote, is_temp_work, is_agency_posting,
source_url, description_fetched_at

-- companies (dimension)
company_id, canonical_name, legal_form, name_variants[], employer_hash,
company_class, class_confidence, domain, regions[], first_seen, last_seen

-- company_signals (one row per company per snapshot)
company_id, snapshot_date, it_postings, total_postings, it_intensity,
level_mix{}, region_count, median_days_open, p90_days_open,
new_7d, new_28d, burst_ratio, tech_top[], tech_hhi, role_mix_completeness,
adjacent_hiring, peer_group

-- opportunities (output)
company_id, snapshot_date, score, demand, pain, fit, timing, confidence,
archetype, headline, reasoning, suggested_approach, evidence_posting_ids[],
weights_version, generated_at
```

`weights_version` and `snapshot_date` on the output table mean you can show *"here's how the
ranking changed when we changed the weights"* — a strong differentiator, and honest.

---

## 10. Must have / should have / nice to have

### Must have — the README's numbered list is the rubric

| # | Requirement | Minimum credible implementation |
| --- | --- | --- |
| 1 | Ingest & process | Parquet → DuckDB, typed, documented |
| 2 | Company normalization | Legal-form/branch stripping + fuzzy blocking + reported error rate |
| 3 | Derive signals | ≥5 real signals, at least 2 non-volume (§5) |
| 4 | Company-level aggregation | `company_signals` table |
| 5 | Identify opportunities | Archetype + segmentation, not just "they're hiring" |
| 6 | Rank | Deterministic weighted score |
| 7 | Explain the ranking | Sub-score breakdown **plus** LLM narrative |
| 8 | Preserve evidence | Posting IDs + titles + clickable `source_url` on every claim |
| 9 | Interface | Dashboard with drill-down + JSON/CSV export |

**Plus two the README implies but doesn't number — and both are cheap and high-scoring:**

- **Filter/classify non-clients** (§6). Without it, requirement 6 is actively wrong.
- **State assumptions & limitations** (explicitly required in "Deliverable"). §3 is your slide.

### Should have — best value per hour

- **Time-on-market** (signal 7). ~30 min from data you already have. Highest-conviction signal.
- **IT intensity** (signal 2). ~10 min. Immediately beats raw counts.
- **Live velocity via facets** (§4.2). ~1 hour. Directly delivers two stretch goals (live acquisition
  + velocity detection) with three API calls.
- **Tunable weights in the UI.** ~1 hour. Transforms the demo.
- **Naive-baseline comparison slide.** ~30 min. Directly answers the grading criterion.
- **CRM-ready CSV export.** ~20 min. Makes it feel like a product.

### Nice to have

- Company clustering / "companies like X" via embeddings
- Geographic analysis (normalized per region — see Trap 2 on Bremen)
- Scheduled monitoring (Cloud Scheduler → daily snapshot → *real* week-over-week deltas)
- Suggested sales approach & draft outreach angle per company
- Technology trend detection across the market (SAP is your headline)
- Confidence intervals on scores rather than point estimates

### Explicitly do NOT build

The README rules these out; building them costs you time and earns nothing:

- Full-web crawling, production CRM integration, automated outreach, production-grade pipelines,
  perfect entity resolution.
- Also skip: authentication/multi-tenancy, a custom-trained ML model (you have no labels), Kubernetes.

---

## 11. Difficulty map

| Task | Difficulty | Time | Notes |
| --- | --- | --- | --- |
| Load & profile the dataset | Trivial | 30 min | 4.5 MB parquet |
| KldB-based IT filter + decode | Easy | 1 h | Need the reference table |
| Company name normalization | **Medium** | 2–3 h | Umlauts, stacked legal forms, branches. Timeboxed, not solved. |
| Fuzzy entity resolution | Medium-Hard | 3–4 h | **Use `arbeitgeberKundennummerHash` and skip most of this.** |
| Agency classification | Easy→Medium | 1–2 h | API flags → regex → entropy → LLM ladder. Stop when good enough. |
| Signal computation | Easy | 2 h | Mostly `GROUP BY` |
| Live API acquisition | **Easy** | 1–2 h | Verified working. Watch the page-50 cap. |
| Description enrichment | Medium | 2–3 h | Concurrency + caching + 25% retro hit rate |
| LLM extraction pipeline | Medium | 2–3 h | Batch + structured output + validation |
| Scoring model | Medium | 2 h | The *thinking* is hard; the code is easy |
| Explanation generation | Easy | 1–2 h | Grounded prompt over computed signals |
| Dashboard | Medium | 3–4 h | Streamlit fast, Next.js slow |
| Evaluation | **Hard (conceptually)** | 2 h | No ground truth — see §12 |
| **Survivorship-bias handling** | **Hard (conceptually), easy to implement** | 1 h | **The differentiator.** |

**Hardest things, ranked by "will silently ruin your result":**

1. **Understanding that `posted_date` trends are fake** — most teams won't, and it invalidates their
   headline metric.
2. **Resisting volume-based ranking** — gravity pulls you there; the brief explicitly forbids it.
3. **Proving it works without labels** — see §12.
4. **Entity resolution** — genuinely hard, explicitly not required. Timebox to 3 hours.
5. **Time management** — the analysis is 20% of the work; ingestion, plumbing and the UI are 80%.

---

## 12. Evaluation without ground truth

There is no labelled "these companies became customers" set. Judges will ask how you know it works.
Have four answers ready — this is where good teams beat clever teams.

1. **Face validity on a hand-audit.** Manually review the top 25. For each, ask *"would a salesperson
   call this company?"* Report the hit rate. 20/25 with 5 honest misses beats a claim of perfection.
2. **Ablation.** Score with and without each signal; show how the top-20 changes. Proves each signal
   does work and isn't decoration.
3. **Negative controls.** Your system must rank agencies, training providers and micro-employers
   *low*. Show that it does. **This is a real, checkable correctness test that costs nothing.**
4. **Stability.** Re-run against live data pulled today. Do the top companies persist? A ranking that
   scrambles completely day-to-day is noise. (You have this for free: the June snapshot and the
   August live pull are two real time points — that's a genuine stability test.)

Plus, if time allows: **LLM-as-judge with a rubric** over the generated narratives (groundedness,
evidence sufficiency, actionability), scored by a *different* model family than the generator, with
chain-of-thought reasoning — reported to improve reliability ~10–15% **[researched]**. Sample 20
outputs, report the distribution, and be honest that it's a proxy.

---

## 13. Demo & judging

### The 5-minute narrative

1. **(30s) The problem, with a number.** "Germany has ~109,000 unfilled IT roles. Which 20 companies
   should we call on Monday?"
2. **(45s) The naive answer, and why it's wrong.** Show the raw top-10: it's Arbitex, PerZukunft,
   ARWA. "These are recruiters. And this trend line" — show the fake exponential — "is survivorship
   bias, not growth."
3. **(90s) The system.** Pipeline diagram, signals, scoring. Emphasize deterministic score + grounded
   explanation.
4. **(90s) Live drill-down.** Top-10 → click #3 → score breakdown → signals → the actual job
   postings → click through to arbeitsagentur.de. **The click-through to the real posting is the
   moment you win.**
5. **(30s) Move a weight slider, re-rank live.**
6. **(45s) Limitations, honestly.** Sample not census; ESCO noisy; no descriptions in the source;
   entity resolution ~X% accurate; snapshot is a single point in time.

### Slides that punch above their weight

- **Before/after leaderboard** (with vs without agency classification)
- **"Why the obvious trend line is wrong"** (Trap 1 table)
- **Spearman ρ vs the naive baseline**, with 3 named movers and reasons
- **One full worked example** in the README's own format — matching their template signals you read
  the brief

### A worked example from real data

> **Company:** Finanz Informatik GmbH & Co. KG
> **Class:** End client (banking IT — Sparkassen-Finanzgruppe)
> **Opportunity score:** 84 / 100 · **Confidence:** high (82 postings, entity hash-resolved)
>
> **Opportunity:** Java/core-banking delivery partnership — sustained multi-site platform programme
>
> **Signals**
> - 82 open IT roles — **rank 1 among non-agency employers** in the snapshot
> - **100% IT intensity** — every posting is a `43x` role
> - Concentrated in Hessen (50) and Niedersachsen (30) — a two-hub delivery model
> - 41 of 82 posted in the final 30 days of the snapshot (burst ratio 0.50) — steady large programme
> - Live check (2026-08-28): 70 open, 28 new in 28d, 9 new in 7d — **still running 3 months later**
> - Java, online-banking backend, Wertpapier, contract management → regulated core-banking stack
>
> **Reasoning:** Sustained, high-volume, geographically concentrated engineering hiring around
> regulated banking platforms. Volume persisting across two independent observations three months
> apart indicates a multi-year programme rather than a hiring spike. Role mix (business analysts +
> Java developers + architects + platform admins) is a complete delivery-squad shape, which
> typically indicates capacity constraint rather than replacement hiring.
>
> **Play:** Framework agreement / dedicated pod. Not a project pitch — the programme predates us.
>
> **Evidence:** `Java-Softwareentwickler (m/w/d) Wertpapierpapiere` · `Softwareentwickler/Architekt
> Online-Banking-Backend` · `Business Analyst Firmenkunden (Konsortial, Avale, Rahmenkredite)` ·
> `IT-Systemadministrator Multifaktor-Authentifizierung` · `Software-Entwickler Vertragsmanagement`
> *(each linking to arbeitsagentur.de)*

Note what makes this good: **it contains a falsifiable claim** ("still running 3 months later")
backed by two independent observations, and it ends with a *play*, not an observation.

---

## 14. Build plan (24–36 h, 4 people)

| Phase | Hours | Owner | Deliverable |
| --- | --- | --- | --- |
| **0. Align** | 0–1 | all | ICP decided, signals chosen, score formula sketched on a whiteboard, schema agreed |
| **1. Ingest + profile** | 1–3 | Data | DuckDB loaded, IT slice defined, profiling notebook, Trap-1 chart produced |
| **2. Normalize + classify** | 3–7 | Data | `companies` table, class labels, 100 hand-labelled rows for accuracy |
| **3. Live acquisition** | 3–6 | Backend | Facet-based velocity table + description fetcher with cache |
| **4. LLM enrichment** | 6–10 | AI | Tech/seniority extraction, company classification, cached |
| **5. Signals + scoring** | 8–12 | Data | `company_signals` + `opportunities`, config-driven weights |
| **6. Explanations** | 10–14 | AI | Grounded narratives with validated citations |
| **7. API + dashboard** | 8–18 | Frontend | List → detail → evidence drill-down, weight sliders, export |
| **8. Evaluation** | 18–22 | all | Hand-audit, ablation, negative controls, baseline ρ |
| **9. Demo prep** | 22–28 | all | Slides, script, **static JSON fallback**, 3 full rehearsals |
| **10. Buffer** | 28–36 | all | Everything takes longer than this table says |

**Parallelization rule:** freeze the `companies` and `company_signals` schemas at hour 3 and have
frontend build against **fixture data** immediately. Do not let the UI wait for the pipeline — that
is the classic way hackathon teams end up with a great pipeline and nothing to show.

**Hour-18 checkpoint:** if there is no end-to-end path from parquet → ranked list → dashboard by
hour 18, **cut LLM enrichment entirely** and ship signals + deterministic scoring + template-based
explanations. A complete simple system demos far better than a sophisticated broken one.

---

## 15. Assumptions, risks, limitations

State these on a slide. Judges consistently reward teams who find their own holes.

**Assumptions**
- Bundesagentur postings are representative of German IT demand. *Partly false* — the BA under-
  represents senior/tech-brand hiring that runs through LinkedIn and company career pages.
- Open vacancies proxy delivery-capacity pressure. Reasonable, unvalidated.
- The employer string ≈ the buying entity. False for groups and shared-service subsidiaries.

**Data limitations**
- Single-source (BA only), single-snapshot (2-hour crawl on 2026-06-06).
- ~8.6% sample of BA stock; ~30% of live IT postings. **Not a census.**
- Zero job descriptions in the provided data.
- Strong regional skew (Bremen over-, Rheinland-Pfalz/BW under-represented).
- 357 Austrian/Swiss rows despite "German" framing.
- ESCO mappings materially noisy; `seniority` 88% unknown; `salary_range` effectively empty.
- Live retro-enrichment recovers only ~25% of snapshot postings.

**Method limitations**
- No ground truth → no precision/recall on *opportunities*, only on classification sub-tasks.
- Weights are judgement, not learned. (Own this: they're *tunable* and *visible*, which is the
  honest form of judgement.)
- Absence of a posting ≠ absence of demand (big firms often don't post on the BA).

**Legal / ethical [researched]**
- Dataset is **CC-BY-4.0 → attribution is mandatory.** Put it in the UI footer.
- Only company-level, publicly published data — no personal data, no contact scraping. Note that a
  handful of employer strings *are* personal names; treat them as B2B entities and exclude them
  from any export.
- B2B lead processing in the EU typically rests on **legitimate interest, Art. 6(1)(f) GDPR**, with a
  documented Legitimate Interest Assessment.
- **Germany-specific:** the UWG effectively requires **prior consent for commercial email**, even
  B2B. So the deliverable is a *prioritized call list with evidence*, **not** an automated outreach
  engine — which conveniently matches the README's "automated outreach is NOT required".

---

## Appendix A — Verified API cookbook

All verified working on 2026-08-28. No registration, no OAuth, static key.

```python
import base64, json, ssl, urllib.request

CTX = ssl.create_default_context()          # BA's cert chain is broken
CTX.check_hostname = False                  # → verification must be off
CTX.verify_mode = ssl.CERT_NONE
H = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Mozilla/5.0"}
BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc"

def get(url):
    req = urllib.request.Request(url, headers=H)
    return json.loads(urllib.request.urlopen(req, timeout=30, context=CTX).read().decode("utf-8"))

# --- 1. Search + facets (v6). v4/app/jobs is DEAD (403).
def search(**params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return get(f"{BASE}/v6/jobs?{q}")

# Per-company velocity: 3 calls -> stock / 28d flow / 7d flow
base_q = dict(berufsfeld="Informatik", angebotsart=1,
              zeitarbeit="false", pav="false", size=1, page=1)
stock = search(**base_q)["facetten"]["arbeitgeber"]["counts"]          # top 100 employers
d28   = search(**base_q, veroeffentlichtseit=28)["facetten"]["arbeitgeber"]["counts"]
d7    = search(**base_q, veroeffentlichtseit=7)["facetten"]["arbeitgeber"]["counts"]
# burst_ratio = d28[c] / stock[c]   -> 1.0 means the whole portfolio is new

# --- 2. Detail (v4) -> description + the two agency ground-truth flags
def detail(refnr):
    enc = base64.b64encode(refnr.encode()).decode()
    return get(f"{BASE}/v4/jobdetails/{enc}")
# -> stellenangebotsBeschreibung, istArbeitnehmerUeberlassung,
#    istPrivateArbeitsvermittlung, arbeitgeberKundennummerHash,
#    datumErsteVeroeffentlichung, aenderungsdatum, homeofficemoeglich,
#    hauptberuf, stellenlokationen[{plz, ort, breite, laenge}]
```

**Gotchas, all verified the hard way**

| Gotcha | Detail |
| --- | --- |
| Endpoint versions | `v6/jobs` for search; `v4/jobdetails` for detail. `v4/app/jobs` → **403** |
| Paging cap | `page=50` works (~5,000 rows), `page=100` fails. **Partition by region/field/date** for full coverage |
| Facet cap | `arbeitgeber` facet returns the **top 100** employers only |
| Detail 404s | ~75% of June-snapshot refnrs are already expired |
| Refnr format change | June: `17102-44225539-65-S`; August: `13669-YHFM6UDDIG6TAMA6-S`. **Join on employer hash, not refnr** |
| Hash coverage | `arbeitgeberKundennummerHash` present on ~77% of live postings |
| TLS | Must disable verification |
| Politeness | ~0.19 s/request. Cap concurrency at 8–16, cache to disk, don't hammer a public service |

Useful `berufsfeld` values and their live open counts **[measured 2026-08-28]**:
`Informatik` 7,571 · `IT-Netzwerktechnik, -Administration, -Organisation` 7,364 ·
`Softwareentwicklung und Programmierung` 4,651 · `IT-Systemanalyse, -Anwendungsberatung und
-Vertrieb` 3,690 → **~23,300 core IT of 820,657 total open**.

---

## Appendix B — Numbers you can quote

| Metric | Value |
| --- | --- |
| Dataset rows / unique employers | 70,584 / 19,943 |
| `description_derived` null rate | **100%** |
| `seniority` = unknown | 88.0% |
| Employers with ≥5 postings | 2,534 (63.2% of all postings) |
| IT postings (KldB `43%`) | 7,136 (10.1%), 3,001 employers |
| IT employers with ≥10 postings | **93** |
| IT postings flagged agency (name regex) | 21.3% |
| Live IT postings from agencies (API facets) | 34% (`zeitarbeit` 23.4% + `pav` 10.8%) |
| Snapshot fetch window | 2 hours, 2026-06-05/06 |
| `posted_date` 2026-05 vs 2026-04 | 22,141 vs 7,522 (+194%, **artifact**) |
| Non-German rows (AT/CH) | 357 |
| Exact duplicate rows | 0 |
| Detail-API retro hit rate | ~25% |
| Description length | mean 3,063 / median 2,945 chars |
| Detail request latency | ~0.19 s |
| Live total open postings (all fields) | 820,657 |
| Germany's unfilled IT roles (Bitkom) | ~109,000 |

---

## Appendix C — Sources

**Dataset & taxonomies**
- [mischeiwiller/german-job-postings (Hugging Face)](https://huggingface.co/datasets/mischeiwiller/german-job-postings)
- [bundesAPI/jobsuche-api (unofficial BA API docs)](https://github.com/bundesAPI/jobsuche-api)
- [Klassifikation der Berufe 2010 — Wikipedia](https://de.wikipedia.org/wiki/Klassifikation_der_Berufe_2010)
- [KldB 2010 Anwenderhinweise — Bundesagentur für Arbeit](https://statistik.arbeitsagentur.de/DE/Statischer-Content/Grundlagen/Klassifikationen/Klassifikation-der-Berufe/KldB2010-erste-Fassung/Generische-Publikationen/Hinweise/Anwenderhinweise.pdf)
- [ESCO v1.2 classification](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-v12) · [ESCO API](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-api)

**Market & prior art**
- [Hiring Signals for B2B Sales — PredictLeads](https://blog.predictleads.com/2026/05/13/hiring-signals-b2b-sales-account-prioritization)
- [Best Job Posting Data Providers — Coresignal](https://coresignal.com/blog/best-job-posting-data-providers-comparison-and-use-cases/)
- [TheirStack vs PredictLeads](https://theirstack.com/en/comparisons/theirstack-vs-predictleads)
- [Sales Intelligence with Job Data — JobDataFeeds](https://jobdatafeeds.com/use-case/sales-intelligence)
- [Bitkom: Germany still lacks 100,000+ IT specialists](https://silicon-saxony.de/en/bitkom-germany-still-lacks-more-than-100000-it-specialists/)
- [Exploding gap of IT talent in Germany until 2040 — Deutscher Outsourcing Verband](https://outsourcing-verband.org/exploding-gap-of-it-talent-in-germany-until-2040/)
- [IT Job Market in Germany: Key Trends for 2026](https://andersenlab.com/blueprint/it-job-market-germany)

**Method**
- [Combining Embeddings and Domain Knowledge for Job Posting Duplicate Detection (arXiv)](https://arxiv.org/pdf/2406.06257)
- [EWMA of season-trend residuals for anomaly detection (IEEE)](https://ieeexplore.ieee.org/document/7729882/)
- [LLM-as-judge evaluation guide — Openlayer](https://www.openlayer.com/blog/llm-as-judge-evaluation-guide)
- [Evaluating LLM Citation & Attribution](https://futureagi.com/blog/evaluating-llm-citation-attribution-2026/)
- [Case-Aware LLM-as-a-Judge for Enterprise RAG (arXiv)](https://arxiv.org/pdf/2602.20379)

**Entity resolution & compliance**
- [Deutsches Handelsregister (OffeneRegister.de) — OpenSanctions](https://www.opensanctions.org/datasets/de_offeneregister/)
- [Germany Handelsregister: Complete Guide 2026](https://zephira.ai/germany-handelsregister-the-complete-guide-to-german-company-registry-data-in-2026/)
- [GDPR-Compliant Lead Generation](https://www.leadscraper.de/en/blog/gdpr-compliant-lead-generation)
- [GDPR and B2B Outreach: What You Can and Cannot Do in 2026](https://totalremoto.com/blog/gdpr-b2b-outreach-2026)

**Infrastructure**
- [Vertex AI batch predictions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/maas/capabilities/batch-prediction)
- [Batch embeddings inference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/batch-prediction-genai-embeddings)
- [Google Vertex AI pricing guide 2026](https://www.cloudzero.com/blog/google-vertex-ai-pricing/)

---

*Data attribution: job posting data © Bundesagentur für Arbeit, redistributed under CC-BY-4.0.*
