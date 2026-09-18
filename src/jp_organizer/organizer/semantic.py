from __future__ import annotations

import logging
from typing import Literal

from jp_organizer.config import get_config
from jp_organizer.state.repository import StateRepository

logger = logging.getLogger(__name__)

CLASSIFIER_SCHEMA_VERSION = 2

ExpressionType = Literal["construction", "idiom", "collocation"] | None
PrimaryClass = Literal["word", "mimetic", "construction", "idiom", "collocation", "other"]

# Deck mapping for primary classes
PRIMARY_CLASS_DECKS: dict[PrimaryClass, str] = {
    "word": "Japanese::Vocabulary::Words",
    "mimetic": "Japanese::Vocabulary::Mimetics",
    "construction": "Japanese::Vocabulary::Expressions::Constructions",
    "idiom": "Japanese::Vocabulary::Expressions::Idioms",
    "collocation": "Japanese::Vocabulary::Expressions::Collocations",
    "other": "Japanese::Vocabulary::Other",
}

# Kind tag mapping for primary classes
PRIMARY_CLASS_KIND_TAGS: dict[PrimaryClass, str] = {
    "word": "jp-organizer::kind::word",
    "mimetic": "jp-organizer::kind::mimetic",
    "construction": "jp-organizer::kind::expression::construction",
    "idiom": "jp-organizer::kind::expression::idiom",
    "collocation": "jp-organizer::kind::expression::collocation",
    "other": "jp-organizer::kind::other",
}

# Old tags that should be removed during migration
OLD_MANAGED_KIND_TAGS = {
    "jp-organizer::kind::vocabulary",
    "jp-organizer::mimetic",
    "jp-organizer::expression::construction",
    "jp-organizer::expression::idiom",
    "jp-organizer::expression::collocation",
}


def determine_primary_class(mimetic: bool, expression_type: ExpressionType) -> PrimaryClass:
    """Determine the mutually exclusive primary class.

    Precedence:
        specific expression classification > mimetic > word > other
    """
    if expression_type == "construction":
        return "construction"
    if expression_type == "idiom":
        return "idiom"
    if expression_type == "collocation":
        return "collocation"
    if mimetic:
        return "mimetic"
    return "word"


def deck_for_primary_class(primary_class: PrimaryClass) -> str:
    return PRIMARY_CLASS_DECKS[primary_class]


def kind_tag_for_primary_class(primary_class: PrimaryClass) -> str:
    return PRIMARY_CLASS_KIND_TAGS[primary_class]


class SemanticClassifier:
    def __init__(self, state: StateRepository | None = None) -> None:
        self.state = state or StateRepository()
        self.cfg = get_config()

    def get_cached(self, note_key: str, entry_text: str) -> dict | None:
        cached = self.state.get_semantic(note_key)
        if cached is None:
            return None
        if cached["classifier_schema_version"] != CLASSIFIER_SCHEMA_VERSION:
            return None
        from jp_organizer.state.repository import hash_entry
        if cached["entry_hash"] != hash_entry(entry_text):
            return None
        return cached

    def cache(
        self,
        note_key: str,
        entry_text: str,
        mimetic: bool,
        expression_type: ExpressionType,
        semantic_source: str | None,
    ) -> None:
        self.state.set_semantic(
            note_key, entry_text, mimetic, expression_type, semantic_source, CLASSIFIER_SCHEMA_VERSION
        )

    def invalidate(self, note_key: str) -> None:
        self.state.delete_semantic(note_key)

    def apply_kind_tag(self, primary_class: PrimaryClass) -> list[str]:
        return [kind_tag_for_primary_class(primary_class)]

    def validate(self, data: dict) -> dict:
        if not isinstance(data.get("mimetic"), bool):
            raise ValueError("mimetic must be boolean")
        et = data.get("expression_type")
        if et not in ("construction", "idiom", "collocation", None):
            raise ValueError("expression_type must be construction, idiom, collocation, or null")
        return {
            "id": str(data["id"]),
            "mimetic": data["mimetic"],
            "expression_type": et,
        }
