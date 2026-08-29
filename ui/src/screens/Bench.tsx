import { useCallback, useMemo, useState, type ReactNode } from "react";
import { Screen, type Tab } from "../App";
import { AiButton } from "../components/Ai";
import { Ranks, type BarRow } from "../components/Chart";
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
  { t: "Family", v: (r) => r[0], cls: "nm",
    help: "Role family — the kind of work, in the shared vocabulary both the postings and the bench are tagged with." },
  { t: "Seniority", v: (r) => r[1],
    help: "Level the demand asks for. 'unknown' means the advertisement did not say, which is most of them." },
  { t: "Technology", v: (r) => r[2],
    help: "Technology category the demand names. 'unspecified' is the parser's placeholder for an advertisement naming none — about half of them.",
    render: (r) => <span className="chip">{r[2]}</span> },
  { t: "Weighted demand", v: (r) => r[3], r: true,
    help: "Vacancies of this shape, weighted by how badly the company holding them is struggling. A unitless score — compare rows against each other, not against anything outside this table.",
    render: (r) => r[3].toFixed(1) },
  {
    t: "Coverage gap", v: (r) => r[4], r: true,
    help: "The share of this demand our bench cannot cover today. 100% means nobody here fits it at all.",
    render: (r) => (
      <>
        <span className="svcbar"><i className={r[4] > 0.5 ? "low" : ""} style={{ width: `${(r[4] * 100).toFixed(0)}%` }} /></span>
        <span className="svctxt">{(r[4] * 100).toFixed(0)}%</span>
      </>
    ),
  },
  {
    t: "Bench depth", v: (r) => r[5], r: true,
    help: "How many consultants could serve this cell. Under three we flag it as thin: one illness or one other project and we cannot deliver.",
    render: (r) => (
      <>
        {fmt(r[5])}
        {r[5] < 3 && <> <span className="tag noise" title="Fewer than three consultants can serve this cell">thin</span></>}
      </>
    ),
  },
  { t: "Vacancies", v: (r) => r[6], r: true,
    help: "Open roles of this exact shape across the whole eligible pool." },
  { t: "Companies", v: (r) => r[7], r: true,
    help: "How many different employers are asking for it. Demand spread across many companies is safer to hire against than the same count at one." },
];

