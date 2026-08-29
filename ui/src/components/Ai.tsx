import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

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
  | { kind: "table"; label: string; columns: string[]; rows: (string | number)[][] };

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

type Args = Record<string, unknown>;

interface ButtonProps {
  task: string;
  args: Args;
  label: string;
  /** shown under the button before anything has been generated */
  hint?: string;
  /** small text button rather than the filled one */
  small?: boolean;
  /** the panel opens above this, e.g. inside an already-open detail row */
  children?: ReactNode;
}

/** A button that asks the analyst for one thing, and the panel it opens. */
export function AiButton({ task, args, label, hint, small }: ButtonProps) {
  const live = useAi();
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<AiReply | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);

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

  /* No analyst, no button. The static page is honest about what it cannot do. */
  if (!live) return null;

  const stop = (e: React.MouseEvent) => { e.stopPropagation(); };

  return (
    <div className="ai" onClick={stop}>
      {!out && (
        <div className="ai-cta">
          <button className={small ? "ai-btn sm" : "ai-btn"} disabled={busy}
            onClick={() => run(false)}>
            {busy ? "Reading the evidence…" : label}
          </button>
          {hint && !busy && <span className="ai-hint">{hint}</span>}
        </div>
      )}

      {err && (
        <p className="ai-err">Could not generate that: {err}
          {" "}<button className="ai-link" onClick={() => run(false)}>try again</button>
        </p>
      )}

      {out && (
        <div className="ai-panel" ref={panel}>
          <div className="ai-head">
            <div>
              <p className="label">{out.task === "outreach" ? "Suggested approach"
                : out.task === "gap" ? "Sourcing brief"
                : out.task === "summary" ? "What this view shows"
                : out.task === "cohort" ? "Cohort briefing"
                : "Account brief"}</p>
              <h4>{out.title}</h4>
              <p className="ai-sub">{out.subtitle}</p>
            </div>
            <div className="ai-actions">
              {out.cached && <span className="tag" title="Generated earlier and stored on disk, so this cost nothing and works offline">cached</span>}
              <button className="ai-link" onClick={() => run(true)} disabled={busy}>
                {busy ? "…" : "Rewrite"}
              </button>
              <button className="ai-link" onClick={() => setOut(null)}>Close</button>
            </div>
          </div>

          <Blocks blocks={out.blocks} />

          <p className="ai-foot">{out.footer}. Every figure above was counted in
            pandas before the model saw it; quotes and links are printed from our
            own data, not written by the model.</p>
        </div>
      )}
    </div>
  );
}
