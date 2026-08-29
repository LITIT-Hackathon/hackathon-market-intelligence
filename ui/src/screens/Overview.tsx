import { useMemo, useState } from "react";
import { Screen, type Tab } from "../App";
import { Cols, HBar, type BarRow } from "../components/Charts";
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
      <h2>What the market<br />looks like</h2>
      <p className="lede">The German job market as it stood on the snapshot date &mdash; who is hiring,
        for what, where, and how long the roles stay open. Nothing here is scored or ranked; it is
        the raw picture the sales list is built from.</p>

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
          <HBar rows={C.kldb_groups.map<BarRow>((r) => [r[0], r[1], r[2] ? "acc" : ""])} />
        </div>
        <div className="panel" style={{ order: 2 }}>
          <p className="label">Supply side</p><h3>Who is posting</h3>
          <p className="hint">Postings by company class. Highlighted classes compete with us for the same placements.</p>
          <HBar rows={C.classes.map<BarRow>((r) => [r[0], r[1], r[2] ? "acc" : ""])} />
        </div>
        <div className="panel" style={{ order: 3 }}>
          <p className="label">Stack</p><h3>Technologies in IT postings</h3>
          <p className="hint">From job titles only — roughly a third of IT postings name a technology. Descriptions would raise this.</p>
          <HBar rows={C.tech} />
        </div>
        <div className="panel" style={{ order: 5 }}>
          <p className="label">Sector</p><h3>Market domains</h3>
          <p className="hint">Across all postings — the sector a role sits in, detected separately from the technology stack. Domain fit is a first-class matching dimension.</p>
          <HBar rows={C.domains} />
        </div>
        <div className="panel" style={{ order: 1 }}>
          <p className="label">Scarcity</p><h3>How long postings stay open</h3>
          <p className="hint">Highlighted buckets are roles the market is failing to fill.</p>
          <Cols rows={C.age_buckets.map<BarRow>((r) => [r[0], r[1], r[0].startsWith("180") || r[0].startsWith("91") ? "acc" : ""])} />
        </div>
        <div className="panel" style={{ order: 6 }}>
          <p className="label">Qualification</p><h3>Requirement level</h3>
          <p className="hint">KldB 5th digit. Present on 99.8% of postings — the reliable way to stratify by level.</p>
          <HBar rows={C.levels} />
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
          <HBar rows={perCapita ? regionRel : regionAbs} />
        </div>
        <div className="panel wide" style={{ order: 8 }}>
          <p className="label">Careful</p><h3>Postings by month posted</h3>
          <p className="hint">Last 18 months.</p>
          <Cols rows={C.months.map<BarRow>((r) => [r[0], r[1], ""])} every={3} />
          <div className="note"><b>This chart is a trap.</b> It looks like the market tripled, and it did not.
            The snapshot only contains postings that were still <em>open</em> on the crawl date — older ones
            are missing because they were <em>filled</em>. This is a survival curve, not a demand curve.
            Real trend data has to come from repeated crawls or an explicit "posted in the last N days" filter.
            It is shown here so nobody rebuilds it by accident.</div>
        </div>
      </div>
    </Screen>
  );
}
