import { useState } from "react";
import type { Payload } from "./data";
import { Brief } from "./screens/Brief";
import { Radar } from "./screens/Radar";
import { Companies } from "./screens/Companies";
import { Overview } from "./screens/Overview";
import { Bench } from "./screens/Bench";
import { Talent } from "./screens/Talent";
import { Candidates } from "./screens/Candidates";

type Tab = "brief" | "radar" | "companies" | "people";

/** One nav tab can reveal several stacked sections; every section stays
    mounted so filters survive a tab switch, exactly as the page did before. */
export function Screen({ id, group, on, children }: { id: string; group: Tab; on: Tab; children: React.ReactNode }) {
  return (
    <section className={group === on ? "screen on" : "screen"} id={id} data-g={group}>
      {children}
    </section>
  );
}

export function App({ data }: { data: Payload }) {
  const m = data.meta;
  const tabs: { id: Tab; label: string }[] = [];
  if (data.brief) tabs.push({ id: "brief", label: "Briefing" });
  if (data.radar) tabs.push({ id: "radar", label: "Opportunities" });
  tabs.push({ id: "companies", label: "Companies" });
  if (data.bench || data.talent) tabs.push({ id: "people", label: "People" });

  // The briefing answers "what changed", which is the question you have
  // before you have a shortlist, so it opens the product when it exists.
  const [on, setOn] = useState<Tab>(tabs[0].id);
  const go = (t: Tab) => {
    setOn(t);
    window.scrollTo(0, 0);
  };

  return (
    <>
      <header>
        <div className="bar">
          <div className="brand">
            <span className="mark">OP<b>_</b>RADAR</span>
            <span className="sub"></span>
          </div>
        </div>
        <nav>
          {tabs.map((t) => (
            <button key={t.id} data-s={t.id} aria-selected={t.id === on} onClick={() => go(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {data.brief && <Brief b={data.brief} on={on} />}
        {data.radar && <Radar R={data.radar} on={on} />}
        <Companies data={data} on={on} />
        <Overview data={data} on={on} />
        {data.bench && <Bench B={data.bench} on={on} />}
        {data.talent && <Talent T={data.talent} on={on} />}
        {data.talent && <Candidates T={data.talent} on={on} />}
      </main>

      <footer>
        Opportunity Radar — parser output viewer. Job posting data ©{"\u00a0"}Bundesagentur für Arbeit,{" "}
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC{"\u00a0"}BY{"\u00a0"}4.0</a>.
        {" "}Snapshot {m.snapshot} · built {m.generated}.
      </footer>
    </>
  );
}

export type { Tab };
