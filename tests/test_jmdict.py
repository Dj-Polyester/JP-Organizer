from pathlib import Path

import pytest

from jp_organizer.config import Config, get_config, set_config
from jp_organizer.dictionaries.jmdict_indexer import JmdictIndexer
from jp_organizer.dictionaries.jmdict_repository import JmdictRepository

JMDICT_FIXTURE = Path(__file__).with_name("fixtures") / "JMdict_test.xml"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path):
    cfg = Config()
    cfg.data_dir = tmp_path / "data"
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.jmdict_index_path = cfg.data_dir / "jmdict.sqlite"
    set_config(cfg)
    JmdictIndexer(xml_path=JMDICT_FIXTURE, db_path=cfg.jmdict_index_path).build(force=True)
    yield cfg


def test_jmdict_index_creates_tables():
    repo = JmdictRepository()
    assert repo.is_ready()
    status = repo.status()
    assert status["schema_version"] == 2
    assert status["entry_count"] > 0


def test_jmdict_lookup_noun():
    repo = JmdictRepository()
    codes = repo.lookup("学生")
    assert "n" in codes


def test_jmdict_lookup_verb():
    repo = JmdictRepository()
    codes = repo.lookup("食べる")
    assert "v5r" in codes


def test_jmdict_lookup_adjective():
    repo = JmdictRepository()
    codes = repo.lookup("きれい")
    assert "adj-i" in codes


def test_jmdict_lookup_adverb():
    repo = JmdictRepository()
    codes = repo.lookup("ゆっくり")
    assert "adv" in codes


def test_jmdict_lookup_multi_reading():
    repo = JmdictRepository()
    codes = repo.lookup("日本")
    assert "n" in codes


def test_jmdict_lookup_unmatched():
    repo = JmdictRepository()
    codes = repo.lookup("存在しない")
    assert codes == []


def test_jmdict_lookup_semantic_mimetic():
    repo = JmdictRepository()
    codes = repo.lookup_semantic("ぐっすり")
    assert "on-mim" in codes


def test_jmdict_lookup_semantic_idiom():
    repo = JmdictRepository()
    codes = repo.lookup_semantic("一石二鳥")
    assert "id" in codes


def test_jmdict_lookup_semantic_expression():
    repo = JmdictRepository()
    # exp is a POS code, not a misc/semantic code
    semantic_codes = repo.lookup_semantic("顔が広い")
    assert semantic_codes == []
    pos_codes = repo.lookup("顔が広い")
    assert "exp" in pos_codes


def test_jmdict_status():
    repo = JmdictRepository()
    status = repo.status()
    assert status["present"] is True
    assert status["entry_count"] == 11
