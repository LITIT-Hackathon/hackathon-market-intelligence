import { Screen, type Tab } from "../App";
import { Kpi, Kv, f0, f0c } from "../components/Kpi";
import type { Payload } from "../data";
import { fmt, pct1, pct2 } from "../format";

export function Quality({ data, on }: { data: Payload; on: Tab }) {
  const q = data.quality;
  const R = data.radar;
  const T = data.talent;
  const review = (q.classification.needs_review_examples || []).slice(0, 12);
  const variants = q.entity.largest_variant_clusters.slice(0, 10);
  const mix = q.seniority.derived_mix;
  const mixTotal = Object.values(mix).reduce((a, b) => a + b, 0);
  const senKnown = (1 - (mix.unknown || 0) / Math.max(mixTotal, 1)) * 100;
  const gt = T?.quality;

  return (
    <Screen id="quality" group="method" on={on}>
      <p className="label">How it works</p>
      <h2>How the list<br />is built</h2>
      <p className="lede">Four things about each company decide its position: how long its IT roles
        have stayed unfilled, how many are senior, whether the hiring is focused on one
        technology, and whether it is still posting. Companies are compared only against each
        other, so a score means "compared with the rest of this list". Nothing is guessed &mdash;
        every number traces to real job ads.</p>

      {R && (
        <>
          <div className="kpis">
            <Kpi label="Not just counting job ads" v={R.validation.v1_rho.toFixed(2)}
              n={<>0 = completely different from ranking by number of ads, 1 = identical.
                Lower is better &mdash; anyone can count ads.</>} />
            <Kpi label="Recruiters in the list" v={R.validation.v2 === "clean" ? "0" : R.validation.v2}
              n="Staffing agencies and our own group, filtered out. Should be zero." />
            <Kpi label="Ranking stability" v={`${R.validation.v3_min}/${R.validation.v3_k}`}
              n="Of the top 20, how many stay there when the four weightings are nudged up or down by a fifth." />
          </div>

          <details className="more">
            <summary>More checks</summary>
            <div className="kpis">
              <Kpi label="Agencies and vendors filtered out" v={fmt(R.meta.channels)}
                n={<>No job ad posted in 90 days &mdash; probably abandoned listings.</>} />
            </div>
          </details>

          <p className="hint spaced">Same data in, same list out &mdash; settings
            fingerprint <code>{R.meta.config_hash}</code>.</p>
        </>
      )}

      <h3 className="tight">What to distrust</h3>
      <p className="lede">The parser reports its own weak spots. Read this before quoting any number
        from the other screens.</p>

      <div className="q">
        <div className="panel">
          <p className="label">Entity resolution</p><h3>Name → company</h3>
          <p className="hint">Exact grouping on the normalised name. Fuzzy merging is off by default —
            over-merging invents companies that do not exist.</p>
          <Kv rows={[
            ["Raw employer strings", fmt(q.entity.raw_employer_strings)],
            ["Resolved entities", fmt(q.entity.resolved_entities)],
            ["Collapsed", pct1(q.entity.collapse_ratio)],
            ["Companies with >1 name variant", fmt(q.entity.companies_with_multiple_name_variants)],
          ]} />
        </div>
        <div className="panel">
          <p className="label">Classification</p><h3>Client vs competitor</h3>
          <p className="hint">Keyword rules. Precision has not been measured against hand labels yet.</p>
          <Kv rows={[
            ["Competitor companies", fmt(q.classification.competitor_companies)],
            ["Competitor postings", fmt(q.classification.competitor_postings)],
            ["Competitor share of all postings", pct1(q.classification.competitor_posting_share)],
            ["Noise companies", fmt(q.classification.noise_companies)],
            ["Flagged for review", fmt(q.classification.needs_review)],
          ]} />
        </div>
        <div className="panel">
          <p className="label">Coverage</p><h3>How much signal exists</h3>
          <p className="hint">Titles name roles, not stacks. These numbers rise once job descriptions are fetched.</p>
          <Kv rows={[
            ["Technology signal, all postings", pct1(q.technology.tech_coverage)],
            ["Technology signal, IT postings", pct1(q.technology.it_tech_coverage)],
            ["Seniority known", senKnown.toFixed(1) + "%"],
            ["Dataset seniority unknown", pct1(q.seniority.raw_unknown_share)],
          ]} />
        </div>
        <div className="panel">
          <p className="label">Completeness</p><h3>Null rates by column</h3>
          <Kv rows={Object.entries(q.nulls).map(([k, v]) => [k, pct2(v)])} />
        </div>
        <div className="panel span2">
          <p className="label">Review queue</p><h3>The rules could not decide</h3>
          <p className="hint">High volume across unrelated sectors and many regions, but no agency keyword in the
            name. That is the fingerprint of a staffing firm — and of a large diversified employer.
            Flagged rather than guessed.</p>
          <Kv rows={review.map((r) => [r.company, `${fmt(r.postings)} postings · ${r.sectors} sectors · ${r.regions} regions`])} />
        </div>
        <div className="panel">
          <p className="label">Merges</p><h3>Largest name-variant clusters</h3>
          <p className="hint">Worth spot-checking: these are the entities where resolution did the most work.</p>
          <Kv rows={variants.map((c) => [c.company, c.variants.length])} />
        </div>
        {gt && (
          <div className="panel span2">
            <p className="label">Candidate dataset</p><h3>Its "ground truth" is not ground truth</h3>
            <p className="hint">The benchmark ships 30 relevant candidates per opening. Recomputing the
              rule it documents shows those 30 are an arbitrary slice of a far larger qualified set,
              and that seniority is ignored completely.</p>
            <Kv rows={[
              ["Labelled pairs", fmt(gt.labelled_pairs)],
              ["Labels per opening", `${f0(gt.labels_per_opening.mean)} (fixed)`],
              ["Satisfy the documented rule", pct1(gt.satisfy_documented_rule)],
              ["Mean qualified pool", f0c(gt.mean_qualified_pool)],
              ["Share of pool that is labelled", pct1(gt.labelled_share_of_pool)],
              ["Labels matching the opening's seniority", `${pct1(gt.same_seniority)} (random ~33%)`],
              ["Labels matching the opening's role", `${pct1(gt.same_role)} (random ~4%)`],
            ]} />
            <div className="note after"><b>Do not report retrieval precision against
              these labels.</b> Unlabelled correct answers are everywhere, so an honest matcher will
              look wrong.</div>
          </div>
        )}
        <div className="panel wide">
          <p className="label">Known limits</p><h3>Read before quoting anything</h3>
          <ul className="lim">
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
    </Screen>
  );
}
