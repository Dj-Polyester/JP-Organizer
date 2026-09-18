from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import MCPServer
from pydantic import BaseModel

from jp_organizer.config import get_config
from jp_organizer.dictionaries.discovery import discover_dictionaries
from jp_organizer.organizer.service import OrganizerService

logger = logging.getLogger(__name__)

mcp = MCPServer("jp-organizer")
service = OrganizerService()


class IndexDictionariesInput(BaseModel):
    jmdict_path: str | None = None
    kanjidic_path: str | None = None
    force: bool = False


class IndexStatusInput(BaseModel):
    pass


class SyncInput(BaseModel):
    source_deck_name: str
    entry_field: str | None = None
    dry_run: bool = False
    force_semantic_reclassification: bool = False
    semantic_classifications: list[dict] | None = None


class ExtractKanjiInput(BaseModel):
    dry_run: bool = False


class LookupVocabularyInput(BaseModel):
    entry: str


class LookupKanjiInput(BaseModel):
    literal: str


@mcp.tool()
async def jp_index_dictionaries(
    jmdict_path: str | None = None,
    kanjidic_path: str | None = None,
    force: bool = False,
) -> str:
    """Index JMdict and/or KANJIDIC XML files into SQLite for fast lookup.

    Parameters:
      jmdict_path: Absolute path to a JMdict XML file (e.g. /home/user/JMdict_e.xml).
      kanjidic_path: Absolute path to a KANJIDIC XML file (e.g. /home/user/kanjidic2.xml).
      force: If True, rebuild indexes even if they already exist.

    Returns a JSON object like:
      {"jmdict": {"status": "ok", "entries": 211311},
       "kanjidic": {"status": "ok", "kanji": 13108}}

    If you do not know the paths, call jp_discover_dictionaries first.
    """
    result = await service.index_dictionaries(
        jmdict_path=jmdict_path,
        kanjidic_path=kanjidic_path,
        force=force,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jp_index_status() -> str:
    """Check whether JMdict and KANJIDIC SQLite indexes are ready.

    Returns a JSON object like:
      {"jmdict": {"ready": true, "entries": 211311},
       "kanjidic": {"ready": true, "kanji": 13108}}

    If a dictionary is not ready, call jp_discover_dictionaries to locate
    the XML file, then call jp_index_dictionaries to build the index.
    """
    status = service.index_status()
    return json.dumps(status.model_dump(), ensure_ascii=False)


@mcp.tool()
async def jp_sync(
    source_deck_name: str,
    entry_field: str | None = None,
    dry_run: bool = False,
    force_semantic_reclassification: bool = False,
    semantic_classifications: list[dict] | None = None,
) -> str:
    """Synchronize a source deck with Japanese::Vocabulary and Japanese::Kanji.

    This tool is idempotent and safe to call multiple times.

    Parameters:
      source_deck_name: Name of the source Anki deck (e.g. "JP Words").
      entry_field: The field name that contains the Japanese word. Common values
        are "Entry", "Expression", "Word", "Front", "Back", "Vocabulary",
        "Japanese". If omitted, the server tries these in order.
      dry_run: If True, preview the plan without creating/updating any notes.
      force_semantic_reclassification: If True, ignore cached classifications
        and reclassify every entry.
      semantic_classifications: Only needed when the server asks for them.
        A list of dicts, one per entry, with exactly these keys:
          - "id": string, the note ID from the requests list
          - "mimetic": boolean, true for sound-symbolic/onomatopoeic words
          - "expression_type": null or one of "construction", "idiom", "collocation"

    Two-phase handshake (only needed on first sync or when forcing reclassification):

      Phase 1 — call without semantic_classifications:
        jp_sync(source_deck_name="JP Words")

      If the response status is "semantic_classification_required", the server
      returns a JSON object with a "requests" array like:
        {"status": "semantic_classification_required",
         "requests": [
           {"id": "1234567890", "entry": "悠長"},
           {"id": "1234567891", "entry": "だらだら"},
           ...
         ]}

      Phase 2 — classify the entries and call again:
        For each request, decide:
          mimetic: true if the word is sound-symbolic (e.g. だらだら, ふわふわ)
          expression_type: use "idiom" for set phrases (e.g. 一石二鳥),
                           "construction" for grammatical patterns (e.g. か否か),
                           "collocation" for common word pairs (e.g. 気を使う),
                           null for ordinary lexical words.

        Then call:
        jp_sync(
          source_deck_name="JP Words",
          semantic_classifications=[
            {"id": "1234567890", "mimetic": false, "expression_type": null},
            {"id": "1234567891", "mimetic": true, "expression_type": null},
            ...
          ]
        )

      The server will then create/update notes in Japanese::Vocabulary leaf decks
      and Japanese::Kanji, tag them with POS (e.g. jp-organizer::pos::noun) and
      kind tags (e.g. jp-organizer::kind::word, jp-organizer::kind::mimetic).
      and return:
        {"status": "ok",
         "plan": {"vocab": {"created": 1217, "updated": 0, "deleted": 0},
                  "kanji": {"created": 1563, "updated": 0, "deleted": 0}}}

    On subsequent syncs, cached classifications are reused automatically.
    """
    result = await service.sync(
        source_deck_name=source_deck_name,
        entry_field=entry_field,
        dry_run=dry_run,
        force_semantic_reclassification=force_semantic_reclassification,
        semantic_classifications=semantic_classifications,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


@mcp.tool()
async def jp_extract_kanji(dry_run: bool = False) -> str:
    """Recalculate Japanese::Kanji from the current vocabulary collection.

    Scans all managed vocabulary notes, extracts unique kanji, and creates
    or updates kanji notes in Japanese::Kanji with readings and meanings
    from KANJIDIC.

    This is idempotent and safe to call repeatedly. It is useful if the
    initial sync timed out before kanji extraction completed.

    Parameters:
      dry_run: If True, preview the plan without creating/updating any notes.

    Returns a JSON object like:
      {"status": "ok", "plan": {"kanji": {"created": 1563, "updated": 0, "deleted": 0}}}
    """
    result = await service.extract_kanji(dry_run=dry_run)
    return json.dumps(result.model_dump(), ensure_ascii=False)


@mcp.tool()
async def jp_lookup_vocabulary(entry: str) -> str:
    """Look up POS and semantic classification for a vocabulary entry.

    Parameters:
      entry: The Japanese word to look up (e.g. "愉快").

    Returns a JSON object like:
      {"entry": "愉快", "jmdict": {"found": true, "pos_tags": ["adjective", "noun"]},
       "semantic": {"classified": true, "mimetic": false, "expression_type": null}}

    If the word is not in JMdict, pos_tags will be empty.
    If no cached semantic classification exists, the "semantic" field will be null.
    """
    result = service.lookup_vocabulary(entry)
    return json.dumps(result.model_dump(), ensure_ascii=False)


@mcp.tool()
async def jp_lookup_kanji(literal: str) -> str:
    """Look up KANJIDIC information for a kanji character.

    Parameters:
      literal: A single kanji character (e.g. "漢").

    Returns a JSON object like:
      {"found": true, "entry": "漢", "meanings": ["Sino-", "China"],
       "readings": {"on": ["カン"], "kun": [], "nanori": ["はる", "はな"]},
       "jmdict": {"found": false, "pos_tags": []}}

    If the kanji is not in KANJIDIC, "found" will be false.
    """
    result = service.lookup_kanji(literal)
    return json.dumps(result.model_dump(), ensure_ascii=False)


@mcp.tool()
async def jp_discover_dictionaries() -> str:
    """Discover JMdict and KANJIDIC XML files on the system using ripgrep.

    Searches the filesystem for JMdict_e*.xml and kanjidic2*.xml files,
    verifies their XML root elements, and returns discovered paths.

    Returns a JSON object like:
      {"jmdict": {"candidates": ["/path/to/JMdict_e.xml"],
                   "verified": ["/path/to/JMdict_e.xml"]},
       "kanjidic": {"candidates": ["/path/to/kanjidic2.xml"],
                    "verified": ["/path/to/kanjidic2.xml"]}}

    Use the verified paths with jp_index_dictionaries to build the indexes.
    Requires ripgrep (rg) to be installed on the system.
    """
    result = discover_dictionaries()
    return json.dumps(result, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="jp-organizer MCP server")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--anki-connect-url", type=str, default=None)
    parser.add_argument("--anki-connect-key", type=str, default=None)
    parser.add_argument("--log-level", type=str, default="INFO")
    parser.add_argument("--remote", action="store_true", help="Run as a remote HTTP server instead of stdio")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = get_config()
    if args.data_dir:
        from pathlib import Path
        cfg.data_dir = Path(args.data_dir)
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        cfg.jmdict_index_path = cfg.data_dir / "jmdict.sqlite"
        cfg.kanjidic_index_path = cfg.data_dir / "kanjidic.sqlite"
        cfg.state_db_path = cfg.data_dir / "organizer-state.sqlite"
    if args.anki_connect_url:
        cfg.anki_connect_url = args.anki_connect_url
    if args.anki_connect_key:
        cfg.anki_connect_key = args.anki_connect_key

    if args.remote:
        logger.info("Starting remote MCP server on http://%s:%d/mcp", args.host, args.port)
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
