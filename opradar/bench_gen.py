"""B3 bench generator (ALGORITHM_PEOPLE.md 4).

Generates a synthetic delivery bench IN THE GERMAN TECH VOCABULARY, so that
Pipeline C is a join by construction. Deterministic: seeded RNG, two runs are
identical (ALGORITHM.md rule 4 applies to generated data too).

The bench profile (reference.py BENCH_PROFILE) is deliberately different from
German demand -- see the "trap in B3": a bench sampled from the demand
distribution matches everything and the product has nothing to say.

Every record carries source='synthetic'. The UI must show that label.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import reference as ref


def _pick(rng: np.random.Generator, options: list[tuple[str, float]]) -> str:
    labels = [o for o, _ in options]
    weights = np.array([w for _, w in options], dtype=float)
    return str(rng.choice(labels, p=weights / weights.sum()))


# plausible years_experience per seniority band -- mirrors the fixture's own
# correlation (junior 0-2, mid 2-6, senior 6-12, lead 8-15)
_YEARS = {"junior": (0, 2), "mid": (2, 6), "senior": (6, 12), "lead": (8, 15)}


def generate(size: int = ref.BENCH_SIZE, seed: int = ref.BENCH_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    counter = 0

    scale = size / sum(spec["n"] for spec in ref.BENCH_PROFILE.values())

    for family, spec in ref.BENCH_PROFILE.items():
        for _ in range(max(1, round(spec["n"] * scale))):
            counter += 1
            seniority = _pick(rng, ref.BENCH_SENIORITY)

            tags = [tag for tag, p in spec["tech"] if rng.random() < p]
            if not tags:                       # every consultant has at least one tag
                tags = [spec["tech"][0][0]]

            lo, hi = _YEARS[seniority]
            languages = ["en", "lt"] + (["de"] if rng.random() < ref.BENCH_GERMAN_RATE else [])

            rows.append({
                "candidate_id": f"B_{counter:04d}",
                "role_family": family,
                "tech_tags": sorted(set(tags)),
                "seniority": seniority,
                "seniority_rank": ref.SENIORITY_RANK[seniority],
                "years_experience": int(rng.integers(lo, hi + 1)),
                "availability": _pick(rng, ref.BENCH_AVAILABILITY),
                "languages": languages,
                "speaks_german": "de" in languages,
                "region": _pick(rng, ref.BENCH_REGIONS),
                "remote_ok": True,
                "source": "synthetic",         # MUST be labelled in the UI
            })

    bench = pd.DataFrame(rows)
    bench["skill_breadth"] = bench["tech_tags"].map(len)
    return bench
