import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Count, DataTable, type Column } from "../components/DataTable";
import { indexer, type Row, type Talent as TalentData } from "../data";
import { fmt } from "../format";

const TECH_FAMS = new Set(["engineering", "data"]);

export function Candidates({ T, on }: { T: TalentData; on: Tab }) {
  const CA = T.candidates;
  const cx = useMemo(() => indexer(CA.cols), [CA]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [sen, setSen] = useState("");
  const [ind, setInd] = useState("");
  const [techOnly, setTechOnly] = useState(false);

  const columns = useMemo<Column<Row>[]>(() => {
    const family = cx<string>("role_family");
    const skills = cx<number[]>("skills");
    const qualified = cx<number>("qualified_for_openings");
    return [
      { t: "ID", v: cx("candidate_id"), cls: "nm",
        help: "Synthetic profile identifier. No real person, and no personal data anywhere in this table." },
      { t: "Role", v: cx("role"), cls: "nm" },
      {
        t: "Family", v: family, render: (r) => {
          const f = family(r);
          return <span className={`tag ${TECH_FAMS.has(f) ? "pub" : ""}`}>{f}</span>;
        },
      },
      { t: "Seniority", v: cx("seniority") },
      { t: "Years", v: cx("years_experience"), r: true },
      { t: "Industry", v: cx("industry") },
      { t: "Education", v: cx("education") },
      {
        t: "Skills", v: skills, sortKey: (r) => skills(r).length,
        help: "Skills on the profile, from a 73-word vocabulary. Only 7 of those have a German equivalent in our extraction, which is why this set cannot be joined to the German data.",
        render: (r) => skills(r).map((i) => <span className="chip" key={i}>{T.dicts.skills[i]}</span>),
      },
      { t: "Qualified for", v: qualified, r: true,
        help: "How many of the openings in this fixture this profile satisfies on the documented rule. A measure of the generator, not of any labour market.",
        render: (r) => fmt(qualified(r)) },
    ];
  }, [cx, T]);

  const rows = useMemo(() => {
    const roleOf = cx<string>("role");
    const senOf = cx<string>("seniority");
    const indOf = cx<string>("industry");
    const family = cx<string>("role_family");
    const skills = cx<number[]>("skills");
    const qq = q.trim().toLowerCase();
    return CA.rows.filter((r) =>
      (!role || roleOf(r) === role)
      && (!sen || senOf(r) === sen)
      && (!ind || indOf(r) === ind)
      && (!techOnly || TECH_FAMS.has(family(r)))
      && (!qq || roleOf(r).toLowerCase().includes(qq)
        || indOf(r).toLowerCase().includes(qq)
        || skills(r).some((i) => T.dicts.skills[i].toLowerCase().includes(qq))));
  }, [CA, cx, T, q, role, sen, ind, techOnly]);

  return (
    <Screen id="candidates" group="people" on={on}>
      <p className="label">Candidates</p>
      <div className="controls">
        <input type="search" id="ca-q" placeholder="Search role, industry or skill..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select id="ca-role" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">All roles</option>
          {T.options.roles.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select id="ca-sen" value={sen} onChange={(e) => setSen(e.target.value)}>
          <option value="">Any seniority</option>
          {T.options.seniority.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select id="ca-ind" value={ind} onChange={(e) => setInd(e.target.value)}>
          <option value="">All industries</option>
          {T.options.industries.map((s) => <option key={s}>{s}</option>)}
        </select>
        <label className="chk"><input type="checkbox" id="ca-tech" checked={techOnly} onChange={(e) => setTechOnly(e.target.checked)} /> Tech roles only</label>
        <Count id="ca-count" n={rows.length} total={CA.rows.length} noun="candidates" />
      </div>
      <DataTable columns={columns} rows={rows} sort={8} dir={-1} bodyId="ca-body" />
    </Screen>
  );
}
