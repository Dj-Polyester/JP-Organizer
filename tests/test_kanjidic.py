from pathlib import Path

import pytest

from jp_organizer.dictionaries.kanjidic_indexer import KanjidicIndexer
from jp_organizer.dictionaries.kanjidic_repository import KanjidicRepository

FIXTURE = Path(__file__).with_name("fixtures") / "kanjidic2_test.xml"


@pytest.fixture
def kanjidic_db(tmp_path):
    db = tmp_path / "kanjidic.sqlite"
    indexer = KanjidicIndexer(xml_path=FIXTURE, db_path=db)
    result = indexer.build(force=True)
    assert result["status"] == "ok"
    return db


def test_kanjidic_lookup_literal(kanjidic_db):
    repo = KanjidicRepository(db_path=kanjidic_db)
    info = repo.lookup("日")
    assert info is not None
    assert info["literal"] == "日"


def test_kanjidic_lookup_meanings(kanjidic_db):
    repo = KanjidicRepository(db_path=kanjidic_db)
    info = repo.lookup("本")
    assert info is not None
    assert "book" in info["meanings"]


def test_kanjidic_lookup_readings(kanjidic_db):
    repo = KanjidicRepository(db_path=kanjidic_db)
    info = repo.lookup("食")
    assert info is not None
    assert "ショク" in info["readings"]["on"]
    assert "た.べる" in info["readings"]["kun"]


def test_kanjidic_batch_lookup(kanjidic_db):
    repo = KanjidicRepository(db_path=kanjidic_db)
    result = repo.batch_lookup(["日", "本", "X"])
    assert "日" in result
    assert "本" in result
    assert "X" not in result


def test_kanjidic_status(kanjidic_db):
    repo = KanjidicRepository(db_path=kanjidic_db)
    status = repo.status()
    assert status["present"] is True
    assert status["kanji_count"] == 5
