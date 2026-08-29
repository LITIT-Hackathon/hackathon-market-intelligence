import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Ranks, Series, type BarRow } from "../components/Chart";
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
      { t: "Skill", v: sx("skill"), cls: "nm",
        help: "One skill from the candidate fixture's 73-word vocabulary." },
      { t: "Family", v: family, render: (r) => <span className="tag">{family(r)}</span> },
      { t: "Supply", v: sx("supply"), r: true,
        help: "Candidates in the fixture who carry this skill." },
      { t: "Supply %", v: sx("supply_share"), r: true,
        help: "Share of all candidates carrying it.",
        render: (r) => pct(sx<number>("supply_share")(r)) },
      { t: "Must-have", v: sx("demand_must"), r: true,
        help: "Openings that require this skill outright." },
      { t: "Nice-to-have", v: sx("demand_nice"), r: true,
        help: "Openings that list it as preferred rather than required." },
      { t: "Demand %", v: sx("demand_share"), r: true,
        help: "Share of all openings asking for it, required or preferred.",
        render: (r) => pct(sx<number>("demand_share")(r)) },
      {
        t: "Tension", v: tension, r: true,
        help: "Demand share divided by supply share. Above 1 means more openings want it than candidates have it. Uniform by construction in this fixture, so treat it as a worked example rather than a finding.",
        render: (r) => {
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
        <div className="panel">
          <p className="label">Shape</p><h3>Role families</h3>
          <p className="hint">Candidates by role family. Engineering and data are the tech-facing ones.</p>
          <Ranks rows={TC.role_family} labelWidth={126} />
        </div>
        <div className="panel">
          <p className="label">Demand</p><h3>Most requested roles</h3>
          <p className="hint">Openings by title.</p>
          <Ranks rows={TC.role_demand} labelWidth={168} />
        </div>
        <div className="panel">
          <p className="label">Level</p><h3>Years of experience</h3>
          <p className="hint">The one distribution in this fixture with a real shape &mdash; a four-fold
            spread between the commonest and rarest band. Seniority, industry and education are split
            almost perfectly evenly by the generator, so they are not charted: there is nothing in
            them to read.</p>
          <Series rows={TC.experience.map<BarRow>((r) => [r[0], r[1], ""])} areaLabel="candidates" height={190} />
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
