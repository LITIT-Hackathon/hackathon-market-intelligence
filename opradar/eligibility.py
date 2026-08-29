"""Who is a prospect, who is a channel, who is noise -- the gate before scoring.

WHY THIS IS A SEPARATE, FIRST-CLASS STAGE
    Measured on the previous build: 16 of the top 20 ranked "opportunities" were
    companies the system's own classifier had flagged as undecidable, and the
    live board confirms several of them are placement agencies advertising other
    people's vacancies (plusYOU 22/22 offers flagged `pav`, empiricus 33/33,
    Ratbacher 128/128). For a company that SELLS IT talent, recommending another
    talent supplier is not a ranking error, it is the wrong answer.

    Standard B2B practice puts fit first for exactly this reason: ICP fit is the
    gate, intent is layered on top, never the reverse. So eligibility is decided
    here, once, on the best evidence available, and the scorer never sees a row
    whose segment it should not be ranking.

THE EVIDENCE LADDER
    Rules over company names were the previous approach and they do not work.
    Measured against the live board's own flags over 686 matched companies:

        feature                 agencies caught   false positives
        recruiter job titles          11 / 174           3
        reference numbers in titles    3 / 174           3
        >= 6 regions                  54 / 174          44

    The dataset carries no job descriptions (`description_derived` is 100% null),
    so there is almost no text to classify from. Inference cannot fix that.
    Fetching the label can: the job board publishes, per offer,
    `istPrivateArbeitsvermittlung` and `istArbeitnehmerUeberlassung`, and per
    employer a `branche` (industry) code. `opradar.balive` collects both.

    The ladder therefore runs highest-authority evidence first and records which
    rung fired, so every segment on screen is attributable:

        1. curated   an expert label, reviewed by hand, with a written reason
        2. ba_flag   the board's own per-offer agency flags (>50% of offers)
        3. ba_branche   the board's industry code for the employer
        4. name_rule    the legacy keyword rules -- still useful, now a fallback
        5. default      end client, UNVERIFIED, and marked as such

SEGMENTS ARE NOT A BINARY FILTER
    Agencies and IT vendors are not noise. FERCHAU, Akkodis and Orizon buy
    subcontracted delivery capacity, and are often an easier first sale than a
    direct enterprise deal. They belong on a CHANNEL list, clearly labelled --
    not silently deleted, and not mixed into the prospect leaderboard. Their IT
    volume is also the saturation signal: how contested a segment already is.

MISSING EVIDENCE IS NOT NEGATIVE EVIDENCE
    A company the board could not match keeps its segment from the weaker rungs
    and is marked `segment_verified = False`. That lowers CONFIDENCE, never the
    opportunity score. "We could not check" and "we checked and it is bad" are
    different states and the output keeps them apart.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import balive
from . import reference as ref

# --- the segments ----------------------------------------------------------
END_CLIENT = "end_client"        # buys IT delivery for its own business
CAPTIVE_IT = "captive_it"        # in-house IT arm of a non-IT group -- prime prospect
PUBLIC = "public_sector"         # prospect, but procurement-bound
IT_VENDOR = "it_vendor"          # sells IT services -- channel/partner, not prospect
AGENCY = "agency"                # sells people -- competitor and channel
TRAINING = "training_provider"   # course listings, not vacancies
INDIVIDUAL = "individual"        # a private person

PROSPECT_SEGMENTS = (END_CLIENT, CAPTIVE_IT, PUBLIC)
CHANNEL_SEGMENTS = (IT_VENDOR, AGENCY)
NOISE_SEGMENTS = (TRAINING, INDIVIDUAL)

# Share of an employer's live offers carrying an agency flag above which we call
# it an agency. Set at half deliberately: the flag is per OFFER, and a genuine
# end client occasionally publishes through an agency, while a real agency runs
# at or near 1.0. Measured on the pool the distribution is strongly bimodal --
# of 686 matched companies, 170 sit above 0.5 and the mass near 0.5 is thin.
AGENCY_FLAG_SHARE = 0.5

_CURATED_COLUMNS = ["company_key", "segment", "reason"]


def load_curated(path: Path | None) -> pd.DataFrame:
    """Hand-reviewed labels. Highest authority, because a human looked."""
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=_CURATED_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = [c for c in _CURATED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"curated segments file missing columns: {missing}")
    return df[_CURATED_COLUMNS].drop_duplicates("company_key", keep="last")


def _name_rule_segment(company_class: str) -> str:
    """Translate the parser's name-regex class into the segment vocabulary."""
    return {
        ref.CLASS_STAFFING: AGENCY,
        ref.CLASS_IT_SERVICES: IT_VENDOR,
        ref.CLASS_PUBLIC: PUBLIC,
        ref.CLASS_TRAINING: TRAINING,
        ref.CLASS_INDIVIDUAL: INDIVIDUAL,
    }.get(company_class, END_CLIENT)


