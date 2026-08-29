import { Screen, type Tab } from "../App";
import { AiButton } from "../components/Ai";
import { Kpi, f0 } from "../components/Kpi";
import type { Brief as BriefData, CohortRow } from "../data";

/* Everything on this tab comes from briefing.json, which is computed in pandas
   by `opradar.brief`. No number here was produced by a model -- the narrator,
   when present, may only re-word the figures, never extend them. */

function Cohort({ id, title, n, hint, rows, fmt, lead }: {
  id: string; title: string; n: number; hint: string; rows: CohortRow[];
  fmt: (r: CohortRow) => string; lead?: boolean;
}) {
  return (
    <div className={lead ? "bf-co lead" : "bf-co"}>
      <h3>{title}</h3>
      <p className="n num">{n}</p>
      <p className="hint">{hint}</p>
      {rows.map((r, i) => (
        <div className="bf-row" key={i}><span>{r.name}</span><b>{fmt(r)}</b></div>
      ))}
      {n > 0 && <AiButton task="cohort" args={{ cohort: id }} small
        label={`What "${title.toLowerCase()}" means this week`} />}
    </div>
  );
}

function Bars({ items, unit = "" }: { items: { name: string; weight: number }[]; unit?: string }) {
  if (!items.length) return null;
  const top = Math.max(...items.map((i) => i.weight)) || 1;
  return (
    <>
      {items.map((i, k) => (
        <div className="bf-bar" key={k}>
          <span className="t">{i.name}</span>
          <span className="track"><span className="fill" style={{ width: `${Math.max(2, Math.round((100 * i.weight) / top))}%` }} /></span>
          <span className="v">{f0(i.weight)}{unit}</span>
        </div>
      ))}
    </>
  );
}

export function Brief({ b, on }: { b: BriefData; on: Tab }) {
  const c = b.cohorts, ours = b.ours, dem = b.demand;
  const extracted = ours.ads_read_in_full || 0;

  return (
    <Screen id="brief" group="brief" on={on}>
      <div className="bf-head">
        <p className="label" style={{ margin: 0 }}>Market briefing</p>
        <span className="bf-when"><b>{b.crawl_date}</b> crawl <i>&rarr;</i>{" "}
          <b>{b.board_date}</b> board</span>
      </div>
      {/* Generated prose, and the only prose left on this screen. Without a
          narration file there is nothing to say here that the figures below
          do not already say. */}
      {b.narration && (
        <>
          {b.narration.paragraphs.map((p, i) => (
            <p className="lede" style={{ marginBottom: "var(--s3)" }} key={i}>{p}</p>
          ))}
          <p className="bf-byline">Written by {b.narration.model} from the figures on this page,
            which were counted in pandas. The narrator cannot see the
            postings and cannot state a number that is not below it.</p>
        </>
      )}

      <div className="kpis">
        <Kpi label="Re-observed today" v={c.observed_n} n={`of ${ours.companies_ranked} ranked companies`} />
        <Kpi hl label="Stalled" v={c.stalled_n} n="open roles, nothing new posted" />
        <Kpi label="Accelerating" v={c.accelerating_n} n="posted again in the last four weeks" />
        <Kpi label="Roles our bench covers" v={f0(ours.roles_our_bench_covers)}
          n={`of ${ours.roles_live_in_our_crawl} still live, across ${ours.companies_with_live_roles} companies`} />
      </div>

      <div className="bf-calls">
        <span className="label">Call these this week</span>
        {b.calls.map((k, i) => (
          <div className="bf-call" key={i}>
            <span className="bf-rk">{k.rank}</span>
            <div>
              <h4>{k.name}</h4><p>{k.why}</p>
              {/* The sentence above is a template built in pandas. This writes
                  the actual approach, and says which channels are legal. */}
              <AiButton task="outreach" args={{ company: k.name }} small
                label="Prepare this call" />
            </div>
          </div>
        ))}
      </div>

      <p className="label" style={{ marginBottom: "var(--s3)" }}>What each company is doing</p>
      <div className="bf-grid">
        <Cohort id="stalled" title="Stalled" n={c.stalled_n} lead
          hint="Stopped advertising and filled nothing. Every role still open has been open over a month — they gave up on the board, not on the need."
          rows={c.stalled} fmt={(r) => `${r.now_it_stock} open · all aged`} />
        <Cohort id="accelerating" title="Accelerating" n={c.accelerating_n}
          hint="Posting new IT roles in the last four weeks, on top of what was already open."
          rows={c.accelerating} fmt={(r) => `+${r.now_it_flow_28} in 28d`} />
        <Cohort id="quiet" title="Gone quiet" n={c.quiet_n}
          hint="Had IT demand when we crawled, nothing new on the board since. Either solved it or stopped looking here."
          rows={c.quiet} fmt={(r) => `${r.it_n} in June → ${r.now_it_stock}`} />
        <Cohort id="stuck" title="Stuck" n={c.stuck_n}
          hint="Still advertising, still not filling: four in five of their open roles have been up over a month."
          rows={c.stuck} fmt={(r) => `${r.now_aged_open}/${r.now_it_stock} aged`} />
      </div>

      <div className="bf-grid">
        <div className="bf-co"><h3>Where the demand sits</h3>
          <p className="hint">Opportunity-weighted, so a role at a company that cannot
            fill anything counts for more than one at a company that can.</p>
          <Bars items={dem.tech.slice(0, 7)} /></div>
        <div className="bf-co"><h3>Which roles</h3>
          <p className="hint">The same weighting, by role family rather than technology.</p>
          <Bars items={dem.families.slice(0, 7)} /></div>
        <div className="bf-co"><h3>Our side of it</h3>
          <p className="hint">What we hold advertisements for, and how much of it our
            bench could actually take.</p>
          <div className="bf-row"><span>Roles still live in our crawl</span>
            <b>{ours.roles_live_in_our_crawl}</b></div>
          <div className="bf-row"><span>Of those, our bench covers</span>
            <b>{ours.roles_our_bench_covers}</b></div>
          <div className="bf-row"><span>Companies with nothing left to staff</span>
            <b>{ours.companies_with_nothing_to_staff}</b></div>
          <p className="bf-note">
            {extracted ? (
              <>{extracted} advertisements read in full — {ours.ads_saying_they_buy_external_help || 0} of them say they already buy external
                help, {ours.ads_with_a_blocker_we_cannot_meet || 0} carry a requirement we could not meet.</>
            ) : (
              <>Advertisement text has not been read yet. Run <code>python -m opradar.enrich extract</code> to add project phase,
                buying signals and blockers to this briefing.</>
            )}
          </p></div>
      </div>

      <p className="bf-note">Counted from the {b.crawl_date} crawl and the
        {" "}{b.board_date} board. Companies the live board could not match are absent
        rather than assumed — {ours.companies_ranked - c.observed_n} of the
        {" "}{ours.companies_ranked} ranked companies have only one observation, so nothing on
        this page claims to know whether they changed.</p>
    </Screen>
  );
}
