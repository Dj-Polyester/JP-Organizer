from __future__ import annotations

import json
import logging

import httpx

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)


class AnkiConnectError(Exception):
    pass


class AnkiConnectClient:
    def __init__(self, url: str | None = None, timeout: float | None = None) -> None:
        cfg = get_config()
        self.url = url or cfg.anki_connect_url
        self.timeout = timeout or cfg.anki_connect_timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def request(self, action: str, **params) -> any:
        payload = {"action": action, "version": 6, "params": params}
        cfg = get_config()
        if cfg.anki_connect_key:
            payload["key"] = cfg.anki_connect_key
        try:
            response = await self._client.post(self.url, json=payload)
        except httpx.ConnectError as exc:
            raise AnkiConnectError(f"Cannot connect to AnkiConnect at {self.url}. Is Anki running?") from exc
        except httpx.TimeoutException as exc:
            raise AnkiConnectError(f"AnkiConnect request timed out: {action}") from exc

        if response.status_code != 200:
            raise AnkiConnectError(f"AnkiConnect returned HTTP {response.status_code}")

        data = response.json()
        if data.get("error") is not None:
            raise AnkiConnectError(f"AnkiConnect error: {data['error']}")

        return data["result"]

    async def deck_names(self) -> list[str]:
        return await self.request("deckNames")

    async def create_deck(self, deck: str) -> int:
        return await self.request("createDeck", deck=deck)

    async def find_notes(self, query: str) -> list[int]:
        return await self.request("findNotes", query=query)

    async def notes_info(self, notes: list[int]) -> list[dict]:
        return await self.request("notesInfo", notes=notes)

    async def add_note(self, note: dict) -> int | None:
        return await self.request("addNote", note=note)

    async def update_note_fields(self, note: dict) -> None:
        await self.request("updateNoteFields", note=note)

    async def add_tags(self, notes: list[int], tags: str) -> None:
        await self.request("addTags", notes=notes, tags=tags)

    async def remove_tags(self, notes: list[int], tags: str) -> None:
        await self.request("removeTags", notes=notes, tags=tags)

    async def delete_notes(self, notes: list[int]) -> None:
        await self.request("deleteNotes", notes=notes)

    async def model_names(self) -> list[str]:
        return await self.request("modelNames")

    async def create_model(self, model: dict) -> None:
        await self.request("createModel", **model)

    async def find_cards(self, query: str) -> list[int]:
        return await self.request("findCards", query=query)

    async def multi(self, actions: list[dict]) -> list:
        return await self.request("multi", actions=actions)
