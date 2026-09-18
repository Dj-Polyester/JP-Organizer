import pytest

from jp_organizer.organizer.pos_classifier import classify_pos, pos_tags


def test_classify_noun():
    assert classify_pos(["n"]) == ["noun"]
    assert classify_pos(["n", "n-suf"]) == ["noun"]


def test_classify_verb():
    assert classify_pos(["v5r"]) == ["verb"]
    assert classify_pos(["v1", "vs"]) == ["verb"]


def test_classify_adjective():
    assert classify_pos(["adj-i"]) == ["adjective"]
    assert classify_pos(["adj-na"]) == ["adjective"]


def test_classify_adverb():
    assert classify_pos(["adv"]) == ["adverb"]
    assert classify_pos(["adv-to"]) == ["adverb"]


def test_classify_other():
    assert classify_pos(["exp"]) == ["other"]
    assert classify_pos(["int"]) == ["other"]


def test_classify_multi():
    assert classify_pos(["n", "v5r"]) == ["noun", "verb"]


def test_classify_empty():
    assert classify_pos([]) == ["other"]


def test_pos_tags():
    assert pos_tags(["n"]) == ["jp-organizer::pos::noun"]
    assert pos_tags(["v5r", "adj-i"]) == [
        "jp-organizer::pos::adjective",
        "jp-organizer::pos::verb",
    ]
