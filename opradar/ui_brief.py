"""The briefing tab's data, for the React UI in `ui/`.

Everything on that tab comes from `briefing.json`, which is computed in pandas
by `opradar.brief`. Nothing on it is generated text and no number on it was
produced by a model -- when a narrator is present (`opradar.narrate`) it may
only re-word the JSON, never extend it. That is what keeps the briefing
checkable: every figure is one click from the company row it came from.

The tab's markup lives in `ui/src/screens/Brief.tsx`; this module only decides
whether the tab exists and hands it the numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Suggested questions for the Ask box, which is live only when
# `python -m opradar.ask` is serving the page.
EXAMPLES = [
    "Which companies stopped advertising but still have roles open?",
    "Who is hiring fastest right now?",
    "Where can our bench cover every open role?",
    "Public sector companies with more than 10 roles open",
]


def narration(data_dir: Path) -> dict | None:
    """{paragraphs, model} from briefing_narrated.json, or None.

    Absent narration is the normal case: `opradar.narrate` needs cloud
    credentials and the deterministic lede in the UI reads fine without it.
    """
    path = Path(data_dir) / "briefing_narrated.json"
    if not path.exists():
        return None
    n = json.loads(path.read_text(encoding="utf-8"))
    paras = [str(p) for p in (n.get("paragraphs") or [])]
    if not paras:
        return None
    return {"paragraphs": paras, "model": str(n.get("model", "Gemini"))}


def build_brief(data_dir: Path) -> dict | None:
    """The Briefing tab's payload, or None when briefing.json has not been built.

    A missing briefing.json is not an error -- the page is simply built without
    the tab, exactly as it is built without the talent screens when there is no
    candidate data.
    """
    path = Path(data_dir) / "briefing.json"
    if not path.exists():
        print("  - briefing.json not found, skipping the Briefing tab "
              "(run `python -m opradar.brief`)", file=sys.stderr)
        return None

    b = json.loads(path.read_text(encoding="utf-8"))
    prose = narration(data_dir)
    if prose:
        print("  + briefing: narrated prose from briefing_narrated.json",
              file=sys.stderr)
    print(f"  + briefing: {b['cohorts']['stalled_n']} stalled, "
          f"{b['cohorts']['accelerating_n']} accelerating, "
          f"{len(b['calls'])} on the call list", file=sys.stderr)
    return {**b, "narration": prose, "examples": EXAMPLES}
