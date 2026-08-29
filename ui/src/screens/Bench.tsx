import { useMemo, useState, type ReactNode } from "react";
import { Screen, type Tab } from "../App";
import { HBar, HBar2, type BarRow, type PairRow } from "../components/Charts";
import { Count, DataTable, type Column } from "../components/DataTable";
import { Kpi } from "../components/Kpi";
import { indexer, type Bench as BenchData, type Row } from "../data";
import { fmt } from "../format";

type CellRow = BenchData["cells"][number];

const FAMILIES = ["dev", "data", "ops", "qa", "analyst", "architect", "security", "support"];

/* Say out loud what the ranking is based on. The three factors are the
   score; showing them as bare 0-1 decimals told the reader nothing. */
const bandWord = (v: number): ReactNode =>
  v >= 0.75 ? <b>high</b> : v >= 0.45 ? "medium" : <span className="z">low</span>;
const AVAIL: Record<string, string> = {
  now: "now", in_30d: "in 30 days", in_90d: "in 90 days", unavailable: "not available",
};
const availWord = (a: string) => AVAIL[a] || a;

const CELL_COLUMNS: Column<CellRow>[] = [
  { t: "Family", v: (r) => r[0], cls: "nm" },
  { t: "Seniority", v: (r) => r[1] },
  { t: "Technology", v: (r) => r[2], render: (r) => <span className="chip">{r[2]}</span> },
  { t: "Weighted demand", v: (r) => r[3], r: true, render: (r) => r[3].toFixed(1) },
  {
    t: "Coverage gap", v: (r) => r[4], r: true, render: (r) => (
      <>
        <span className="svcbar"><i className={r[4] > 0.5 ? "low" : ""} style={{ width: `${(r[4] * 100).toFixed(0)}%` }} /></span>
        <span className="svctxt">{(r[4] * 100).toFixed(0)}%</span>
      </>
    ),
  },
  {
    t: "Bench depth", v: (r) => r[5], r: true, render: (r) => (
      <>
        {fmt(r[5])}
        {r[5] < 3 && <> <span className="tag noise" title="Fewer than three consultants can serve this cell">thin</span></>}
      </>
    ),
  },
  { t: "Vacancies", v: (r) => r[6], r: true },
  { t: "Companies", v: (r) => r[7], r: true },
];

