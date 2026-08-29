import { useCallback, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Ranks, Series, type BarRow } from "./Chart";

/* The AI layer, in one component.

   Everything here talks to `python -m opradar.ask`, which serves this page and
   holds the credentials. A page opened straight off disk gets no answer from
   the probe below and shows no AI buttons at all -- the same honest behaviour
   the ask box already has, because a button that cannot do anything is worse
   than no button.

   The server returns render blocks, never raw model output: quotes and links
   are rendered from our own parquet files, and any figure the number guard
   could not find in the facts arrives already flagged. So this file only has
   to lay blocks out; it never has to decide whether to believe them. */

export interface AiLink { title: string; url: string; meta: string }
export interface AiQuote { quote: string; note: string }

export type AiBlock =
  | { kind: "lede" | "para"; text: string }
  | { kind: "section"; label: string; text: string }
  | { kind: "script"; label: string; lang: string; text: string }
  | { kind: "verdict"; label: string; tone?: string; text: string; note?: string }
  | { kind: "bullets"; label: string; tone?: string; items: string[] }
  | { kind: "quotes"; label: string; items: AiQuote[] }
  | { kind: "links"; label: string; items: AiLink[] }
  | { kind: "table"; label: string; columns: string[]; rows: (string | number)[][] }
  /* Drawn from OUR arrays. The model chose which chart to show, by number;
     it never saw the points and could not have written one. */
  | { kind: "chart"; title: string; what: string; chart: "series" | "ranks";
      unit?: string; points: [string, number][] };

export interface AiReply {
  task: string;
  title: string;
  subtitle: string;
  blocks: AiBlock[];
  footer: string;
  model: string;
  cached: boolean;
  unverified_numbers: string[];
}

interface AiProbe { ok?: boolean; model?: string; tasks?: string[]; cached?: number }

/* One probe for the whole page, not one per button: the Opportunities table
   alone mounts a button per open row. */
let probe: Promise<AiProbe | null> | null = null;
function askProbe(): Promise<AiProbe | null> {
  if (!probe) {
    probe = fetch("/ai")
      .then((r) => (r.ok ? (r.json() as Promise<AiProbe>) : null))
      .catch(() => null);
  }
  return probe;
}

/** True once the analyst has answered. Drives whether AI controls exist. */
export function useAi(): AiProbe | null {
  const [state, setState] = useState<AiProbe | null>(null);
  useEffect(() => {
    let alive = true;
    askProbe().then((p) => { if (alive && p && p.ok) setState(p); });
    return () => { alive = false; };
  }, []);
  return state;
}

