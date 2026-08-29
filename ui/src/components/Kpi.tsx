import type { ReactNode } from "react";

export function Kpi({ label, v, n, hl, id }: { label: ReactNode; v: ReactNode; n: ReactNode; hl?: boolean; id?: string }) {
  return (
    <div className={hl ? "kpi hl" : "kpi"}>
      <p className="label">{label}</p>
      <p className="v num" id={id}>{v}</p>
      <p className="n">{n}</p>
    </div>
  );
}

/** Two-column key/value table used on the quality screen. */
export function Kv({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <table className="kv">
      <tbody>
        {rows.map(([k, v], i) => (
          <tr key={i}><td>{k}</td><td>{v}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

/** Python's f"{x:.0f}": round half to even, so labels match the pandas side. */
export function f0(x: number): string {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return String(f + 1);
  if (d < 0.5) return String(f);
  return String(f % 2 === 0 ? f : f + 1);
}

/** Python's f"{x:,.0f}" */
export function f0c(x: number): string {
  return Number(f0(x)).toLocaleString("en-US");
}
