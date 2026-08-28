"""Simulated enrichment layer.

    python -m opradar.simulate

Adds the fields we would get from sources we are not integrating: repeated
crawls, salary statistics, company registers, procurement notices and GitHub.
Everything invented carries a `sim_` prefix. Columns without that prefix are
computed from the real German posting data.

Writes:
    data/processed/postings_sim.parquet    per posting: lifecycle, salary, project
    data/processed/companies_sim.parquet   per company: firmographics, urgency, type
    data/processed/projects.parquet        detected multi-role programmes
    data/processed/bench_sim.parquet       per consultant: GitHub, cost, availability

Deterministic: one seed, so two runs produce identical files. A simulated
dataset that shifts under you is worse than no dataset at all -- you cannot
tell a real ranking change from generator noise.

WHAT IS REAL vs SIMULATED
    real        employer, title, posted_date, region, tech tags, role family,
                seniority-from-title, and the project detection in §5 (that is
                genuine co-occurrence over real postings)
    simulated   everything named sim_*

Swapping in a real source later means deleting one function here, not
unpicking the pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import simcoeff as C
from . import signals

SEED = 20260829
SNAPSHOT = pd.Timestamp("2026-06-06")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _lognormal(rng, median: float, sigma: float, size=None):
    """Draw around a median with multiplicative spread (never negative)."""
    return np.exp(rng.normal(np.log(max(median, 1e-9)), sigma, size))


def _tags(t) -> list[str]:
    """tech_categories comes back as a numpy array; `t or []` is ambiguous on one."""
    if t is None:
        return []
    try:
        return [str(x) for x in t]
    except TypeError:
        return []


# ---------------------------------------------------------------------------
# 1. Salary  (stands in for the Entgeltatlas)
# ---------------------------------------------------------------------------

def market_salary(df: pd.DataFrame) -> pd.Series:
    """What a German employer pays for this role, in this region, EUR/year."""
    base = df["seniority_derived"].map(C.SALARY_BASE).fillna(C.SALARY_UNKNOWN)
    region = df["region_clean"].map(C.REGION_SALARY_INDEX).fillna(C.REGION_SALARY_DEFAULT)
    tech = df["tech_categories"].map(
        lambda t: max((C.TECH_SALARY_PREMIUM.get(x, 1.0) for x in _tags(t)), default=1.0))
    return (base * region * tech).round(-2).astype("int64")


# ---------------------------------------------------------------------------
# 2. Vacancy lifecycle  (stands in for repeated crawls)
# ---------------------------------------------------------------------------

def _size_factor(employees: float) -> float:
    for ceiling, factor in C.FILL_DAYS_SIZE_FACTOR:
        if employees <= ceiling:
            return factor
    return 1.0


def lifecycle(df: pd.DataFrame, employees: pd.Series, rng) -> pd.DataFrame:
    """Give every posting an expected time-to-fill, then decide its fate.

    A posting is 'filled' if its expected fill time already elapsed inside the
    window it has been open; otherwise it is still open. This reproduces what
    diffing two crawls would tell us, including the fact that hard-to-fill
    roles are over-represented among the ones still visible.
    """
    exp_days = df["seniority_derived"].map(C.FILL_DAYS_BASE).fillna(C.FILL_DAYS_UNKNOWN)
    exp_days = exp_days * df["tech_categories"].map(
        lambda t: max((C.FILL_DAYS_TECH_FACTOR.get(x, 1.0) for x in _tags(t)), default=1.0))
    exp_days = exp_days * df["region_clean"].map(C.FILL_DAYS_REGION_FACTOR).fillna(
        C.FILL_DAYS_REGION_DEFAULT)
    exp_days = exp_days * employees.map(_size_factor).fillna(1.0)

    draw = _lognormal(rng, 1.0, C.FILL_DAYS_SIGMA, len(df)) * exp_days.to_numpy()
    age = df["posting_age_days"].to_numpy()

    filled = draw <= age
    ttf = np.where(filled, np.round(draw), np.nan)

    # unfilled roles get re-advertised now and again
    reposts = np.where(
        ~filled,
        rng.binomial(np.maximum(age // 60, 0).astype(int), C.REPOST_PROB_PER_60D),
        0)

    posted = pd.to_datetime(df["posted_date"])
    return pd.DataFrame({
        "sim_expected_fill_days": np.round(exp_days.to_numpy()).astype("int64"),
        "sim_filled": filled,
        "sim_still_open": ~filled,
        "sim_time_to_fill_days": pd.array(ttf, dtype="Int64"),
        "sim_filled_on": pd.to_datetime(
            np.where(filled, posted + pd.to_timedelta(np.nan_to_num(ttf), unit="D"),
                     pd.NaT)),
        "sim_repost_count": reposts.astype("int64"),
        # days already open beyond what this kind of role normally takes
        "sim_overdue_days": np.maximum(0, age - exp_days.to_numpy()).round().astype("int64"),
    }, index=df.index)


# ---------------------------------------------------------------------------
# 3. Firmographics  (stands in for Handelsregister / Bundesanzeiger)
# ---------------------------------------------------------------------------

INDUSTRY_KEYWORDS = {
    "energy": "energie|strom|netz|windkraft|solar|kraftwerk",
    "banking": "bank|sparkasse|kredit|finanz",
    "insurance": "versicher|assekuranz",
    "automotive": "automotive|fahrzeug|automobil",
    "retail": "handel|retail|filial|verkauf|markt",
    "logistics": "logistik|spedition|transport|lager",
    "healthcare": "klinik|pflege|gesundheit|medizin|krankenhaus",
    "construction": "bau|hochbau|tiefbau|architekt",
    "manufacturing": "produktion|fertigung|maschinen|werk",
    "public": "stadt|kommun|amt|behoerde|bund|land",
}


def infer_industry(postings: pd.DataFrame) -> pd.Series:
    """Industry from a company's own NON-IT postings -- real, not simulated.

    A company that also advertises nurses is in healthcare; one advertising
    Netzmonteure is in energy. This is free firmographic signal that the
    dataset already contains.
    """
    import re

    non_it = postings[~postings["is_it_role"].fillna(False)]
    text = (non_it.assign(_t=non_it["title_clean"].astype(str).str.lower())
            .groupby("company_key")["_t"].apply(" ".join))

    patterns = {name: re.compile(pat) for name, pat in INDUSTRY_KEYWORDS.items()}

    def pick(blob: str) -> str:
        best, best_n = "other", 0
        for name, pat in patterns.items():
            n = len(pat.findall(blob))
            if n > best_n:
                best, best_n = name, n
        return best

    return text.map(pick)


def firmographics(companies: pd.DataFrame, industry: pd.Series, rng) -> pd.DataFrame:
    postings = companies["postings"].to_numpy(dtype=float)
    employees = (C.HEADCOUNT_A * np.power(np.maximum(postings, 1), C.HEADCOUNT_B)
                 * _lognormal(rng, 1.0, C.HEADCOUNT_SIGMA, len(companies)))
    employees = np.maximum(C.HEADCOUNT_MIN, employees).round().astype("int64")

    ind = companies["company_key"].map(industry).fillna("other")
    rev_per = ind.map(C.REVENUE_PER_EMPLOYEE).fillna(C.REVENUE_PER_EMPLOYEE["other"])
    revenue = (employees * rev_per.to_numpy()
               * _lognormal(rng, 1.0, C.REVENUE_SIGMA, len(companies)))

    lo, hi = C.FOUNDED_YEAR_RANGE
    founded = (hi - np.round(_lognormal(rng, 28, 0.85, len(companies)))).clip(lo, hi)

    return pd.DataFrame({
        "company_key": companies["company_key"].to_numpy(),
        "industry": ind.to_numpy(),                        # real (inferred)
        "sim_employees": employees,
        "sim_revenue_eur": revenue.round(-3).astype("int64"),
        "sim_founded_year": founded.astype("int64"),
    })


# ---------------------------------------------------------------------------
# 4. Public tenders  (stands in for TED procurement notices)
# ---------------------------------------------------------------------------

def tenders(companies: pd.DataFrame, rng) -> pd.DataFrame:
    eligible = companies["company_class"].isin(C.TENDER_CLASSES).to_numpy()
    has = eligible & (rng.random(len(companies)) < C.TENDER_RATE)
    lo, hi = C.TENDER_VALUE_RANGE
    value = np.where(has, _lognormal(rng, lo * 4, 0.9, len(companies)).clip(lo, hi), np.nan)
    ref = np.where(has, [f"TED-2026-{n:06d}" for n in rng.integers(1, 999_999, len(companies))], None)
    return pd.DataFrame({
        "company_key": companies["company_key"].to_numpy(),
        "sim_has_tender": has,
        "sim_tender_ref": ref,
        "sim_tender_value_eur": pd.array(np.round(value, -3), dtype="Int64"),
    })


# ---------------------------------------------------------------------------
# 5. Hidden projects  -- REAL: co-occurrence over actual postings
# ---------------------------------------------------------------------------

def detect_projects(elig: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """A cluster of related roles opened close together is a programme.

    Not simulated. One architect, three backend engineers and a QA all posted
    by the same company inside three weeks, sharing a technology, is a project
    starting -- and nobody announced it. This is the 'hidden project' signal,
    and it needs no data we do not already hold.
    """
    rows, assign = [], {}
    df = elig.dropna(subset=["posted_date"]).sort_values("posted_date")

    for key, grp in df.groupby("company_key"):
        for tech in {t for tags in grp["tech_categories"] for t in _tags(tags)}:
            sub = grp[grp["tech_categories"].map(lambda t: tech in _tags(t))]
            if len(sub) < C.PROJECT_MIN_ROLES:
                continue
            dates = pd.to_datetime(sub["posted_date"])
            start = dates.min()
            window = sub[(dates - start).dt.days <= C.PROJECT_WINDOW_DAYS]
            if len(window) < C.PROJECT_MIN_ROLES:
                continue
            if window["role_family"].nunique() < C.PROJECT_MIN_FAMILIES:
                continue
            pid = f"P{len(rows)+1:04d}"
            rows.append({
                "project_id": pid,
                "company_key": key,
                "company_name": window["company_name"].iloc[0]
                if "company_name" in window else key,
                "technology": tech,
                "roles": int(len(window)),
                "role_families": int(window["role_family"].nunique()),
                "started": start.date(),
                "span_days": int((pd.to_datetime(window["posted_date"]).max() - start).days),
                "seniors": int(window["seniority_derived"].isin(["senior", "lead"]).sum()),
            })
            for idx in window.index:
                assign[idx] = pid

    projects = pd.DataFrame(rows)
    return projects, pd.Series(assign, dtype="object")


# ---------------------------------------------------------------------------
# 6. Opportunity type + urgency
# ---------------------------------------------------------------------------

def opportunity_type(row) -> str:
    if row["has_project"]:
        return "transformation"          # multi-role programme under way
    if row["it_n"] >= 8 and row["fresh_share"] >= 0.5:
        return "scaling"                 # hiring hard and hiring now
    if row["overdue_share"] >= 0.5:
        return "stuck"                   # cannot fill what it has advertised
    if row["it_n"] <= 3 and row["fresh_share"] >= 0.5:
        return "new_entry"               # just started building
    if row["fresh_share"] <= 0.2:
        return "low_demand"              # quiet, mostly old ads
    return "replacement"                 # routine backfill


def urgency(row) -> float:
    """0-1. High means the window is open now: fresh, accelerating, staffable."""
    score = (0.40 * row["fresh_share"]
             + 0.25 * min(1.0, row["it_n"] / 10)
             + 0.20 * (1.0 - min(1.0, row["overdue_share"]))
             + 0.15 * (1.0 if row["has_project"] else 0.0))
    return round(float(score), 4)


def urgency_band(score: float) -> tuple[int, str]:
    for threshold, days, label in C.URGENCY_BANDS:
        if score >= threshold:
            return days, label
    return 90, "no rush"


# ---------------------------------------------------------------------------
# 7. Bench enrichment  (GitHub, cost, certifications)
# ---------------------------------------------------------------------------

def enrich_bench(bench: pd.DataFrame, rng) -> pd.DataFrame:
    n = len(bench)
    fam = bench["role_family"]
    yrs = bench["years_experience"].to_numpy(dtype=float)
    exp_mult = 1.0 + C.GITHUB_YEARS_FACTOR * yrs

    has_profile = rng.random(n) < fam.map(C.GITHUB_PROFILE_RATE).fillna(
        C.GITHUB_PROFILE_RATE_DEFAULT).to_numpy()

    repos = _lognormal(rng, 1.0, C.GITHUB_REPOS_SIGMA, n) * fam.map(
        C.GITHUB_REPOS_MEDIAN).fillna(4).to_numpy() * exp_mult
    contrib = _lognormal(rng, 1.0, C.GITHUB_CONTRIB_SIGMA, n) * fam.map(
        C.GITHUB_CONTRIB_MEDIAN).fillna(40).to_numpy() * exp_mult
    stars = _lognormal(rng, 1.2, C.GITHUB_STARS_SIGMA, n) * np.maximum(repos, 1) * 0.35

    rate = bench["seniority"].map(C.BENCH_DAY_RATE).fillna(490).to_numpy(dtype=float)
    rate = rate * _lognormal(rng, 1.0, C.BENCH_RATE_SIGMA, n)
    rate = rate * np.where(bench["speaks_german"].to_numpy(), C.BENCH_GERMAN_PREMIUM, 1.0)

    cert_rate = bench["seniority"].map(C.CERT_RATE_BY_SENIORITY).fillna(0.3).to_numpy()
    certs = []
    for i, tags in enumerate(bench["tech_tags"]):
        pool = [c for t in _tags(tags) for c in C.CERTIFICATIONS.get(t, [])]
        certs.append([str(rng.choice(pool))] if pool and rng.random() < cert_rate[i] else [])

    ulo, uhi = C.BENCH_UTILISATION
    rlo, rhi = C.BENCH_RATING

    out = bench.copy()
    out["sim_github_profile"] = has_profile
    out["sim_github_repos"] = np.where(has_profile, np.round(repos), 0).astype("int64")
    out["sim_github_contributions_12m"] = np.where(has_profile, np.round(contrib), 0).astype("int64")
    out["sim_github_stars"] = np.where(has_profile, np.round(stars), 0).astype("int64")
    out["sim_day_rate_eur"] = np.round(rate).astype("int64")
    out["sim_notice_days"] = bench["availability"].map(C.BENCH_NOTICE_DAYS).fillna(30).astype("int64")
    out["sim_utilisation"] = np.round(rng.uniform(ulo, uhi, n), 3)
    out["sim_client_rating"] = np.round(rng.uniform(rlo, rhi, n), 2)
    out["sim_certifications"] = certs
    return out


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def run(root: Path) -> None:
    rng = np.random.default_rng(SEED)
    data = root / "data" / "processed"

    _log("[1/6] loading")
    postings = pd.read_parquet(data / "postings.parquet")
    companies = pd.read_parquet(data / "companies.parquet")

    _log("[2/6] industry (real, inferred from non-IT postings) + firmographics")
    industry = infer_industry(postings)
    firm = firmographics(companies, industry, rng)
    tend = tenders(companies, rng)

    _log("[3/6] salary + vacancy lifecycle")
    emp_by_key = firm.set_index("company_key")["sim_employees"]
    employees = postings["company_key"].map(emp_by_key).fillna(200)
    post = postings.copy()
    post["sim_market_salary_eur"] = market_salary(post)
    post = pd.concat([post, lifecycle(post, employees, rng)], axis=1)

    _log("[4/6] hidden projects (real co-occurrence)")
    elig = signals.eligible_postings(postings)
    if "company_name" not in elig.columns:
        elig = elig.merge(companies[["company_key", "company_name"]], on="company_key", how="left")
    projects, assign = detect_projects(elig)
    post["project_id"] = post.index.map(assign).astype("object")
    _log(f"      {len(projects)} projects across {projects['company_key'].nunique() if len(projects) else 0} companies")

    _log("[5/6] opportunity type + urgency")
    e = post.loc[elig.index]
    agg = e.groupby("company_key").agg(
        it_n=("posting_id", "count"),
        fresh_share=("is_fresh_30d", "mean"),
        overdue_share=("sim_overdue_days", lambda s: float((s > 0).mean())),
        open_salary_bill=("sim_market_salary_eur", "sum"),
        median_ttf=("sim_time_to_fill_days", "median"),
    ).reset_index()
    agg["has_project"] = agg["company_key"].isin(projects["company_key"] if len(projects) else [])
    agg["sim_opportunity_type"] = agg.apply(opportunity_type, axis=1)
    agg["sim_urgency"] = agg.apply(urgency, axis=1)
    bands = agg["sim_urgency"].map(urgency_band)
    agg["sim_act_within_days"] = [b[0] for b in bands]
    agg["sim_act_label"] = [b[1] for b in bands]

    comp = (companies
            .merge(firm.drop(columns=["industry"]), on="company_key", how="left")
            .merge(firm[["company_key", "industry"]], on="company_key", how="left")
            .merge(tend, on="company_key", how="left")
            .merge(agg.drop(columns=["has_project"]), on="company_key", how="left"))
    comp = comp.rename(columns={"open_salary_bill": "sim_open_roles_salary_eur",
                                "median_ttf": "sim_median_time_to_fill"})

    _log("[6/6] bench enrichment")
    bench_path = data / "bench.parquet"
    if bench_path.exists():
        bench = enrich_bench(pd.read_parquet(bench_path), rng)
        bench.to_parquet(data / "bench_sim.parquet", index=False)
        _log(f"      bench_sim.parquet  {len(bench)} consultants, "
             f"{int(bench['sim_github_profile'].sum())} with a public GitHub")
    else:
        _log("      bench.parquet missing -- run opradar.score first, skipping")

    post.to_parquet(data / "postings_sim.parquet", index=False)
    comp.to_parquet(data / "companies_sim.parquet", index=False)
    if len(projects):
        projects.to_parquet(data / "projects.parquet", index=False)

    filled = int(post["sim_filled"].sum())
    _log(f"\ndone -> postings_sim.parquet ({len(post):,} rows, {filled:,} simulated as filled)")
    _log(f"     -> companies_sim.parquet ({len(comp):,} rows)")
    _log(f"     -> projects.parquet ({len(projects):,} rows)")


if __name__ == "__main__":
    run(Path(__file__).resolve().parent.parent)
