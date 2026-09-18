from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from jp_organizer.anki.client import AnkiConnectClient
from jp_organizer.anki.repository import AnkiRepository
from jp_organizer.config import Config, get_config, set_config
from jp_organizer.dictionaries.jmdict_indexer import JmdictIndexer
from jp_organizer.dictionaries.jmdict_repository import JmdictRepository
from jp_organizer.dictionaries.kanjidic_indexer import KanjidicIndexer
from jp_organizer.dictionaries.kanjidic_repository import KanjidicRepository
from jp_organizer.organizer.reconciliation import Reconciler
from jp_organizer.organizer.service import OrganizerService
from jp_organizer.state.repository import StateRepository

JMDICT_FIXTURE = Path(__file__).with_name("fixtures") / "JMdict_test.xml"
KANJIDIC_FIXTURE = Path(__file__).with_name("fixtures") / "kanjidic2_test.xml"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path):
    cfg = Config()
    cfg.data_dir = tmp_path / "data"
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.jmdict_index_path = cfg.data_dir / "jmdict.sqlite"
    cfg.kanjidic_index_path = cfg.data_dir / "kanjidic.sqlite"
    cfg.state_db_path = cfg.data_dir / "state.sqlite"
    set_config(cfg)
    JmdictIndexer(xml_path=JMDICT_FIXTURE, db_path=cfg.jmdict_index_path).build(force=True)
    KanjidicIndexer(xml_path=KANJIDIC_FIXTURE, db_path=cfg.kanjidic_index_path).build(force=True)
    yield cfg


@pytest.fixture
def mock_anki_client():
    client = AsyncMock(spec=AnkiConnectClient)
    client.deck_names = AsyncMock(return_value=["Japanese Inbox", "Japanese::Vocabulary", "Japanese::Kanji"])
    client.create_deck = AsyncMock(return_value=1)
    client.find_notes = AsyncMock(return_value=[])
    client.notes_info = AsyncMock(return_value=[])
    client.add_note = AsyncMock(return_value=9999)
    client.update_note_fields = AsyncMock(return_value=None)
    client.add_tags = AsyncMock(return_value=None)
    client.remove_tags = AsyncMock(return_value=None)
    client.delete_notes = AsyncMock(return_value=None)
    client.model_names = AsyncMock(return_value=["Basic"])
    client.create_model = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_anki_repo(mock_anki_client):
    return AnkiRepository(client=mock_anki_client)


async def test_sync_jmdict_resolves_mimetic_no_llm(mock_anki_repo):
    """ぐっすり has on-mim in JMdict test fixture → should resolve without LLM."""
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "ぐっすり", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=None,
        force_reclassify=False,
    )
    assert len(plan.semantic_requests) == 0
    assert len(plan.vocab.create) == 1
    assert plan.vocab.create[0]["entry"] == "ぐっすり"
    assert "jp-organizer::kind::mimetic" in plan.vocab.create[0]["tags"]
    assert "jp-organizer::pos::adverb" in plan.vocab.create[0]["tags"]
    assert plan.vocab.create[0]["target_deck"] == "Japanese::Vocabulary::Mimetics"


async def test_sync_jmdict_resolves_idiom_no_llm(mock_anki_repo):
    """一石二鳥 has id in JMdict test fixture → should resolve without LLM."""
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "一石二鳥", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=None,
        force_reclassify=False,
    )
    assert len(plan.semantic_requests) == 0
    assert len(plan.vocab.create) == 1
    assert "jp-organizer::kind::expression::idiom" in plan.vocab.create[0]["tags"]
    assert plan.vocab.create[0]["target_deck"] == "Japanese::Vocabulary::Expressions::Idioms"


async def test_sync_generic_expression_needs_llm(mock_anki_repo):
    """顔が広い has only exp in JMdict test fixture → needs LLM fallback."""
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "顔が広い", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=None,
        force_reclassify=False,
    )
    assert len(plan.semantic_requests) == 1
    assert plan.semantic_requests[0]["entry"] == "顔が広い"


async def test_sync_creates_vocab_with_llm_fallback(mock_anki_repo):
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "学生", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    assert len(plan.vocab.create) == 1
    assert plan.vocab.create[0]["entry"] == "学生"
    assert "jp-organizer::kind::word" in plan.vocab.create[0]["tags"]
    assert plan.vocab.create[0]["target_deck"] == "Japanese::Vocabulary::Words"


async def test_sync_dry_run(mock_anki_repo):
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "学生", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    result = await reconciler.apply_plan(plan, dry_run=True)
    assert result["vocab"]["created"] == 1
    mock_anki_repo.client.add_note.assert_not_called()


async def test_sync_deletes_removed_source(mock_anki_repo):
    state = StateRepository()
    state.set_mapping(101, 9999, "oldentry", "Japanese Inbox", "JP Organizer Vocabulary")
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[])

    reconciler = Reconciler(anki=mock_anki_repo, state=state)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[],
        force_reclassify=False,
    )
    assert 9999 in plan.vocab.delete


