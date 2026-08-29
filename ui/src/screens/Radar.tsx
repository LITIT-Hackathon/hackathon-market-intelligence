import { useCallback, useMemo, useState, type ReactNode } from "react";
import { Screen, type Tab } from "../App";
import { Count, DataTable, type Column } from "../components/DataTable";
import { indexer, type Radar as RadarData, type Row, type TimelineAd } from "../data";
import { fmt, plural } from "../format";
import { Timeline } from "./Timeline";

/* Live weights over the scorer's own arithmetic: six effective signals
   (already shrunk toward the pool prior by their evidence weights),
   combined as a weighted GEOMETRIC mean, then read as a percentile inside
   the pool. Reproducing it here rather than approximating it means the
   sliders move the real ranking, not a second looser model. */
const SIG = ["unmet", "expansion", "programme", "seniority", "svcsig", "dealsig"] as const;
type Sig = (typeof SIG)[number];
const OURS: Sig[] = ["svcsig", "dealsig"];        /* our side of the trade */
const MARKET: Sig[] = SIG.filter((k) => OURS.indexOf(k) < 0);
const WKEY: Partial<Record<Sig, string>> = { svcsig: "serviceability", dealsig: "dealsize" };
const SLIDER: Record<Sig, string> = {
  unmet: "Roles they cannot fill",
  expansion: "Hiring above their own baseline",
  programme: "One programme, not scattered backfill",
  seniority: "Senior roles they cannot fill",
  svcsig: "How much of it we could staff",
  dealsig: "How many people we could place at once",
};
const NEEDMIX: [Sig, string][] = [
  ["unmet", "Roles they cannot fill"],
  ["expansion", "Hiring above their own baseline"],
  ["programme", "One programme, not scattered backfill"],
  ["seniority", "Senior roles they cannot fill"],
];
type Weights = Record<Sig, number>;

/* Serviceability in words. The number is a ratio nobody reads correctly;
   the label is what a salesperson actually needs. */
const staffLabel = (v: number) =>
  v >= 0.8 ? "nearly all of it"
    : v >= 0.6 ? "most of it"
    : v >= 0.35 ? "about half"
    : v > 0 ? "only part of it"
    : "none of it";

/* Everything on a row is a percentile of this pool, including the two
   meters. Raw geometric means are tiny and incomparable -- "Demand 15"
   beside "Score 91" reads as a bug, when both describe the same company. */
function rank01(rows: Row[], fn: (r: Row) => number): Map<Row, number> {
  const xs = rows.map((r) => [r, fn(r)] as const).sort((a, b) => a[1] - b[1]);
  const m = new Map<Row, number>();
  xs.forEach(([r], i) => m.set(r, xs.length > 1 ? Math.round((1000 * i) / (xs.length - 1)) / 10 : 100));
  return m;
}

function Meter({ cls, label, pct }: { cls: string; label: string; pct: number }) {
  const w = Math.max(1.5, Math.min(100, pct));
  return (
    <span className={`sigrow ${cls}`}>
      <span className="k">{label}</span>
      <span className="t"><i style={{ width: `${w.toFixed(1)}%` }} /></span>
      <span className="n">{Math.round(pct)}</span>
    </span>
  );
}

function Tile({ k, v, cls }: { k: string; v: ReactNode; cls?: string }) {
  return <div className={`tile ${cls || ""}`}><p className="k">{k}</p><p className="v">{v}</p></div>;
}

function MixRow({ cls, label, frac }: { cls: string; label: string; frac: number }) {
  return (
    <div className={`mixrow ${cls}`}>
      <span className="k">{label}</span>
      <span className="t"><i style={{ width: `${Math.max(1.5, frac * 100).toFixed(1)}%` }} /></span>
      <span className="n">{Math.round(frac * 100)}</span>
    </div>
  );
}

