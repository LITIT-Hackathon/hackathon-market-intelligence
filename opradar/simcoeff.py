"""Coefficient tables for the simulated enrichment layer (opradar.simulate).

NOTHING HERE IS MEASURED. These are hand-set coefficients chosen so that the
generated columns behave like the real world would, and so the algorithms
downstream can be built and demonstrated before any of the real sources exist.

Every column produced from this file carries a `sim_` prefix. That prefix is
the contract: if a column starts with `sim_`, it is invented. If it does not,
it came from the German posting data.

Each block names the real source it stands in for, so swapping simulation for
reality later is a localised change rather than an archaeology exercise.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. SALARY  -- stands in for: Bundesagentur Entgeltatlas
#    (median gross annual salary by KldB occupation, region and age band)
# ---------------------------------------------------------------------------

# German gross annual salary for IT roles, EUR. Mid-market baseline before
# regional and technology adjustment.
SALARY_BASE = {
    "junior": 48_000,
    "mid":    62_000,
    "senior": 80_000,
    "lead":   98_000,
}
SALARY_UNKNOWN = 62_000          # seniority is unknown on ~76% of postings

# Regional cost index. Munich/Frankfurt/Stuttgart carry a metro premium; the
# eastern Laender sit well below the national line. Ratios are deliberately
# conservative -- the east/west gap is real but often overstated.
REGION_SALARY_INDEX = {
    "Bayern": 1.12, "Hessen": 1.10, "Baden-Württemberg": 1.08, "Hamburg": 1.06,
    "Nordrhein-Westfalen": 1.00, "Berlin": 0.98, "Rheinland-Pfalz": 0.96,
    "Niedersachsen": 0.95, "Bremen": 0.95, "Saarland": 0.93,
    "Schleswig-Holstein": 0.93, "Brandenburg": 0.86, "Sachsen": 0.85,
    "Thüringen": 0.83, "Sachsen-Anhalt": 0.82, "Mecklenburg-Vorpommern": 0.82,
    # Austrian/Swiss rows exist in tiny numbers
    "Wien": 1.05, "Oberösterreich": 1.02, "Salzburg": 1.03, "Tirol": 1.00,
    "Steiermark": 0.99, "Kärnten": 0.96, "Niederösterreich": 1.00,
    "Vorarlberg": 1.04, "Zürich": 1.55, "Nordwestschweiz (mit Basel)": 1.50,
}
REGION_SALARY_DEFAULT = 0.97

# Technology premium. Scarce enterprise skills pay above general development;
# support and frontend sit below it.
TECH_SALARY_PREMIUM = {
    "sap": 1.14, "erp": 1.10, "security": 1.11, "cloud": 1.09, "data": 1.08,
    "devops": 1.07, "embedded": 1.05, "platform": 1.02, "backend": 1.02,
    "language": 1.00, "quality": 0.97, "network": 0.97, "frontend": 0.96,
    "mobile": 1.00, "support": 0.90,
}

# ---------------------------------------------------------------------------
# 2. VACANCY LIFECYCLE  -- stands in for: a second and third BA API snapshot
#    Real version: diff consecutive crawls; a posting that disappears was
#    filled or withdrawn, one that persists was not.
# ---------------------------------------------------------------------------

# Expected days to fill, before adjustment. Senior and lead roles take
# markedly longer -- this is the single most important realism knob, because
# it is what makes "unfilled senior demand" a meaningful signal at all.
FILL_DAYS_BASE = {
    "junior": 38,
    "mid":    55,
    "senior": 84,
    "lead":  105,
}
FILL_DAYS_UNKNOWN = 58

# Scarce skills take longer to fill.
FILL_DAYS_TECH_FACTOR = {
    "sap": 1.35, "security": 1.30, "data": 1.22, "cloud": 1.20, "embedded": 1.25,
    "devops": 1.18, "erp": 1.20, "platform": 1.05, "backend": 1.05,
    "language": 1.00, "network": 0.98, "quality": 0.95, "frontend": 0.92,
    "mobile": 1.00, "support": 0.82,
}

# Tight metro labour markets fill slower for the same role.
FILL_DAYS_REGION_FACTOR = {
    "Bayern": 1.12, "Baden-Württemberg": 1.10, "Hessen": 1.08, "Hamburg": 1.05,
    "Berlin": 1.02, "Nordrhein-Westfalen": 1.00,
}
FILL_DAYS_REGION_DEFAULT = 0.95

# Big employers fill faster (brand, recruiting capacity). Multiplier applied
# by headcount band.
FILL_DAYS_SIZE_FACTOR = [(50, 1.18), (250, 1.08), (1000, 1.00), (10_000, 0.94), (10**9, 0.88)]

FILL_DAYS_SIGMA = 0.32        # lognormal spread around the expected value
REPOST_PROB_PER_60D = 0.35    # chance an unfilled role is re-advertised

# ---------------------------------------------------------------------------
# 3. FIRMOGRAPHICS  -- stands in for: Handelsregister + Bundesanzeiger filings
# ---------------------------------------------------------------------------

# Headcount is estimated from observed posting volume: a company advertising
# 800 roles is large. Postings-per-employee is not linear, so this is fitted
# as employees ~ a * postings^b with heavy noise.
HEADCOUNT_A, HEADCOUNT_B = 210.0, 0.78
HEADCOUNT_SIGMA = 0.55
HEADCOUNT_MIN = 12

# Revenue per employee, EUR, by inferred industry. Capital-intensive sectors
# (energy, banking, automotive) run far higher than services.
REVENUE_PER_EMPLOYEE = {
    "energy": 620_000, "banking": 480_000, "insurance": 430_000,
    "automotive": 310_000, "retail": 260_000, "logistics": 210_000,
    "manufacturing": 265_000, "public": 120_000, "healthcare": 105_000,
    "it_services": 145_000, "construction": 230_000, "other": 195_000,
}
REVENUE_SIGMA = 0.30

FOUNDED_YEAR_RANGE = (1875, 2021)   # skewed old: German Mittelstand

# ---------------------------------------------------------------------------
# 4. GITHUB / ENGINEERING FOOTPRINT  -- stands in for: GitHub org + user API
#    Applied to PEOPLE, not companies: for the German mid-market employers we
#    target, a public GitHub presence is rare and uninformative, whereas for
#    an individual consultant it is a genuine competence signal.
# ---------------------------------------------------------------------------

# Probability a consultant in this role family has a public profile at all.
GITHUB_PROFILE_RATE = {
    "dev": 0.78, "data": 0.58, "architect": 0.62, "ops": 0.48,
    "security": 0.44, "qa": 0.36, "analyst": 0.16, "support": 0.10,
}
GITHUB_PROFILE_RATE_DEFAULT = 0.30

# Median public repos and yearly contributions for someone who has a profile,
# before the experience multiplier. Both are heavy-tailed in reality, so the
# generator draws lognormally rather than uniformly.
GITHUB_REPOS_MEDIAN = {"dev": 14, "data": 9, "architect": 11, "ops": 8,
                       "security": 7, "qa": 5, "analyst": 3, "support": 2}
GITHUB_CONTRIB_MEDIAN = {"dev": 210, "data": 130, "architect": 120, "ops": 95,
                         "security": 70, "qa": 55, "analyst": 25, "support": 15}
GITHUB_REPOS_SIGMA = 0.75
GITHUB_CONTRIB_SIGMA = 0.95
GITHUB_STARS_SIGMA = 1.9        # very heavy tail: most people have almost none
GITHUB_YEARS_FACTOR = 0.055     # per year of experience, compounding

# ---------------------------------------------------------------------------
# 5. BENCH COMMERCIALS  -- stands in for: internal rate card and HR records
# ---------------------------------------------------------------------------

# Lithuanian nearshore day rate charged to a German client, EUR.
BENCH_DAY_RATE = {"junior": 370, "mid": 490, "senior": 640, "lead": 810}
BENCH_RATE_SIGMA = 0.09

# German capability is chargeable: a consultant who can run client meetings in
# German commands a premium and unlocks work others cannot take.
BENCH_GERMAN_PREMIUM = 1.12

BENCH_NOTICE_DAYS = {"now": 0, "in_30d": 30, "in_90d": 90, "unavailable": 180}
BENCH_UTILISATION = (0.55, 0.98)     # share of the last year billed
BENCH_RATING = (3.2, 5.0)            # internal delivery rating

CERTIFICATIONS = {
    "cloud": ["AWS Solutions Architect", "Azure Administrator", "GCP Professional"],
    "security": ["CISSP", "OSCP", "ISO 27001 Lead Auditor"],
    "sap": ["SAP S/4HANA Certified", "SAP ABAP Certified"],
    "erp": ["SAP S/4HANA Certified", "Dynamics 365 Certified"],
    "data": ["Databricks Data Engineer", "Power BI Data Analyst"],
    "devops": ["CKA (Kubernetes)", "Terraform Associate"],
    "quality": ["ISTQB Advanced"],
    "platform": ["ITIL 4"],
}
CERT_RATE_BY_SENIORITY = {"junior": 0.12, "mid": 0.34, "senior": 0.58, "lead": 0.68}

# ---------------------------------------------------------------------------
# 6. HIDDEN PROJECTS + URGENCY
#    Project detection is NOT simulated -- it is computed from real posting
#    co-occurrence. Only the tender corroboration below is invented.
# ---------------------------------------------------------------------------

PROJECT_WINDOW_DAYS = 21      # roles opened this close together read as one push
PROJECT_MIN_ROLES = 3
PROJECT_MIN_FAMILIES = 2      # a real programme needs more than one kind of person

# stands in for: TED / EU public procurement notices
TENDER_CLASSES = {"public_sector"}
TENDER_RATE = 0.42            # share of public bodies with a live IT tender
TENDER_VALUE_RANGE = (250_000, 12_000_000)

# Act-fast bands, in days. Derived from hiring acceleration and how long the
# roles have already been open -- a company that just opened a programme is
# reachable; one that has been failing for months is already talking to
# somebody.
URGENCY_BANDS = [(0.80, 7, "this week"), (0.60, 14, "within two weeks"),
                 (0.40, 30, "this month"), (0.0, 90, "no rush")]
