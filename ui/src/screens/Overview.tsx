import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Ranks, Series, type BarRow } from "../components/Chart";
import { Kpi } from "../components/Kpi";
import { f0 } from "../components/Kpi";
import type { Payload } from "../data";
import { fmt } from "../format";

export function Overview({ data, on }: { data: Payload; on: Tab }) {
  const C = data.charts;
  const m = data.meta;
  const [perCapita, setPerCapita] = useState(false);

  const regionAbs = useMemo<BarRow[]>(() => C.regions.map((r) => [r[0], r[1], ""]), [C]);
  const regionRel = useMemo<BarRow[]>(
    () =>
      C.regions
        .filter((r) => r[2])
        .map<BarRow>((r) => [r[0], Math.round(r[1] / (r[2] as number)), ""])
        .sort((a, b) => b[1] - a[1]),
    [C],
  );

  return (
    <Screen id="overview" group="companies" on={on}>
      <p className="label">Overview</p>
      <div className="kpis">
        <Kpi hl label="Companies hiring IT" v={fmt(m.it_companies_3plus)}
          n={<>with three or more IT roles open &mdash; the market we can sell into</>} />
        <Kpi label="Roles open past 3 months" v={f0(m.stale_share * 100) + "%"}
          n="German IT hiring is slow, and that slowness is the opening" />
        <Kpi label="Hiring done by agencies" v={f0(m.competitor_it_share * 100) + "%"}
          n="of IT roles are posted by recruiters and IT firms, not the employer" />
      </div>

      <details className="more">
        <summary>More numbers about the data</summary>
        <div className="kpis">
          <Kpi label="Job ads" v={fmt(m.postings_total)} n="after cleaning" />
          <Kpi label="Companies" v={fmt(m.entities)} n={`from ${fmt(m.raw_employers)} raw employer names`} />
          <Kpi label="IT job ads" v={fmt(m.it_postings)} n="official German occupation code 43" />
          <Kpi label="Typical time open" v={`${m.median_age}d`} n="middle of the range" />
        </div>
      </details>

      <div className="grid">
        <div className="panel" style={{ order: 4 }}>
          <p className="label">Demand</p><h3>Occupational groups</h3>
          <p className="hint">Top 10 of 37. IT highlighted.</p>
          <Ranks rows={C.kldb_groups.map<BarRow>((r) => [r[0], r[1], r[2] ? "acc" : ""])} labelWidth={150} />
        </div>
        <div className="panel" style={{ order: 2 }}>
          <p className="label">Supply side</p><h3>Who is posting</h3>
          <p className="hint">Postings by company class. Highlighted classes compete with us for the same placements.</p>
          <Ranks rows={C.classes.map<BarRow>((r) => [r[0], r[1], r[2] ? "acc" : ""])} labelWidth={150} />
        </div>
        <div className="panel" style={{ order: 3 }}>
          <p className="label">Stack</p><h3>Technologies in IT postings</h3>
          <p className="hint">From job titles only — roughly a third of IT postings name a technology. Descriptions would raise this.</p>
          <Ranks rows={C.tech} />
        </div>
        <div className="panel" style={{ order: 5 }}>
          <p className="label">Sector</p><h3>Market domains</h3>
          <p className="hint">Across all postings — the sector a role sits in, detected separately from the technology stack. Domain fit is a first-class matching dimension.</p>
          <Ranks rows={C.domains} />
        </div>
        <div className="panel" style={{ order: 1 }}>
          <p className="label">Scarcity</p><h3>How long postings stay open</h3>
          <p className="hint">The tail past 90 days is what the market is failing to fill.
            The rise at the end is not a recovery &mdash; it is every unfilled role
            ever posted, piling up in the last bucket.</p>
          <Series rows={C.age_buckets.map<BarRow>((r) => [r[0], r[1], ""])} areaLabel="postings open" />
        </div>
        <div className="panel" style={{ order: 6 }}>
          <p className="label">Qualification</p><h3>Requirement level</h3>
          <p className="hint">KldB 5th digit. Present on 99.8% of postings — the reliable way to stratify by level.</p>
          <Series rows={C.levels} areaLabel="postings" />
        </div>
        <div className="panel wide" style={{ order: 7 }}>
          <p className="label">Geography</p><h3>Where the postings are</h3>
          <p className="hint" id="region-hint">
            {perCapita
              ? "Postings per million inhabitants. Bremen and Hamburg stay high, which is the crawl, not the market."
              : "Raw counts. These reflect crawl coverage as much as labour demand — switch to per-capita."}
          </p>
          <label className="chk spaced">
            <input type="checkbox" id="region-norm" checked={perCapita} onChange={(e) => setPerCapita(e.target.checked)} />
            {" "}Per million inhabitants
          </label>
          <Ranks rows={perCapita ? regionRel : regionAbs} labelWidth={168} />
        </div>
      </div>
    </Screen>
  );
}
