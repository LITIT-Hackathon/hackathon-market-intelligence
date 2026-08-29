import { useEffect, useRef, useState, type ReactNode } from "react";

/* Headline numbers arrive by counting up to themselves.

   Eased, not linear -- a linear counter reads as a progress bar, an eased one
   reads as a number settling. It runs off one rAF loop and lands EXACTLY on
   the target rather than near it, because the last frame is assigned, not
   interpolated: a KPI that stops at 141 of 142 is worse than one that never
   moved. Anyone who has asked their machine to stop animating gets the number
   straight away. */
const STILL = typeof window !== "undefined"
  && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function useCountUp(target: number, ms = 900, run = 0): number {
  const [v, setV] = useState(STILL ? target : 0);
  const from = useRef(0);
  useEffect(() => {
    if (STILL || !Number.isFinite(target)) { setV(target); return; }
    // a fresh run counts from zero again; a changed target continues from
    // wherever the last one got to, so a filter nudges rather than restarts
    const start = performance.now();
    const a = run === from.current ? from.current : (from.current = 0);
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      // cubic ease-out: fast off the mark, then it settles
      const e = 1 - Math.pow(1 - t, 3);
      const next = t >= 1 ? target : a + (target - a) * e;
      setV(next);
      from.current = next;
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, run]);
  return v;
}

/** A number that counts up to itself every time it comes on screen.

    Tied to visibility rather than to mount, because the screens stay mounted
    and only toggle `display` -- counting on mount would mean the numbers boom
    once, on the first tab you happen to land on, and sit still ever after. An
    element that is `display:none` does not intersect, so showing its tab is
    exactly the event we want. */
export function Num({ v, format, ms }: {
  v: number; format?: (n: number) => string; ms?: number;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const [run, setRun] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el || STILL || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setRun((r) => r + 1);
    }, { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const n = useCountUp(v, ms, run);
  const f = format || ((x: number) => Math.round(x).toLocaleString("en-US"));
  return <span ref={ref}>{f(n)}</span>;
}

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
