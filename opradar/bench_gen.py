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
    return _commercials(_github(bench, rng), rng)


# ---------------------------------------------------------------------------
# display attributes -- simulated, and kept out of every score
# ---------------------------------------------------------------------------

def _github(bench: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Public engineering footprint, drawn per role family.

    Two properties are the point, and a uniform draw would destroy both:

      * RELEVANCE VARIES BY FAMILY. Developers publish code; support and
        analyst profiles largely do not, so an empty GitHub says nothing about
        them. `sim_github_relevant` carries that distinction, and the UI shows
        "not a signal for this role" rather than a zero that reads as a bad
        consultant.
      * IT IS HEAVY-TAILED. Most engineers have a handful of repositories and
        a few have hundreds of stars. Lognormal draws reproduce that; a uniform
        one would make the field a useless discriminator.

    Simulated. `sim_` prefixed so the label survives every join, and read by
    nothing except the UI.
    """
    b = bench.copy()
    fam = b["role_family"]
    years = b["years_experience"].astype(float)

    rate = fam.map(ref.BENCH_GITHUB_PROFILE_RATE).fillna(
        ref.BENCH_GITHUB_PROFILE_RATE_DEFAULT).to_numpy(dtype=float)
    has_profile = rng.random(len(b)) < rate
    # experience compounds: a lead has had years to accumulate a footprint
    seniority_factor = (1 + ref.BENCH_GITHUB_YEARS_FACTOR) ** years.to_numpy()

    def _lognormal(medians: dict, sigma: float, scale=1.0):
        med = fam.map(medians).fillna(1).to_numpy(dtype=float)
        return np.round(med * scale * rng.lognormal(0.0, sigma, len(b))).astype(int)

    repos = _lognormal(ref.BENCH_GITHUB_REPOS_MEDIAN, ref.BENCH_GITHUB_REPOS_SIGMA,
                       seniority_factor)
    contrib = _lognormal(ref.BENCH_GITHUB_CONTRIB_MEDIAN, ref.BENCH_GITHUB_CONTRIB_SIGMA,
                         seniority_factor)
    stars = np.round(rng.lognormal(0.0, ref.BENCH_GITHUB_STARS_SIGMA, len(b))
                     * np.maximum(repos, 1) * 0.4).astype(int)

    b["sim_github_profile"] = has_profile
    b["sim_github_repos"] = np.where(has_profile, repos, 0)
    b["sim_github_contributions_12m"] = np.where(has_profile, contrib, 0)
    b["sim_github_stars"] = np.where(has_profile, stars, 0)
    b["sim_github_relevant"] = fam.isin(ref.BENCH_GITHUB_RELEVANT)

    # A 0-100 reading of the footprint, percentile-ranked WITHIN the families
    # where it means anything. Ranking it across all families would say a
    # support consultant is a weak engineer for not publishing code, which the
    # signal cannot support.
    b["sim_github_score"] = float("nan")
    mask = b["sim_github_relevant"] & b["sim_github_profile"]
    if mask.any():
        strength = (b.loc[mask, "sim_github_contributions_12m"]
                    + 3 * b.loc[mask, "sim_github_repos"]
                    + 0.5 * b.loc[mask, "sim_github_stars"])
        b.loc[mask, "sim_github_score"] = (
            100 * strength.rank(pct=True, method="average")).round(0)
    return b


def _commercials(bench: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Day rate charged to a German client, and the annual cost it implies.

    The annual figure exists because that is the number a client actually
    compares us against -- a day rate alone reads as expensive next to a salary
    until it is annualised over billable days.

    Simulated, and deliberately not fed into `value`: pricing should inform who
    a salesperson pitches, not silently reorder who the algorithm rates.
    """
    b = bench.copy()
    base = b["seniority"].map(ref.BENCH_DAY_RATE).astype(float)
    premium = np.where(b["speaks_german"], ref.BENCH_GERMAN_PREMIUM, 1.0)
    noise = rng.lognormal(0.0, ref.BENCH_RATE_SIGMA, len(b))

    b["sim_day_rate_eur"] = np.round(base.to_numpy() * premium * noise).astype(int)
    b["sim_annual_cost_eur"] = (b["sim_day_rate_eur"] * ref.BENCH_BILLABLE_DAYS_YEAR).astype(int)
    return b