export function Radar({ R, on }: { R: RadarData; on: Tab }) {
  const rx = useMemo(() => indexer(R.cols), [R]);
  const FLOOR = R.meta.floor || 0.05;
  const W0 = useMemo<Weights>(() => {
    const w = {} as Weights;
    SIG.forEach((k) => (w[k] = Math.round((R.meta.weights[WKEY[k] || k] || 0) * 100)));
    return w;
  }, [R]);
  const [W, setW] = useState<Weights>(W0);
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [band, setBand] = useState("");
  const [noRev, setNoRev] = useState(false);
  const [openKey, setOpenKey] = useState<string | null>(null);

  const { oppOf, demandOf, reachOf } = useMemo(() => {
    const gmean = (r: Row, keys: readonly Sig[]) => {
      let tw = 0, acc = 0;
      keys.forEach((k) => {
        const w = W[k];
        if (!w) return;
        tw += w;
        acc += w * Math.log(Math.max(FLOOR, rx<number>(k)(r)));
      });
      return tw ? Math.exp(acc / tw) : 0;
    };
    const PCT = rank01(R.rows, (r) => gmean(r, SIG));
    /* the market's four signals on their own -- the half of the score that has
       nothing to do with us */
    const PDEM = rank01(R.rows, (r) => gmean(r, MARKET));
    const PREACH = rank01(R.rows, (r) => gmean(r, OURS));
    return {
      oppOf: (r: Row) => PCT.get(r) ?? 0,
      demandOf: (r: Row) => PDEM.get(r) ?? 0,
      reachOf: (r: Row) => PREACH.get(r) ?? 0,
    };
  }, [R, rx, W, FLOOR]);

  const name = rx<string>("name");
  const rows = useMemo(() => {
    const segment = rx<string>("segment");
    const bandOf = rx<string>("band");
    const review = rx<boolean>("review");
    const qq = q.trim().toLowerCase();
    return R.rows.filter((r) =>
      (!qq || name(r).toLowerCase().includes(qq))
      && (!cls || segment(r) === cls)
      && (!band || bandOf(r) === band)
      && (!noRev || !review(r)));
  }, [R, rx, name, q, cls, band, noRev]);

  /* headline numbers describe what is on screen -- a header saying 306
     above a list of 109 reads as a bug to anyone who is not us */
  const sum = (k: string) => rows.reduce((a, r) => a + rx<number>(k)(r), 0);

  const columns = useMemo<Column<Row>[]>(() => {
    const review = rx<boolean>("review");
    const bandOf = rx<string>("band");
    const verified = rx<boolean>("verified");
    const covered = rx<number>("covered");
    const uncovered = rx<number>("uncovered");
    const techs = rx<string[]>("techs");
    const itN = rx<number>("it_n"), deadN = rx<number>("dead_n"), open45 = rx<number>("open45");
    const seniorN = rx<number>("senior_n");
    const nowStock = rx<number | null>("now_stock"), nowAged = rx<number | null>("now_aged");
    const svc = rx<number>("svc");

    /* One plain-English line describing what is happening at this company.
       Non-technical readers get the story here; the numbers are the columns. */
    const plain = (r: Row) => {
      const it = itN(r), dead = deadN(r) || 0, up = it - dead;
      const o45 = open45(r);
      const sen = seniorN(r), t = techs(r);
      const stock = nowStock(r), aged = nowAged(r);
      const bits: string[] = [];
      /* Where the live board answered, lead with what is open TODAY: the
         snapshot is a June crawl and its counts are three months stale. */
      if (verified(r) && stock !== null && stock !== undefined) {
        bits.push(`${plural(stock, "IT role", "IT roles")} open on the board today`);
        if (aged) bits.push(`${aged} of them for over a month`);
      } else {
        bits.push(`${plural(up, "IT role", "IT roles")} still up`);
        if (dead) bits.push(`${dead} already taken down`);
        if (o45) bits.push(`${o45} open over 6 weeks`);
      }
      if (sen) bits.push(`${plural(sen, "is senior", "are senior")}`);
      let s = bits.join(", ") + ".";
      if (t.length) s += ` Mostly ${t.slice(0, 2).join(" and ")}.`;
      const v = svc(r);
      if (v < 0.5) s += ` We could only staff ${staffLabel(v)}.`;
      return s;
    };

    return [
      { t: "#", v: (r) => Math.round(oppOf(r)), r: true, render: (_r, pos) => <span className="rk">{pos}</span> },
      {
        t: "Company", v: name, cls: "nm", render: (r) => (
          <>
            <span className="cname">{name(r)}</span>
            {review(r) && <> <span className="tag warn" title="We could not confirm from the data whether this is a customer or an IT supplier. Check before calling.">unconfirmed</span></>}
            {bandOf(r) === "low" && <> <span className="tag" title="Based on only a few job ads">thin evidence</span></>}
            {verified(r) && <> <span className="tag pub" title="Re-observed on the Bundesagentur board today: open roles, posting flow and agency flags all come from the source rather than from our inference">live-checked</span></>}
            {/* Every advertisement we hold for this company has since been taken
                down, so there is no role here we could name or staff today. Say
                so on the ROW: it is the single fact that decides whether the lead
                is callable, and it must not be something you discover only after
                opening the panel. */}
            {covered(r) + uncovered(r) === 0 && <> <span className="tag gone" title="Every job ad we hold for this company has since been delisted. The demand signals may still be strong, but we cannot name a role to pitch until this company is crawled again.">nothing to staff</span></>}
            <span className="csub">{plain(r)}</span>
            <span className="cchips">
              {techs(r).slice(0, 3).map((t, i) => <span className="chip" key={i}>{t}</span>)}
            </span>
          </>
        ),
      },
      {
        t: "Demand · we staff", v: demandOf, cls: "sg", render: (r) => (
          <span className="sig">
            <Meter cls="" label="Demand" pct={demandOf(r)} />
            <Meter cls="sup" label="We staff" pct={reachOf(r)} />
          </span>
        ),
      },
      {
        t: "Score /100", v: oppOf, r: true, render: (r) => {
          const v = oppOf(r);
          return (
            <span className="scorecell">
              <span className="scoren">{Math.round(v)}</span>
              <span className="scoremeter"><i style={{ height: `${Math.max(4, Math.min(100, v)).toFixed(0)}%` }} /></span>
              <span className="exp"></span>
            </span>
          );
        },
      },
    ];
  }, [rx, name, oppOf, demandOf, reachOf]);

  const setWeight = (k: Sig, v: number) => {
    setW((w) => ({ ...w, [k]: v }));
    setOpenKey(null);
  };
  const reset = () => { setW(W0); setOpenKey(null); };

  const rowClass = useCallback((r: Row) => (name(r) === openKey ? "clickable open" : "clickable"), [name, openKey]);
  const onRowClick = useCallback((r: Row) => {
    const key = name(r);
    setOpenKey((k) => (k === key ? null : key));
  }, [name]);
  const expanded = useCallback((r: Row) => (name(r) === openKey ? <Detail r={r} rx={rx} /> : null), [name, openKey, rx]);

  return (
    <Screen id="radar" group="radar" on={on}>
      <p className="label">Opportunities &middot; demand matched to people</p>
      <h2>Who to call,<br />and why</h2>
      <p className="lede">Both halves of the product in one list. We find German companies that
        cannot fill their IT roles, then check each one against the people we could actually
        put on the work &mdash; so the top of this list is not just who is struggling, but who
        is struggling <em>with work we can take</em>. Every company scores out of 100, judged
        against the others here. Click any row for the real job ads behind it.</p>

      <div className="kpis">
        <div className="kpi hl"><p className="label">Companies worth calling</p><p className="v num" id="k-ranked">{fmt(rows.length)}</p><p className="n">ranked below, best first</p></div>
        <div className="kpi"><p className="label">IT roles they cannot fill</p><p className="v num" id="k-roles">{fmt(sum("it_n"))}</p><p className="n">open right now across all of them</p></div>
        <div className="kpi"><p className="label">Open over 6 weeks</p><p className="v num" id="k-stuck">{fmt(sum("open45"))}</p><p className="n">still not filled after six weeks</p></div>
      </div>

      <div className="controls stick">
        <input type="search" id="ra-q" placeholder="Search for a company..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select id="ra-class" value={cls} onChange={(e) => setCls(e.target.value)}>
          <option value="">Every type of company</option>
          <option value="end_client">Businesses</option>
          <option value="public_sector">Public sector</option>
          <option value="captive_it">In-house IT arms</option>
        </select>
        <select id="ra-band" value={band} onChange={(e) => setBand(e.target.value)}>
          <option value="">Any amount of evidence</option>
          <option value="high">Strong evidence</option>
          <option value="medium">Some evidence</option>
          <option value="low">Thin evidence</option>
        </select>
        <label className="chk"><input type="checkbox" id="ra-noreview" checked={noRev} onChange={(e) => setNoRev(e.target.checked)} /> Only externally verified</label>
        <Count id="ra-count" n={rows.length} total={R.rows.length} noun="companies" />
      </div>
      <DataTable columns={columns} rows={rows} sort={3} dir={-1} bodyId="ra-body"
        rowClass={rowClass} onRowClick={onRowClick} expanded={expanded} />

      <details className="adv">
        <summary>Advanced &mdash; change what counts as a good lead</summary>
        <p className="hint">Drag a slider and the ranking re-sorts instantly. Nothing is hardcoded:
          these four things are what decide the order.</p>
        <div className="sliders">
          {SIG.map((k) => (
            <label key={k}>{SLIDER[k]}{" "}
              <input type="range" id={"w-" + k} min="0" max="50" value={W[k]} onChange={(e) => setWeight(k, +e.target.value)} />
              <b id={"wv-" + k}>{W[k]}</b>
            </label>
          ))}
          <button id="w-reset" className="resetbtn" onClick={reset}>Reset</button>
        </div>
      </details>

      <div className="note after"><b>How to read a row.</b> Each row carries two meters.
        {" "}<em>Demand</em> combines the four market signals — unfilled roles, hiring above their
        own baseline, one concentrated programme, and seniority; <em>We staff</em> is how much
        of that demand our bench could take &mdash; both how well we fit it and how many people
        we could place at once, because a one-person contract is not really a contract. The score is the two combined and then
        read as a percentile of this pool, so 87 means ahead of 87% of the companies here.
        A company with demand we cannot serve does not reach the top. Click any row for the whole
        breakdown &mdash; the four things behind Demand, what we bring against them, and the
        real job ads on arbeitsagentur.de. <em>unconfirmed</em> marks companies the keyword
        rules could not classify as customer or supplier; their confidence is already
        discounted, but check before calling.</div>
    </Screen>
  );
}