async def test_repeated_sync_no_duplicate(mock_anki_repo):
    source_note = {"noteId": 101, "fields": {"Front": {"value": "学生", "order": 0}}, "tags": [], "modelName": "Basic"}
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[source_note])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan1 = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    await reconciler.apply_plan(plan1)

    # Second sync: managed note exists in leaf deck
    managed = {
        "noteId": 9999,
        "fields": {"Entry": {"value": "学生"}, "SourceNoteId": {"value": "101"}},
        "tags": plan1.vocab.create[0]["tags"],
        "modelName": "JP Organizer Vocabulary",
        "deckName": "Japanese::Vocabulary::Words",
    }

    def mock_find_notes(query: str):
        if '"deck:Japanese::Vocabulary::Words"' in query:
            return [9999]
        if '"deck:Japanese Inbox"' in query:
            return [101]
        return []

    def mock_notes_info(note_ids):
        if 101 in note_ids:
            return [source_note]
        if 9999 in note_ids:
            return [managed]
        return []

    mock_anki_repo.client.find_notes = AsyncMock(side_effect=mock_find_notes)
    mock_anki_repo.client.notes_info = AsyncMock(side_effect=mock_notes_info)

    plan2 = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    assert len(plan2.vocab.create) == 0
    assert len(plan2.vocab.update) == 0
    assert len(plan2.vocab.retag) == 0


async def test_sync_extracts_kanji(mock_anki_repo):
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Front": {"value": "学生", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    assert len(plan.kanji.create) >= 2
    literals = {k["char"] for k in plan.kanji.create}
    assert "学" in literals
    assert "生" in literals


async def test_unmanaged_notes_never_deleted(mock_anki_repo):
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 8888, "fields": {"Entry": {"value": "学生"}}, "tags": [], "modelName": "Basic"}
    ])

    state = StateRepository()
    reconciler = Reconciler(anki=mock_anki_repo, state=state)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[],
        force_reclassify=False,
    )
    assert 8888 not in plan.vocab.delete


async def test_in_place_classify(mock_anki_repo):
    cfg = get_config()
    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[
        {"noteId": 101, "fields": {"Entry": {"value": "学生", "order": 0}}, "tags": [], "modelName": "Basic"}
    ])

    reconciler = Reconciler(anki=mock_anki_repo)
    plan = await reconciler.build_plan(
        source_deck=cfg.vocabulary_deck,
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": None}],
        force_reclassify=False,
    )
    assert len(plan.vocab.retag) == 1
    assert plan.vocab.retag[0]["managed_note_id"] == 101
    assert len(plan.vocab.create) == 0
    assert len(plan.vocab.delete) == 0


async def test_classification_change_moves_card(mock_anki_repo):
    """When primary_class changes, the existing card should be moved, not duplicated."""
    source_note = {"noteId": 101, "fields": {"Front": {"value": "顔が広い", "order": 0}}, "tags": [], "modelName": "Basic"}
    state = StateRepository()
    state.set_mapping(101, 9999, "顔が広い", "Japanese Inbox", "JP Organizer Vocabulary")
    state.set_semantic("Japanese Inbox::101", "顔が広い", False, "idiom", "llm", 2)

    mock_anki_repo.client.find_notes = AsyncMock(return_value=[101])
    mock_anki_repo.client.notes_info = AsyncMock(return_value=[source_note])

    # First sync: classify as idiom
    reconciler = Reconciler(anki=mock_anki_repo, state=state)
    plan = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": "idiom"}],
        force_reclassify=False,
    )
    await reconciler.apply_plan(plan)

    # Now simulate the managed note exists in Words deck but should be in Idioms
    managed = {
        "noteId": 9999,
        "fields": {"Entry": {"value": "顔が広い"}, "SourceNoteId": {"value": "101"}},
        "tags": ["jp-organizer::kind::word", "jp-organizer::pos::other"],
        "modelName": "JP Organizer Vocabulary",
        "deckName": "Japanese::Vocabulary::Words",
    }

    def mock_find_notes(query: str):
        if '"deck:Japanese::Vocabulary::Words"' in query:
            return [9999]
        if '"deck:Japanese Inbox"' in query:
            return [101]
        return []

    def mock_notes_info(note_ids):
        if 101 in note_ids:
            return [source_note]
        if 9999 in note_ids:
            return [managed]
        return []

    mock_anki_repo.client.find_notes = AsyncMock(side_effect=mock_find_notes)
    mock_anki_repo.client.notes_info = AsyncMock(side_effect=mock_notes_info)

    plan2 = await reconciler.build_plan(
        source_deck="Japanese Inbox",
        entry_field=None,
        semantic_classifications=[{"id": "101", "mimetic": False, "expression_type": "idiom"}],
        force_reclassify=False,
    )
    assert len(plan2.vocab.move) == 1
    assert plan2.vocab.move[0]["target_deck"] == "Japanese::Vocabulary::Expressions::Idioms"
    assert len(plan2.vocab.create) == 0
