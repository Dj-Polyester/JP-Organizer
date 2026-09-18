from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jp_organizer.anki.repository import KIND_TAG_KANJI, AnkiRepository, VOCAB_LEAF_DECKS
from jp_organizer.config import get_config
from jp_organizer.dictionaries.jmdict_repository import JmdictRepository
from jp_organizer.dictionaries.kanjidic_repository import KanjidicRepository
from jp_organizer.organizer.jmdict_semantic_mapper import map_semantic
from jp_organizer.organizer.kanji import KanjiExtractor
from jp_organizer.organizer.pos_classifier import pos_tags
from jp_organizer.organizer.semantic import (
    SemanticClassifier,
    deck_for_primary_class,
    determine_primary_class,
    kind_tag_for_primary_class,
)
from jp_organizer.state.repository import StateRepository

logger = logging.getLogger(__name__)


@dataclass
class VocabPlan:
    create: list[dict] = field(default_factory=list)
    update: list[dict] = field(default_factory=list)
    move: list[dict] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)
    retag: list[dict] = field(default_factory=list)


@dataclass
class KanjiPlan:
    create: list[dict] = field(default_factory=list)
    update: list[dict] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)


@dataclass
class ReconciliationPlan:
    vocab: VocabPlan = field(default_factory=VocabPlan)
    kanji: KanjiPlan = field(default_factory=KanjiPlan)
    semantic_requests: list[dict] = field(default_factory=list)


