import { useCallback, useMemo, useState, type ReactNode } from "react";
import { Screen, type Tab } from "../App";
import { AiButton } from "../components/Ai";
import { Count, DataTable, type Column } from "../components/DataTable";
import { indexer, type Radar as RadarData, type Row, type TimelineAd } from "../data";
import { fmt, plural } from "../format";
import { Timeline } from "./Timeline";

/* Live weights over the scorer's own arithmetic: six effective signals
   (already shrunk toward the pool prior by their evidence weights),
   combined as a weighted GEOMETRIC mean, then read as an ABSOLUTE position
   on the model's own log scale. Reproducing it here rather than
   approximating it means the sliders move the real ranking, not a second
   looser model. */
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
/* The sliders are split the way the score is: four things about the market,
   two about us. Unlabelled, a reader cannot tell which half they are moving. */
const SIDES: [string, string, Sig[]][] = [
  ["What they need", "measured from the German job board", MARKET],
  ["What we can bring", "measured against our bench", OURS],
];
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

/* Every number on a row -- the score and both meters -- is an ABSOLUTE
   position on the same scale, read the way the scorer reads it.

   A weighted geometric mean of signals that each live in [floor, 1] lives in
   [floor, 1] too, and both ends mean something: the floor is a company that
   fails every part as hard as the model allows, 1 is a company that is
   perfect on all of them at once. The score is the position between them, on
   the log scale the model actually multiplies in.

   This replaced a percentile of the visible rows, which printed a 100 and a 0
   for the best and worst row no matter what they scored, moved every number
   whenever a filter changed the pool, and made the two meters incomparable
   with each other. Nobody reaches 100: the market signals are built from
   saturating and logistic terms that approach 1 without arriving. */
const position = (p: number, floor: number) =>
  100 * (1 + Math.log(Math.max(p, floor)) / -Math.log(floor));

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

function Tile({ k, v, cls, hint }: { k: string; v: ReactNode; cls?: string; hint?: string }) {
  return (
    <div className={`tile ${cls || ""}`} title={hint}>
      <p className="k">{k}</p><p className="v">{v}</p>
    </div>
  );
}

/* One signal, on the same absolute scale as the score above it. `v` is the
   raw effective signal in [floor, 1]; `position` puts it where the score
   would put it, so a reader can add these up in their head instead of
   switching units halfway down the panel. */
