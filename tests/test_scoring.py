"""Self-checks for the scoring layer (Pipelines A, B, C).

Run standalone:  python tests/test_scoring.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from opradar import bench_gen, match, signals  # noqa: E402
from opradar.config import CONFIG, config_hash  # noqa: E402
from opradar.scoring import confidence, need_components  # noqa: E402


def _signals_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        # a: high volume but ageing demand, no fresh postings
        dict(company_key="a", it_n=10, it_w=5.0, fresh_w=0.0, open_45=8, open_90=6,
             senior_n=5, senior_share=0.5,
             hhi=0.6, tech_covered_n=6, fresh_n=0, window_n=4, momentum_raw=0.0,
             name_variant_count=1, class_confidence=0.35, in_review=False, corrob=0.9,
             has_fresh_30d=False, has_recent_90d=True),
        # b: fresh burst -- must dominate under fresh-first N1
        dict(company_key="b", it_n=6, it_w=5.5, fresh_w=4.5, open_45=0, open_90=0,
             senior_n=1, senior_share=0.17,
             hhi=0.3, tech_covered_n=3, fresh_n=5, window_n=6, momentum_raw=0.83,
             name_variant_count=3, class_confidence=0.35, in_review=False, corrob=0.5,
             has_fresh_30d=True, has_recent_90d=True),
        # c: every posting ancient -- the N4 zero-denominator case
        dict(company_key="c", it_n=4, it_w=0.4, fresh_w=0.0, open_45=4, open_90=4,
             senior_n=0, senior_share=0.0,
             hhi=0.0, tech_covered_n=0, fresh_n=0, window_n=0, momentum_raw=0.0,
             name_variant_count=1, class_confidence=0.35, in_review=True, corrob=0.0,
             has_fresh_30d=False, has_recent_90d=False),
    ])


def test_need_components_are_percentiles():
    s = need_components(_signals_fixture())
    for col in ("n1", "n2", "n3", "n4"):
        assert s[col].between(0, 1).all(), col
    # fresh-first: the fresh-burst company must top both N1 and N4
    assert s.loc[s.company_key == "b", "n1"].iloc[0] == s["n1"].max()
    assert s.loc[s.company_key == "b", "n4"].iloc[0] == s["n4"].max()


def test_n4_zero_denominator_scores_zero_raw():
    s = _signals_fixture()
    assert s.loc[s.company_key == "c", "momentum_raw"].iloc[0] == 0.0


def test_confidence_bands_and_review_discount():
    s = confidence(_signals_fixture())
    assert set(s["confidence_band"]) <= {"low", "medium", "high"}
    # the review-flagged, stale, thin-evidence company must band lowest
    by = s.set_index("company_key")
    assert by.loc["c", "confidence"] < by.loc["a", "confidence"]
    assert by.loc["c", "confidence_band"] == "low"


def test_match_rules():
    bench = pd.DataFrame([
        dict(candidate_id="x", role_family="dev", tech_tags=["language", "backend"],
             seniority="senior", seniority_rank=2, availability="now"),
        dict(candidate_id="y", role_family="dev", tech_tags=["frontend"],
             seniority="junior", seniority_rank=0, availability="now"),
        dict(candidate_id="z", role_family="data", tech_tags=["data"],
             seniority="mid", seniority_rank=1, availability="unavailable"),
    ])
    pool = pd.DataFrame([
        # senior dev with backend tech: covered fully by x
        dict(company_key="c1", role_family="dev", seniority_rank=2.0,
             tech_categories=["backend"], posting_age_days=100),
        # lead dev: x is exactly one below -> adjacent credit only
        dict(company_key="c2", role_family="dev", seniority_rank=3.0,
             tech_categories=["backend"], posting_age_days=100),
        # data role: only candidate is unavailable -> uncovered
        dict(company_key="c3", role_family="data", seniority_rank=1.0,
             tech_categories=["data"], posting_age_days=100),
        # no tech signal, unknown seniority: must pass both tests
        dict(company_key="c4", role_family="dev", seniority_rank=float("nan"),
             tech_categories=[], posting_age_days=100),
        # embedded tech that nobody on the bench holds -> uncovered
        dict(company_key="c5", role_family="dev", seniority_rank=1.0,
             tech_categories=["embedded"], posting_age_days=100),
    ])
    svc = match.serviceability(pool, bench).set_index("company_key")
    m = CONFIG["match"]

    full = m["coverage_weight"] * 1.0 + m["depth_weight"] * (1 / m["depth_saturation"])
    assert abs(svc.loc["c1", "serviceability"] - round(full, 4)) < 1e-6
    adj = m["coverage_weight"] * m["adjacent_credit"] + m["depth_weight"] * (1 / m["depth_saturation"])
    assert abs(svc.loc["c2", "serviceability"] - round(adj, 4)) < 1e-6
    assert svc.loc["c3", "serviceability"] == 0.0
    assert svc.loc["c4", "serviceability"] > 0.5          # passes tech + seniority
    assert svc.loc["c5", "serviceability"] == 0.0         # phantom tech never matches
    assert svc.loc["c3", "atoms_uncovered"] == 1


def test_bench_is_deterministic_and_labelled():
    b1, b2 = bench_gen.generate(), bench_gen.generate()
    assert b1.drop(columns=["tech_tags", "languages"]).equals(
        b2.drop(columns=["tech_tags", "languages"]))
    assert list(map(tuple, b1["tech_tags"])) == list(map(tuple, b2["tech_tags"]))
    assert (b1["source"] == "synthetic").all()
    assert len(b1) >= 115  # rounding keeps it near BENCH_SIZE
    # the deliberate profile gap: nobody on the bench does embedded or mobile
    held = set().union(*b1["tech_tags"])
    assert "embedded" not in held and "mobile" not in held


def test_role_family_classification():
    cases = {
        "senior java entwickler": "dev",
        "softwarearchitekt cloud": "architect",
        "it-systemadministrator": "ops",
        "devops engineer": "ops",
        "data engineer ki team": "data",
        "it security engineer": "security",
        "softwaretester automatisierung": "qa",
        "sap berater": "analyst",
        "it-projektmanager": "analyst",
        "helpdesk mitarbeiter first level": "support",
        "fachinformatiker anwendungsentwicklung": "dev",
    }
    for title, expected in cases.items():
        got = signals.role_family(title)
        assert got == expected, f"{title!r} -> {got}, expected {expected}"


def test_age_weight_decay_and_cap():
    from opradar.signals import age_weight
    a = CONFIG["age"]
    assert age_weight(0) == 1.0
    assert age_weight(a["full_weight_days"]) == 1.0
    mid = (a["full_weight_days"] + a["hard_cap_days"]) / 2
    assert abs(age_weight(mid) - 0.5) < 1e-9
    assert age_weight(a["hard_cap_days"]) == 0.0
    assert age_weight(a["hard_cap_days"] + 200) == 0.0


def test_liveness_weights_and_fresh_decay():
    from opradar.signals import age_weight, attach_liveness
    snap = pd.Timestamp("2026-06-06")
    elig = pd.DataFrame([
        # newest ad, verified alive: near-full weight
        dict(posting_id="r0", posting_age_days=0, snapshot_date=snap),
        # young + verified alive: already decaying (fresh-first, no plateau)
        dict(posting_id="r1", posting_age_days=10, snapshot_date=snap),
        # young + verified dead: same curve, damped to dead_weight
        dict(posting_id="r2", posting_age_days=10, snapshot_date=snap),
        # ~3 months old + verified alive: dropped -- too old, alive or not
        dict(posting_id="r3", posting_age_days=120, snapshot_date=snap),
        # ancient + unchecked: dropped by the hard cap
        dict(posting_id="r4", posting_age_days=400, snapshot_date=snap),
        # mid-decay + unchecked: partial weight
        dict(posting_id="r5", posting_age_days=45, snapshot_date=snap),
    ])
    liveness = pd.DataFrame([
        dict(refnr="r0", alive=True, checked_at="2026-08-29T00:00:00+00:00"),
        dict(refnr="r1", alive=True, checked_at="2026-08-29T00:00:00+00:00"),
        dict(refnr="r2", alive=False, checked_at="2026-08-29T00:00:00+00:00"),
        dict(refnr="r3", alive=True, checked_at="2026-08-29T00:00:00+00:00"),
    ])
    out = attach_liveness(elig, liveness).set_index("posting_id")

    assert "r3" not in out.index                       # too old, alive or not
    assert "r4" not in out.index                       # hard cap drops it
    assert out.loc["r0", "signal_weight"] == 1.0       # day-0 ad: full weight
    assert out.loc["r1", "age_effective"] == 10        # posted age, no lag
    w10 = round(float(age_weight(10)), 4)
    assert out.loc["r1", "signal_weight"] == w10       # newer = higher
    assert out.loc["r1", "signal_weight"] < out.loc["r0", "signal_weight"]
    assert out.loc["r2", "signal_weight"] == round(w10 * CONFIG["liveness"]["dead_weight"], 4)
    assert 0.0 < out.loc["r5", "signal_weight"] < w10  # deeper in the decay


def test_liveness_without_data_is_age_policy_only():
    from opradar.signals import age_weight, attach_liveness
    snap = pd.Timestamp("2026-06-06")
    elig = pd.DataFrame([
        dict(posting_id="r1", posting_age_days=10, snapshot_date=snap),
        dict(posting_id="r2", posting_age_days=400, snapshot_date=snap),
    ])
    out = attach_liveness(elig, None).set_index("posting_id")
    assert out.loc["r1", "signal_weight"] == round(float(age_weight(10)), 4)
    assert out.loc["r1", "age_effective"] == 10
    assert "r2" not in out.index


def test_evidence_excludes_dead_links():
    from opradar.scoring import _evidence
    import json as _json
    grp = pd.DataFrame([
        dict(posting_id="p1", title_clean="Old dead", source_url="u1",
             posting_age_days=80, age_effective=80.0, role_family="dev",
             alive=False),
        dict(posting_id="p2", title_clean="Old alive", source_url="u2",
             posting_age_days=66, age_effective=66.0, role_family="dev",
             alive=True),
        dict(posting_id="p3", title_clean="Unchecked", source_url="u3",
             posting_age_days=20, age_effective=20.0, role_family="dev",
             alive=None),
    ])
    grp["alive"] = grp["alive"].astype("boolean")
    out = _json.loads(_evidence(grp))
    urls = [e["url"] for e in out]
    assert "u1" not in urls                            # dead link never shown
    assert set(urls) == {"u2", "u3"}
    by_url = {e["url"]: e for e in out}
    assert by_url["u2"]["live"] is True and by_url["u2"]["age"] == 66
    assert by_url["u3"]["live"] is None
    assert out[0]["url"] == "u3"                       # freshest leads the panel


def test_liveness_status_classification():
    from opradar.liveness import classify
    assert classify(200) is True
    assert classify(404) is False
    assert classify(410) is False
    assert classify(403) is None
    assert classify(None) is None


def test_config_hash_is_stable_and_sensitive():
    h1 = config_hash()
    h2 = config_hash()
    assert h1 == h2 and len(h1) == 12
    tweaked = {**CONFIG, "min_it_postings": 4}
    assert config_hash(tweaked) != h1


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL  {name}: {exc}")
    print(f"\n{'all passed' if not failures else f'{failures} failed'}")
    raise SystemExit(1 if failures else 0)
