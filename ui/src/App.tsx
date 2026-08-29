import { useCallback, useMemo, useState } from "react";
import type { Payload } from "./data";
import { NavWheel, type NavItem } from "./components/NavWheel";
import RotatingText from "./components/RotatingText";
import { Collapse } from "./components/Collapse";
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
  const tabs = useMemo<NavItem<Tab>[]>(() => {
    const t: NavItem<Tab>[] = [];
    if (data.brief) t.push({ id: "brief", label: "Briefing" });
    if (data.radar) t.push({ id: "radar", label: "Opportunities" });
    t.push({ id: "companies", label: "Companies" });
    if (data.bench || data.talent) t.push({ id: "people", label: "People" });
    return t;
  }, [data]);

  // The briefing answers "what changed", which is the question you have
  // before you have a shortlist, so it opens the product when it exists.
  const [on, setOn] = useState<Tab>(tabs[0].id);
  const go = useCallback((t: Tab) => {
    setOn(t);
    window.scrollTo(0, 0);
  }, []);
  const here = tabs.find((t) => t.id === on);
  // A brand mark that never stops moving is exactly what this setting asks
  // us not to do, so it falls back to the wordmark it spells out.
  const still = typeof window !== "undefined"
    && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  return (
    <>
      <NavWheel items={tabs} on={on} go={go} />

      <header>
        <div className="bar">
          {/* The mark reads itself out: OP_ -- RADAR_ -- SCANNING_ -- FOR OPS_,
              keeping the underscore the wordmark always carried. The cursor is
              the last character of every string rather than a fixed span next
              to them, so it can never drift while the width animates; the CSS
              paints the last glyph in the accent. The section name sits at the
              other end of the bar, so a changing mark never nudges it. */}
          <div className="brand">
            {still ? (
              <span className="mark">OP<b>_</b>RADAR</span>
            ) : (
              <span className="mark">
                <RotatingText
                  texts={["OP_Radar", "Scanning_For Ops"]}
                  rotationInterval={2200}
                  staggerDuration={0.028}
                  staggerFrom="last"
                  initial={{ y: "100%" }}
                  animate={{ y: 0 }}
                  exit={{ y: "-120%" }}
                  transition={{ type: "spring", damping: 30, stiffness: 400 }}
                  splitLevelClassName="mark-clip"
                />
              </span>
            )}
          </div>
          <span className="sub">{here?.label}</span>
        </div>
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
        <p className="foot-legal">
          Opportunity Radar — parser output viewer. Job posting data ©{"\u00a0"}Bundesagentur für Arbeit,{" "}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC{"\u00a0"}BY{"\u00a0"}4.0</a>.
          {" "}Snapshot {m.snapshot} · built {m.generated}.
        </p>
        <Collapse />
      </footer>
    </>
  );
}

export type { Tab };
