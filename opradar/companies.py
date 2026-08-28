"""Company entity resolution, classification and aggregation.

Entity resolution here is deliberately modest. The brief does not require it to be
perfect, and over-merging is worse than under-merging for a sales/placement list --
a wrongly merged company produces a lead that does not exist.

The ladder, cheapest first:
  1. canonicalise the name (umlauts, punctuation, "&" -> "und")
  2. cut at the first legal-form token -- this removes divisions, branches and
     duplicated suffixes in one step
  3. group on the resulting key (exact)
  4. optionally, blocked fuzzy merge (off by default, --fuzzy)

Step 5, not implemented here because it needs the live API: the source publishes a
stable `arbeitgeberKundennummerHash` per employer. Where present it beats every
string heuristic. See RESEARCH.md section 4.2.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import pandas as pd

from . import reference as ref
from . import text as txt


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def build_keys(employers: pd.Series) -> pd.DataFrame:
    """Map each distinct raw employer string to its resolution keys."""
    distinct = sorted({e for e in employers.fillna("").astype(str) if e.strip()})

    rows = []
    for raw in distinct:
        canonical = txt.canonicalise(raw)
        core, legal_form = txt.split_legal_form(canonical)
        core = txt.strip_branch(core)
        loose = txt.strip_loose_suffixes(core)

        key = txt.match_key(core) or txt.match_key(canonical)
        key_loose = txt.match_key(loose) or key

        rows.append(
            {
                "employer_raw": raw,
                "canonical": canonical,
                "core_name": core,
                "legal_form": legal_form,
                "company_key": key,
                "company_key_loose": key_loose,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Optional fuzzy merge
# ---------------------------------------------------------------------------

class _Union:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Deterministic: the lexicographically smaller key wins.
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra


def fuzzy_merge(
    keys: pd.DataFrame,
    weights: dict[str, int],
    threshold: float = 0.92,
    min_len: int = 6,
) -> tuple[dict[str, str], list[tuple[str, str, float]]]:
    """Blocked fuzzy merge over company keys.

    Blocking on the first 4 characters keeps this O(n * block) instead of O(n^2).
    Short keys are excluded -- "dis" vs "dhs" scores high and means nothing.
    """
    unique_keys = sorted(set(keys["company_key"]))
    blocks: dict[str, list[str]] = defaultdict(list)
    for key in unique_keys:
        if len(key) >= min_len:
            blocks[key[:4]].append(key)

    union = _Union()
    merges: list[tuple[str, str, float]] = []

    for block in blocks.values():
        if len(block) < 2:
            continue
        for i in range(len(block)):
            for j in range(i + 1, len(block)):
                a, b = block[i], block[j]
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio >= threshold:
                    union.union(a, b)
                    merges.append((a, b, round(ratio, 3)))

    mapping = {}
    for key in unique_keys:
        root = union.find(key) if len(key) >= min_len else key
        mapping[key] = root

    # Name each cluster after its highest-volume member, not an arbitrary root.
    cluster_members: dict[str, list[str]] = defaultdict(list)
    for key, root in mapping.items():
        cluster_members[root].append(key)
    canonical_of_root = {
        root: max(members, key=lambda k: (weights.get(k, 0), -len(k)))
        for root, members in cluster_members.items()
    }
    mapping = {key: canonical_of_root[root] for key, root in mapping.items()}

    return mapping, merges


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_COMPILED_CLASS = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in ref.CLASS_PATTERNS]


def classify_name(raw_name: str, canonical: str) -> tuple[str, float, str]:
    """Rule-based company classification from the name alone.

    Returns (class, confidence, matched_rule). Confidence is deliberately modest:
    these are keyword rules, and the honest thing is to say so and let the
    behavioural features (below) and a later LLM pass refine them.
    """
    if not raw_name:
        return ref.CLASS_END_CLIENT, 0.0, "empty"

    if ref.INDIVIDUAL_PATTERN.match(raw_name.strip()):
        return ref.CLASS_INDIVIDUAL, 0.8, "person_name"

    for label, pattern in _COMPILED_CLASS:
        match = pattern.search(canonical)
        if match:
            confidence = 0.85 if label in (ref.CLASS_TRAINING, ref.CLASS_STAFFING) else 0.6
            return label, confidence, match.group(0)

    return ref.CLASS_END_CLIENT, 0.35, "default"


def _entropy(counts: Counter) -> float:
    """Shannon entropy, normalised to 0..1 over the observed alphabet."""
    total = sum(counts.values())
    if total <= 0 or len(counts) <= 1:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in counts.values() if c > 0)
    return h / math.log(len(counts))


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _present(value) -> bool:
    """True for a real value. Guards against NaN, which is truthy and unsortable."""
    if value is None:
        return False
    if isinstance(value, float) and value != value:
        return False
    return value != ""


def _display_name(variant_counts: Counter, fallback: str) -> str:
    """Pick the cleanest rendering of an entity from its observed name variants.

    Frequency is the wrong criterion: a company with 60 branch offices has more
    postings under "FERCHAU GmbH Niederlassung Hannover" than under "FERCHAU GmbH".
    Prefer a variant that carries a legal form (so we keep "Brunel GmbH" over the
    bare "Brunel"), then the shortest, then the most common.
    """
    if not variant_counts:
        return fallback

    # Trim each variant to "<name> <legal form>" first, then choose among the trimmed
    # forms. Trimming is what actually removes the branch tails; choosing shortest
    # afterwards just breaks ties between spellings.
    trimmed: Counter = Counter()
    for name, count in variant_counts.items():
        trimmed[txt.display_name(name)] += count

    def score(item: tuple[str, int]) -> tuple[int, int, int]:
        name, count = item
        has_legal_form = bool(txt.split_legal_form(txt.canonicalise(name))[1])
        return (0 if has_legal_form else 1, len(name), -count)

    return min(trimmed.items(), key=score)[0]


def _mode(values: list):
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _median(values: list[float]):
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    mid = n // 2
    return float(values[mid]) if n % 2 else float((values[mid - 1] + values[mid]) / 2)


def _quantile(values: list[float], q: float):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, int(round(q * (len(values) - 1))))
    return float(values[idx])


def build(postings: pd.DataFrame) -> pd.DataFrame:
    """Aggregate parsed postings into one row per resolved company.

    Deliberately not a pandas groupby-apply: with ~17k groups, per-group pandas
    operations cost minutes. Pulling the columns out to plain Python lists once and
    indexing them positionally turns the same work into a few seconds.
    """
    # Materialise the columns we need once.
    cols = {
        name: postings[name].tolist()
        for name in [
            "employer_raw", "company_key_loose", "kldb_sector_code", "kldb_group_code",
            "region_clean", "country", "is_it_core", "is_it_role", "is_training_role",
            "technologies", "posting_age_days",
            "is_stale_90d", "is_fresh_30d", "seniority_derived", "kldb_level",
        ]
    }
    posted = postings["posted_date"].tolist()

    rows = []
    for key, idx in postings.groupby("company_key", dropna=True).indices.items():
        idx = list(idx)
        n = len(idx)

        variant_counts = Counter(
            cols["employer_raw"][i] for i in idx if _present(cols["employer_raw"][i])
        )
        display = _display_name(variant_counts, key)

        canonical = txt.canonicalise(display)
        company_class, class_conf, rule = classify_name(display, canonical)

        sector_counts = Counter(
            cols["kldb_sector_code"][i] for i in idx if _present(cols["kldb_sector_code"][i])
        )
        group_counts = Counter(
            cols["kldb_group_code"][i] for i in idx if _present(cols["kldb_group_code"][i])
        )
        regions = [cols["region_clean"][i] for i in idx if _present(cols["region_clean"][i])]
        countries = {cols["country"][i] for i in idx if _present(cols["country"][i])}

        # IT slice is TITLE-based per the ALGORITHM.md contract: is_it_role and not
        # a training posting. KldB (`is_it_core`) is kept as corroboration counts.
        it_idx = [i for i in idx if cols["is_it_role"][i] and not cols["is_training_role"][i]]
        core_n = sum(1 for i in idx if cols["is_it_core"][i])
        training_n = sum(1 for i in idx if cols["is_training_role"][i])
        corrob_n = sum(1 for i in it_idx if cols["is_it_core"][i])
        tech_counter: Counter = Counter()
        for i in it_idx:
            tech_counter.update(cols["technologies"][i])

        ages = [cols["posting_age_days"][i] for i in idx if cols["posting_age_days"][i] == cols["posting_age_days"][i]]
        it_ages = [
            cols["posting_age_days"][i]
            for i in it_idx
            if cols["posting_age_days"][i] == cols["posting_age_days"][i]
        ]
        dates = [posted[i] for i in idx if _present(posted[i])]

        sector_entropy = _entropy(sector_counts)
        n_regions = len(set(regions))

        # Behavioural agency fingerprint: agencies post many unrelated roles across
        # many regions. This catches firms the name regex misses.
        breadth = min(1.0, sector_entropy) * min(1.0, n_regions / 6.0) * min(1.0, n / 20.0)

        rows.append(
            {
                "company_key": key,
                "company_key_loose": _mode(
                    [cols["company_key_loose"][i] for i in idx if _present(cols["company_key_loose"][i])]
                ) or key,
                "company_name": display,
                "name_variants": sorted(variant_counts),
                "name_variant_count": len(variant_counts),
                "company_class": company_class,
                "class_confidence": class_conf,
                "class_rule": rule,
                "postings": n,
                "it_postings": len(it_idx),
                "it_intensity": round(len(it_idx) / n, 4) if n else 0.0,
                "it_core_postings": core_n,
                "training_postings": training_n,
                # share of the company's IT postings where KldB agrees -> the
                # `corrob` Confidence input (ALGORITHM.md 4.5)
                "it_corroboration": round(corrob_n / len(it_idx), 4) if it_idx else None,
                "regions": sorted(set(regions)),
                "region_count": n_regions,
                "primary_region": _mode(regions),
                "countries": sorted(countries),
                "kldb_sectors": sorted(sector_counts),
                "kldb_sector_entropy": round(sector_entropy, 4),
                "top_kldb_group": group_counts.most_common(1)[0][0] if group_counts else None,
                "seniority_mix": dict(Counter(cols["seniority_derived"][i] for i in idx)),
                "kldb_level_mix": dict(
                    Counter(cols["kldb_level"][i] for i in idx if _present(cols["kldb_level"][i]))
                ),
                "top_technologies": [t for t, _ in tech_counter.most_common(8)],
                "median_age_days": _median(ages),
                "p90_age_days": _quantile(ages, 0.9),
                "median_it_age_days": _median(it_ages),
                "stale_90d_share": round(
                    sum(1 for i in idx if cols["is_stale_90d"][i]) / n, 4
                ),
                "fresh_30d_share": round(
                    sum(1 for i in idx if cols["is_fresh_30d"][i]) / n, 4
                ),
                "first_posted": min(dates) if dates else None,
                "last_posted": max(dates) if dates else None,
                "agency_breadth_score": round(breadth, 4),
            }
        )

    companies = pd.DataFrame(rows)
    if companies.empty:
        return companies

    # Combine the name rule with the behavioural fingerprint into one likelihood.
    name_says_agency = companies["company_class"].eq(ref.CLASS_STAFFING).astype(float)
    companies["agency_likelihood"] = (
        0.6 * name_says_agency + 0.4 * companies["agency_breadth_score"]
    ).round(4)

    # Companies the name rules cannot decide: high volume, spread across unrelated
    # occupational sectors and many regions, but no agency keyword in the name.
    # That is the fingerprint of a staffing firm -- and also of a genuinely large
    # diversified employer, which is why this flags for review instead of relabelling.
    #
    # Thresholds tuned to produce a queue of ~60 companies: small enough to review by
    # hand or with one LLM pass, and it does catch real misses (Office People,
    # Bankpower and F mal s are all staffing firms with no agency keyword in the name).
    companies["needs_review"] = (
        companies["company_class"].eq(ref.CLASS_END_CLIENT)
        & (companies["agency_breadth_score"] >= 0.65)
        & (companies["postings"] >= 30)
        & (companies["kldb_sectors"].map(len) >= 6)
    )

    # T2 (ALGORITHM.md 4.3): small, IT-dense, classified end_client. T1 above only
    # catches large diversified companies; T2 catches small IT service providers
    # whose names carry no keyword (inovex, EMOS, BCM...). Measured overlap with
    # T1: zero -- the triggers are complementary. Both queues feed the LLM pass.
    companies["needs_review_t2"] = (
        companies["company_class"].eq(ref.CLASS_END_CLIENT)
        & (companies["it_intensity"] >= 0.5)
        & (companies["it_postings"] >= 3)
    )

    # Competitors = anyone selling the same placements we would.
    companies["is_competitor"] = companies["company_class"].isin(
        [ref.CLASS_STAFFING, ref.CLASS_IT_SERVICES]
    )
    # Not a real hiring employer: training providers and private individuals.
    companies["is_noise"] = companies["company_class"].isin(
        [ref.CLASS_TRAINING, ref.CLASS_INDIVIDUAL]
    )

    return companies.sort_values("postings", ascending=False).reset_index(drop=True)
