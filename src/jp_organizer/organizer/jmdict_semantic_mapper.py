from __future__ import annotations

# Centralized mapping from JMdict semantic entity codes to project semantic classes.
#
# This module converts raw JMdict semantic metadata into one of:
#   - decisive mimetic
#   - decisive idiom
#   - insufficient semantic information (needs LLM fallback)
#   - no semantic classification

# JMdict entity codes that directly map to a decisive semantic class.
DECISIVE_MIMETIC_CODES = {"on-mim"}
DECISIVE_IDIOM_CODES = {"id"}

# Codes that indicate expression-like but do not resolve the subtype.
# These require LLM fallback for construction/idiom/collocation distinction.
GENERIC_EXPRESSION_CODES = {"exp"}


def map_semantic(semantic_codes: list[str], pos_codes: list[str] | None = None) -> dict:
    """Map JMdict semantic codes to a project semantic classification.

    Parameters:
      semantic_codes: Codes from JMdict <misc> elements.
      pos_codes: Optional codes from JMdict <pos> elements (used to detect
                 expression-like entries via the "exp" POS code).

    Returns a dict with keys:
      - classification: "mimetic" | "idiom" | "expression" | None
      - decisive: bool  # True if JMdict alone resolved it, False if LLM needed
      - raw_codes: list[str]

    Logic:
      - If any code is in DECISIVE_MIMETIC_CODES → classification="mimetic", decisive=True
      - Else if any code is in DECISIVE_IDIOM_CODES → classification="idiom", decisive=True
      - Else if any code is in GENERIC_EXPRESSION_CODES OR "exp" in pos_codes
                 → classification="expression", decisive=False
      - Else → classification=None, decisive=False
    """
    codes = set(semantic_codes)
    pos = set(pos_codes or [])

    if codes & DECISIVE_MIMETIC_CODES:
        return {"classification": "mimetic", "decisive": True, "raw_codes": list(codes)}

    if codes & DECISIVE_IDIOM_CODES:
        return {"classification": "idiom", "decisive": True, "raw_codes": list(codes)}

    if (codes & GENERIC_EXPRESSION_CODES) or (pos & GENERIC_EXPRESSION_CODES):
        return {"classification": "expression", "decisive": False, "raw_codes": list(codes | pos)}

    return {"classification": None, "decisive": False, "raw_codes": list(codes)}