def classify(companies: pd.DataFrame, ba: pd.DataFrame | None = None,
             curated: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per company: segment, why, how confident, and whether verified.

    Pure function over frames -- no I/O, no network -- so every rung of the
    ladder is unit-testable on its own.
    """
    out = companies[["company_key", "company_name", "company_class"]].copy()

    if ba is not None and len(ba):
        cols = ["company_key", "ba_matched", "ba_stock", "ba_pav_true", "ba_za_true",
                "ba_branche", "ba_branche_label", "ba_it_stock", "ba_it_flow_28",
                "ba_flow_28", "ba_name_used"]
        out = out.merge(ba[[c for c in cols if c in ba.columns]],
                        on="company_key", how="left")
    for col, fill in (("ba_matched", False), ("ba_stock", 0), ("ba_pav_true", 0),
                      ("ba_za_true", 0), ("ba_it_stock", 0), ("ba_it_flow_28", 0),
                      ("ba_flow_28", 0)):
        if col not in out.columns:
            out[col] = fill
        out[col] = out[col].fillna(fill)
    if "ba_branche" not in out.columns:
        out["ba_branche"] = None
    out["ba_matched"] = out["ba_matched"].astype(bool)

    stock = out["ba_stock"].clip(lower=1)
    out["agency_flag_share"] = ((out["ba_pav_true"] + out["ba_za_true"]) / stock).round(4)
    out.loc[~out["ba_matched"], "agency_flag_share"] = float("nan")

    # --- rung 5: default ---------------------------------------------------
    out["segment"] = out["company_class"].map(_name_rule_segment)
    out["segment_source"] = "name_rule"
    out["segment_confidence"] = 0.55
    out["segment_reason"] = "company name matched a keyword rule"
    plain = out["company_class"].eq(ref.CLASS_END_CLIENT)
    out.loc[plain, ["segment_source", "segment_confidence", "segment_reason"]] = [
        "default", 0.35, "no rule fired; assumed an end client"]

    # --- rung 3: the board's industry code ---------------------------------
    br = out["ba_branche"].astype("string")
    is_agency_branche = br.isin(sorted(balive.BRANCHE_AGENCY)) & out["ba_matched"]
    out.loc[is_agency_branche, "segment"] = AGENCY
    out.loc[is_agency_branche, "segment_source"] = "ba_branche"
    out.loc[is_agency_branche, "segment_confidence"] = 0.90
    out.loc[is_agency_branche, "segment_reason"] = (
        "job board lists this employer under " + br[is_agency_branche].fillna(""))

    # branche 11 is "Information und Kommunikation" -- IT SECTOR, which is not
    # the same thing as IT VENDOR. Delivery Hero and Telekom MMS sit here and
    # both buy delivery capacity. So this rung sets a soft label that curation
    # is expected to correct, and says so in the reason.
    is_it_branche = br.isin(sorted(balive.BRANCHE_IT)) & out["ba_matched"]
    soft = is_it_branche & out["segment"].isin([END_CLIENT])
    out.loc[soft, "segment"] = IT_VENDOR
    out.loc[soft, "segment_source"] = "ba_branche"
    out.loc[soft, "segment_confidence"] = 0.50
    out.loc[soft, "segment_reason"] = (
        "job board industry is Information und Kommunikation -- IT sector, so "
        "treated as a vendor until reviewed")

    # The POSITIVE rung, and the one that keeps this from marking every real
    # client "unverified": the board matched this employer, its industry is not
    # an agency industry and not IT, and effectively none of its live offers
    # carry an agency flag. That is outside evidence that the company hires for
    # itself -- weaker than a curated label, far stronger than "no rule fired".
    clean_branche = out["ba_matched"] & br.notna() & ~br.isin(
        sorted(balive.BRANCHE_AGENCY | balive.BRANCHE_IT | {"18"}))
    confirmed_client = (clean_branche
                        & (out["agency_flag_share"].fillna(1.0) < 0.05)
                        & out["segment"].eq(END_CLIENT))
    out.loc[confirmed_client, "segment_source"] = "ba_branche"
    out.loc[confirmed_client, "segment_confidence"] = 0.80
    labels = br.map(lambda code: balive.BRANCHE_LABEL.get(code, f"code {code}")
                    if pd.notna(code) else "")
    out.loc[confirmed_client, "segment_reason"] = (
        "job board industry is " + labels[confirmed_client]
        + " and no live offer is flagged placement or leasing")

    is_public_branche = br.eq("18") & out["ba_matched"] & ~out["segment"].isin([AGENCY])
    out.loc[is_public_branche, "segment"] = PUBLIC
    out.loc[is_public_branche, "segment_source"] = "ba_branche"
    out.loc[is_public_branche, "segment_confidence"] = 0.85
    out.loc[is_public_branche, "segment_reason"] = "job board industry is public administration"

    # --- rung 2: the board's own per-offer agency flags (beats industry) ----
    flagged = out["ba_matched"] & (out["agency_flag_share"] >= AGENCY_FLAG_SHARE)
    out.loc[flagged, "segment"] = AGENCY
    out.loc[flagged, "segment_source"] = "ba_flag"
    out.loc[flagged, "segment_confidence"] = 0.95
    share = (out["agency_flag_share"] * 100).round(0)
    out.loc[flagged, "segment_reason"] = (
        share[flagged].astype("Int64").astype(str)
        + "% of its live offers are flagged private placement or labour leasing")

    # --- rung 1: curated expert labels -------------------------------------
    if curated is not None and len(curated):
        idx = out["company_key"].isin(set(curated["company_key"]))
        lookup = curated.set_index("company_key")
        keys = out.loc[idx, "company_key"]
        out.loc[idx, "segment"] = keys.map(lookup["segment"]).values
        out.loc[idx, "segment_source"] = "curated"
        out.loc[idx, "segment_confidence"] = 0.95
        out.loc[idx, "segment_reason"] = keys.map(lookup["reason"]).values

    # A segment is VERIFIED when an authority outside the company's own name
    # said so. Everything else is an assumption we are making on their behalf.
    out["segment_verified"] = out["segment_source"].isin(["curated", "ba_flag", "ba_branche"])
    out["is_prospect"] = out["segment"].isin(PROSPECT_SEGMENTS)
    out["is_channel"] = out["segment"].isin(CHANNEL_SEGMENTS)
    return out


def summary(segments: pd.DataFrame) -> pd.DataFrame:
    """Segment x source counts -- the table to put in front of a reviewer."""
    return (segments.groupby(["segment", "segment_source"]).size()
            .rename("companies").reset_index()
            .sort_values(["segment", "companies"], ascending=[True, False]))
