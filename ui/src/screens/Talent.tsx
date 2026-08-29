import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { HBar, HBar2, type BarRow } from "../components/Charts";
import { Count, DataTable, type Column } from "../components/DataTable";
import { Kpi, f0c } from "../components/Kpi";
import { indexer, type Row, type Talent as TalentData } from "../data";
import { fmt, pct } from "../format";

export function Talent({ T, on }: { T: TalentData; on: Tab }) {
  const TC = T.charts;
  const SK = T.skills;
  const sx = useMemo(() => indexer(SK.cols), [SK]);
  const families = useMemo(() => Array.from(new Set(SK.rows.map((r) => r[1] as string))).sort(), [SK]);
  const [q, setQ] = useState("");
  const [fam, setFam] = useState("");

  const columns = useMemo<Column<Row>[]>(() => {
    const family = sx<string>("skill_family");
    const tension = sx<number>("tension");
    return [
      { t: "Skill", v: sx("skill"), cls: "nm" },
      { t: "Family", v: family, render: (r) => <span className="tag">{family(r)}</span> },
      { t: "Supply", v: sx("supply"), r: true },
      { t: "Supply %", v: sx("supply_share"), r: true, render: (r) => pct(sx<number>("supply_share")(r)) },
      { t: "Must-have", v: sx("demand_must"), r: true },
      { t: "Nice-to-have", v: sx("demand_nice"), r: true },
      { t: "Demand %", v: sx("demand_share"), r: true, render: (r) => pct(sx<number>("demand_share")(r)) },
      {
        t: "Tension", v: tension, r: true, render: (r) => {
          const v = tension(r);
          return <span className={`age ${v >= 1 ? "old" : ""}`}>{v.toFixed(2)}</span>;
        },
      },
    ];
  }, [sx]);

  const rows = useMemo(() => {
    const skill = sx<string>("skill");
    const family = sx<string>("skill_family");
    const qq = q.trim().toLowerCase();
    return SK.rows.filter((r) => (!qq || skill(r).toLowerCase().includes(qq)) && (!fam || family(r) === fam));
  }, [SK, sx, q, fam]);

  const tm = T.meta;
  return (
    <Screen id="talent" group="people" on={on}>
      <p className="label">Talent &middot; supply side</p>
      <h2>Who is<br />available</h2>
      <p className="lede">The other half of the market: {fmt(tm.candidates)} candidate profiles and {fmt(tm.openings)} openings from a
        synthetic benchmark dataset. Same treatment as the demand side &mdash; normalised, aggregated,
        and honest about what it can and cannot tell you.</p>

      <div className="note"><b>Two things to know before reading any of this.</b>
        {" "}The dataset is <em>synthetic and LLM-generated</em>, so the near-uniform distributions below
        measure the generator, not a labour market. And it <em>does not join to the German posting
        data</em>: only {tm.bridge_pct}% of its skill vocabulary has an equivalent in our German
        extraction, covering {tm.bridge_coverage}% of German IT postings. Use it to build and demo the
        matcher, not to claim anything about Germany.</div>

      <details className="more">
        <summary>Numbers about this candidate dataset</summary>
        <div className="kpis">
          <Kpi label="Candidate profiles" v={fmt(tm.candidates)} n="all synthetic" />
          <Kpi label="In tech roles" v={fmt(tm.tech_candidates)} n="engineering, data, technical" />
          <Kpi label="Openings" v={fmt(tm.openings)} n="also synthetic" />
          <Kpi label="Different skills" v={String(tm.skill_vocabulary)} n={`${tm.mean_skills.toFixed(1)} per candidate`} />
          <Kpi label="Match too loose" v={f0c(tm.mean_pool)}
            n={<>candidates qualify for a typical opening &mdash; far too many to be realistic</>} />
        </div>
      </details>

      <div className="grid">
        <div className="panel wide">
          <p className="label">The core question</p><h3>Skill supply vs demand</h3>
          <p className="hint">Share of candidates holding each skill (violet) against share of openings
            asking for it (dark). Where dark outruns violet, the market wants more than the bench
            carries.</p>
          <HBar2 rows={TC.supply_demand} legend={["candidates who have it", "openings asking for it"]} />
        </div>
        <div className="panel">
          <p className="label">Scarcity</p><h3>Highest tension</h3>
          <p className="hint">Demand share divided by supply share, normalised so the market average is 1.0.
            The spread is narrow because the generator is close to uniform &mdash; on real data expect
            a far wider range.</p>
          <HBar rows={TC.tension_top.map<BarRow>((r) => [r[0], r[1], "acc"])} format={(v) => v.toFixed(2)} />
        </div>
        <div className="panel">
          <p className="label">Oversupply</p><h3>Lowest tension</h3>
          <p className="hint">More bench than market. On a real bench these are the hardest people to place.</p>
          <HBar rows={TC.tension_bottom.map<BarRow>((r) => [r[0], r[1], "mut"])} format={(v) => v.toFixed(2)} />
        </div>
        <div className="panel">
          <p className="label">Shape</p><h3>Role families</h3>
          <p className="hint">Candidates by role family. Engineering and data are the tech-facing ones.</p>
          <HBar rows={TC.role_family} />
        </div>
        <div className="panel">
          <p className="label">Demand</p><h3>Most requested roles</h3>
          <p className="hint">Openings by title.</p>
          <HBar rows={TC.role_demand} />
        </div>
        <div className="panel">
          <p className="label">Level</p><h3>Seniority and experience</h3>
          <p className="hint">Note the near-perfect thirds. That is the generator, not a talent pool.</p>
          <HBar rows={TC.seniority} />
          <div className="stack"></div>
          <HBar rows={TC.experience.map<BarRow>((r) => [r[0], r[1], "mut"])} />
        </div>
        <div className="panel">
          <p className="label">Background</p><h3>Industry and education</h3>
          <p className="hint">Ten industries at roughly 10% each, five education levels at roughly 20% each.</p>
          <HBar rows={TC.industry} />
          <div className="stack"></div>
          <HBar rows={TC.education.map<BarRow>((r) => [r[0], r[1], "mut"])} />
        </div>
        <div className="panel wide">
          <p className="label">Skill market</p><h3>Every skill, supply against demand</h3>
          <p className="hint">Sort any column. Tension above 1.0 means demand outruns supply.</p>
          <div className="controls">
            <input type="search" id="sk-q" placeholder="Search skill..." value={q} onChange={(e) => setQ(e.target.value)} />
            <select id="sk-fam" value={fam} onChange={(e) => setFam(e.target.value)}>
              <option value="">All skill families</option>
              {families.map((f) => <option key={f}>{f}</option>)}
            </select>
            <Count id="sk-count" n={rows.length} total={SK.rows.length} noun="skills" />
          </div>
          <DataTable columns={columns} rows={rows} sort={7} dir={-1} bodyId="sk-body" maxHeight="52vh" />
        </div>
      </div>
    </Screen>
  );
}
