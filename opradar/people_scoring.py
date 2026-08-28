"""P5 -- candidate value: Value = MarketPull x Scarcity x Deployability.

Multiplicative, mirroring Opportunity: a candidate nobody wants, or one we have
forty of, is not valuable regardless of the other factors.

MarketPull comes from the REAL German demand per cell (market_pull.py), never
from synthetic openings. Scarcity is 1/depth of the candidate's bench cell,
percentiled so thin cells cannot explode the scale; cells under the thin-cell
guard are additionally flagged. Deployability mixes seniority, availability
and skill breadth.
"""

from __future__ import annotations

import pandas as pd

from .config import CONFIG


def _pct(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average")


def score(bench: pd.DataFrame, supply_index: pd.DataFrame,
          pull: pd.DataFrame) -> pd.DataFrame:
    p = CONFIG["people"]
    dw = p["deploy_weights"]

    cells = supply_index.merge(
        pull[pull["seniority"] != "all"], on=["role_family", "seniority"], how="left")
    cells["unfilled_45"] = cells["unfilled_45"].fillna(0)

    # cell-level components, percentiled across occupied cells
    cells["market_pull"] = _pct(cells["unfilled_45"])
    cells["scarcity"] = _pct(1.0 / cells["depth"])

    cell_lookup = cells.set_index(["role_family", "seniority"])

    b = bench.copy()
    keys = list(zip(b["role_family"], b["seniority"]))
    b["market_pull"] = [round(float(cell_lookup.loc[k, "market_pull"]), 4) for k in keys]
    b["scarcity"] = [round(float(cell_lookup.loc[k, "scarcity"]), 4) for k in keys]
    b["thin_cell"] = [bool(cell_lookup.loc[k, "thin_cell"]) for k in keys]
    b["cell_unfilled_45"] = [int(cell_lookup.loc[k, "unfilled_45"]) for k in keys]
    b["cell_depth"] = [int(cell_lookup.loc[k, "depth"]) for k in keys]

    readiness = b["availability"].map(p["readiness"])
    b["deployability"] = (
        dw["seniority"] * _pct(b["seniority_rank"])
        + dw["readiness"] * readiness
        + dw["breadth"] * _pct(b["skill_breadth"])
    ).round(4)

    b["value"] = (100 * b["market_pull"] * b["scarcity"] * b["deployability"]).round(1)
    b = b.sort_values("value", ascending=False).reset_index(drop=True)
    b["rank"] = b.index + 1
    return b, cells
