from __future__ import annotations

import logging

from jp_organizer.anki.client import AnkiConnectClient
from jp_organizer.config import get_config, strip_html

logger = logging.getLogger(__name__)

VOCAB_FIELDS = ["Entry", "SourceDeck", "SourceNoteId"]
KANJI_FIELDS = ["Entry", "Meanings", "Readings"]

VOCAB_TEMPLATE = {
    "modelName": "JP Organizer Vocabulary",
    "inOrderFields": VOCAB_FIELDS,
    "css": ".card { font-family: sans-serif; font-size: 24px; text-align: center; }",
    "cardTemplates": [
        {
            "Name": "Recognition",
            "Front": "{{Entry}}",
            "Back": "{{Entry}}<br><br><small>{{SourceDeck}}</small>",
        }
    ],
}

KANJI_TEMPLATE = {
    "modelName": "JP Organizer Kanji",
    "inOrderFields": KANJI_FIELDS,
    "css": ".card { font-family: sans-serif; font-size: 36px; text-align: center; }",
    "cardTemplates": [
        {
            "Name": "Recognition",
            "Front": "{{Entry}}",
            "Back": "{{Entry}}<br><br>{{Meanings}}<br><br>{{Readings}}",
        }
    ],
}

KIND_TAG_KANJI = "jp-organizer::kind::kanji"

# All managed tag prefixes that the organizer controls
MANAGED_TAG_PREFIXES = [
    "jp-organizer::pos::",
    "jp-organizer::kind::",
    "jp-organizer::mimetic",
    "jp-organizer::expression::",
]

# Vocabulary leaf decks
VOCAB_LEAF_DECKS = [
    "Japanese::Vocabulary::Words",
    "Japanese::Vocabulary::Mimetics",
    "Japanese::Vocabulary::Expressions::Constructions",
    "Japanese::Vocabulary::Expressions::Idioms",
    "Japanese::Vocabulary::Expressions::Collocations",
    "Japanese::Vocabulary::Other",
]


class AnkiRepository:
    def __init__(self, client: AnkiConnectClient | None = None) -> None:
        self.client = client or AnkiConnectClient()
        self.cfg = get_config()

    async def ensure_decks(self) -> None:
        decks = await self.client.deck_names()
        all_decks = [self.cfg.vocabulary_deck, self.cfg.expressions_deck] + VOCAB_LEAF_DECKS + [self.cfg.kanji_deck]
        for deck in all_decks:
            if deck not in decks:
                logger.info("Creating deck: %s", deck)
                await self.client.create_deck(deck=deck)

    async def ensure_models(self) -> None:
        models = await self.client.model_names()
        if self.cfg.vocabulary_model not in models:
            logger.info("Creating model: %s", self.cfg.vocabulary_model)
            await self.client.create_model(model=VOCAB_TEMPLATE)
        if self.cfg.kanji_model not in models:
            logger.info("Creating model: %s", self.cfg.kanji_model)
            await self.client.create_model(model=KANJI_TEMPLATE)

    async def get_source_notes(self, source_deck: str) -> list[dict]:
        note_ids = await self.client.find_notes(f'"deck:{source_deck}"')
        if not note_ids:
            return []
        return await self.client.notes_info(note_ids)

    def extract_entry(self, note: dict, entry_field: str | None = None) -> str | None:
        fields = note.get("fields", {})
        if entry_field:
            val = fields.get(entry_field, {}).get("value", "")
            return strip_html(val) if val else None
        for name in ["Expression", "Word", "Front", "Back", "Vocabulary", "Japanese", "Entry"]:
            val = fields.get(name, {}).get("value", "")
            text = strip_html(val)
            if text:
                return text
        for fld in fields.values():
            text = strip_html(fld.get("value", ""))
            if text:
                return text
        return None

    async def create_vocab_note(self, entry: str, source_deck: str, source_note_id: int, tags: list[str], target_deck: str | None = None) -> int:
        note = {
            "deckName": target_deck or self.cfg.words_deck,
            "modelName": self.cfg.vocabulary_model,
            "fields": {
                "Entry": entry,
                "SourceDeck": source_deck,
                "SourceNoteId": str(source_note_id),
            },
            "tags": tags,
            "options": {
                "allowDuplicate": True,
                "duplicateScope": "deck",
            },
        }
        result = await self.client.add_note(note=note)
        if result is None:
            raise RuntimeError(f"Failed to create vocabulary note for {entry}")
        return result

    async def update_vocab_note(self, note_id: int, entry: str, tags: list[str]) -> None:
        await self.client.update_note_fields(
            note={
                "id": note_id,
                "fields": {"Entry": entry},
                "tags": tags,
            }
        )

    async def move_note_to_deck(self, note_id: int, deck: str) -> None:
        """Move a note's cards to a different deck."""
        card_ids = await self.client.find_cards(f"nid:{note_id}")
        if card_ids:
            await self.client.multi([
                {"action": "changeDeck", "params": {"cards": card_ids, "deck": deck}}
            ])

    async def create_kanji_note(self, entry: str, meanings: str, readings: str, tags: list[str]) -> int:
        note = {
            "deckName": self.cfg.kanji_deck,
            "modelName": self.cfg.kanji_model,
            "fields": {
                "Entry": entry,
                "Meanings": meanings,
                "Readings": readings,
            },
            "tags": tags,
        }
        result = await self.client.add_note(note=note)
        if result is None:
            raise RuntimeError(f"Failed to create kanji note for {entry}")
        return result

    async def update_kanji_note(self, note_id: int, meanings: str, readings: str, tags: list[str]) -> None:
        await self.client.update_note_fields(
            note={
                "id": note_id,
                "fields": {
                    "Meanings": meanings,
                    "Readings": readings,
                },
                "tags": tags,
            }
        )

    async def delete_notes(self, note_ids: list[int]) -> None:
        if note_ids:
            await self.client.delete_notes(notes=note_ids)

    async def get_managed_vocab_notes(self) -> list[dict]:
        """Get all managed vocab notes across all vocabulary leaf decks."""
        all_notes = []
        for deck in VOCAB_LEAF_DECKS:
            query = f'"deck:{deck}" "note:{self.cfg.vocabulary_model}"'
            note_ids = await self.client.find_notes(query)
            if note_ids:
                all_notes.extend(await self.client.notes_info(note_ids))
        return all_notes

    async def get_all_vocab_notes(self) -> list[dict]:
        """Get all notes under Japanese::Vocabulary (including subdecks)."""
        query = f'"deck:{self.cfg.vocabulary_deck}"'
        note_ids = await self.client.find_notes(query)
        if not note_ids:
            return []
        return await self.client.notes_info(note_ids)

    async def get_managed_kanji_notes(self) -> list[dict]:
        query = f'"deck:{self.cfg.kanji_deck}" "note:{self.cfg.kanji_model}"'
        note_ids = await self.client.find_notes(query)
        if not note_ids:
            return []
        return await self.client.notes_info(note_ids)

    async def replace_tags(self, note_id: int, new_tags: list[str]) -> None:
        info = await self.client.notes_info([note_id])
        if not info:
            return
        current = info[0].get("tags", [])
        # Remove all old managed tags
        preserved = [t for t in current if not any(t.startswith(p) for p in MANAGED_TAG_PREFIXES)]
        final = list(dict.fromkeys(preserved + new_tags))
        add = [t for t in final if t not in current]
        remove = [t for t in current if t not in final]
        if add:
            await self.client.add_tags(notes=[note_id], tags=" ".join(add))
        if remove:
            await self.client.remove_tags(notes=[note_id], tags=" ".join(remove))
