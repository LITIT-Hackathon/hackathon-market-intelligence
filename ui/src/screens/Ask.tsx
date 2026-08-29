import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Screen, type Tab } from "../App";

/* The question box, on its own tab.

   It used to sit inside the briefing, between the headline numbers and the
   call list, where it read as a widget bolted onto a report. It is the one
   part of the product you operate rather than read, so it gets the room to be
   operated in.

   It talks to `python -m opradar.ask` on the same origin. The built page
   carries no key and no endpoint of its own: opened as a plain file the probe
   below fails and the tab says so instead of pretending. */

interface AskTable { columns: string[]; rows: Record<string, unknown>[] }
interface AskReply { answer?: string; error?: string; table?: AskTable }

const num = (v: unknown): ReactNode =>
  typeof v === "number" && !Number.isInteger(v) ? v.toFixed(v < 10 ? 2 : 0) : String(v ?? "");

export function Ask({ examples, pool, on }: { examples: string[]; pool: number; on: Tab }) {
  const [live, setLive] = useState<boolean | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [asked, setAsked] = useState("");
  const [out, setOut] = useState<ReactNode>(null);

  useEffect(() => {
    let alive = true;
    fetch("/ask")
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { ok?: boolean } | null) => { if (alive) setLive(!!(j && j.ok)); })
      .catch(() => { if (alive) setLive(false); });
    return () => { alive = false; };
  }, []);

  const ask = (question: string) => {
    if (!question) return;
    setBusy(true);
    setAsked(question);
    setOut(<p className="a muted">Working&hellip;</p>);
    fetch("/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q: question }),
    })
      .then((r) => r.json())
      .then((j: AskReply) => {
        if (j.error) { setOut(<p className="a">{j.error}</p>); return; }
        /* The table is printed under every answer on purpose: it is where the
           numbers in the prose came from, and it is what makes them checkable. */
        const t = j.table;
        const rows = t && t.rows ? t.rows.length : 0;
        setOut(
          <>
            <p className="a">{j.answer}</p>
            {t && rows > 0 && (
              <>
                <p className="askcap">The rows the question filtered to &mdash; every number above
                  is one of these.</p>
                <div className="bf-tw">
                  <table>
                    <thead><tr>{t.columns.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead>
                    <tbody>
                      {t.rows.map((r, i) => (
                        <tr key={i}>{t.columns.map((c) => <td key={c}>{num(r[c])}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="bf-src">Counted in pandas from the ranked pool. Ranks match the
                  Opportunities tab.</p>
              </>
            )}
          </>,
        );
      })
      .catch(() => {
        setOut(<p className="a">Could not reach the ask service. Is <code>python -m opradar.ask</code> still running?</p>);
      })
      .then(() => setBusy(false));
  };

  const submit = (e: FormEvent) => { e.preventDefault(); ask(q.trim()); };
  const off = live === false;

  return (
    <Screen id="ask" group="ask" on={on}>
      <div className="askhero">
        <p className="label">Ask</p>
        <h2>Put a question to the {pool ? `${pool} ranked companies` : "ranked pool"}</h2>
        <p className="lede">Your question becomes a filter. The filter runs in pandas, and only the
          result is written up &mdash; so every number in an answer is one of the rows printed
          beneath it. Nothing is recalled from memory.</p>

        <form className="askform" id="bf-form" onSubmit={submit}>
          <input id="bf-q" type="text" autoComplete="off" disabled={off}
            placeholder={off ? "The ask service is not running" : "Who went quiet in the last month?"}
            value={q} onChange={(e) => setQ(e.target.value)} />
          <button id="bf-send" type="submit" disabled={busy || off}>
            {busy ? "Asking…" : "Ask"}
          </button>
        </form>

        {off && (
          <p className="askoff">This page is not talking to a model. Start the service with{" "}
            <code>python -m opradar.ask --project &lt;gcp-project-id&gt;</code> and reload &mdash;
            everything else on this page works without it.</p>
        )}

        {!!examples.length && !off && (
          <>
            <p className="askegh">Or start from one of these</p>
            <div className="askeg">
              {examples.map((e) => (
                <button type="button" key={e} onClick={() => { setQ(e); ask(e); }}>{e}</button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className={out ? "askout on" : "askout"} id="bf-out">
        {asked && <p className="askq">{asked}</p>}
        {out}
      </div>
    </Screen>
  );
}
