import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import DepthText from "./DepthText";
import FallingText from "./FallingText";

/* The one control on this page that is not about the data.

   It is an unlabelled slab of extruded type in the footer. Press it and the
   words you are currently looking at come off the page and fall into a heap
   you can shove around; every figure keeps the accent it had. Esc puts it
   back, and so does a reload -- nothing here is written down anywhere. */

// `highlightWords` matches on a prefix, so this highlights any word that
// starts with a digit or a currency mark: the numbers, which is the whole
// point of the page, stay lit while the prose falls grey.
const FIGURES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "€", "+", "-"];

const MAX_WORDS = 130;

/** The words on screen right now, in reading order. */
function harvest(limit = MAX_WORDS): string {
  const roots = [
    document.querySelector("header"),
    document.querySelector(".screen.on"),
    document.querySelector("footer"),
  ];
  const words: string[] = [];
  const blank = /^\s*$/;

  for (const root of roots) {
    if (!root || words.length >= limit) continue;
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node: Node | null = walk.nextNode();
    while (node && words.length < limit) {
      const el = node.parentElement;
      const text = node.textContent || "";
      node = walk.nextNode();
      if (!el || blank.test(text)) continue;
      // skip our own furniture, and anything scrolled out of the viewport --
      // what falls should be what the reader can actually see
      if (el.closest(".collapse,.navw,.text-rotate-sr-only")) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || r.bottom < 0 || r.top > window.innerHeight) continue;
      for (const raw of text.split(/\s+/)) {
        const w = raw.trim().slice(0, 24);
        if (w) words.push(w);
        if (words.length >= limit) break;
      }
    }
  }
  return words.join(" ");
}

export function Collapse() {
  const [fallen, setFallen] = useState<string | null>(null);

  const restore = useCallback(() => setFallen(null), []);

  useEffect(() => {
    if (fallen === null) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") restore();
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("keydown", key);
      document.body.style.overflow = prev;
    };
  }, [fallen, restore]);

  return (
    <>
      <button
        type="button"
        className="secret"
        aria-label="Drop everything"
        title=""
        onClick={() => setFallen(harvest())}
      >
        <DepthText
          text="OPS"
          layers={30}
          depth={1.8}
          faceColor="#FFFFFF"
          depthColor="#5B47F5"
          tilt={12}
          smoothing={0.12}
          perspective={460}
          autoOrbit
          orbitSpeed={0.16}
          fontSize="1.9rem"
          fontWeight={800}
          shadow
        />
      </button>

      {fallen !== null && createPortal(
        <div className="collapse" role="dialog" aria-label="Everything fell over">
          <FallingText
            text={fallen}
            highlightWords={FIGURES}
            trigger="auto"
            gravity={0.58}
            mouseConstraintStiffness={0.85}
            fontSize="clamp(.95rem,1.35vw,1.5rem)"
          />
          <p className="collapse-hint">
            drag them around &middot; <b>Esc</b> puts the page back
          </p>
        </div>,
        document.body,
      )}
    </>
  );
}
