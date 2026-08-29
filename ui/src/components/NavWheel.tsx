import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import OptionWheel from "./OptionWheel";

/* The navigation.

   The folder tabs are gone. Sections now live on a wheel that sits off the
   left edge of the page and comes in either way you reach for it: push the
   pointer into the first few pixels of the screen, or click the rail that is
   always parked there. Once it is open the wheel takes scroll, drag, arrow
   keys and clicks, and the page behind it changes as the wheel turns, so
   choosing a section and seeing it are the same gesture.

   The digits 1-n jump straight to a section without opening anything, which
   is why each option carries its number. That path does not run through the
   wheel, so it bumps `seed` to remount the wheel on the new index -- the
   component owns its position internally and has no controlled mode. */

export interface NavItem<T extends string> {
  id: T;
  label: string;
}

const HOVER_IN = 130; // dwell on the edge before it opens, so a pass-by does not
const HOVER_OUT = 320; // grace after the pointer leaves, so a wobble does not close

export function NavWheel<T extends string>({
  items,
  on,
  go,
}: {
  items: NavItem<T>[];
  on: T;
  go: (id: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const [seed, setSeed] = useState(0);
  const sheetRef = useRef<HTMLElement | null>(null);
  const openedBy = useRef<"hover" | "click">("click");
  const dwell = useRef<number | null>(null);
  const grace = useRef<number | null>(null);
  const idx = Math.max(0, items.findIndex((i) => i.id === on));
  const current = items[idx];

  const clear = (t: RefObject<number | null>) => {
    if (t.current !== null) {
      window.clearTimeout(t.current);
      t.current = null;
    }
  };

  const show = useCallback((how: "hover" | "click") => {
    openedBy.current = how;
    setOpen(true);
  }, []);

  // hover-to-open, on the sliver of screen left of the content gutter
  const edgeIn = () => {
    if (open || dwell.current !== null) return;
    dwell.current = window.setTimeout(() => {
      dwell.current = null;
      show("hover");
    }, HOVER_IN);
  };
  const edgeOut = () => clear(dwell);

  // A sheet the pointer opened closes when the pointer leaves it. One opened
  // by click is a deliberate act and waits for Esc, a choice, or the scrim.
  const sheetOut = () => {
    if (openedBy.current !== "hover") return;
    clear(grace);
    grace.current = window.setTimeout(() => setOpen(false), HOVER_OUT);
  };
  const sheetIn = () => clear(grace);

  useEffect(() => () => {
    clear(dwell);
    clear(grace);
  }, []);

  // the wheel takes the keyboard as soon as it is on screen
  useEffect(() => {
    if (!open) return;
    sheetRef.current?.querySelector<HTMLElement>(".option-wheel")?.focus({ preventScroll: true });
  }, [open]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      const el = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      const n = Number(e.key);
      if (!Number.isInteger(n) || n < 1 || n > items.length) return;
      e.preventDefault();
      go(items[n - 1].id);
      setSeed((s) => s + 1);
      setOpen(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [items, go]);

  // Stamp the section id onto each option. The wheel is vendored and renders
  // plain labels; this keeps `[data-s="radar"]` addressable the way the old
  // tab buttons were, for tests and for anything linking into a section.
  useEffect(() => {
    const opts = sheetRef.current?.querySelectorAll<HTMLElement>(".option-wheel__item");
    opts?.forEach((el, i) => {
      if (items[i]) el.dataset.s = items[i].id;
    });
  }, [items, seed]);

  return (
    <div className={open ? "navw open" : "navw"}>
      {/* One hover zone: the sliver of screen at the edge, with the rail
          parked inside it so reaching for either opens the same sheet. */}
      <div className="navw-edge" onMouseEnter={edgeIn} onMouseLeave={edgeOut}>
        <button
          type="button"
          className="navw-tab"
          aria-expanded={open}
          aria-label={`Sections — currently ${current.label}`}
          onClick={() => (open ? setOpen(false) : show("click"))}
        >
          <span className="navw-burger" aria-hidden="true"><i /><i /><i /></span>
          <span className="navw-now">{current.label}</span>
        </button>
      </div>

      <div className="navw-scrim" onClick={() => setOpen(false)} aria-hidden="true" />

      <aside
        className="navw-sheet"
        ref={sheetRef}
        inert={!open}
        aria-label="Sections"
        onPointerEnter={sheetIn}
        onPointerLeave={sheetOut}
        onClick={(e) => {
          // a click straight onto an option is a choice: let it snap, then leave
          if ((e.target as HTMLElement).closest(".option-wheel__item")) {
            window.setTimeout(() => setOpen(false), 220);
          }
        }}
      >
        <p className="navw-eyebrow">Sections</p>

        <div className="navw-wheel">
          <OptionWheel
            key={seed}
            items={items.map((i) => i.label)}
            defaultSelected={idx}
            onChange={(i) => go(items[i].id)}
            side="left"
            textColor="#5C625F"
            activeColor="#FFFFFF"
            fontSize={2.55}
            spacing={1.5}
            curve={1}
            tilt={7}
            blur={1.4}
            fade={0.3}
            minOpacity={0.14}
            smoothing={170}
            inset={54}
            loop={false}
            draggable
          />
        </div>

        <p className="navw-hint">
          Scroll, drag or <b>↑ ↓</b> · <b>1–{items.length}</b> jumps · <b>Esc</b> closes
        </p>
      </aside>
    </div>
  );
}
