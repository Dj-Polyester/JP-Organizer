import pytest

from jp_organizer.organizer.semantic import (
    SemanticClassifier,
    deck_for_primary_class,
    determine_primary_class,
    kind_tag_for_primary_class,
)
from jp_organizer.state.repository import StateRepository


@pytest.fixture
def semantic(tmp_path):
    state = StateRepository(db_path=tmp_path / "state.sqlite")
    return SemanticClassifier(state)


def test_cache_and_retrieve(semantic):
    semantic.cache("key1", "entry", True, "idiom", "llm")
    cached = semantic.get_cached("key1", "entry")
    assert cached is not None
    assert cached["mimetic"] is True
    assert cached["expression_type"] == "idiom"
    assert cached["semantic_source"] == "llm"


def test_cache_miss(semantic):
    cached = semantic.get_cached("missing", "entry")
    assert cached is None


def test_invalidate_on_hash_change(semantic):
    semantic.cache("key1", "entry", False, None, "jmdict")
    cached = semantic.get_cached("key1", "changed")
    assert cached is None


def test_apply_kind_tag(semantic):
    assert semantic.apply_kind_tag("word") == ["jp-organizer::kind::word"]
    assert semantic.apply_kind_tag("mimetic") == ["jp-organizer::kind::mimetic"]
    assert semantic.apply_kind_tag("idiom") == ["jp-organizer::kind::expression::idiom"]


def test_validate_ok(semantic):
    data = {"id": "1", "mimetic": False, "expression_type": "idiom"}
    result = semantic.validate(data)
    assert result["mimetic"] is False
    assert result["expression_type"] == "idiom"


def test_validate_null_expression(semantic):
    data = {"id": "1", "mimetic": True, "expression_type": None}
    result = semantic.validate(data)
    assert result["expression_type"] is None


def test_validate_invalid_expression_type(semantic):
    with pytest.raises(ValueError):
        semantic.validate({"id": "1", "mimetic": False, "expression_type": "invalid"})


def test_validate_missing_mimetic(semantic):
    with pytest.raises(ValueError):
        semantic.validate({"id": "1", "expression_type": None})


def test_determine_primary_class():
    assert determine_primary_class(False, "construction") == "construction"
    assert determine_primary_class(False, "idiom") == "idiom"
    assert determine_primary_class(False, "collocation") == "collocation"
    assert determine_primary_class(True, None) == "mimetic"
    assert determine_primary_class(False, None) == "word"


def test_deck_for_primary_class():
    assert deck_for_primary_class("word") == "Japanese::Vocabulary::Words"
    assert deck_for_primary_class("mimetic") == "Japanese::Vocabulary::Mimetics"
    assert deck_for_primary_class("idiom") == "Japanese::Vocabulary::Expressions::Idioms"


def test_kind_tag_for_primary_class():
    assert kind_tag_for_primary_class("word") == "jp-organizer::kind::word"
    assert kind_tag_for_primary_class("mimetic") == "jp-organizer::kind::mimetic"
    assert kind_tag_for_primary_class("collocation") == "jp-organizer::kind::expression::collocation"