function Blocks({ blocks }: { blocks: AiBlock[] }) {
  return (
    <>
      {blocks.map((b, i) => {
        switch (b.kind) {
          case "lede":
            return <p className="ai-lede" key={i}>{b.text}</p>;
          case "para":
            return <p className="ai-para" key={i}>{b.text}</p>;
          case "section":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}</p>
                <p className="ai-para">{b.text}</p>
              </div>
            );
          case "script":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}</p>
                <blockquote className="ai-script" lang={b.lang}>{b.text}</blockquote>
              </div>
            );
          case "verdict":
            return (
              <div className={`ai-verdict ${b.tone || ""}`} key={i}>
                <p className="k">{b.label}</p>
                <p className="v">{b.text}</p>
                {b.note && <p className="n">{b.note}</p>}
              </div>
            );
          case "bullets":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}</p>
                <ul className={`why ${b.tone === "warn" ? "risk" : ""}`}>
                  {b.items.map((t, k) => <li key={k}>{t}</li>)}
                </ul>
              </div>
            );
          case "quotes":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}
                  <span className="sfx">copied from the advertisement, never paraphrased</span></p>
                {b.items.map((q, k) => (
                  <blockquote className="ai-quote" key={k}>
                    {q.quote}
                    {q.note && <span className="tag pub">{q.note}</span>}
                  </blockquote>
                ))}
              </div>
            );
          case "chart": {
            /* pre-sorted descending in pandas, so the first bar is the driver
               and gets the ink; the rest stay iris */
            const rows: BarRow[] = b.points.map(
              ([k, v], n) => [k, v, b.chart === "ranks" && n === 0 ? "acc" : ""]);
            return (
              <div className="ai-sec ai-chart" key={i}>
                <p className="evhead">{b.title}
                  <span className="sfx">counted in pandas &mdash; the model chose the chart, not the numbers</span></p>
                {b.chart === "series"
                  ? <Series rows={rows} height={200} unit={b.unit} areaLabel="open roles" />
                  : <Ranks rows={rows} layout="vertical" unit={b.unit} labelWidth={148} />}
                <p className="ai-cap">{b.what}</p>
              </div>
            );
          }
          case "links":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}
                  <span className="sfx">opens on arbeitsagentur.de</span></p>
                <ul className="ai-links">
                  {b.items.map((l, k) => (
                    <li key={k}>
                      <a href={l.url} target="_blank" rel="noopener">{l.title}</a>
                      <span className="meta">{l.meta}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          case "table":
            return (
              <div className="ai-sec" key={i}>
                <p className="evhead">{b.label}</p>
                <div className="ai-tw">
                  <table>
                    <thead><tr>{b.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>
                      {b.rows.map((r, k) => (
                        <tr key={k}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          default:
            return null;
        }
      })}
    </>
  );
}

const KIND: Record<string, string> = {
  outreach: "Suggested approach",
  gap: "Sourcing brief",
  summary: "What this view shows",
  cohort: "Cohort briefing",
  company: "Account brief",
};

/* The result opens in a drawer, not under the button.

   These buttons sit inside table rows, and several of those tables scroll
   inside a capped box -- an answer rendered in place was clipped by its own
   container and read as broken. A drawer is portalled to <body>, so no
   `overflow` above it can cut it off, it scrolls on its own, and the table
   underneath keeps the size it was designed at. */
/* The shape of an answer, before there is one. Not a spinner: a spinner says
   "something is happening", this says "a headline, three sections and a chart
   are on their way", which is the honest promise and makes the wait shorter. */
function Skeleton() {
  return (
    <div className="ai-skel" aria-live="polite" aria-label="Reading the evidence">
      <span className="sk sk-lede" />
      <span className="sk sk-lede short" />
      {[0, 1, 2].map((i) => (
        <div className="sk-sec" key={i}>
          <span className="sk sk-head" />
          <span className="sk sk-line" />
          <span className="sk sk-line" />
          <span className="sk sk-line short" />
        </div>
      ))}
      <span className="sk sk-chart" />
      <p className="sk-note">Reading the evidence &mdash; the figures are counted
        first, then the model is handed only those.</p>
    </div>
  );
}

function Drawer({ out, busy, pending, onRewrite, onClose }: {
  out: AiReply | null; busy: boolean; pending: ReactNode;
  onRewrite: () => void; onClose: () => void;
}) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return createPortal(
    <div className="ai-scrim" onClick={onClose}>
      <aside className="ai-drawer" role="dialog" aria-modal="true"
        aria-label={out ? `${KIND[out.task] || "Analysis"}: ${out.title}` : "Working"}
        onClick={(e) => e.stopPropagation()}>
        <header className="ai-head">
          <div>
            <p className="label">{out ? (KIND[out.task] || "Analysis") : "Working"}</p>
            <h4>{out ? out.title : pending}</h4>
            <p className="ai-sub">{out ? out.subtitle : "counting the evidence"}</p>
          </div>
          <div className="ai-actions">
            {out?.cached && (
              <span className="tag" title="Generated earlier and stored on disk, so this cost nothing and works offline">cached</span>
            )}
            {out && (
              <button className="ai-link" onClick={onRewrite} disabled={busy}>
                {busy ? "…" : "Rewrite"}
              </button>
            )}
            <button className="ai-x" onClick={onClose} aria-label="Close">×</button>
          </div>
        </header>

        <div className="ai-body">
          {out ? (
            <>
              <Blocks blocks={out.blocks} />
              <p className="ai-foot">{out.footer}.</p>
            </>
          ) : <Skeleton />}
        </div>
      </aside>
    </div>,
    document.body,
  );
}

type Args = Record<string, unknown>;

interface ButtonProps {
  task: string;
  args: Args;
  label: string;
  /** shown beside the button before anything has been generated */
  hint?: string;
  /** small text button rather than the filled one */
  small?: boolean;
}

/** A button that asks the analyst for one thing, and the drawer it opens. */
export function AiButton({ task, args, label, hint, small }: ButtonProps) {
  const live = useAi();
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<AiReply | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback((refresh: boolean) => {
    setBusy(true);
    setErr(null);
    fetch("/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, ...args, refresh }),
    })
      .then(async (r) => {
        const j = (await r.json()) as AiReply & { error?: string };
        if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
        return j;
      })
      .then((j) => { setOut(j); })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [task, args]);

  /* While it works the drawer is titled by what it is about, not by the button
     that was pressed: "Deichmann SE" is what you are waiting for, "Write the
     full brief" is what you already did. */
  const a = args as Record<string, unknown>;
  const subject = [a.company, a.cohort, a.cell, a.label].find(
    (x): x is string => typeof x === "string" && !!x) || label;

  /* No analyst, no button. The static page is honest about what it cannot do. */
  if (!live) return null;

  return (
    <div className="ai" onClick={(e) => e.stopPropagation()}>
      <div className="ai-cta">
        <button className={small ? "ai-btn sm" : "ai-btn"} disabled={busy}
          onClick={() => run(false)}>
          {busy ? "Reading the evidence…" : label}
        </button>
        {hint && !busy && !out && <span className="ai-hint">{hint}</span>}
      </div>

      {err && (
        <p className="ai-err">Could not generate that: {err}
          {" "}<button className="ai-link" onClick={() => run(false)}>try again</button>
        </p>
      )}

      {(out || busy) && (
        <Drawer out={out} busy={busy} pending={subject} onRewrite={() => run(true)}
          onClose={() => { setOut(null); setBusy(false); }} />
      )}
    </div>
  );
}
