import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Count, DataTable, type Column } from "../components/DataTable";
import { indexer, type Payload, type Row } from "../data";
import { fmt, pct } from "../format";

export function Companies({ data, on }: { data: Payload; on: Tab }) {
  const CO = data.companies;
  const co = useMemo(() => indexer(CO.cols), [CO]);
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [minIt, setMinIt] = useState(0);
  const [hideComp, setHideComp] = useState(false);
  const [hideNoise, setHideNoise] = useState(true);

  const columns = useMemo<Column<Row>[]>(() => {
    const name = co<string>("company_name");
    const klass = co<string>("company_class");
    const isComp = co<boolean>("is_competitor");
    const isNoise = co<boolean>("is_noise");
    const review = co<boolean>("needs_review");
    const medAge = co<number | null>("median_it_age_days");
    const techs = co<string[]>("top_technologies");
    return [
      { t: "Company", v: name, cls: "nm" },
      {
        t: "Class", v: klass, render: (r) => {
          const c = klass(r);
          const tag = isComp(r) ? "comp" : isNoise(r) ? "noise" : c === "public_sector" ? "pub" : "";
          return (
            <>
              <span className={`tag ${tag}`}>{c.replace(/_/g, " ")}</span>
              {review(r) && (
                <>
                  {" "}
                  <span className="tag" title="High volume across unrelated sectors and regions, but no agency keyword in the name — the rules cannot decide">review</span>
                </>
              )}
            </>
          );
        },
      },
      { t: "Postings", v: co("postings"), r: true },
      { t: "IT", v: co("it_postings"), r: true },
      { t: "IT %", v: co("it_intensity"), r: true, render: (r) => pct(co<number>("it_intensity")(r)) },
      {
        t: "Median IT age", v: medAge, r: true, render: (r) => {
          const v = medAge(r);
          return v === null
            ? <span style={{ color: "var(--muted-2)" }}>–</span>
            : <span className={`age ${v > 90 ? "old" : ""}`}>{fmt(v)}d</span>;
        },
      },
      { t: "Regions", v: co("region_count"), r: true },
      {
        t: "Top technologies", v: techs, sortKey: (r) => techs(r).length,
        render: (r) => techs(r).slice(0, 5).map((t, i) => <span className="chip" key={i}>{t}</span>),
      },
    ];
  }, [co]);

  const rows = useMemo(() => {
    const name = co<string>("company_name");
    const klass = co<string>("company_class");
    const isComp = co<boolean>("is_competitor");
    const isNoise = co<boolean>("is_noise");
    const itN = co<number>("it_postings");
    const qq = q.trim().toLowerCase();
    return CO.rows.filter((r) =>
      (!qq || name(r).toLowerCase().includes(qq))
      && (!cls || klass(r) === cls)
      && (!hideComp || !isComp(r))
      && (!hideNoise || !isNoise(r))
      && itN(r) >= minIt);
  }, [CO, co, q, cls, hideComp, hideNoise, minIt]);

  return (
    <Screen id="companies" group="companies" on={on}>
      <p className="label">Companies &middot; the demand side</p>
      <h2>Every company<br />we found</h2>
      <p className="lede">All {fmt(data.meta.companies_total)} employers, after merging the different spellings of the same company
        into one. Each is labelled by what it is &mdash; a business that might buy from us, a
        recruitment agency, an IT firm we compete with &mdash; because that label decides whether it
        can appear as a sales lead at all. <em>Review</em> marks the ones we could not tell apart
        automatically.</p>

      <div className="controls">
        <input type="search" id="co-q" placeholder="Search company…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select id="co-class" value={cls} onChange={(e) => setCls(e.target.value)}>
          <option value="">All classes</option>
          {data.options.classes.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select id="co-minit" value={minIt} onChange={(e) => setMinIt(+e.target.value)}>
          <option value="0">Any IT volume</option>
          <option value="1">1+ IT postings</option>
          <option value="3">3+ IT postings</option>
          <option value="10">10+ IT postings</option>
        </select>
        <label className="chk"><input type="checkbox" id="co-hidecomp" checked={hideComp} onChange={(e) => setHideComp(e.target.checked)} /> Hide competitors</label>
        <label className="chk"><input type="checkbox" id="co-hidenoise" checked={hideNoise} onChange={(e) => setHideNoise(e.target.checked)} /> Hide noise</label>
        <Count id="co-count" n={rows.length} total={CO.rows.length} noun="companies" />
      </div>
      <DataTable columns={columns} rows={rows} sort={3} dir={-1} bodyId="co-body" />
    </Screen>
  );
}
