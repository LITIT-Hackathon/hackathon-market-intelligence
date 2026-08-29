import { fmt } from "../format";

export type BarRow = [string, number, string?];

/** Horizontal bars. `cls` on a row is 'acc' (yellow) or 'mut' (grey). */
export function HBar({ rows, format }: { rows: BarRow[]; format?: (v: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r[1]));
  return (
    <div className="hbar">
      {rows.map((r, i) => (
        <RowFrag key={i} r={r} max={max} format={format} />
      ))}
    </div>
  );
}

function RowFrag({ r, max, format }: { r: BarRow; max: number; format?: (v: number) => string }) {
  return (
    <>
      <div className="k" title={r[0]}>{r[0]}</div>
      <div className="t">
        <i className={r[2] || ""} style={{ width: `${((r[1] / max) * 100).toFixed(1)}%` }} />
      </div>
      <div className="v">{format ? format(r[1]) : fmt(r[1])}</div>
    </>
  );
}

/** Vertical columns with a label row; `every` thins the labels out. */
export function Cols({ rows, every }: { rows: BarRow[]; every?: number }) {
  const max = Math.max(1, ...rows.map((r) => r[1]));
  return (
    <>
      <div className="cols">
        {rows.map((r, i) => (
          <div
            key={i}
            className={r[2] || ""}
            style={{ height: `${Math.max(2, (r[1] / max) * 100)}%` }}
            title={`${r[0]}: ${fmt(r[1])}`}
          />
        ))}
      </div>
      <div className="colx">
        {rows.map((r, i) => (
          <span key={i}>{every && i % every ? "" : r[0]}</span>
        ))}
      </div>
    </>
  );
}

export type PairRow = [string, number, number, number?];

/** Paired bars: rows are [label, ours, market, tension?] -- the first bar is
    always our side of the trade, the second always the market's. */
export function HBar2({ rows, legend }: { rows: PairRow[]; legend?: [string, string] }) {
  const [lo, lm] = legend || ["supply", "demand"];
  const max = Math.max(1e-9, ...rows.flatMap((r) => [r[1], r[2]]));
  const tension = rows.some((r) => r[3] !== undefined);
  return (
    <>
      <div className="hbar2">
        {rows.map((r, i) => (
          <PairFrag key={i} r={r} max={max} lo={lo} lm={lm} />
        ))}
      </div>
      <div className="lg">
        <span><i className="s" />{lo}</span>
        <span><i className="d" />{lm}</span>
        {tension && <span style={{ marginLeft: "auto" }}>tension</span>}
      </div>
    </>
  );
}

function PairFrag({ r, max, lo, lm }: { r: PairRow; max: number; lo: string; lm: string }) {
  const a = ((r[1] / max) * 100).toFixed(1);
  const b = ((r[2] / max) * 100).toFixed(1);
  return (
    <>
      <div className="k" title={r[0]}>{r[0]}</div>
      <div className="t2">
        <i className="s" style={{ width: `${a}%` }} title={`${lo} ${(r[1] * 100).toFixed(1)}%`} />
        <i className="d" style={{ width: `${b}%` }} title={`${lm} ${(r[2] * 100).toFixed(1)}%`} />
      </div>
      <div className="v">{r[3] !== undefined ? r[3].toFixed(2) : ""}</div>
    </>
  );
}
