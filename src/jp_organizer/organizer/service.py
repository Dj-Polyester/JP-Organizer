from __future__ import annotations

import logging

from jp_organizer.anki.client import AnkiConnectClient
from jp_organizer.anki.repository import AnkiRepository
from jp_organizer.config import get_config
from jp_organizer.dictionaries.jmdict_indexer import JmdictIndexer
from jp_organizer.dictionaries.jmdict_repository import JmdictRepository
from jp_organizer.dictionaries.kanjidic_indexer import KanjidicIndexer
from jp_organizer.dictionaries.kanjidic_repository import KanjidicRepository
from jp_organizer.models import (
    IndexStatusResult,
    JmdictIndexStatus,
    KanjidicIndexStatus,
    KanjiLookupResult,
    SemanticClassification,
    SyncResult,
    VocabularyLookupResult,
)
from jp_organizer.organizer.jmdict_semantic_mapper import map_semantic
from jp_organizer.organizer.kanji import KanjiExtractor
from jp_organizer.organizer.pos_classifier import pos_tags
from jp_organizer.organizer.reconciliation import Reconciler
from jp_organizer.organizer.semantic import (
    SemanticClassifier,
    deck_for_primary_class,
    determine_primary_class,
    kind_tag_for_primary_class,
)
from jp_organizer.state.repository import StateRepository

logger = logging.getLogger(__name__)