export function Bench({ B, on }: { B: BenchData; on: Tab }) {
  const bx = useMemo(() => indexer(B.cand_cols), [B]);
  const [q, setQ] = useState("");
  const [fam, setFam] = useState("");
  const [avail, setAvail] = useState(false);
  const [openCell, setOpenCell] = useState<string | null>(null);

  /* A cell is family/seniority/technology -- the same triple the capability
     plan is keyed on, so the row the reader clicked is the row the analyst
     looks up. Clicking one asks what to do about the gap. */
  const cellKey = (r: CellRow) => `${r[0]}/${r[1]}/${r[2]}`;
  const cellClass = useCallback(
    (r: CellRow) => (cellKey(r) === openCell ? "clickable open" : "clickable"), [openCell]);
  const onCellClick = useCallback(
    (r: CellRow) => setOpenCell((k) => (k === cellKey(r) ? null : cellKey(r))), []);
  const cellExpanded = useCallback((r: CellRow) => (
    cellKey(r) === openCell ? (
      <div className="ex">
        <AiButton task="gap" args={{ cell: cellKey(r) }} label="Write the sourcing brief"
          hint="What this gap costs us, who to hire against it, and which ranked companies are asking for it." />
      </div>
    ) : null), [openCell]);

  /* supply_vs_pull rows are [family, consultants, vacancies]. The two counts
     on their own rank almost identically, so what is plotted is the load each
     consultant would carry -- which does not rank like either input. */
  const load = useMemo<BarRow[]>(() => {
    const rows = B.supply_vs_pull
      .filter((r) => r[1] > 0)
      .map((r) => [r[0], r[2] / r[1]] as [string, number])
      .sort((a, b) => b[1] - a[1]);
    return rows.map<BarRow>((r, i) => [r[0], r[1], i < 3 ? "acc" : ""]);
  }, [B]);

  const columns = useMemo<Column<Row>[]>(() => {
    const id = bx<string>("id");
    const tags = bx<string[]>("tags");
    const german = bx<boolean>("german");
    const availability = bx<string>("availability");
    const pullOf = bx<number>("pull");
    const scar = bx<number>("scarcity");
    const thin = bx<boolean>("thin");
    const value = bx<number>("value");
    /* Simulated attributes -- day rate, delivery rating and public GitHub
       activity. Null where the consultant has no public profile, which is
       the honest reading for most non-dev families. */
    const ghC = bx<number | null>("gh_commits");
    const ghR = bx<number | null>("gh_repos");
    const ghS = bx<number | null>("gh_stars");
    const rate = bx<number | null>("rate");
    const rating = bx<number | null>("rating");
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
      { t: "#", v: bx("rank"), r: true,
        help: "Position by Score within the consultants currently shown.",
        render: (_r, pos) => <b>{pos}</b> },
      {
        t: "Consultant", v: id, cls: "nm",
        help: "A generated consultant — no real person. The sentence underneath says what they are and how the German market treats that profile.",
        render: (r) => (
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
        help: "Technology categories this consultant carries, in the same vocabulary the German postings are tagged with. Sorts by how many.",
        render: (r) => tags(r).map((t, i) => <span className="chip" key={i}>{t}</span>),
      },
      { t: "Available", v: availability,
        help: "When they could start. A consultant who cannot start this quarter is worth little to a client who is already late, so this feeds the score.",
        render: (r) => availWord(availability(r)) },
      { t: "German demand for this", v: pullOf, r: true,
        help: "How much unfilled German demand matches this profile, as a band. Measured from the real postings — never from the synthetic candidate set.",
        render: (r) => bandWord(pullOf(r)) },
      {
        t: "How rare on our bench", v: scar, r: true,
        help: "How few other people here could cover the same work. Rare is valuable: someone we have forty of adds little, however employable they are.",
        render: (r) => (
          <>
            {bandWord(scar(r))}
            {thin(r) && <> <span className="tag noise">thin</span></>}
          </>
        ),
      },
      {
        t: "GitHub", v: ghC, sortKey: (r) => ghC(r) ?? -1, r: true,
        help: "SIMULATED. Public contributions in the last 12 months, with repositories and stars underneath. Most non-developer profiles have no public presence, which is how GitHub actually looks.",
        render: (r) => {
          const c = ghC(r);
          if (c === null || c === undefined) return <span className="z">no profile</span>;
          return (
            <span className="gh" title={`${fmt(c)} contributions in 12 months, ${fmt(ghR(r) ?? 0)} repos, ${fmt(ghS(r) ?? 0)} stars`}>
              <b>{fmt(c)}</b>
              <span className="ghm">{fmt(ghR(r) ?? 0)} repos &middot; {fmt(ghS(r) ?? 0)} &#9733;</span>
            </span>
          );
        },
      },
      {
        t: "Day rate", v: rate, sortKey: (r) => rate(r) ?? -1, r: true,
        help: "SIMULATED. What we would charge a German client per day, before any discount. Rises with seniority and carries a premium for German.",
        render: (r) => {
          const v = rate(r);
          return v === null || v === undefined
            ? <span className="z">&ndash;</span>
            : <span className="rate">&euro;{fmt(v)}</span>;
        },
      },
      {
        t: "Rating", v: rating, sortKey: (r) => rating(r) ?? -1, r: true,
        help: "SIMULATED. Internal delivery rating out of 5 from past engagements. Not a customer review and not evidence of anything.",
        render: (r) => {
          const v = rating(r);
          if (v === null || v === undefined) return <span className="z">&ndash;</span>;
          return (
            <span className="stars" title={`${v.toFixed(2)} of 5 on delivery`}>
              <span className="sb"><i style={{ width: `${(v / 5) * 100}%` }} /></span>
              <b>{v.toFixed(1)}</b>
            </span>
          );
        },
      },
      { t: "Score", v: value, r: true,
        help: "Value = market pull × rarity × deployability, all percentiled and multiplied. Multiplicative on purpose: a zero on any one of the three should sink the row.",
        render: (r) => <span className="score">{value(r).toFixed(0)}</span> },
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
          <p className="label">Where we are stretched</p><h3>Open German vacancies per consultant</h3>
          <p className="hint">Unfilled German vacancies in each role family, divided by the people
            we have who could serve it &mdash; how many open roles each of our consultants would
            have to cover. The three worst are marked. Plotted as one ratio rather than two counts,
            because demand and bench both peak in <em>dev</em> and their shapes matched.</p>
          <Ranks rows={load} labelWidth={104}
            fmtV={(v) => (v >= 10 ? v.toFixed(0) : v.toFixed(1))} unit=" per consultant" />
        </div>
        <div className="panel wide">
          <p className="label">Cells</p><h3>Supply index &mdash; the Pipeline C hand-off</h3>
          <p className="hint">One row per role family &times; seniority. Thin cells (&lt;5 people) are
            flagged: scarcity = 1/depth explodes there, so they are never ranked &mdash; dead code on
            a 120-person bench in some cells, load-bearing the moment the real bench arrives.
            {" "}<b>Click a row</b> for a sourcing brief on that gap.</p>
          <DataTable columns={CELL_COLUMNS} rows={B.cells}
            sort={3} dir={-1} bodyId="ce-body" maxHeight="44vh"
            rowClass={cellClass} onRowClick={onCellClick} expanded={cellExpanded} />
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
          <DataTable columns={columns} rows={rows} sort={9} dir={-1} bodyId="be-body" maxHeight="56vh" />
        </div>
      </div>
    </Screen>
  );
}
