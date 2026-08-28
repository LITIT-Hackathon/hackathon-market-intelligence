"""Self-checks for the parser's normalisation rules.

Run with pytest, or standalone:  python tests/test_parser.py

These are the cases that actually bit us. Add to them whenever you find a name or
title the parser mangles -- that is cheaper than re-discovering it in the demo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opradar import companies as C  # noqa: E402
from opradar import reference as ref  # noqa: E402
from opradar import text as txt  # noqa: E402


def test_canonicalise_folds_german():
    assert txt.canonicalise("TÜV SÜD AG") == "tuev sued ag"
    assert txt.canonicalise("GmbH & Co. KG") == "gmbh und co kg"
    assert txt.canonicalise("GmbH&Co.KG") == "gmbh und co kg"
    assert txt.canonicalise("Schäfer & Söhne GmbH") == "schaefer und soehne gmbh"


def test_split_legal_form_cuts_divisions_and_branches():
    cases = {
        "DIS AG Personaldienstleistungen": "dis",
        "DIS AG Germany": "dis",
        "FERCHAU GmbH Niederlassung Bremen City": "ferchau",
        "Siemens Energy Global GmbH & Co. KG": "siemens energy global",
        # duplicated legal-form suffixes really do occur in the source data
        "PerZukunft Arbeitsvermittlung GmbH&Co.KG GmbH & Co. KG": "perzukunft arbeitsvermittlung",
        "quo data GmbH Qualitätsmanagement und Statistik": "quo data",
        "Hitachi": "hitachi",  # no legal form at all
    }
    for raw, expected in cases.items():
        core, _ = txt.split_legal_form(txt.canonicalise(raw))
        assert txt.strip_branch(core) == expected, f"{raw!r} -> {core!r}"


def test_legal_form_at_start_is_not_stripped():
    """A name that begins with a legal-form token must survive intact."""
    core, form = txt.split_legal_form(txt.canonicalise("AG Solar Technik"))
    assert core == "ag solar technik" and form == ""


def test_match_keys_group_variants():
    variants = [
        "DIS AG", "DIS AG Germany", "DIS AG Finance", "DIS AG FB Office & Management",
    ]
    keys = {txt.match_key(txt.strip_branch(txt.split_legal_form(txt.canonicalise(v))[0]))
            for v in variants}
    assert keys == {"dis"}


def test_display_name_trims_branch_tails():
    cases = {
        "Orizon GmbH NL Halle": "Orizon GmbH",
        "persona service AG & Co. KG Troisdorf": "persona service AG & Co. KG",
        "Tempton Personaldienstleistungen GmbH - NL Eisenach": "Tempton Personaldienstleistungen GmbH",
        "STRABAG AG, Direktion Großprojekte Nord-West": "STRABAG AG",
        "Ferchau  GmbH": "Ferchau GmbH",
        "Brunel": "Brunel",
        "shoob.de": "shoob.de",
    }
    for raw, expected in cases.items():
        assert txt.display_name(raw) == expected, f"{raw!r} -> {txt.display_name(raw)!r}"


def test_clean_title_strips_gender_markers_and_ref_codes():
    cases = {
        "Senior Java Developer (m/w/d)": "Senior Java Developer",
        "355/B - IT-Systemadministrator Multifaktor-Authentifizierung (m/w/d)":
            "IT-Systemadministrator Multifaktor-Authentifizierung",
        "QA Automation Engineer (gn)": "QA Automation Engineer",
        "Train Test Engineer (all gender)": "Train Test Engineer",
        "Data Analyst (w/m/x) | Vollzeit": "Data Analyst",
    }
    for raw, expected in cases.items():
        assert txt.clean_title(raw) == expected, f"{raw!r} -> {txt.clean_title(raw)!r}"


def _tech(title: str) -> set[str]:
    folded = txt.fold(txt.clean_title(title))
    return {n for n, (_, p) in ref.TECH_COMPILED.items() if p.search(folded)}


def test_technology_matching_avoids_known_false_positives():
    # driving-licence classes must not register as the C language
    assert "C/C++" not in _tech("Berufskraftfahrer (C/CE) im Nahverkehr (m/w/d)")
    assert "C/C++" not in _tech("Auslieferungsfahrer mit Führerschein der Klasse C, CE oder C1E")
    # occupational safety is not IT security
    assert "Security" not in _tech("Fachkraft für Arbeitssicherheit (m/w/d)")
    assert "Security" not in _tech("Sicherheitsmitarbeiter (m/w/d) Großbaustelle")
    # "AI"/"KI" must not fire from inside German words
    assert "AI/ML" not in _tech("Klinikleitung (m/w/d)")
    assert "AI/ML" not in _tech("Maindenker (m/w/d)")


def test_technology_matching_finds_real_signal():
    assert "C/C++" in _tech("Embedded Softwareentwickler (m/w/d) mit C/C++ oder Python")
    assert "Python" in _tech("Embedded Softwareentwickler (m/w/d) mit C/C++ oder Python")
    assert "Security" in _tech("IT-Sicherheitsexpert:in (m/w/d) für Software")
    assert "Security" in _tech("Senior Engineer Embedded Security")
    assert "AI/ML" in _tech("Data Engineer im KI Team (m/w/d)")
    assert "SAP" in _tech("SAP Anwendungsentwickler:in ABAP Cloud")
    # German compounds must still match
    assert "Network" in _tech("Netzwerkadministrator (m/w/d)")
    assert "Network" in _tech("Netzwerktechniker / IT-Security Engineer (m/w/d)")


def test_domains_are_separate_from_technologies():
    folded = txt.fold("Hardwareentwickler Steuergerät Automotive (m/w/d)")
    domains = {n for n, p in ref.DOMAIN_COMPILED.items() if p.search(folded)}
    assert "Automotive" in domains
    assert "Automotive" not in ref.TECH_COMPILED
    # umlaut-folded German patterns must fire
    assert "Embedded" in {n for n, (_, p) in ref.TECH_COMPILED.items() if p.search(folded)}


def test_classification():
    cases = {
        "Brunel GmbH": ref.CLASS_STAFFING,
        "persona service AG & Co. KG": ref.CLASS_STAFFING,
        "ARWA Personaldienstleistungen GmbH": ref.CLASS_STAFFING,
        "alfatraining Bildungszentrum GmbH": ref.CLASS_TRAINING,
        "Bundeskriminalamt": ref.CLASS_PUBLIC,
        "Akkodis Germany Tech Experts GmbH": ref.CLASS_IT_SERVICES,
        # product/captive IT companies are end clients, not competitors
        "Finanz Informatik GmbH & Co. KG": ref.CLASS_END_CLIENT,
        "zollsoft GmbH": ref.CLASS_END_CLIENT,
        "Rheinmetall AG": ref.CLASS_END_CLIENT,
        "Ängel, Ahmet": ref.CLASS_INDIVIDUAL,
    }
    for name, expected in cases.items():
        got, _, rule = C.classify_name(name, txt.canonicalise(name))
        assert got == expected, f"{name!r} -> {got} (rule={rule}), expected {expected}"


def test_entropy_bounds():
    from collections import Counter

    assert C._entropy(Counter()) == 0.0
    assert C._entropy(Counter({"a": 10})) == 0.0
    assert abs(C._entropy(Counter({"a": 5, "b": 5})) - 1.0) < 1e-9


def test_present_guards_nan():
    assert not C._present(float("nan"))
    assert not C._present(None)
    assert not C._present("")
    assert C._present("x")


# ---------------------------------------------------------------------------
# candidate dataset
# ---------------------------------------------------------------------------

def test_candidate_taxonomies_are_complete():
    """Every role and skill in the dataset must map to a family, or aggregates lie."""
    assert len(ref.ROLE_TO_FAMILY) == 24, len(ref.ROLE_TO_FAMILY)
    assert len(ref.SKILL_TO_FAMILY) == 73, len(ref.SKILL_TO_FAMILY)
    # families must not overlap
    for table in (ref.ROLE_FAMILIES, ref.SKILL_FAMILIES):
        flat = [x for members in table.values() for x in members]
        assert len(flat) == len(set(flat)), "an entry appears in two families"


def test_candidate_mappings():
    assert ref.CANDIDATE_SENIORITY["Senior"] == "senior"
    assert set(ref.CANDIDATE_SENIORITY.values()) <= set(ref.SENIORITY_ORDER)
    # industries with no equivalent stay None rather than being forced into a bucket
    assert ref.CANDIDATE_INDUSTRY_TO_DOMAIN["FinTech"] == "Banking"
    assert ref.CANDIDATE_INDUSTRY_TO_DOMAIN["Gaming"] is None
    assert set(v for v in ref.CANDIDATE_INDUSTRY_TO_DOMAIN.values() if v) <= set(ref.DOMAIN_PATTERNS)


def test_experience_bands_are_contiguous():
    covered = set()
    for lo, hi, _ in ref.EXPERIENCE_BANDS:
        covered |= set(range(lo, min(hi, 40) + 1))
    assert set(range(0, 13)) <= covered, "a plausible years_experience value has no band"


def test_skill_market_tension_is_normalised():
    """Tension must centre on 1.0, or the number reads as meaningful while not being."""
    import pandas as pd
    from opradar import candidates as cand

    profiles = pd.DataFrame({
        "candidate_id": ["a", "b", "c", "d"],
        # 3 of 4 hold Python, 1 of 4 holds Java
        "skills": [["Python", "SQL"], ["Python", "SQL"], ["Python", "SQL"], ["Java", "SQL"]],
    })
    openings = pd.DataFrame({
        "opening_id": ["j1", "j2"],
        "must_have_skills": [["Java"], ["Java"]],
        "nice_to_have_skills": [[], []],
    })
    market = cand.build_skill_market(profiles, openings)
    row = {r.skill: r for r in market.itertuples()}
    # Java: scarce on the bench and demanded by every opening -> well above 1
    assert row["Java"].tension > 1.5, row["Java"].tension
    # Python: plentiful and unwanted -> at the bottom
    assert row["Python"].tension < row["Java"].tension
    assert market["tension"].notna().all()


def test_qualified_pool_matches_the_documented_rule():
    import pandas as pd
    from opradar import candidates as cand

    profiles = pd.DataFrame({
        "candidate_id": ["a", "b", "c"],
        "skills": [["X", "Y", "Z"], ["X", "Y"], ["X"]],
    })
    openings = pd.DataFrame({
        "opening_id": ["j"],
        "must_have_skills": [["X", "Y", "Z"]],
        "nice_to_have_skills": [[]],
    })
    matrix, index = cand.skill_matrix(profiles)
    profiles, openings = cand.compute_pools(profiles, openings, matrix, index)
    # 3/3 and 2/3 clear the 0.6 threshold; 1/3 does not
    assert int(openings["qualified_pool"].iloc[0]) == 2
    assert profiles["qualified_for_openings"].tolist() == [1, 1, 0]


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
