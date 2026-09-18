from __future__ import annotations

# Centralized mapping from JMdict POS entity codes to simplified taxonomy.

VERB_CODES = {
    "v1", "v1-s", "v2a-s", "v2b-k", "v2b-s", "v2d-k", "v2d-s",
    "v2g-k", "v2g-s", "v2h-k", "v2h-s", "v2k-k", "v2k-s", "v2m-k",
    "v2m-s", "v2n-s", "v2r-k", "v2r-s", "v2s-s", "v2t-k", "v2t-s",
    "v2w-s", "v2y-k", "v2y-s", "v2z-s", "v4b", "v4g", "v4h", "v4k",
    "v4m", "v4n", "v4r", "v4s", "v4t", "v5aru", "v5b", "v5g", "v5k",
    "v5k-s", "v5m", "v5n", "v5r", "v5r-i", "v5s", "v5t", "v5u",
    "v5u-s", "v-unspec", "vk", "vz", "vs", "vs-i", "vs-s", "aux-v",
}

ADJECTIVE_CODES = {
    "adj-i", "adj-ix", "adj-na", "adj-no", "adj-pn", "adj-t",
    "adj-f", "adj-kari", "adj-ku", "adj-nari", "adj-shiku",
    "aux-adj",
}

ADVERB_CODES = {"adv", "adv-to"}

NOUN_CODES = {
    "n", "n-adv", "n-pr", "n-pref", "n-suf", "n-t", "num", "pn",
    "pref", "prt", "suf", "ctr",
}

ALL_KNOWN = VERB_CODES | ADJECTIVE_CODES | ADVERB_CODES | NOUN_CODES


def classify_pos(pos_codes: list[str]) -> list[str]:
    """Map JMdict POS codes to simplified categories."""
    categories: set[str] = set()
    for code in pos_codes:
        if code in VERB_CODES:
            categories.add("verb")
        elif code in ADJECTIVE_CODES:
            categories.add("adjective")
        elif code in ADVERB_CODES:
            categories.add("adverb")
        elif code in NOUN_CODES:
            categories.add("noun")
        else:
            categories.add("other")
    if not categories:
        categories.add("other")
    return sorted(categories)


def pos_tags(pos_codes: list[str]) -> list[str]:
    """Return full jp-organizer POS tags."""
    return [f"jp-organizer::pos::{cat}" for cat in classify_pos(pos_codes)]