/* ---- the detail tier: every number the collapsed row left out ---- */
function Detail({ r, rx }: { r: Row; rx: ReturnType<typeof indexer> }) {
  const dead = rx<number>("dead_n")(r) || 0, live = rx<number>("it_n")(r) - dead;
  const o45 = rx<number>("open45")(r), sen = rx<number>("senior_n")(r);
  const cov = rx<number>("covered")(r), tot = cov + rx<number>("uncovered")(r);
  const unc = rx<Record<string, number>>("uncovered_families")(r);
  const techs = rx<string[]>("techs")(r);
  const verified = rx<boolean>("verified")(r);
  const stock = rx<number | null>("now_stock")(r), aged = rx<number | null>("now_aged")(r);
  const svc = rx<number>("svc")(r), deal = rx<number>("deal")(r), placeable = rx<number>("placeable")(r);
  const tl = rx<TimelineAd[]>("timeline")(r);

  /* Plain reasons, driven by the same percentiles that drive the score. */
  const dem: string[] = [], sup: string[] = [];
  if (rx<number>("unmet")(r) >= 0.6)
    dem.push("A high share of their IT ads is still sitting unfilled — demand they cannot close on their own.");
  else if (o45)
    dem.push(`${plural(o45, "role has", "roles have")} been open more than 6 weeks.`);
  if (rx<number>("expansion")(r) >= 0.6)
    dem.push("They are hiring well above their own recent baseline — this is growth, not backfill.");
  if (rx<number>("programme")(r) >= 0.6 && techs.length)
    dem.push(`Hiring is concentrated in ${techs[0]} far past what a company this size would do by chance — that is one programme, not routine churn.`);
  if (rx<number>("seniority")(r) >= 0.6 && sen)
    dem.push(`Heavy on senior and lead roles (${sen}) — the hardest and slowest to hire.`);
  if (!dem.length)
    dem.push("Steady IT hiring, but nothing unusual about the pattern.");
  /* Staffing bullet: counts only roles still up (delisted ads are not
     demand anyone can staff), and explains depth instead of contradicting
     the "Can we staff it" column. */
  if (!tot)
    sup.push("Every ad they were running has since been taken down — nothing left to staff today.");
  else if (cov === tot && svc >= 0.8)
    sup.push(`Our bench covers all ${plural(tot, "role still up", "roles still up")}, with depth behind them.`);
  else if (cov === tot)
    sup.push(`Someone on our bench fits each of the ${tot} roles still up, but depth is thin in places.`);
  else
    sup.push(`Our bench could cover ${cov} of the ${tot} roles still up.`);
  /* Deal size: more people on one contract is a different kind of deal. */
  if (deal >= 0.95)
    sup.push(`Team-sized: enough staffable roles here to place about ${Math.round(placeable)} people at once, not one.`);
  else if (tot && placeable < 1.2)
    sup.push("Thin deal — about one placeable role, which is a body-shop order rather than a project.");

  /* Two different observations, labelled as such. The board is today and it
     is what the score rests on; the crawl is June and it is the only thing
     we hold clickable URLs for. Showing one without the other is what makes
     "99/100" beside eight dead links look like a bug. */
  const hasBoard = verified && stock !== null && stock !== undefined;
  return (
    <div className="ex">
      <div className="extiles">
        {hasBoard && (
          <>
            <Tile k="Open on the board today" v={stock} cls={stock ? "acc" : "zero"} />
            <Tile k="Open there over a month" v={aged || 0} cls={aged ? "acc" : "zero"} />
          </>
        )}
        <Tile k="From our crawl, still up" v={live} cls={live ? "" : "zero"} />
        <Tile k="From our crawl, taken down" v={dead} cls={dead ? "" : "zero"} />
        <Tile k="Open 6+ weeks at crawl" v={o45} cls={o45 ? "" : "zero"} />
        <Tile k="Senior or lead" v={sen} cls={sen ? "" : "zero"} />
        <Tile k="Typical age" v={<>{rx<number>("median_age")(r)}<span className="sfx">days</span></>} />
        {tot === 0
          ? <Tile k="Roles we could fill" v="none" cls="zero" />
          : <Tile k="Roles we could fill" v={<>{cov}<span className="sfx">of {tot}</span></>} cls="acc" />}
        <Tile k="People we could place" v={placeable.toFixed(1)} cls="acc" />
      </div>
      <div className="excols">
        <div>
          <p className="evhead">Why this company</p>
          <ul className="why">
            {dem.map((t, i) => <li key={"d" + i}>{t}</li>)}
            {sup.map((t, i) => <li className="sup" key={"s" + i}>{t}</li>)}
          </ul>
        </div>
        <div>
          <p className="evhead">What the market is doing <span className="sfx">percentile vs the rest of this list</span></p>
          <div className="mix">
            {NEEDMIX.map(([k, label]) => <MixRow cls="" label={label} frac={rx<number>(k)(r)} key={k} />)}
          </div>
          <p className="evhead">What we bring</p>
          <div className="mix">
            <MixRow cls="sup" label="Depth of bench behind those roles" frac={svc} />
            <MixRow cls="sup" label="Deal size — people we could place at once" frac={deal} />
          </div>
          {Object.keys(unc).length > 0 && (
            <p className="uncov"><b>We cannot staff:</b>{" "}
              {Object.entries(unc).map(([k, v]) => <span className="chip" key={k}>{k} ×{v}</span>)}
              {" "}not skills our bench carries today.</p>
          )}
        </div>
      </div>
      <p className="evhead">Open roles over time
        <span className="sfx">from the June crawl &mdash; hover the line to see which</span></p>
      <Timeline tl={tl} />
    </div>
  );
}