export function Bench({ B, on }: { B: BenchData; on: Tab }) {
  const bx = useMemo(() => indexer(B.cand_cols), [B]);
  const [q, setQ] = useState("");
  const [fam, setFam] = useState("");
  const [avail, setAvail] = useState(false);

  const gap = useMemo<PairRow[]>(() => {
    const dMax = Math.max(...B.gap.map((x) => x[1]));
    const bMax = Math.max(...B.gap.map((x) => x[2]));
    return B.gap.map((g) => [g[0], g[2] / Math.max(bMax, 1), g[1] / Math.max(dMax, 1)]);
  }, [B]);
  const pull = useMemo<BarRow[]>(
    () => B.supply_vs_pull.map<BarRow>((r) => [r[0], r[2], "acc"]).sort((a, b) => b[1] - a[1]), [B]);
  const supply = useMemo<BarRow[]>(
    () => B.supply_vs_pull.map<BarRow>((r) => [r[0], r[1], ""]).sort((a, b) => b[1] - a[1]), [B]);

  const columns = useMemo<Column<Row>[]>(() => {
    const id = bx<string>("id");
    const tags = bx<string[]>("tags");
    const german = bx<boolean>("german");
    const availability = bx<string>("availability");
    const pullOf = bx<number>("pull");
    const scar = bx<number>("scarcity");
    const thin = bx<boolean>("thin");
    const value = bx<number>("value");
    const sen = bx<string>("seniority");
    const family = bx<string>("family");
    const yrs = bx<number>("years");
    const plain = (r: Row) => {
      const t = tags(r);
      let s = `${sen(r)} ${family(r)}, ${yrs(r)} yrs`;
      if (t.length) s += ` — ${t.slice(0, 2).join(" and ")}`;
      s += ".";
      const p = pullOf(r), sc = scar(r);
      s += p >= 0.75 ? " German companies badly need this skill"
        : p >= 0.45 ? " There is steady German demand for this"
        : " German demand for this is thin";
      s += sc >= 0.75 ? ", and we have very few people like this."
        : sc >= 0.45 ? ", and we are not deep in it."
        : ", and we already have plenty of them.";
      return s;
    };
    return [
      { t: "#", v: bx("rank"), r: true, render: (_r, pos) => <b>{pos}</b> },
      {
        t: "Consultant", v: id, cls: "nm", render: (r) => (
          <>
            <span className="cname">{id(r)}</span>
            {" "}<span className="tag noise" title="Generated bench — no real person">synthetic</span>
            {german(r) && <> <span className="tag">speaks German</span></>}
            <span className="csub">{plain(r)}</span>
          </>
        ),
      },
      {
        t: "Skills", v: tags, sortKey: (r) => tags(r).length,
        render: (r) => tags(r).map((t, i) => <span className="chip" key={i}>{t}</span>),
      },
      { t: "Available", v: availability, render: (r) => availWord(availability(r)) },
      { t: "German demand for this", v: pullOf, r: true, render: (r) => bandWord(pullOf(r)) },
      {
        t: "How rare on our bench", v: scar, r: true, render: (r) => (
          <>
            {bandWord(scar(r))}
            {thin(r) && <> <span className="tag noise">thin</span></>}
          </>
        ),
      },
      { t: "Score", v: value, r: true, render: (r) => <span className="score">{value(r).toFixed(0)}</span> },
    ];
  }, [bx]);

  const rows = useMemo(() => {
    const family = bx<string>("family");
    const tags = bx<string[]>("tags");
    const availability = bx<string>("availability");
    const qq = q.trim().toLowerCase();
    return B.cand_rows.filter((r) =>
      (!fam || family(r) === fam)
      && (!avail || ["now", "in_30d"].includes(availability(r)))
      && (!qq || family(r).toLowerCase().includes(qq)
        || tags(r).some((t) => t.toLowerCase().includes(qq))));
  }, [B, bx, q, fam, avail]);

  const bm = B.meta;
  return (
    <Screen id="bench" group="people" on={on}>
      <p className="label">Bench &middot; people scoring</p>
      <h2>Who we can<br />deploy</h2>
      <p className="lede">A <b>synthetic</b> delivery bench of {bm.size} consultants, generated in the
        German tech vocabulary (option B3) so matching against real demand is a join, not a guess.
        Each consultant is scored <b>Value = MarketPull &times; Scarcity &times; Deployability</b>{" "}
        &mdash; and MarketPull comes from the <em>real German postings</em>, never from synthetic
        openings.</p>

      <div className="note"><b>Every person on this screen is synthetic.</b>
        {" "}The bench profile is a deliberate model of a Lithuanian nearshore consultancy &mdash; strong in
        modern software delivery, thin in SAP/embedded &mdash; so the gap against German demand is
        visible instead of flattered away. Swap in the real bench and every number recomputes.</div>

      <div className="kpis">
        <Kpi hl label="People on the bench" v={String(bm.size)} n="who we could put on a project" />
        <Kpi label="Speak German" v={String(bm.german_speakers)} n="the hard limit on how much German work we can take" />
        <Kpi label="Thin skill groups" v={String(bm.thin_cells)} n={<>fewer than 5 people &mdash; we flag these rather than promise them</>} />
      </div>

      <details className="more">
        <summary>More numbers about the bench</summary>
        <div className="kpis">
          <Kpi label="Skill groups" v={String(bm.cells)} n={<>role type &times; seniority</>} />
          <Kpi label="Not just the longest CV" v={bm.people_rho.toFixed(2)}
            n="how little our ranking agrees with simply counting skills; near zero is good" />
        </div>
      </details>

      <div className="grid">
        <div className="panel wide">
          <p className="label">The gap</p><h3>German demand vs bench capability</h3>
          <p className="hint">Bench consultants carrying each tech category (violet) against eligible
            German postings naming it (dark). Where dark towers over violet &mdash; SAP/erp, embedded,
            security &mdash; is exactly what the bench cannot serve. This chart is the honest version
            of Serviceability.</p>
          <HBar2 rows={gap} legend={["our bench", "German demand"]} />
        </div>
        <div className="panel">
          <p className="label">Demand</p><h3>Unfilled German demand by role family</h3>
          <p className="hint">Postings open &gt;45 days in the eligible pool &mdash; the MarketPull input.</p>
          <HBar rows={pull} />
        </div>
        <div className="panel">
          <p className="label">Supply</p><h3>Bench by role family</h3>
          <p className="hint">Where our capacity actually sits.</p>
          <HBar rows={supply} />
        </div>
        <div className="panel wide">
          <p className="label">Cells</p><h3>Supply index &mdash; the Pipeline C hand-off</h3>
          <p className="hint">One row per role family &times; seniority. Thin cells (&lt;5 people) are
            flagged: scarcity = 1/depth explodes there, so they are never ranked &mdash; dead code on
            a 120-person bench in some cells, load-bearing the moment the real bench arrives.</p>
          <DataTable columns={CELL_COLUMNS} rows={B.cells}
            sort={3} dir={-1} bodyId="ce-body" maxHeight="44vh" />
        </div>
        <div className="panel wide">
          <p className="label">People ranking</p><h3>Bench value</h3>
          <p className="hint">Value = MarketPull &times; Scarcity &times; Deployability, all percentiled.
            Multiplicative: a candidate nobody wants, or one we have forty of, is not valuable
            regardless of the other factors.</p>
          <div className="controls">
            <input type="search" id="be-q" placeholder="Search family or tag..." value={q} onChange={(e) => setQ(e.target.value)} />
            <select id="be-fam" value={fam} onChange={(e) => setFam(e.target.value)}>
              <option value="">All families</option>
              {FAMILIES.map((f) => <option key={f}>{f}</option>)}
            </select>
            <label className="chk"><input type="checkbox" id="be-avail" checked={avail} onChange={(e) => setAvail(e.target.checked)} /> Available now / 30d only</label>
            <Count id="be-count" n={rows.length} total={B.cand_rows.length} noun="consultants" />
          </div>
          <DataTable columns={columns} rows={rows} sort={6} dir={-1} bodyId="be-body" maxHeight="56vh" />
        </div>
      </div>
    </Screen>
  );
}
