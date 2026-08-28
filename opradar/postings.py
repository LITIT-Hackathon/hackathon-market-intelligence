"""Posting-level parsing: one raw row -> one clean, enriched posting record."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import reference as ref
from . import text as txt


# ---------------------------------------------------------------------------
# Nested-field flattening
# ---------------------------------------------------------------------------

def _iter_items(value) -> list:
    """Parquet list columns arrive as numpy arrays, lists or None. Normalise that."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "tolist"):
        try:
            return list(value.tolist())
        except Exception:  # pragma: no cover - defensive
            return []
    return []


def _dict_get(value, key: str):
    if isinstance(value, dict):
        return value.get(key)
    return None


def flatten_esco(df: pd.DataFrame) -> pd.DataFrame:
    """Pull ESCO occupation label + skill labels out of their struct columns.

    Note: these tags are machine-assigned and demonstrably noisy (the skill list is
    a top-5 nearest-neighbour assignment, not extraction). Treat them as a weak prior,
    never as ground truth -- cross-check against kldb_2010 and the title.
    """
    df["esco_occupation_label"] = df["esco_occupation"].map(lambda v: _dict_get(v, "label"))
    df["esco_occupation_uri"] = df["esco_occupation"].map(lambda v: _dict_get(v, "uri"))

    skills = df["esco_skills"].map(
        lambda v: [s.get("label") for s in _iter_items(v) if isinstance(s, dict) and s.get("label")]
    )
    df["esco_skills_list"] = skills
    df["esco_skill_count"] = skills.map(len)
    return df


def flatten_salary(df: pd.DataFrame) -> pd.DataFrame:
    df["salary_min_eur"] = df["salary_range"].map(lambda v: _dict_get(v, "min_eur"))
    df["salary_max_eur"] = df["salary_range"].map(lambda v: _dict_get(v, "max_eur"))
    df["salary_period"] = df["salary_range"].map(lambda v: _dict_get(v, "period"))
    return df


# ---------------------------------------------------------------------------
# KldB decoding
# ---------------------------------------------------------------------------

_KLDB_VALID = re.compile(r"^\d{5}$")


def decode_kldb(df: pd.DataFrame) -> pd.DataFrame:
    code = df["kldb_2010"].fillna("").astype(str).str.strip()
    valid = code.str.match(_KLDB_VALID)

    df["kldb_code"] = code.where(valid, None)
    df["kldb_sector_code"] = code.str[:1].where(valid, None)
    df["kldb_group_code"] = code.str[:2].where(valid, None)
    df["kldb_subgroup_code"] = code.str[:4].where(valid, None)
    df["kldb_level_code"] = code.str[4:5].where(valid, None)

    df["kldb_sector"] = df["kldb_sector_code"].map(ref.KLDB_SECTOR)
    df["kldb_group"] = df["kldb_group_code"].map(ref.KLDB_GROUP)
    df["kldb_level"] = df["kldb_level_code"].map(lambda c: ref.KLDB_LEVEL.get(c, (None, None))[0])
    df["kldb_level_label"] = df["kldb_level_code"].map(
        lambda c: ref.KLDB_LEVEL.get(c, (None, None))[1]
    )

    grp = df["kldb_group_code"].fillna("")
    df["is_it_core"] = grp.isin(ref.KLDB_IT_CORE)
    df["is_it_extended"] = grp.isin(ref.KLDB_IT_EXTENDED)
    return df


# ---------------------------------------------------------------------------
# Titles, technologies, seniority
# ---------------------------------------------------------------------------

def clean_titles(df: pd.DataFrame) -> pd.DataFrame:
    df["title_clean"] = df["title"].fillna("").map(txt.clean_title)
    df["title_fold"] = df["title_clean"].map(txt.fold)
    return df


