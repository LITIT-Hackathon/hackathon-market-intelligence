import { useMemo, type ReactNode } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmt } from "../format";

/* Charts, on Recharts.

   Two shapes, chosen by what the x-axis actually is:

     Series  an ORDINAL axis -- months, age buckets, years of experience,
             requirement level. These are continuous readings, so they are
             drawn as a line over an area, which is the only form that shows
             a trend rather than nine unrelated quantities.
     Ranks   a CATEGORICAL axis -- technologies, regions, occupational
             groups. There is no trend between "java" and "sap", so these
             stay bars; they are simply vertical, sorted, and hoverable
             instead of a wall of CSS divs.

   Both share the tokens the rest of the page uses. Iris is our side of the
   trade and owns the light panels; ink is the market; the yellow accent is
   illegible on white and never appears here. */

const INK = "#1A1C1B";
const IRIS = "#5B47F5";
const IRIS_LIT = "#9384FF";
const LINE = "#E4E4DF";
const MUTED2 = "#8D918E";
const PAPER = "#FFFFFF";

const AXIS = { fontSize: 11, fontFamily: "Inter, Arial, sans-serif", fill: MUTED2 };
const GRID = { stroke: LINE, strokeDasharray: "2 4" };

export type BarRow = [string, number, string?];

interface TipProps {
  active?: boolean;
  payload?: { name?: string; value?: number; color?: string; dataKey?: string }[];
  label?: string | number;
  fmtV?: (v: number) => string;
  unit?: string;
}

/** One tooltip for every chart here, so hovering feels the same everywhere. */
function Tip({ active, payload, label, fmtV, unit }: TipProps) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rc-tip">
      <p className="k">{label}</p>
      {payload.map((p, i) => (
        <p className="v" key={i}>
          <i style={{ background: p.color }} />
          {payload.length > 1 && <span className="n">{p.name}</span>}
          <b>{fmtV ? fmtV(Number(p.value)) : fmt(Number(p.value))}{unit || ""}</b>
        </p>
      ))}
    </div>
  );
}

const shorten = (s: string, n: number) =>
  s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;

/* ------------------------------------------------------------------ series */

interface SeriesProps {
  rows: BarRow[];
  height?: number;
  /** thin the x labels out when there are more than the axis can hold */
  every?: number;
  fmtV?: (v: number) => string;
  unit?: string;
  /** the reading is a share, so the axis starts at zero and ends at the max */
  areaLabel?: string;
}

/** A line over a soft fill: the ordinal charts. */
export function Series({ rows, height = 190, every, fmtV, unit, areaLabel }: SeriesProps) {
  const data = useMemo(
    () => rows.map((r) => ({ k: r[0], v: r[1], hi: r[2] === "acc" })), [rows]);
  const interval = every ? every - 1 : "preserveStartEnd";
  return (
    <div className="rc" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
          <defs>
            <linearGradient id="rc-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={IRIS} stopOpacity={0.22} />
              <stop offset="100%" stopColor={IRIS} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid {...GRID} vertical={false} />
          <XAxis dataKey="k" tick={AXIS} tickLine={false} axisLine={{ stroke: LINE }}
            interval={interval as number | "preserveStartEnd"} tickMargin={8} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52}
            tickFormatter={(v: number) => (fmtV ? fmtV(v) : fmt(v))} />
          <Tooltip content={<Tip fmtV={fmtV} unit={unit} />} cursor={{ stroke: LINE }} />
          <Area type="monotone" dataKey="v" name={areaLabel || "postings"}
            stroke={IRIS} strokeWidth={2} fill="url(#rc-fill)"
            dot={false} activeDot={{ r: 4, fill: IRIS, stroke: PAPER, strokeWidth: 2 }}
            animationDuration={420} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------- ranks */

interface RanksProps {
  rows: BarRow[];
  height?: number;
  fmtV?: (v: number) => string;
  unit?: string;
  /** long category names read better down the left than rotated underneath */
  layout?: "vertical" | "horizontal";
  labelWidth?: number;
}

/** Sorted categorical bars. `acc` on a row paints it ink instead of iris. */
export function Ranks({
  rows, height, fmtV, unit, layout = "vertical", labelWidth = 132,
}: RanksProps) {
  const data = useMemo(
    () => rows.map((r) => ({ k: r[0], v: r[1], hi: r[2] === "acc" })), [rows]);
  const h = height ?? (layout === "vertical" ? Math.max(150, data.length * 26 + 24) : 220);

  if (layout === "vertical") {
    // horizontal bars, categories down the left -- the readable choice when
    // the labels are words like "Softwareentwicklung" rather than months
    return (
      <div className="rc" style={{ height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical"
            margin={{ top: 2, right: 34, bottom: 2, left: 2 }} barCategoryGap="22%">
            <CartesianGrid {...GRID} horizontal={false} />
            <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false}
              tickFormatter={(v: number) => (fmtV ? fmtV(v) : fmt(v))} />
            <YAxis type="category" dataKey="k" tick={AXIS} tickLine={false}
              axisLine={{ stroke: LINE }} width={labelWidth}
              tickFormatter={(s: string) => shorten(s, Math.floor(labelWidth / 6.6))} />
            <Tooltip content={<Tip fmtV={fmtV} unit={unit} />}
              cursor={{ fill: "rgba(91,71,245,.06)" }} />
            <Bar dataKey="v" name="count" radius={[0, 3, 3, 0]} animationDuration={420}
              maxBarSize={17}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.hi ? INK : IRIS} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return (
    <div className="rc" style={{ height: h }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid {...GRID} vertical={false} />
          <XAxis dataKey="k" tick={AXIS} tickLine={false} axisLine={{ stroke: LINE }}
            interval={0} tickMargin={8} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52}
            tickFormatter={(v: number) => (fmtV ? fmtV(v) : fmt(v))} />
          <Tooltip content={<Tip fmtV={fmtV} unit={unit} />}
            cursor={{ fill: "rgba(91,71,245,.06)" }} />
          <Bar dataKey="v" name="count" radius={[3, 3, 0, 0]} animationDuration={420}
            maxBarSize={44}>
            {data.map((d, i) => <Cell key={i} fill={d.hi ? INK : IRIS} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------- legend note */

export function ChartNote({ children }: { children: ReactNode }) {
  return <p className="rc-note">{children}</p>;
}

export const IRIS_COLOR = IRIS;
export const INK_COLOR = INK;
export const IRIS_LIT_COLOR = IRIS_LIT;