function MixRow({ cls, label, v, floor }: { cls: string; label: string; v: number; floor: number }) {
  const pct = position(v, floor);
  return (
    <div className={`mixrow ${cls}`}>
      <span className="k">{label}</span>
      <span className="t"><i style={{ width: `${Math.max(1.5, pct).toFixed(1)}%` }} /></span>
      <span className="n">{Math.round(pct)}</span>
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
    /* the market's four signals on their own -- the half of the score that has
       nothing to do with us -- and our two, each read on the same scale as the
       score, so "their need 78, we could staff 91" is a sentence that means
       what it looks like it means */
    return {
      oppOf: (r: Row) => position(gmean(r, SIG), FLOOR),
      demandOf: (r: Row) => position(gmean(r, MARKET), FLOOR),
      reachOf: (r: Row) => position(gmean(r, OURS), FLOOR),
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

  /* What the analyst is asked to summarise: the rows the filters left, and a
     sentence naming the filter so the summary can say what it is describing. */
  const summaryArgs = useMemo(() => {
    const bits: string[] = [];
    if (q.trim()) bits.push(`matching "${q.trim()}"`);
    if (cls) bits.push(cls.replace(/_/g, " "));
    if (band) bits.push(`${band} evidence`);
    if (noRev) bits.push("externally verified only");
    return {
      companies: rows.map(name),
      label: bits.length ? `filtered to ${bits.join(", ")}` : "the whole ranked pool",
    };
  }, [rows, name, q, cls, band, noRev]);

  const stalePct = Math.round((R.meta.stale_weight ?? 0.5) * 100);

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
      const sen = seniorN(r);
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
      const v = svc(r);
      if (v < 0.5) s += ` We could only staff ${staffLabel(v)}.`;
      return s;
    };

    return [
      { t: "#", v: (r) => Math.round(oppOf(r)), r: true,
        help: "Position in this filtered list, best first. It moves when you change a filter or a weight slider.", render: (_r, pos) => <span className="rk">{pos}</span> },
      {
        t: "Company", v: name, cls: "nm",
        help: "The employer, and one plain sentence describing what they are doing on the job board right now. Badges flag anything that should change how you read the row.",
        render: (r) => (
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
            {covered(r) + uncovered(r) === 0 && <> <span className="tag gone" title={`Every job ad we hold for this company has since been delisted, so we cannot name a live role to pitch until it is crawled again. How much of their work our bench fits is measured on June's ads instead, carried at ${stalePct}% of a live reading, fitted from the companies where both can be measured. Deal size is not carried at all: the board reports how many roles are open, not what they are.`}>no live ad</span></>}
            <span className="csub">{plain(r)}</span>
            <span className="cchips">
              {techs(r).slice(0, 3).map((t, i) => <span className="chip" key={i}>{t}</span>)}
            </span>
          </>
        ),
      },
      {
        t: "Their need · what we could staff", v: demandOf, cls: "sg",
        help: "Two absolute scores on the same 0–100 scale, so they are directly comparable with each other and with the Score column. 0 is as bad as the model allows, 100 is perfect and unreachable. Their need combines the four market signals: unfilled roles, hiring above their own baseline, one concentrated programme, and seniority. What we could staff is how much of that work our bench could actually take. A company can score 80 on need and 30 on staffing; that is a lead we cannot serve.",
        render: (r) => (
          <span className="sig">
            <Meter cls="" label="Their need" pct={demandOf(r)} />
            <Meter cls="sup" label="We could staff" pct={reachOf(r)} />
          </span>
        ),
      },
      {
        t: "Score /100", v: oppOf, r: true,
        help: "Their need and What we could staff combined as a weighted geometric mean, then read as an absolute position between a company that fails every signal and one that is perfect on all six. Nobody scores 100 and nobody can: four of the six signals approach their maximum without ever reaching it. The best company here is in the 80s, and the number does not move when you filter the list.",
        render: (r) => {
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
  }, [rx, name, oppOf, demandOf, reachOf, stalePct]);

  /* what a slider is actually worth: its share of the total, which is what
     the geometric mean normalises by */
  const share = (k: Sig) => {
    const tw = SIG.reduce((a, x) => a + W[x], 0);
    return tw ? Math.round((100 * W[k]) / tw) : 0;
  };

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
  const expanded = useCallback((r: Row) => (name(r) === openKey ? <Detail r={r} rx={rx} floor={FLOOR} stalePct={stalePct} /> : null), [name, openKey, rx, FLOOR, stalePct]);

  return (
    <Screen id="radar" group="radar" on={on}>
      <p className="label">Opportunities &middot; demand matched to people</p>
      <div className="kpis slim">
        <div className="kpi hl"><p className="label">Companies worth calling</p><p className="v num" id="k-ranked">{fmt(rows.length)}</p><p className="n">ranked below, best first</p></div>
        <div className="kpi"><p className="label">IT roles they cannot fill</p><p className="v num" id="k-roles">{fmt(sum("it_n"))}</p><p className="n">open right now across all of them</p></div>
        <div className="kpi"><p className="label">Open over 6 weeks</p><p className="v num" id="k-stuck">{fmt(sum("open45"))}</p><p className="n">still not filled after six weeks</p></div>
      </div>

      {/* Everything you can change sits above the thing it changes. The
          weight sliders used to live below the table, so the control was off
          screen whenever the list it controlled was on it. */}
      <details className="adv">
        <summary>Change what makes a good lead &mdash; the list re-ranks as you drag</summary>
        <p className="hint">Each slider is how much of the 100-point score that one signal is
          allowed to award. Push it up and companies strong on that signal rise; drag it to
          zero and it stops counting entirely. The percentage beside each is its current share
          of the score. They start at the model&rsquo;s own weights.</p>
        <div className="sliders">
          {SIDES.map(([title, sub, keys]) => (
            <div className="sliderset" key={title}>
              <p className="k">{title}<span>{sub}</span></p>
              {keys.map((k) => (
                <label key={k}>
                  <span className="t">{SLIDER[k]}</span>
                  <input type="range" id={"w-" + k} min="0" max="50" value={W[k]}
                    onChange={(e) => setWeight(k, +e.target.value)} />
                  <b id={"wv-" + k}>{share(k)}%</b>
                </label>
              ))}
            </div>
          ))}
        </div>
        <button id="w-reset" className="resetbtn" onClick={reset}>Back to the model&rsquo;s weights</button>
      </details>

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
        <AiButton task="summary" args={summaryArgs} small
          label={`Summarise these ${rows.length}`} />
      </div>

      {/* This table is the product, not a panel on a page about the product. */}
      <DataTable columns={columns} rows={rows} sort={3} dir={-1} bodyId="ra-body"
        wrapClass="lead" rowClass={rowClass} onRowClick={onRowClick} expanded={expanded} />

    </Screen>
  );
}

/* ---- the detail tier: every number the collapsed row left out ---- */
function Detail({ r, rx, floor, stalePct }: { r: Row; rx: ReturnType<typeof indexer>; floor: number; stalePct: number }) {
  const company = rx<string>("name")(r);
  const dead = rx<number>("dead_n")(r) || 0, live = rx<number>("it_n")(r) - dead;
  const o45 = rx<number>("open45")(r), sen = rx<number>("senior_n")(r);
  const cov = rx<number>("covered")(r), tot = cov + rx<number>("uncovered")(r);
  /* What the bench signals were scored on. Where nothing we hold is still up,
     that is June's crawl at the fitted stale weight rather than a zero -- so the tiles
     must report the same rows the meters were computed from, or the panel
     contradicts the column beside it. */
  const snapBench = rx<boolean>("bench_snap")(r);
  const sCov = rx<number>("scored_cov")(r), sTot = rx<number>("scored_tot")(r);
  const asOf = snapBench ? " (June)" : "";
  const unc = rx<Record<string, number>>("uncovered_families")(r);
  const techs = rx<string[]>("techs")(r);
  const verified = rx<boolean>("verified")(r);
  const stock = rx<number | null>("now_stock")(r), aged = rx<number | null>("now_aged")(r);
  const svc = rx<number>("svc")(r), deal = rx<number>("deal")(r);
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
    sup.push(`Every ad they were running has since been taken down, so there is no live role to name. Judged on June's ${sTot} instead, carried at ${stalePct}% of a live reading: our bench fitted ${sCov} of them.`);
  else if (cov === tot && svc >= 0.8)
    sup.push(`Our bench covers all ${plural(tot, "role still up", "roles still up")}, with depth behind them.`);
  else if (cov === tot)
    sup.push(`Someone on our bench fits each of the ${tot} roles still up, but depth is thin in places.`);
  else
    sup.push(`Our bench could cover ${cov} of the ${tot} roles still up.`);
  /* Deal size: more people on one contract is a different kind of deal.
     Said in roles, which is a real count, not in the weighted sum behind the
     signal — that number is age x match-credit and is not a headcount, so
     printing it as "3.7 people" was a promise the arithmetic never made.
     Silent where nothing is live, because there the deal size is not
     something we measured: it is the pool prior standing in for it. */
  if (snapBench)
    sup.push("How large a deal that is, we cannot say — sizing it needs the roles themselves, and the board gives us only a count.");
  else if (deal >= 0.95)
    sup.push(`Team-sized: our bench fits ${sCov} of these roles, so this is a project to lead rather than one seat to fill.`);
  else if (tot && sCov <= 1)
    sup.push("Thin deal — one role we could fit, which is a body-shop order rather than a project.");

  /* Two different observations, labelled as such. The board is today and it
     is what the score rests on; the crawl is June and it is the only thing
     we hold clickable URLs for. Showing one without the other is what makes
     "99/100" beside eight dead links look like a bug. */
  const hasBoard = verified && stock !== null && stock !== undefined;
  return (
    <div className="ex">
      <div className="extiles">
        {/* Two different observations of two different things, which is why
            they do not agree: the board is this employer's WHOLE current IT
            listing, ours is what survives of the sample we crawled in June.
            They were two adjacent tiles of bare numbers and read as the same
            count twice, so the crawl is now one tile that states the fraction
            it is. */}
        {hasBoard && (
          <>
            <Tile k="Open on the board today" v={stock} cls={stock ? "acc" : "zero"}
              hint="Every IT role this employer has listed on arbeitsagentur.de right now, counted by the board itself. This is what the score rests on." />
            <Tile k="Of those, open over a month" v={aged || 0} cls={aged ? "acc" : "zero"}
              hint="The board's own count of how many of those roles were published more than a month ago and are still up — roles they have failed to fill." />
          </>
        )}
        <Tile k="Ads we crawled in June" v={<>{live}<span className="sfx">of {live + dead} still up</span></>}
          cls={live ? "" : "zero"}
          hint="Our own sample, from the 2026-06-06 crawl, re-checked since. These are the only ads we hold clickable links for, which is why the timeline below is drawn from them and not from the board. A smaller number than the board's is normal: the board is everything they have listed today, this is what is left of one crawl." />
        <Tile k="Open 6+ weeks at crawl" v={o45} cls={o45 ? "" : "zero"} />
        <Tile k="Senior or lead" v={sen} cls={sen ? "" : "zero"} />
        <Tile k="Typical age" v={<>{rx<number>("median_age")(r)}<span className="sfx">days</span></>} />
        {sTot === 0
          ? <Tile k="Roles our bench fits" v="none" cls="zero" />
          : <Tile k={"Roles our bench fits" + asOf} v={<>{sCov}<span className="sfx">of {sTot}</span></>}
              cls={sCov ? "acc" : "zero"}
              hint="How many of those roles at least one available consultant matches on role family, technology and seniority." />}
      </div>
      {/* Chart on the left, the reading of it on the right. The prose used to
          sit above the timeline, which left the reader scrolling between the
          claim and the evidence for it. */}
      <div className="exmain">
        <div className="extl">
          <p className="evhead">Open roles over time
            <span className="sfx">from the June crawl &mdash; hover the line to see which</span></p>
          <Timeline tl={tl} />
        </div>

        <div className="exwhy">
          <p className="evhead">Why this company</p>
          <ul className="why">
            {dem.map((t, i) => <li key={"d" + i}>{t}</li>)}
            {sup.map((t, i) => <li className="sup" key={"s" + i}>{t}</li>)}
          </ul>
          {Object.keys(unc).length > 0 && (
            <p className="uncov"><b>We cannot staff:</b>{" "}
              {Object.entries(unc).map(([k, v]) => <span className="chip" key={k}>{k} ×{v}</span>)}
              {" "}not skills our bench carries today.</p>
          )}
          <div className="exai">
            <AiButton task="company" args={{ company }} label="Write the full brief" />
            <AiButton task="outreach" args={{ company }} label="Prepare the call" small />
          </div>
        </div>
      </div>

      <div className="exsig">
        <div>
          <p className="evhead">Their need, signal by signal
            <span className="sfx">each on the same 0–100 scale as the score</span></p>
          <div className="mix">
            {NEEDMIX.map(([k, label]) =>
              <MixRow cls="" label={label} v={rx<number>(k)(r)} floor={floor} key={k} />)}
          </div>
        </div>
        <div>
          <p className="evhead">What we could bring
            <span className="sfx">the same scale again</span></p>
          <div className="mix">
            <MixRow cls="sup" label="Depth of bench behind those roles" v={svc} floor={floor} />
            <MixRow cls="sup" label="Deal size — people we could place at once" v={deal} floor={floor} />
          </div>
        </div>
      </div>
    </div>
  );
}
