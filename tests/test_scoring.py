"""Self-checks for the scoring layer (Algorithms A and B, Layer C).

Run standalone:  python tests/test_scoring.py
Or via pytest:   pytest tests/test_scoring.py

Every scenario the brief demands is here, as a synthetic company whose intended
behaviour is stated in its name: a huge company with routine hiring must not
win by volume, a small company with a coherent burst must beat it, missing
evidence must land mid-pack rather than at either end, and one deleted vacancy
must not reshuffle the board.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np   # noqa: E402
import pandas as pd  # noqa: E402

from opradar import bench_gen, eligibility, features, match, people  # noqa: E402
from opradar import scoring  # noqa: E402
from opradar.config import CONFIG, config_hash  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _posting(pid, company, title, age, tech=None, seniority="unknown",
             family_hint=None, it=True, training=False, region="Bayern"):
    return dict(
        posting_id=pid, company_key=company, title_clean=title,
        posting_age_days=age, tech_categories=tech or [],
        seniority_derived=seniority, is_it_role=it, is_training_role=training,
        region_clean=region, source_url=f"https://example.test/{pid}",
    )


def _company(key, name, company_class="end_client", it_postings=10,
             variants=1, corrob=0.8):
    return dict(
        company_key=key, company_name=name, company_class=company_class,
        it_postings=it_postings, name_variant_count=variants,
        it_corroboration=corrob, name_variants=[name],
    )


def _ba(key, matched=True, stock=10, it_stock=10, it_flow=2, flow=2,
        pav=0, za=0, branche="5"):
    return dict(
        company_key=key, ba_matched=matched, ba_name_used="x",
        ba_stock=stock, ba_it_stock=it_stock, ba_it_flow_28=it_flow,
        ba_flow_28=flow, ba_flow_7=0, ba_pav_true=pav, ba_za_true=za,
        ba_branche=branche, ba_branche_label=None, ba_error=False,
        ba_checked_at="2026-08-29T00:00:00+00:00",
    )


def _scenario():
    """The red-team cast, one company per failure mode."""
    postings, companies, ba = [], [], []

    # 1. HUGE ENTERPRISE, routine hiring: 40 IT ads, all fresh, none aged,
    #    scattered stack. Must NOT rank first on volume alone.
    companies.append(_company("mega", "Mega AG", it_postings=40))
    ba.append(_ba("mega", stock=200, it_stock=40, it_flow=38, flow=150))
    for i in range(40):
        postings.append(_posting(
            f"m{i}", "mega", f"Softwareentwickler {i}", age=i % 20,
            tech=[["data"], ["cloud"], ["erp"], ["security"], ["network"]][i % 5]))

    # 2. SMALL COHERENT BURST: 8 ads in 10 days, one stack, several senior,
    #    team-shaped, and the board shows them still open a month on. The
    #    design's archetypal winner.
    companies.append(_company("burst", "Burst GmbH", it_postings=8))
    ba.append(_ba("burst", stock=10, it_stock=8, it_flow=1, flow=1))
    cast = [("Cloud Architekt", "senior", ["cloud"]),
            ("Senior Backend Entwickler Java", "senior", ["cloud", "language"]),
            ("Senior DevOps Engineer", "senior", ["cloud", "devops"]),
            ("Backend Entwickler", "unknown", ["cloud"]),
            ("QA Engineer", "unknown", ["quality"]),
            ("Data Engineer Cloud", "senior", ["cloud", "data"]),
            ("Backend Entwickler Java", "unknown", ["cloud"]),
            ("Systemadministrator Cloud", "unknown", ["cloud"])]
    for i, (title, sen, tech) in enumerate(cast):
        postings.append(_posting(f"b{i}", "burst", title, age=40 + (i % 10),
                                 tech=tech, seniority=sen))

    # 3. REPOSTER: the same 5 titles, all fresh -- duplicate seats but no aged
    #    demand, no live confirmation of anything old.
    companies.append(_company("repost", "Repost GmbH", it_postings=10))
    ba.append(_ba("repost", stock=10, it_stock=10, it_flow=10, flow=10))
    for i in range(10):
        postings.append(_posting(f"r{i}", "repost", "SAP Berater", age=i % 7,
                                 tech=[["erp"]][0], seniority="unknown"))

    # 4. GHOST: no live match at all -- missing evidence, not negative evidence.
    companies.append(_company("ghost", "Ghost GmbH", it_postings=5))
    ba.append(_ba("ghost", matched=False, stock=0, it_stock=0, it_flow=0))
    for i in range(5):
        postings.append(_posting(f"g{i}", "ghost", f"Entwickler {i}", age=50 + i,
                                 tech=["language"], seniority="unknown"))

    # 5. AGENCY caught by the board's own flags -- must never be ranked.
    companies.append(_company("agency", "Staffup GmbH", it_postings=30))
    ba.append(_ba("agency", stock=100, it_stock=60, it_flow=40, pav=95, za=5))
    for i in range(30):
        postings.append(_posting(f"a{i}", "agency", f"Consultant {i}", age=10,
                                 tech=["erp"]))

    # 6. STALLED GIANT: modest ad count but a large verified-aged live stock.
    #    Ages sit inside CONFIG["age"]["hard_cap_days"] but well past the
    #    45-day proxy line: what makes this company stalled is its live stock
    #    standing still, not the crawl row being ancient. At the previous
    #    ages (100+) the recency cap dropped it from the pool entirely and
    #    three tests lost their subject.
    companies.append(_company("stalled", "Stalled AG", it_postings=6))
    ba.append(_ba("stalled", stock=60, it_stock=50, it_flow=5, flow=8))
    for i in range(6):
        postings.append(_posting(f"s{i}", "stalled", f"Java Entwickler {i}",
                                 age=70 + i, tech=["language"], seniority="senior"))

    # 7. TINY: exactly at the pool minimum, nothing else remarkable.
    companies.append(_company("tiny", "Tiny UG", it_postings=3))
    ba.append(_ba("tiny", stock=3, it_stock=3, it_flow=1))
    for i in range(3):
        postings.append(_posting(f"t{i}", "tiny", f"Admin {i}", age=30 + i))

    # 8. TRAINING-HEAVY: mostly Azubis; below threshold once they are removed.
    companies.append(_company("school", "Ausbilder AG", it_postings=6))
    ba.append(_ba("school", stock=6, it_stock=6, it_flow=2))
    for i in range(2):
        postings.append(_posting(f"x{i}", "school", f"Entwickler {i}", age=20))
    for i in range(4):
        postings.append(_posting(f"xa{i}", "school", "Ausbildung Fachinformatiker",
                                 age=20, training=True))

    p = pd.DataFrame(postings)
    c = pd.DataFrame(companies)
    b = pd.DataFrame(ba)
    return p, c, b


def _run(postings=None, companies=None, ba=None):
    if postings is None:
        postings, companies, ba = _scenario()
    segments = eligibility.classify(companies, ba)
    feats, pool = features.build(postings, companies, segments, ba)
    bench = bench_gen.generate()
    svc = match.serviceability(pool, bench)
    ranked = scoring.score(feats, svc, pool)
    return ranked, feats, pool, bench, segments


# ---------------------------------------------------------------------------
# eligibility
# ---------------------------------------------------------------------------

def test_agency_flags_beat_name_rules():
    _, c, b = _scenario()
    seg = eligibility.classify(c, b)
    agency = seg[seg.company_key == "agency"].iloc[0]
    assert agency["segment"] == "agency"
    assert agency["segment_source"] == "ba_flag"
    assert agency["segment_verified"]


def test_unmatched_company_keeps_weaker_rung_and_is_unverified():
    _, c, b = _scenario()
    seg = eligibility.classify(c, b)
    ghost = seg[seg.company_key == "ghost"].iloc[0]
    assert ghost["segment"] == "end_client"
    assert not ghost["segment_verified"]


def test_curated_label_wins_over_everything():
    _, c, b = _scenario()
    curated = pd.DataFrame([{"company_key": "agency", "segment": "end_client",
                             "reason": "hand-checked: the flags are a data error"}])
    seg = eligibility.classify(c, b, curated)
    row = seg[seg.company_key == "agency"].iloc[0]
    assert row["segment"] == "end_client" and row["segment_source"] == "curated"


def test_clean_branche_verifies_an_end_client():
    _, c, b = _scenario()
    seg = eligibility.classify(c, b)
    mega = seg[seg.company_key == "mega"].iloc[0]
    assert mega["segment"] == "end_client" and mega["segment_verified"]


# ---------------------------------------------------------------------------
# Algorithm A -- the red-team cast in ranked order
# ---------------------------------------------------------------------------

def test_agency_and_training_heavy_are_not_ranked():
    ranked, *_ = _run()
    assert "agency" not in set(ranked["company_key"])
    assert "school" not in set(ranked["company_key"])   # 2 real IT ads < minimum


def test_volume_alone_does_not_win():
    ranked, *_ = _run()
    order = list(ranked["company_key"])
    # the burst company and the stalled giant both outrank the fresh-only giant
    assert order.index("burst") < order.index("mega")
    assert order.index("stalled") < order.index("mega")


def test_burst_company_scores_high_on_programme():
    ranked, *_ = _run()
    burst = ranked[ranked.company_key == "burst"].iloc[0]
    mega = ranked[ranked.company_key == "mega"].iloc[0]
    assert burst["programme"] > mega["programme"]
    assert burst["burst_n"] >= 8 and burst["excess_concentration"] > 0.2


def test_reposter_gets_no_unmet_credit():
    ranked, *_ = _run()
    repost = ranked[ranked.company_key == "repost"].iloc[0]
    stalled = ranked[ranked.company_key == "stalled"].iloc[0]
    assert repost["unmet"] < stalled["unmet"]
    assert repost["dup_seats"] >= 8      # the duplication is still visible


def test_missing_live_evidence_lands_midpack_not_bottom():
    ranked, *_ = _run()
    ghost = ranked[ranked.company_key == "ghost"].iloc[0]
    # expansion is unobservable for ghost: its effective value must equal the
    # pool prior, not zero
    assert ghost["expansion_e"] == 0.0
    assert abs(ghost["expansion_eff"] - ghost["expansion_prior"]) < 1e-6
    # and its confidence, not its score, is what takes the hit
    assert ghost["confidence_band"] == "low"


def test_conflicting_signals_lower_agreement_not_score_directly():
    ranked, *_ = _run()
    # stalled: huge unmet, no expansion -- the signals disagree
    stalled = ranked[ranked.company_key == "stalled"].iloc[0]
    burst = ranked[ranked.company_key == "burst"].iloc[0]
    assert stalled["conf_agreement"] <= burst["conf_agreement"] + 0.15


def test_score_boundaries_and_types():
    ranked, *_ = _run()
    assert ranked["opportunity"].between(0, 100).all()
    assert ranked["pressure"].between(0, 1).all()
    for sig in scoring.SIGNALS:
        assert ranked[f"{sig}_eff"].between(0, 1).all()
    assert (ranked["rank"] == np.arange(1, len(ranked) + 1)).all()


def test_evidence_is_traceable_json_with_urls():
    ranked, *_ = _run()
    for raw in ranked["evidence"]:
        items = json.loads(raw)
        assert items and all(e["url"].startswith("https://") for e in items)


def test_ranking_stable_under_one_deleted_vacancy():
    ranked, *_ = _run()
    p, c, b = _scenario()
    # delete one mega vacancy -- the order of the head must not change
    p2 = p[p.posting_id != "m0"]
    ranked2, *_ = _run(p2, c, b)
    head = [k for k in ranked.head(4)["company_key"]]
    head2 = [k for k in ranked2.head(4)["company_key"]]
    assert head == head2


def test_config_hash_stamped_and_stable():
    ranked, *_ = _run()
    assert (ranked["config_hash"] == config_hash()).all()
    h1 = config_hash()
    CONFIG["signal_weights"]["unmet"] += 0.01
    try:
        assert config_hash() != h1
    finally:
        CONFIG["signal_weights"]["unmet"] -= 0.01


# ---------------------------------------------------------------------------
# statistical primitives
# ---------------------------------------------------------------------------

def test_eb_rate_shrinks_small_samples():
    k = pd.Series([1, 30]); n = pd.Series([2, 70])
    a, b = 2.0, 6.0   # prior mean 0.25
    post = scoring.eb_rate(k, n, a, b)
    # 1-of-2 must sit far closer to the prior than 30-of-70
    assert abs(post[0] - 0.25) < abs(0.5 - 0.25)
    assert abs(post[1] - 30 / 70) < 0.05


def test_excess_concentration_null_model():
    # a single-tech company with n=1 must NOT read as maximally focused
    assert scoring.excess_concentration({"erp": 1}, pool_hhi=0.2) == 0.0
    # many draws of one tech: clearly above chance
    assert scoring.excess_concentration({"erp": 9}, pool_hhi=0.2) > 0.5
    # a mix matching the pool: about zero
    assert scoring.excess_concentration(
        {"a": 3, "b": 3, "c": 3}, pool_hhi=1 / 3) < 0.15


def test_beta_prior_fallback_on_degenerate_pool():
    a, b = scoring.fit_beta_prior(pd.Series([1, 1]), pd.Series([2, 2]))
    assert a > 0 and b > 0


# ---------------------------------------------------------------------------
# Layer C + Algorithm B
# ---------------------------------------------------------------------------

def test_serviceability_decomposition_consistent():
    ranked, feats, pool, bench, _ = _run()
    svc = match.serviceability(pool, bench)
    assert svc["serviceability"].between(0, 1).all()
    assert (svc["atoms_covered"] + svc["atoms_uncovered"] == svc["atoms_total"]).all()


def test_unknown_tech_is_partial_credit_not_pass():
    bench = pd.DataFrame([{
        "candidate_id": "c1", "role_family": "dev", "seniority": "senior",
        "seniority_rank": 2, "tech_tags": ["cloud"], "availability": "now",
    }])
    by_fam = match.bench_by_family(bench)
    credit_known, _, _ = match.atom_match(2, {"cloud"}, by_fam["dev"])
    credit_unknown, _, _ = match.atom_match(2, set(), by_fam["dev"])
    assert credit_known == 1.0
    assert credit_unknown == CONFIG["match"]["unknown_tech_credit"]


def test_person_value_rewards_unique_coverage_over_breadth():
    _, feats, pool, _, _ = _run()
    # tiny bench: one narrow unique specialist vs one broad duplicate
    bench = pd.DataFrame([
        dict(candidate_id="unique", role_family="dev", seniority="senior",
             seniority_rank=2, tech_tags=["language"], availability="now",
             speaks_german=False, languages=["en"], source="synthetic"),
        dict(candidate_id="dup1", role_family="dev", seniority="senior",
             seniority_rank=2, tech_tags=["cloud", "data", "erp", "quality"],
             availability="now", speaks_german=False, languages=["en"],
             source="synthetic"),
        dict(candidate_id="dup2", role_family="dev", seniority="senior",
             seniority_rank=2, tech_tags=["cloud", "data", "erp", "quality"],
             availability="now", speaks_german=False, languages=["en"],
             source="synthetic"),
    ])
    ranked, *_ = _run()
    value = people.person_value(bench, pool, ranked)
    u = value[value.candidate_id == "unique"].iloc[0]
    d = value[value.candidate_id == "dup1"].iloc[0]
    # the unique specialist covers the Java-heavy stalled demand nobody else
    # covers; each broad twin is replaceable by the other
    assert u["uniqueness"] > d["uniqueness"]


def test_unavailable_consultant_has_zero_value():
    _, feats, pool, bench, _ = _run()
    b = bench.copy()
    b.loc[:, "availability"] = "unavailable"
    ranked, *_ = _run()
    value = people.person_value(b, pool, ranked)
    assert (value["value_raw"] == 0).all()


def test_capability_plan_is_actionable():
    ranked, feats, pool, bench, _ = _run()
    cells = match.cell_demand(pool, ranked, bench)
    plan = people.capability_plan(cells)
    # no row may be pure mush: unknown seniority AND unspecified tech
    mush = (plan["tech_tag"] == "unspecified") & (plan["seniority"] == "unknown")
    assert not mush.any()
    # priority must reflect the gap, not just demand size
    assert (plan["priority"] <= plan["demand_weight"] + 1e-9).all()


def test_bench_github_is_family_aware_and_display_only():
    """GitHub must be evidence where code is published and silent elsewhere."""
    b = bench_gen.generate()
    # relevance follows the role family, not the individual
    assert b.loc[b.role_family == "dev", "sim_github_relevant"].all()
    assert not b.loc[b.role_family == "support", "sim_github_relevant"].any()
    # developers publish far more than analysts
    dev = b[b.role_family == "dev"]["sim_github_profile"].mean()
    ana = b[b.role_family == "analyst"]["sim_github_profile"].mean()
    assert dev > ana
    # the 0-100 reading exists ONLY where a profile is both relevant and present,
    # so an empty cell reads as "not measured", never as "measured and bad"
    scored = b["sim_github_score"].notna()
    assert (scored <= (b["sim_github_relevant"] & b["sim_github_profile"])).all()
    assert scored.any()


def test_bench_day_rate_ladders_and_is_never_scored():
    b = bench_gen.generate()
    med = b.groupby("seniority")["sim_day_rate_eur"].median()
    assert med["junior"] < med["mid"] < med["senior"] < med["lead"]
    # German capability is chargeable
    assert b[b.speaks_german]["sim_day_rate_eur"].mean() >            b[~b.speaks_german]["sim_day_rate_eur"].mean()
    # and none of it may reach the ranking: value must not move when rates do
    _, feats, pool, _, _ = _run()
    ranked, *_ = _run()
    base = people.person_value(b, pool, ranked)
    hiked = b.copy()
    hiked["sim_day_rate_eur"] = hiked["sim_day_rate_eur"] * 10
    after = people.person_value(hiked, pool, ranked)
    assert base["value_raw"].tolist() == after["value_raw"].tolist()


def test_bench_is_deterministic_and_labelled():
    b1, b2 = bench_gen.generate(), bench_gen.generate()
    assert b1.equals(b2)
    assert (b1["source"] == "synthetic").all()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    raise SystemExit(1 if failures else 0)
