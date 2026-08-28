"""String normalisation primitives.

German-specific rules matter here: a matcher that does not fold ae/ä, oe/ö, ue/ü
and ss/ß produces false negatives on a large share of German company names.
"""

from __future__ import annotations

import re
import unicodedata

from . import reference as ref

UMLAUT_MAP = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
    "à": "a", "á": "a", "â": "a", "ã": "a", "å": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ø": "o",
    "ù": "u", "ú": "u", "û": "u",
    "ç": "c", "ñ": "n", "ý": "y",
}

_PUNCT = re.compile(r"[.,;:!?/\\()\[\]{}'\"`´’“”„–—_+*]")
_WS = re.compile(r"\s+")


def fold(text: str) -> str:
    """Lowercase and expand German umlauts / strip accents. Reversible enough for matching."""
    if not text:
        return ""
    out = []
    for ch in text:
        if ch in UMLAUT_MAP:
            out.append(UMLAUT_MAP[ch])
        else:
            out.append(ch)
    s = "".join(out).lower()
    # Anything still non-ASCII gets decomposed and stripped.
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def canonicalise(name: str) -> str:
    """Company name -> canonical token stream used for legal-form detection.

    "GmbH & Co. KG"  -> "gmbh und co kg"
    "GmbH&Co.KG"     -> "gmbh und co kg"
    "TUEV SUED AG"   -> "tuev sued ag"
    """
    if not name:
        return ""
    s = fold(name)
    s = s.replace("&", " und ")
    s = s.replace("+", " und ")
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def split_legal_form(canonical: str) -> tuple[str, str]:
    """Split a canonical name at the first legal-form token.

    Returns (core, legal_form). Everything at and after the legal form is dropped --
    that removes branch names, divisions and duplicated suffixes in one step:

        "dis ag personaldienstleistungen"       -> ("dis", "ag")
        "ferchau gmbh niederlassung bremen city"-> ("ferchau", "gmbh")
        "perzukunft arbeitsvermittlung gmbh und co kg gmbh und co kg"
                                                -> ("perzukunft arbeitsvermittlung", "gmbh und co kg")
    """
    if not canonical:
        return "", ""

    tokens = canonical.split()
    best_idx: int | None = None
    best_form = ""

    for form in ref.LEGAL_FORMS:  # already longest-first
        form_tokens = form.split()
        n = len(form_tokens)
        for i in range(len(tokens) - n + 1):
            if tokens[i : i + n] == form_tokens:
                # Prefer the earliest position; at equal position prefer the longer form.
                if best_idx is None or i < best_idx or (i == best_idx and n > len(best_form.split())):
                    best_idx, best_form = i, form
                break

    if best_idx is None:
        return canonical, ""
    if best_idx == 0:
        # Name starts with something that looks like a legal form -- don't gut it.
        return canonical, ""
    return " ".join(tokens[:best_idx]), best_form


def strip_branch(core: str) -> str:
    """Drop a trailing branch/division clause from a name that has no legal form."""
    tokens = core.split()
    for i, tok in enumerate(tokens):
        if i > 0 and tok in ref.BRANCH_MARKERS:
            return " ".join(tokens[:i])
    return core


def strip_loose_suffixes(core: str) -> str:
    """Drop country/group qualifiers. Merges more, and sometimes merges wrongly."""
    tokens = core.split()
    while len(tokens) > 1 and tokens[-1] in ref.LOOSE_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def match_key(core: str) -> str:
    """Collapse to alphanumerics -- the grouping key for entity resolution."""
    return re.sub(r"[^a-z0-9]", "", core)


def _legal_form_display_regex() -> re.Pattern:
    """Regex matching a legal form as it appears in the ORIGINAL (unfolded) string.

    Built from the same LEGAL_FORMS list, but tolerant of the punctuation and casing
    that canonicalise() would have removed: "GmbH & Co. KG", "GmbH&Co.KG", "gmbh und co kg".
    Longest alternatives first, so "AG & Co. KG" wins over a bare "AG".
    """
    alternatives = []
    for form in ref.LEGAL_FORMS:  # already longest-first
        parts = []
        for token in form.split():
            if token == "und":
                parts.append(r"(?:&|und|\+)")
            elif token == "haftungsbeschraenkt":
                parts.append(r"\(?\s*haftungsbeschr[äa]nkt\s*\)?")
            else:
                parts.append("".join(f"{ch}\\.?" if ch.isalpha() else ch for ch in token))
        alternatives.append(r"\s*\.?\s*".join(parts))
    return re.compile(r"(?<![A-Za-zÀ-ÿ])(" + "|".join(alternatives) + r")(?![A-Za-zÀ-ÿ])", re.IGNORECASE)


LEGAL_FORM_DISPLAY = _legal_form_display_regex()


def display_name(raw: str) -> str:
    """Trim a raw employer string to its cleanest readable form.

    Cuts everything after the legal form, which removes branch and division tails
    while preserving the original casing:

        "Orizon GmbH NL Halle"                     -> "Orizon GmbH"
        "persona service AG & Co. KG Troisdorf"    -> "persona service AG & Co. KG"
        "Tempton Personaldienstleistungen GmbH - NL Eisenach"
                                                   -> "Tempton Personaldienstleistungen GmbH"
        "Brunel"                                   -> "Brunel"
    """
    if not raw:
        return raw
    s = _WS.sub(" ", raw).strip()
    match = LEGAL_FORM_DISPLAY.search(s)
    if match and match.start() > 0:
        s = s[: match.end()].strip()
    return s.strip(" ,-–|/")


def clean_title(title: str) -> str:
    """Strip gender markers, reference codes and trailing boilerplate from a job title."""
    if not title:
        return ""
    s = ref.REF_CODE_PREFIX.sub("", title)
    s = ref.GENDER_MARKERS.sub(" ", s)
    s = ref.TITLE_TAIL_NOISE.sub("", s)
    s = re.sub(r"\(\s*\)", " ", s)                 # empty brackets left behind
    s = re.sub(r"\s*[-–|,/]\s*$", "", s)           # dangling separators
    s = _WS.sub(" ", s).strip(" -–|,")
    return s.strip()