class Reconciler:
    def __init__(
        self,
        anki: AnkiRepository | None = None,
        jmdict: JmdictRepository | None = None,
        kanjidic: KanjidicRepository | None = None,
        state: StateRepository | None = None,
        semantic: SemanticClassifier | None = None,
        kanji_extractor: KanjiExtractor | None = None,
    ) -> None:
        self.anki = anki or AnkiRepository()
        self.jmdict = jmdict or JmdictRepository()
        self.kanjidic = kanjidic or KanjidicRepository()
        self.state = state or StateRepository()
        self.semantic = semantic or SemanticClassifier(self.state)
        self.kanji_extractor = kanji_extractor or KanjiExtractor(self.kanjidic)
        self.cfg = get_config()

    async def build_plan(
        self,
        source_deck: str,
        entry_field: str | None,
        semantic_classifications: list[dict] | None,
        force_reclassify: bool,
    ) -> ReconciliationPlan:
        plan = ReconciliationPlan()
        in_place = source_deck == self.cfg.vocabulary_deck

        source_notes = await self.anki.get_source_notes(source_deck)
        source_entries: dict[int, str] = {}
        ambiguous: list[int] = []
        for note in source_notes:
            note_id = note["noteId"]
            entry = self.anki.extract_entry(note, entry_field)
            if entry is None:
                ambiguous.append(note_id)
                continue
            source_entries[note_id] = entry

        if ambiguous:
            logger.warning("Could not determine entry for source notes: %s", ambiguous)

        if in_place:
            managed_vocab = await self.anki.get_all_vocab_notes()
        else:
            managed_vocab = await self.anki.get_managed_vocab_notes()
        managed_by_id: dict[int, dict] = {n["noteId"]: n for n in managed_vocab}
        managed_by_source: dict[int, int] = {}
        for m in managed_vocab:
            fields = m.get("fields", {})
            sid = fields.get("SourceNoteId", {}).get("value", "")
            try:
                managed_by_source[int(sid)] = m["noteId"]
            except ValueError:
                pass

        existing_mappings = {m["source_note_id"]: m for m in self.state.all_mappings()}

        semantic_input: dict[str, dict] = {}
        if semantic_classifications:
            for sc in semantic_classifications:
                validated = self.semantic.validate(sc)
                semantic_input[validated["id"]] = validated

        desired_vocab: dict[int, dict] = {}
        for source_id, entry in source_entries.items():
            note_key = f"{source_deck}::{source_id}"
            pos_codes = self.jmdict.lookup(entry)
            pos_tags_list = pos_tags(pos_codes)

            # JMdict-first semantic classification
            pos_codes = self.jmdict.lookup(entry)
            semantic_codes = self.jmdict.lookup_semantic(entry)
            jmdict_semantic = map_semantic(semantic_codes, pos_codes)

            mimetic = False
            expression_type = None
            semantic_source = None

            cached = None
            if not force_reclassify:
                cached = self.semantic.get_cached(note_key, entry)

            if jmdict_semantic["classification"] == "mimetic":
                mimetic = True
                expression_type = None
                semantic_source = "jmdict"
                self.semantic.cache(note_key, entry, True, None, "jmdict")
            elif jmdict_semantic["classification"] == "idiom":
                mimetic = False
                expression_type = "idiom"
                semantic_source = "jmdict"
                self.semantic.cache(note_key, entry, False, "idiom", "jmdict")
            elif jmdict_semantic["classification"] == "expression":
                # Generic expression - needs LLM fallback for subtype
                if cached is None and semantic_input:
                    cached = semantic_input.get(str(source_id))
                    if cached:
                        self.semantic.cache(
                            note_key, entry, cached["mimetic"], cached["expression_type"], "llm"
                        )

                if cached is not None:
                    mimetic = cached["mimetic"]
                    expression_type = cached.get("expression_type")
                    semantic_source = cached.get("semantic_source", "llm")
                else:
                    plan.semantic_requests.append({"id": str(source_id), "entry": entry})
                    continue
            else:
                # Check cached or LLM input for normal lexical items
                if cached is None and semantic_input:
                    cached = semantic_input.get(str(source_id))
                    if cached:
                        self.semantic.cache(
                            note_key, entry, cached["mimetic"], cached["expression_type"], "llm"
                        )

                if cached is not None:
                    mimetic = cached["mimetic"]
                    expression_type = cached.get("expression_type")
                    semantic_source = cached.get("semantic_source", "llm")
                # else: normal lexical item → word

            if plan.semantic_requests:
                # Continue to collect all unresolved entries before returning
                continue

            primary_class = determine_primary_class(mimetic, expression_type)
            target_deck = deck_for_primary_class(primary_class)
            kind_tag = kind_tag_for_primary_class(primary_class)
            tags = [kind_tag] + pos_tags_list

            desired_vocab[source_id] = {
                "entry": entry,
                "tags": tags,
                "primary_class": primary_class,
                "target_deck": target_deck,
                "semantic_source": semantic_source,
            }

        if plan.semantic_requests:
            return plan

        for source_id, desired in desired_vocab.items():
            if in_place:
                managed = managed_by_id.get(source_id)
                if managed is None:
                    plan.vocab.retag.append({
                        "managed_note_id": source_id,
                        "tags": desired["tags"],
                    })
                else:
                    current_tags = managed.get("tags", [])
                    if set(current_tags) != set(desired["tags"]):
                        plan.vocab.retag.append({
                            "managed_note_id": source_id,
                            "tags": desired["tags"],
                        })
                model_name = managed.get("modelName", "") if managed else self.cfg.vocabulary_model
                self.state.set_mapping(
                    source_note_id=source_id,
                    managed_note_id=source_id,
                    entry_text=desired["entry"],
                    source_deck=source_deck,
                    model_name=model_name,
                )
                continue

            mapping = existing_mappings.get(source_id)
            managed_id = managed_by_source.get(source_id)
            if managed_id is None and mapping is not None:
                managed_id = mapping["managed_note_id"]
                managed_by_source[source_id] = managed_id

            if managed_id is None:
                plan.vocab.create.append({
                    "source_note_id": source_id,
                    "source_deck": source_deck,
                    "entry": desired["entry"],
                    "tags": desired["tags"],
                    "target_deck": desired["target_deck"],
                })
            else:
                managed = managed_by_id.get(managed_id)
                if managed is None:
                    plan.vocab.create.append({
                        "source_note_id": source_id,
                        "source_deck": source_deck,
                        "entry": desired["entry"],
                        "tags": desired["tags"],
                        "target_deck": desired["target_deck"],
                    })
                    continue

                current_entry = self.anki.extract_entry(managed) or ""
                current_tags = managed.get("tags", [])
                desired_tags = desired["tags"]
                current_deck = managed.get("deckName", "")
                desired_deck = desired["target_deck"]

                needs_move = current_deck != desired_deck and current_deck in VOCAB_LEAF_DECKS
                needs_update = current_entry != desired["entry"]
                needs_retag = set(current_tags) != set(desired_tags)

                if needs_update:
                    plan.vocab.update.append({
                        "managed_note_id": managed_id,
                        "entry": desired["entry"],
                        "tags": desired_tags,
                        "target_deck": desired_deck,
                    })
                elif needs_move:
                    plan.vocab.move.append({
                        "managed_note_id": managed_id,
                        "target_deck": desired_deck,
                        "tags": desired_tags,
                    })
                elif needs_retag:
                    plan.vocab.retag.append({
                        "managed_note_id": managed_id,
                        "tags": desired_tags,
                    })

                self.state.set_mapping(
                    source_note_id=source_id,
                    managed_note_id=managed_id,
                    entry_text=desired["entry"],
                    source_deck=source_deck,
                    model_name=self.cfg.vocabulary_model,
                )

        source_ids_set = set(source_entries.keys())
        for source_id, mapping in existing_mappings.items():
            if mapping["source_deck"] != source_deck:
                continue
            if source_id not in source_ids_set:
                managed_id = mapping["managed_note_id"]
                if not in_place:
                    plan.vocab.delete.append(managed_id)
                self.state.delete_mapping(source_id)
                self.state.delete_semantic(f"{source_deck}::{source_id}")

        vocab_entries = [desired["entry"] for desired in desired_vocab.values()]
        desired_kanji = self.kanji_extractor.extract_unique_kanji(vocab_entries)
        managed_kanji = await self.anki.get_managed_kanji_notes()
        managed_kanji_by_char: dict[str, int] = {}
        for mk in managed_kanji:
            char = self.anki.extract_entry(mk) or ""
            if char:
                managed_kanji_by_char[char] = mk["noteId"]

        for char in desired_kanji:
            info = self.kanjidic.lookup(char)
            if info is None:
                continue
            meanings = "; ".join(info["meanings"])
            readings = self.kanji_extractor.build_readings_text(info)
            tags = [KIND_TAG_KANJI]
            if char not in managed_kanji_by_char:
                plan.kanji.create.append({
                    "char": char,
                    "meanings": meanings,
                    "readings": readings,
                    "tags": tags,
                })
            else:
                mk = next((k for k in managed_kanji if k["noteId"] == managed_kanji_by_char[char]), None)
                if mk:
                    fields = mk.get("fields", {})
                    cur_meanings = fields.get("Meanings", {}).get("value", "")
                    cur_readings = fields.get("Readings", {}).get("value", "")
                    if cur_meanings != meanings or cur_readings != readings:
                        plan.kanji.update.append({
                            "managed_note_id": managed_kanji_by_char[char],
                            "meanings": meanings,
                            "readings": readings,
                            "tags": tags,
                        })

        desired_kanji_set = set(desired_kanji)
        for char, managed_id in managed_kanji_by_char.items():
            if char not in desired_kanji_set:
                plan.kanji.delete.append(managed_id)

        return plan

    async def apply_plan(self, plan: ReconciliationPlan, dry_run: bool = False) -> dict:
        result = {
            "vocab": {"created": 0, "updated": 0, "moved": 0, "deleted": 0, "retagged": 0},
            "kanji": {"created": 0, "updated": 0, "deleted": 0},
        }
        if dry_run:
            result["vocab"]["created"] = len(plan.vocab.create)
            result["vocab"]["updated"] = len(plan.vocab.update)
            result["vocab"]["moved"] = len(plan.vocab.move)
            result["vocab"]["deleted"] = len(plan.vocab.delete)
            result["vocab"]["retagged"] = len(plan.vocab.retag)
            result["kanji"]["created"] = len(plan.kanji.create)
            result["kanji"]["updated"] = len(plan.kanji.update)
            result["kanji"]["deleted"] = len(plan.kanji.delete)
            return result

        for item in plan.vocab.create:
            managed_id = await self.anki.create_vocab_note(
                entry=item["entry"],
                source_deck=item.get("source_deck", ""),
                source_note_id=item["source_note_id"],
                tags=item["tags"],
                target_deck=item.get("target_deck"),
            )
            self.state.set_mapping(
                source_note_id=item["source_note_id"],
                managed_note_id=managed_id,
                entry_text=item["entry"],
                source_deck=item.get("source_deck", ""),
                model_name=self.cfg.vocabulary_model,
            )
            result["vocab"]["created"] += 1

        for item in plan.vocab.update:
            await self.anki.update_vocab_note(
                note_id=item["managed_note_id"],
                entry=item["entry"],
                tags=item["tags"],
            )
            if item.get("target_deck"):
                await self.anki.move_note_to_deck(item["managed_note_id"], item["target_deck"])
            result["vocab"]["updated"] += 1

        for item in plan.vocab.move:
            await self.anki.move_note_to_deck(item["managed_note_id"], item["target_deck"])
            await self.anki.replace_tags(item["managed_note_id"], item["tags"])
            result["vocab"]["moved"] += 1

        for item in plan.vocab.retag:
            await self.anki.replace_tags(item["managed_note_id"], item["tags"])
            result["vocab"]["retagged"] += 1

        if plan.vocab.delete:
            await self.anki.delete_notes(plan.vocab.delete)
            result["vocab"]["deleted"] += len(plan.vocab.delete)

        for item in plan.kanji.create:
            await self.anki.create_kanji_note(
                entry=item["char"],
                meanings=item["meanings"],
                readings=item["readings"],
                tags=item["tags"],
            )
            result["kanji"]["created"] += 1

        for item in plan.kanji.update:
            await self.anki.update_kanji_note(
                note_id=item["managed_note_id"],
                meanings=item["meanings"],
                readings=item["readings"],
                tags=item["tags"],
            )
            result["kanji"]["updated"] += 1

        if plan.kanji.delete:
            await self.anki.delete_notes(plan.kanji.delete)
            result["kanji"]["deleted"] += len(plan.kanji.delete)

        return result