def extract_technologies(df: pd.DataFrame, column: str = "title_fold") -> pd.DataFrame:
    """Match the technology dictionary against a text column.

    Runs against the *folded* text (lowercase, umlauts expanded) because the patterns
    are written in ASCII: "steuergeraet" cannot match "Steuergerat" otherwise.

    Coverage from titles alone is low by construction -- most German job titles name
    a role, not a stack. The same function runs over job descriptions once those are
    fetched, which is where the real coverage comes from.
    """
    source = df[column].fillna("")
    hits: list[list[str]] = []
    cats: list[list[str]] = []

    for value in source:
        found: list[str] = []
        found_cats: set[str] = set()
        for name, (category, pattern) in ref.TECH_COMPILED.items():
            if pattern.search(value):
                found.append(name)
                found_cats.add(category)
        hits.append(found)
        cats.append(sorted(found_cats))

    df["technologies"] = hits
    df["tech_categories"] = cats
    df["tech_count"] = [len(h) for h in hits]
    df["has_tech_signal"] = df["tech_count"] > 0
    return df


def extract_domains(df: pd.DataFrame, column: str = "title_fold") -> pd.DataFrame:
    """Market sector the role sits in. Kept separate from `technologies`.

    Domain fit is a first-class matching dimension for placement ("we have three
    people with core-banking experience"), and mixing it into the technology list
    would put "Automotive" at the top of a technology ranking, which is nonsense.
    """
    source = df[column].fillna("")
    hits = [
        [name for name, pattern in ref.DOMAIN_COMPILED.items() if pattern.search(value)]
        for value in source
    ]
    df["domains"] = hits
    df["domain_count"] = [len(h) for h in hits]
    return df


def derive_role_flags(df: pd.DataFrame) -> pd.DataFrame:
    """The two columns of the ALGORITHM.md interface contract.

    is_it_role       -- the TITLE says this is an IT job. Title-primary by design:
                        the KldB code stays available as `is_it_core` for
                        corroboration (Confidence input), never as a gate.
    is_training_role -- Ausbildung / duales Studium / Werkstudent / Praktikum.

    The scorer's eligible posting is:
        company_class in {end_client, public_sector}
        AND is_it_role AND NOT is_training_role

    Both patterns live in reference.py -- the single shared lexicon. Do not
    re-implement them downstream.
    """
    folded = df["title_fold"].fillna("")
    df["is_it_role"] = folded.str.contains(ref.IT_ROLE_PATTERN)
    df["is_training_role"] = folded.str.contains(ref.TRAINING_ROLE_PATTERN)
    return df


def _seniority_from_title(title_fold: str) -> str | None:
    for label, pattern in ref.SENIORITY_TITLE_PATTERNS:
        if re.search(pattern, title_fold, re.IGNORECASE):
            return label
    return None


def derive_seniority(df: pd.DataFrame) -> pd.DataFrame:
    """Combine the available weak sources into one field.

    Priority: explicit title keyword > dataset column > unknown.

    The KldB requirement level is deliberately NOT used as a fallback. It measures
    qualification (level 4 = "requires a degree"), not career stage, and mapping it
    to seniority labelled ~45% of the market "senior". `kldb_level` stays available
    as its own column for anyone who wants it -- it just is not this.

    Result: seniority is known for ~31% of postings instead of the dataset's 12%,
    and the ~69% that stay unknown are honestly unknown.
    """
    from_title = df["title_fold"].map(_seniority_from_title)
    from_dataset = df["seniority"].fillna("unknown").map(ref.SENIORITY_FROM_DATASET)
    from_kldb = df["kldb_level_code"].map(ref.SENIORITY_FROM_KLDB_LEVEL)

    derived = from_title.copy()
    source = pd.Series(np.where(derived.notna(), "title", None), index=df.index)

    mask = derived.isna() & from_dataset.notna()
    derived = derived.where(~mask, from_dataset)
    source = source.where(~mask, "dataset")

    mask = derived.isna() & from_kldb.notna()
    derived = derived.where(~mask, from_kldb)
    source = source.where(~mask, "kldb")

    df["seniority_derived"] = derived.fillna("unknown")
    df["seniority_source"] = source.fillna("none")
    return df


# ---------------------------------------------------------------------------
# Dates and geography
# ---------------------------------------------------------------------------

