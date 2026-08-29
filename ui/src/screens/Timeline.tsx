import { useLayoutEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import type { TimelineAd } from "../data";

/* ------------------------------------------------------ open-roles timeline
   The snapshot is a STOCK of ads that were open on the crawl date, so every
   ad counts as open from the day it went up until the day we verified it
   gone: this curve is real concurrent demand, not a per-day posting
   histogram (length bias makes those meaningless). Between the snapshot and
   the re-check we know nothing, so that stretch is drawn as an explicit
   dashed gap instead of a guessed fill date. Hovering anywhere reads out the
   roles that were open at that moment. */

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ELLIPSIS = "…";

/* SVG has no word wrap, and clipping titles mid-word was the whole problem
   with the first version: wrap to two lines, ellipsis only as a last resort */
function tlWrap(t: string, per: number, maxLines: number): string[] {
  const words = String(t).split(/\s+/);
  const lines: string[] = [];
  let cur = "", cut = false;
  for (const w of words) {
    const next = cur ? cur + " " + w : w;
    if (next.length <= per) { cur = next; continue; }
    if (cur && lines.length + 1 >= maxLines) { cut = true; break; }
    if (cur) lines.push(cur);
    cur = w.length > per ? w.slice(0, per - 1) + ELLIPSIS : w;
  }
  if (cur) lines.push(cur);
  if (cut) {
    const i = lines.length - 1;
    lines[i] = lines[i].slice(0, per - 1).replace(/[\s,;/-]+$/, "") + ELLIPSIS;
  }
  return lines.slice(0, maxLines);
}

interface OpenRole { title: string; url: string; live: boolean | null; family: string; when: string }
interface Period {
  a0: number; a1: number; open: TimelineAd[]; tail: boolean;
  n: number; x0: number; x1: number; y: number;
  /** the posting day that opened it */
  day: number | null;
  label: string;
  roles: OpenRole[];
}
interface Label {
  d: number; x: number; ups: TimelineAd[]; lines: string[]; w: number; dead: boolean;
  lx: number; lane: number; hide: boolean;
}
interface Model {
  W: number; H: number; L: number; R: number; T: number; PH: number; pw: number;
  xSnap: number; wB: number; lastD: number; lo: number; yMax: number;
  periods: Period[]; labels: Label[]; vis: Label[]; lanes: number;
  Y: (c: number) => number; X: (a: number) => number; laneTop: (k: number) => number;
  dstr: (a: number, yr?: boolean) => string;
  after: Map<number, number>;
  downs: { d: number; n: number }[];
  solid: [number, number][]; dash: [number, number][];
  ads: TimelineAd[]; maxAge: number; liveN: number; deadN: number; unkN: number;
}

const LN = 13.5, LMAX = 3, CH = 6.15;

function build(tl: TimelineAd[]): Model {
  const ads = tl.slice().sort((a, b) => b.age - a.age);          /* oldest first */

  /* +1 the day an ad went up, -1 the day we verified it gone */
  const evm = new Map<number, { up: TimelineAd[]; down: TimelineAd[] }>();
  const slot = (d: number) => {
    let s = evm.get(d);
    if (!s) { s = { up: [], down: [] }; evm.set(d, s); }
    return s;
  };
  ads.forEach((a) => {
    slot(a.age).up.push(a);
    if (a.gone !== null && a.gone !== undefined && a.gone < a.age) slot(a.gone).down.push(a);
  });
  const days = [...evm.keys()].sort((a, b) => b - a);            /* left -> right */

  const maxAge = ads[0].age;
  const lastD = days[days.length - 1];
  /* a tail past the last take-down, otherwise the drop lands exactly on the
     right edge and the state it drops TO is a zero-width period */
  const tail = lastD < 0 ? Math.max(3, Math.round(-lastD * 0.14)) : 0;
  const hi = lastD < 0 ? lastD - tail : 0;                       /* right edge, days ago */
  const lo = Math.max(maxAge + 3, 10);                           /* left edge */

  const W = 1000, L = 46, R = 20, B = 40, PH = 152;
  const pw = W - L - R;
  const gapShare = hi < 0 ? 0.19 : 0;    /* the unobserved stretch, compressed */
  const wA = pw * (1 - gapShare), wB = pw - wA;
  const X = (a: number) => (a >= 0 ? L + ((lo - a) / lo) * wA : L + wA + ((-a) / (-hi)) * wB);
  const xSnap = L + wA;

  const withDate = ads.find((a) => a.posted);
  const snapMs = withDate ? Date.parse(withDate.posted as string) + withDate.age * 864e5 : null;
  const dstr = (a: number, yr?: boolean) => {
    if (snapMs === null) return a >= 0 ? a + "d ago" : (-a) + "d later";
    const d = new Date(snapMs - a * 864e5);
    return d.getDate() + " " + MON[d.getMonth()] + (yr ? " " + d.getFullYear() : "");
  };

  /* periods: a run of days over which the set of open roles does not change */
  const periods: Period[] = [];
  const after = new Map<number, number>();
  let open: TimelineAd[] = [], cursor = lo;
  const mk = (a0: number, a1: number, o: TimelineAd[], tailP: boolean): Period => ({
    a0, a1, open: o, tail: tailP, n: 0, x0: 0, x1: 0, y: 0, day: null, label: "", roles: [],
  });
  days.forEach((d) => {
    periods.push(mk(cursor, d, open.slice(), false));
    const ev = evm.get(d)!;
    open = open.filter((x) => ev.down.indexOf(x) < 0).concat(ev.up);
    after.set(d, open.length);
    cursor = d;
  });
  periods.push(mk(cursor, hi, open.slice(), tail > 0));
  periods.forEach((q) => { q.n = q.open.length; q.x0 = X(q.a0); q.x1 = X(q.a1); });
  const yMax = Math.max(2, periods.reduce((m, q) => Math.max(m, q.n), 0) + 1);

  /* one label per posting day, packed into lanes so two can never collide */
  const labels: Label[] = [];
  days.forEach((d) => {
    const ev = evm.get(d)!;
    if (!ev.up.length) return;
    const lines = tlWrap(ev.up[0].title, 30, 2);
    if (ev.up.length > 1) {                     /* the counter never wraps alone */
      const suf = "  +" + (ev.up.length - 1);
      const i = lines.length - 1;
      if (lines[i].length + suf.length > 30) lines[i] = lines[i].slice(0, 27 - suf.length) + ELLIPSIS;
      lines[i] += suf;
    }
    labels.push({
      d, x: X(d), ups: ev.up, lines,
      w: Math.max(...lines.map((x) => x.length)) * CH + 20,
      dead: ev.up.every((a) => a.live === false),
      lx: 0, lane: 0, hide: false,
    });
  });
  const laneEnd: number[] = [];
  let lanes = 1;
  labels.forEach((lb) => {
    lb.lx = Math.min(Math.max(lb.x, L + lb.w / 2), W - R - lb.w / 2);
    let k = 0;
    while (k < LMAX && laneEnd[k] !== undefined && laneEnd[k] > lb.lx - lb.w / 2) k++;
    if (k >= LMAX) { lb.hide = true; return; }   /* too dense to label: it is in the hover */
    lb.lane = k;
    laneEnd[k] = lb.lx + lb.w / 2 + 10;
    lanes = Math.max(lanes, k + 1);
  });

  const LANEH = 2 * LN + 11;
  const T = 12 + lanes * LANEH + 24;
  const H = Math.round(T + PH + B);
  const Y = (c: number) => T + (1 - c / yMax) * PH;
  const laneTop = (k: number) => 12 + (lanes - 1 - k) * LANEH;
  periods.forEach((q) => { q.y = Y(q.n); });

  /* ---- the step line: solid where observed, dashed across the gap ---- */
  const pts: [number, number][] = [];
  let cc = 0;
  pts.push([L, Y(0)]);
  days.forEach((d) => {
    const x = X(d);
    pts.push([x, Y(cc)]);
    cc = after.get(d)!;
    pts.push([x, Y(cc)]);
  });
  pts.push([X(hi), Y(cc)]);

  const solid: [number, number][] = [], dash: [number, number][] = [];
  pts.forEach((q) => {
    if (q[0] <= xSnap + 0.01) solid.push(q);
    else {
      if (!dash.length) dash.push([xSnap, solid[solid.length - 1][1]]);
      dash.push(q);
    }
  });
  if (dash.length && solid[solid.length - 1][0] < xSnap - 0.01)
    solid.push([xSnap, solid[solid.length - 1][1]]);

  periods.forEach((q) => {
    q.day = q.a0 >= lo ? null : q.a0;
    q.label = q.tail ? "as of " + dstr(q.a0)
      : (q.a0 >= lo ? "before " + dstr(q.a1) : dstr(q.a0) + " – " + dstr(q.a1));
    q.roles = q.open.map((a) => ({ title: a.title, url: a.url, live: a.live, family: a.family, when: dstr(a.age, true) }));
  });

  const downs = days.filter((d) => evm.get(d)!.down.length).map((d) => ({ d, n: evm.get(d)!.down.length }));
  const liveN = ads.filter((a) => a.live === true).length;
  const deadN = ads.filter((a) => a.live === false).length;
  const unkN = ads.length - liveN - deadN;

  return {
    W, H, L, R, T, PH, pw, xSnap, wB, lastD, lo, yMax, periods, labels,
    vis: labels.filter((lb) => !lb.hide), lanes, Y, X, laneTop, dstr, after, downs,
    solid, dash, ads, maxAge, liveN, deadN, unkN,
  };
}

const f = (v: number) => v.toFixed(1);
const pstr = (arr: [number, number][]) => arr.map((q, i) => (i ? "L" : "M") + f(q[0]) + " " + f(q[1])).join(" ");

let seq = 0;

interface Hover { qi: number; cx: number; cy: number; vx: number }

export function Timeline({ tl }: { tl: TimelineAd[] }) {
  const [id] = useState(() => "tl" + (++seq));
  const m = useMemo(() => (tl && tl.length ? build(tl) : null), [tl]);
  const [hover, setHover] = useState<Hover | null>(null);
  const [pinned, setPinned] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const tip = useRef<HTMLDivElement>(null);

  /* Flip to the other side of the cursor rather than clamping: clamping
     parks the panel on top of the half of the chart being pointed at. */
  useLayoutEffect(() => {
    if (!hover || !tip.current || !box.current) return;
    const t = tip.current, b = box.current;
    const tw = t.offsetWidth, th = t.offsetHeight;
    const bw = b.clientWidth, bh = b.clientHeight, PAD = 8, OFF = 18;
    const { cx, cy } = hover;
    const left = cx + OFF + tw <= bw - PAD ? cx + OFF
      : (cx - OFF - tw >= PAD ? cx - OFF - tw : Math.max(PAD, bw - tw - PAD));
    t.style.left = left + "px";
    t.style.top = Math.max(PAD, Math.min(cy - th / 2, bh - th - PAD)) + "px";
  }, [hover]);

  if (!m) return null;

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    if (pinned || !svg.current || !box.current) return;
    const r = svg.current.getBoundingClientRect(), b = box.current.getBoundingClientRect();
    const vx = ((e.clientX - r.left) / r.width) * m.W;
    let qi = -1;
    m.periods.forEach((z, i) => { if (vx >= z.x0 - 0.5) qi = i; });
    if (qi < 0) { setHover(null); return; }
    setHover({ qi, cx: e.clientX - b.left, cy: e.clientY - b.top, vx });
  };
  const onLeave = () => { if (!pinned) setHover(null); };
  const onClick = (e: MouseEvent<SVGSVGElement>) => {
    const t = e.target as Element;
    if (t.closest && t.closest("a")) return;
    const np = !pinned;
    setPinned(np);
    if (!np) setHover(null);
  };

  const q = hover ? m.periods[hover.qi] : null;
  const litDay = q ? q.day : null;
  const { W, H, L, R, T, PH, pw, xSnap, wB, lastD, lo, yMax, Y, X, laneTop, dstr, after } = m;

  /* ---- grid + axes ---- */
  const grid = [];
  const yStep = Math.max(1, Math.ceil(yMax / 4));
  for (let c = 0; c <= yMax; c += yStep) {
    grid.push(
      <g key={"y" + c}>
        <line x1={L} y1={f(Y(c))} x2={W - R} y2={f(Y(c))} stroke="#2B2E2C" />
        <text x={L - 10} y={f(Y(c) + 4)} textAnchor="end" fontSize="11.5" fill="#8D918E">{c}</text>
      </g>,
    );
  }
  const NT = 5;
  const ticks = [];
  for (let i = 0; i < NT; i++) {
    const a = lo - (lo * i) / NT, x = X(a);
    ticks.push(
      <g key={"x" + i}>
        <line x1={f(x)} y1={f(T)} x2={f(x)} y2={f(T + PH)} stroke="#232624" />
        <text x={f(x)} y={f(T + PH + 17)} textAnchor="middle" fontSize="11" fill="#8D918E">{dstr(a)}</text>
      </g>,
    );
  }

  const vw = q ? 17 + String(q.n).length * 7 : 0;
  return (
    <div className="tlc" id={id} ref={box}>
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} xmlns="http://www.w3.org/2000/svg" fontFamily="Inter,Arial,sans-serif"
        onMouseMove={onMove} onMouseLeave={onLeave} onClick={onClick}>
        <defs>
          <linearGradient id={id + "g"} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FFEB00" stopOpacity=".2" />
            <stop offset="1" stopColor="#FFEB00" stopOpacity="0" />
          </linearGradient>
        </defs>
        {grid}
        <text transform={`translate(15,${f(T + PH / 2)}) rotate(-90)`} textAnchor="middle"
          fontSize="9.5" letterSpacing="1.3" fill="#6B6F6C">OPEN ROLES</text>
        {ticks}

        {/* ---- the snapshot divider and the stretch we have no data for ---- */}
        {wB > 0 && (
          <>
            <rect x={f(xSnap)} y={f(T)} width={f(wB)} height={PH} fill="#FFFFFF" opacity=".035" />
            <text x={f((xSnap + X(lastD)) / 2)} y={f(T + PH + 17)} textAnchor="middle"
              fontSize="10.5" fill="#6B6F6C">not observed</text>
            <text x={W - R} y={f(T - 12)} textAnchor="end" fontSize="9.5" letterSpacing="1.1"
              fill="#8D918E">RE-CHECKED {dstr(lastD).toUpperCase()}</text>
          </>
        )}
        <line x1={f(xSnap)} y1={f(T - 6)} x2={f(xSnap)} y2={f(T + PH + 3)} stroke="#565A57" strokeDasharray="2 4" />
        <text x={f(xSnap - 6)} y={f(T - 12)} textAnchor="end" fontSize="9.5" letterSpacing="1.1"
          fill="#8D918E">SNAPSHOT {dstr(0).toUpperCase()}</text>

        {/* ---- the step line ---- */}
        <path d={`${pstr(m.solid)} L${f(m.solid[m.solid.length - 1][0])} ${f(T + PH)} L${L} ${f(T + PH)} Z`} fill={`url(#${id}g)`} />
        <path d={pstr(m.solid)} fill="none" stroke="#FFEB00" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" />
        {m.dash.length > 0 && (
          <path d={pstr(m.dash)} fill="none" stroke="#FFEB00" strokeWidth="2" strokeDasharray="5 5" opacity=".5" strokeLinejoin="round" />
        )}

        {/* ---- markers: a dot per step up, a ring per verified take-down ----
            a bare 4.5px dot disappears against the line it sits on: each marker is
            a solid core inside a translucent halo that grows when its step is
            hovered, so the point of change is unmistakable */}
        {m.labels.map((lb) => {
          const cy = Y(after.get(lb.d)!);
          return (
            <g className={lb.d === litDay ? "tlm on" : "tlm"} key={"m" + lb.d}>
              <circle className="halo" cx={f(lb.x)} cy={f(cy)} r="9.5"
                fill={lb.dead ? "#8D918E" : "#FFEB00"} opacity={lb.dead ? ".1" : ".16"} />
              <circle cx={f(lb.x)} cy={f(cy)} r="5.5" fill={lb.dead ? "#1A1C1B" : "#FFEB00"}
                stroke={lb.dead ? "#8D918E" : "#1A1C1B"} strokeWidth="2.5" />
            </g>
          );
        })}
        {m.downs.map(({ d, n }) => {
          const x = X(d), y = Y(after.get(d)!);
          return (
            <g className={d === litDay ? "tlm on" : "tlm"} key={"d" + d}>
              <circle className="halo" cx={f(x)} cy={f(y)} r="9.5" fill="#8D918E" opacity=".1" />
              <circle cx={f(x)} cy={f(y)} r="5.5" fill="#1A1C1B" stroke="#A8ADA9" strokeWidth="2.5" />
              <text x={f(x - 12)} y={f(y + 4)} textAnchor="end" fontSize="11.5" fontWeight="600"
                fill="#A8ADA9">{"−"}{n} taken down</text>
            </g>
          );
        })}

        {/* ---- labels: leaders first, then chips, so nothing draws over a title ---- */}
        {m.vis.map((lb) => {
          const top = laneTop(lb.lane), h = lb.lines.length * LN + 9;
          return (
            <line className={lb.d === litDay ? "tll on" : "tll"} key={"l" + lb.d}
              x1={f(lb.lx)} y1={f(top + h)} x2={f(lb.x)} y2={f(Y(after.get(lb.d)!) - 10)} />
          );
        })}
        {m.vis.map((lb) => {
          const top = laneTop(lb.lane), h = lb.lines.length * LN + 9, x0 = lb.lx - lb.w / 2;
          return (
            <g className={lb.d === litDay ? "tlb on" : "tlb"} key={"b" + lb.d}>
              <a href={lb.ups[0].url} target="_blank" rel="noopener">
                <title>{lb.ups.map((a) => a.title).join("\n")}</title>
                <rect className="cbg" x={f(x0)} y={f(top)} width={f(lb.w)} height={f(h)} rx="5" />
                <rect x={f(x0)} y={f(top)} width="2.5" height={f(h)} rx="1.2" fill={lb.dead ? "#8D918E" : "#FFEB00"} />
                {lb.lines.map((t, j) => (
                  <text key={j} x={f(x0 + 11)} y={f(top + 6 + LN * (j + 1) - 3)} fontSize="12"
                    fontWeight={j ? 400 : 600} fill={lb.dead ? "#9AA09C" : "#F2F2EE"}>{t}</text>
                ))}
              </a>
            </g>
          );
        })}

        {/* ---- hover layer: a full crosshair. The vertical line finds the date,
            the horizontal one runs back to the axis and carries the count, so
            the number can be read off the chart without going to the tooltip. */}
        {hover && q && (
          <g className="tlhi">
            <rect x={q.x0} y={f(T)} width={Math.max(0, q.x1 - q.x0)} height={PH} fill="#FFEB00" opacity=".07" />
            <line x1={hover.vx} x2={hover.vx} y1={f(T - 6)} y2={f(T + PH)} stroke="#FFEB00" opacity=".5" />
            <line x1={f(L)} x2={hover.vx} y1={q.y} y2={q.y} stroke="#FFEB00" opacity=".3" strokeDasharray="3 4" />
            <circle cx={hover.vx} cy={q.y} r="6" fill="#FFEB00" stroke="#1A1C1B" strokeWidth="2.5" />
            <g>
              <rect rx="4" x={L - 7 - vw} y={q.y - 9} width={vw} height="18" fill="#FFEB00" />
              <text x={L - 7 - vw / 2} y={q.y + 4} textAnchor="middle" fontSize="11.5" fontWeight="700" fill="#1A1C1B">{q.n}</text>
            </g>
          </g>
        )}
        <rect className="tlhit" x={L} y={f(T - 6)} width={f(pw)} height={f(PH + 6)} fill="transparent" />
      </svg>

      <div className={"tltip" + (hover ? " on" : "") + (pinned ? " pin" : "")} ref={tip}>
        <div className="ttbody">
          {q && (
            <>
              <div className="tth"><b>{q.n}</b> {q.n === 1 ? "role open" : "roles open"}<span>{q.label}</span></div>
              {q.roles.length ? (
                <>
                  {q.roles.slice(0, 5).map((a, i) => (
                    <a className={"ttr" + (a.live === false ? " dead" : a.live === true ? "" : " unk")}
                      href={a.url} target="_blank" rel="noopener" key={i}>
                      <i></i>
                      <span className="ttt">{a.title}</span>
                      <span className="ttm">{a.family} &middot; posted {a.when}{a.live === false ? " · since taken down" : ""}</span>
                    </a>
                  ))}
                  {q.roles.length > 5 && <div className="ttmore">+{q.roles.length - 5} more open at the time</div>}
                </>
              ) : (
                <div className="ttmore">Nothing open yet.</div>
              )}
            </>
          )}
        </div>
        <div className="tlpin">pinned &mdash; click the chart to release</div>
      </div>

      <div className="tlmeta">Every step up is one ad going live; the height is how many
        roles were open at the same time. <b>{m.ads.length}</b> ads over {m.maxAge} days
        {m.deadN ? <> &middot; <b>{m.deadN}</b> taken down by the re-check</> : null}
        {m.liveN ? <> &middot; <b>{m.liveN}</b> still live</> : null}
        {m.unkN ? <> &middot; {m.unkN} not re-checked</> : null}
        {" "}&middot; hover the line for the roles open on any date, click to pin.
        {m.labels.length > m.vis.length ? (
          <> <b>{m.labels.length - m.vis.length}</b> more posting days than fit as labels &mdash; they are all on the line.</>
        ) : null}
      </div>
    </div>
  );
}