class OrganizerService:
    def __init__(self) -> None:
        self.cfg = get_config()
        self.anki = AnkiRepository()
        self.jmdict = JmdictRepository()
        self.kanjidic = KanjidicRepository()
        self.state = StateRepository()
        self.semantic = SemanticClassifier(self.state)
        self.reconciler = Reconciler(
            anki=self.anki,
            jmdict=self.jmdict,
            kanjidic=self.kanjidic,
            state=self.state,
            semantic=self.semantic,
        )

    async def index_dictionaries(
        self, jmdict_path: str | None = None, kanjidic_path: str | None = None, force: bool = False
    ) -> dict:
        result = {}
        if jmdict_path:
            indexer = JmdictIndexer(xml_path=jmdict_path)
            result["jmdict"] = indexer.build(force=force)
        if kanjidic_path:
            indexer = KanjidicIndexer(xml_path=kanjidic_path)
            result["kanjidic"] = indexer.build(force=force)
        return result

    def index_status(self) -> IndexStatusResult:
        jmdict = self.jmdict.status()
        kanjidic = self.kanjidic.status()
        return IndexStatusResult(
            jmdict=JmdictIndexStatus(**jmdict),
            kanjidic=KanjidicIndexStatus(**kanjidic),
        )

    async def sync(
        self,
        source_deck_name: str,
        entry_field: str | None = None,
        dry_run: bool = False,
        force_semantic_reclassification: bool = False,
        semantic_classifications: list[dict] | None = None,
    ) -> SyncResult:
        if not self.jmdict.is_ready():
            return SyncResult(
                status="error",
                message="JMdict index missing",
                error={
                    "code": "JMDICT_INDEX_MISSING",
                    "required_dictionary": "jmdict",
                    "message": "JMdict SQLite index is missing.",
                    "suggested_action": "Call jp_discover_dictionaries to locate JMdict XML, then call jp_index_dictionaries.",
                },
            )
        if not self.kanjidic.is_ready():
            return SyncResult(
                status="error",
                message="KANJIDIC index missing",
                error={
                    "code": "KANJIDIC_INDEX_MISSING",
                    "required_dictionary": "kanjidic",
                    "message": "KANJIDIC SQLite index is missing.",
                    "suggested_action": "Call jp_discover_dictionaries to locate KANJIDIC XML, then call jp_index_dictionaries.",
                },
            )

        await self.anki.ensure_decks()
        await self.anki.ensure_models()

        plan = await self.reconciler.build_plan(
            source_deck=source_deck_name,
            entry_field=entry_field,
            semantic_classifications=semantic_classifications,
            force_reclassify=force_semantic_reclassification,
        )

        if plan.semantic_requests:
            return SyncResult(
                status="semantic_classification_required",
                requests=plan.semantic_requests,
            )

        result = await self.reconciler.apply_plan(plan, dry_run=dry_run)
        return SyncResult(
            status="ok",
            plan=result,
        )

    async def extract_kanji(self, dry_run: bool = False) -> SyncResult:
        if not self.kanjidic.is_ready():
            return SyncResult(
                status="error",
                message="KANJIDIC index missing",
                error={
                    "code": "KANJIDIC_INDEX_MISSING",
                    "required_dictionary": "kanjidic",
                    "message": "KANJIDIC SQLite index is missing.",
                    "suggested_action": "Locate KANJIDIC XML and call jp_index_dictionaries.",
                },
            )
        await self.anki.ensure_decks()
        await self.anki.ensure_models()

        managed_vocab = await self.anki.get_managed_vocab_notes()
        entries = [self.anki.extract_entry(n) or "" for n in managed_vocab]
        extractor = KanjiExtractor(self.kanjidic)
        desired_kanji = extractor.extract_unique_kanji(entries)
        managed_kanji = await self.anki.get_managed_kanji_notes()
        managed_by_char = {}
        for mk in managed_kanji:
            char = self.anki.extract_entry(mk) or ""
            if char:
                managed_by_char[char] = mk["noteId"]

        plan = {"create": 0, "update": 0, "delete": 0}
        for char in desired_kanji:
            info = self.kanjidic.lookup(char)
            if info is None:
                continue
            meanings = "; ".join(info["meanings"])
            readings = extractor.build_readings_text(info)
            tags = ["jp-organizer::kind::kanji"]
            if char not in managed_by_char:
                if not dry_run:
                    await self.anki.create_kanji_note(char, meanings, readings, tags)
                plan["create"] += 1
            else:
                mk = next((k for k in managed_kanji if k["noteId"] == managed_by_char[char]), None)
                if mk:
                    fields = mk.get("fields", {})
                    cur_meanings = fields.get("Meanings", {}).get("value", "")
                    cur_readings = fields.get("Readings", {}).get("value", "")
                    if cur_meanings != meanings or cur_readings != readings:
                        if not dry_run:
                            await self.anki.update_kanji_note(managed_by_char[char], meanings, readings, tags)
                        plan["update"] += 1

        desired_set = set(desired_kanji)
        delete_ids = [mid for char, mid in managed_by_char.items() if char not in desired_set]
        if delete_ids:
            if not dry_run:
                await self.anki.delete_notes(delete_ids)
            plan["delete"] += len(delete_ids)

        return SyncResult(status="ok", plan={"kanji": plan})

    def lookup_vocabulary(self, entry: str) -> VocabularyLookupResult:
        pos_codes = self.jmdict.lookup(entry)
        pos_tags_list = pos_tags(pos_codes)

        semantic_codes = self.jmdict.lookup_semantic(entry)
        jmdict_semantic = map_semantic(semantic_codes)

        mimetic = False
        expression_type = None
        semantic_source = None

        if jmdict_semantic["classification"] == "mimetic":
            mimetic = True
            semantic_source = "jmdict"
        elif jmdict_semantic["classification"] == "idiom":
            expression_type = "idiom"
            semantic_source = "jmdict"

        # Check cache
        if semantic_source is None:
            for key, cached in self.state.get_all_semantic().items():
                from jp_organizer.state.repository import hash_entry
                if cached.get("entry_hash") == hash_entry(entry):
                    mimetic = cached["mimetic"]
                    expression_type = cached.get("expression_type")
                    semantic_source = cached.get("semantic_source", "llm")
                    break

        primary_class = determine_primary_class(mimetic, expression_type)
        target_deck = deck_for_primary_class(primary_class)
        kind_tag = kind_tag_for_primary_class(primary_class)

        return VocabularyLookupResult(
            entry=entry,
            primary_class=primary_class,
            target_deck=target_deck,
            kind_tag=kind_tag,
            jmdict={
                "found": bool(pos_codes),
                "pos_tags": pos_tags_list,
                "semantic_markers": semantic_codes,
            },
            semantic={
                "mimetic": mimetic,
                "expression_type": expression_type,
                "source": semantic_source,
            } if semantic_source else None,
        )

    def lookup_kanji(self, literal: str) -> KanjiLookupResult:
        info = self.kanjidic.lookup(literal)
        if info is None:
            return KanjiLookupResult(
                found=False,
                entry=literal,
                meanings=[],
                readings={"on": [], "kun": [], "nanori": []},
            )
        return KanjiLookupResult(
            found=True,
            entry=literal,
            meanings=info["meanings"],
            readings=info["readings"],
        )