def derive_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Posting age relative to the crawl date.

    IMPORTANT: this dataset is a *stock* of postings that were still open at crawl
    time, not a *flow* of postings created over time. Two consequences:

      1. Counting postings by `posted_date` produces a fake exponential growth curve.
         Old postings are missing because they were FILLED, not because hiring was
         slower. Never read a trend off this column.
      2. `posting_age_days` is length-biased: long-lived postings are over-sampled
         by construction. It is valid for ranking cells against each other, and
         invalid as an absolute "average time to fill".

    Within those limits, age is the most useful signal in the dataset: a role open
    for months is a direct measurement of a company failing to hire locally.
    """
    posted = pd.to_datetime(df["posted_date"], errors="coerce")
    fetched = pd.to_datetime(df["fetched_at"], errors="coerce", utc=True).dt.tz_localize(None)

    snapshot = fetched.max()
    if pd.isna(snapshot):
        snapshot = posted.max()

    df["posted_date"] = posted
    df["fetched_at"] = fetched
    df["snapshot_date"] = snapshot
    df["posting_age_days"] = (snapshot - posted).dt.days
    df["posted_year_month"] = posted.dt.to_period("M").astype(str)

    age = df["posting_age_days"]
    df["is_fresh_30d"] = age <= 30
    df["is_stale_90d"] = age > 90
    df["is_stale_180d"] = age > 180
    return df


def derive_geography(df: pd.DataFrame) -> pd.DataFrame:
    region = df["region"].fillna("").astype(str).str.strip()
    nuts = df["nuts_code"].fillna("").astype(str).str.strip()

    # Fill missing region from NUTS where possible.
    filled = region.where(region != "", nuts.map(ref.NUTS_TO_REGION).fillna(""))
    df["region_clean"] = filled.replace("", None)

    def country(row_region: str, row_nuts: str) -> str:
        if row_region in ref.AUSTRIAN_REGIONS:
            return "AT"
        if row_region in ref.SWISS_REGIONS:
            return "CH"
        if row_nuts.startswith("DE"):
            return "DE"
        if row_region:
            return "DE"
        return "unknown"

    df["country"] = [
        country(r or "", n or "")
        for r, n in zip(df["region_clean"].fillna(""), nuts)
    ]

    region_folded = df["region_clean"].fillna("").map(txt.fold)
    pop_folded = {txt.fold(k): v for k, v in ref.REGION_POPULATION_M.items()}
    df["region_population_m"] = region_folded.map(pop_folded)
    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    # identity
    "posting_id", "source_url", "source",
    # company
    "employer_raw", "company_key", "company_key_loose", "company_name",
    # role
    "title", "title_clean",
    "kldb_code", "kldb_sector_code", "kldb_sector", "kldb_group_code", "kldb_group",
    "kldb_subgroup_code", "kldb_level_code", "kldb_level", "kldb_level_label",
    "is_it_core", "is_it_extended", "is_it_role", "is_training_role",
    "esco_occupation_label", "esco_occupation_uri", "esco_skills_list", "esco_skill_count",
    "technologies", "tech_categories", "tech_count", "has_tech_signal",
    "domains", "domain_count",
    "seniority_raw", "seniority_derived", "seniority_source",
    # time
    "posted_date", "fetched_at", "snapshot_date", "posted_year_month",
    "posting_age_days", "is_fresh_30d", "is_stale_90d", "is_stale_180d",
    # place
    "region_clean", "nuts_code", "country", "region_population_m",
    # other
    "is_green", "salary_min_eur", "salary_max_eur", "salary_period",
]


def parse(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw dataset rows -> clean posting records (company fields filled in later)."""
    df = raw.copy()
    df = df.rename(columns={"id": "posting_id", "seniority": "seniority_raw"})
    df["employer_raw"] = df["employer"]

    df = flatten_esco(df)
    df = flatten_salary(df)
    df = decode_kldb(df)
    df = clean_titles(df)
    df = extract_technologies(df, column="title_fold")
    df = extract_domains(df, column="title_fold")
    df = derive_role_flags(df)
    df["seniority"] = df["seniority_raw"]
    df = derive_seniority(df)
    df = df.drop(columns=["seniority"])
    df = derive_dates(df)
    df = derive_geography(df)
    return df
