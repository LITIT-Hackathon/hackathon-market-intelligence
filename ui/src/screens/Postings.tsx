import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Count, DataTable, type Column } from "../components/DataTable";
import { dict, indexer, type Payload, type Row } from "../data";
import { fmt } from "../format";

export function Postings({ data, on }: { data: Payload; on: Tab }) {
  const P = data.postings;
  const D = data.dicts;
  const px = useMemo(() => indexer(P.cols), [P]);
  const [q, setQ] = useState("");
  const [sen, setSen] = useState("");
  const [tech, setTech] = useState("");
  const [reg, setReg] = useState("");
  const [minAge, setMinAge] = useState(0);
  const [hideComp, setHideComp] = useState(false);

  const columns = useMemo<Column<Row>[]>(() => {
    const title = px<string>("title");
    const id = px<string>("id");
    const techs = px<number[]>("tech");
    const age = px<number | null>("age");
    return [
      {
        t: "Title", v: title, cls: "ti", render: (r) => (
          <a href={`https://www.arbeitsagentur.de/jobsuche/jobdetail/${encodeURIComponent(id(r))}`}
            target="_blank" rel="noopener">{title(r)}</a>
        ),
      },
      { t: "Company", v: (r) => dict(D.companies, px<number | null>("company")(r)), cls: "nm" },
      { t: "Occupational group", v: (r) => dict(D.groups, px<number | null>("group")(r)) },
      { t: "Level", v: (r) => dict(D.levels, px<number | null>("level")(r)) },
      { t: "Seniority", v: (r) => dict(D.seniority, px<number | null>("seniority")(r)) },
      {
        t: "Technologies", v: techs, sortKey: (r) => techs(r).length,
        render: (r) => {
          const t = techs(r);
          return t.length
            ? t.map((i) => <span className="chip" key={i}>{D.tech[i]}</span>)
            : <span style={{ color: "var(--muted-2)" }}>–</span>;
        },
      },
      { t: "Region", v: (r) => dict(D.regions, px<number | null>("region")(r)) },
      {
        t: "Age", v: age, r: true, render: (r) => {
          const v = age(r);
          return v === null ? "" : <span className={`age ${v > 90 ? "old" : ""}`}>{fmt(v)}d</span>;
        },
      },
    ];
  }, [px, D]);

  const rows = useMemo(() => {
    const title = px<string>("title");
    const company = px<number | null>("company");
    const seniority = px<number | null>("seniority");
    const region = px<number | null>("region");
    const techs = px<number[]>("tech");
    const age = px<number | null>("age");
    const comp = px<boolean>("comp");
    const qq = q.trim().toLowerCase();
    return P.rows.filter((r) =>
      (!qq || title(r).toLowerCase().includes(qq)
        || (D.companies[company(r) as number] || "").toLowerCase().includes(qq))
      && (!sen || D.seniority[seniority(r) as number] === sen)
      && (!reg || D.regions[region(r) as number] === reg)
      && (!tech || techs(r).some((i) => D.tech[i] === tech))
      && (age(r) ?? 0) >= minAge
      && (!hideComp || !comp(r)));
  }, [P, px, D, q, sen, reg, tech, minAge, hideComp]);

  return (
    <Screen id="postings" group="method" on={on}>
      <p className="label">Postings</p>
      <h2>The evidence<br />layer</h2>
      <p className="lede">Showing {fmt(data.meta.postings_shown)} {data.meta.scope}. Every title links to the live posting on
        arbeitsagentur.de — this is what any score has to be traceable back to.</p>
      <div className="note"><b>Sorted by how long each posting has been open.</b>
        {" "}The extreme tail is real but not useful: postings older than roughly two years are records the
        source never delisted, not live demand. The scarcity signal worth acting on sits in the
        90–400 day band — use the age filter.</div>

      <div className="controls">
        <input type="search" id="po-q" placeholder="Search title or company…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select id="po-sen" value={sen} onChange={(e) => setSen(e.target.value)}>
          <option value="">Any seniority</option>
          {data.options.seniority.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select id="po-tech" value={tech} onChange={(e) => setTech(e.target.value)}>
          <option value="">Any technology</option>
          {data.options.tech.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select id="po-reg" value={reg} onChange={(e) => setReg(e.target.value)}>
          <option value="">All regions</option>
          {data.options.regions.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select id="po-age" value={minAge} onChange={(e) => setMinAge(+e.target.value)}>
          <option value="0">Any age</option>
          <option value="30">Open 30+ days</option>
          <option value="90">Open 90+ days</option>
          <option value="180">Open 180+ days</option>
        </select>
        <label className="chk"><input type="checkbox" id="po-hidecomp" checked={hideComp} onChange={(e) => setHideComp(e.target.checked)} /> Hide competitor postings</label>
        <Count id="po-count" n={rows.length} total={P.rows.length} noun="postings" />
      </div>
      <DataTable columns={columns} rows={rows} sort={7} dir={-1} bodyId="po-body" />
    </Screen>
  );
}
