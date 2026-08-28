"""opradar -- parser for the German job-postings dataset.

Turns the raw dataset into two clean, queryable tables:
  postings.parquet   one row per job posting, enriched and normalised
  companies.parquet  one row per resolved company entity, classified and aggregated

Usage:
    python -m opradar
"""

__version__ = "0.1.0"

from .pipeline import Options, run  # noqa: F401
