from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)

STATE_SCHEMA_VERSION = 2


def hash_entry(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class StateRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_config().state_db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_to_managed (
                source_note_id INTEGER PRIMARY KEY,
                managed_note_id INTEGER NOT NULL,
                entry_text TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                source_deck TEXT NOT NULL,
                model_name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS semantic_cache (
                note_key TEXT PRIMARY KEY,
                entry_hash TEXT NOT NULL,
                mimetic INTEGER NOT NULL,
                expression_type TEXT,
                semantic_source TEXT,
                classifier_schema_version INTEGER NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            CREATE TABLE IF NOT EXISTS index_metadata (
                dictionary TEXT PRIMARY KEY,
                schema_version INTEGER,
                created_at INTEGER,
                source_path TEXT,
                source_mtime REAL,
                source_size INTEGER
            );
            """
        )
        conn.commit()
        conn.close()

    def get_mapping(self, source_note_id: int) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT managed_note_id, entry_text, entry_hash, source_deck, model_name FROM source_to_managed WHERE source_note_id = ?",
            (source_note_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return {
            "source_note_id": source_note_id,
            "managed_note_id": row[0],
            "entry_text": row[1],
            "entry_hash": row[2],
            "source_deck": row[3],
            "model_name": row[4],
        }

    def set_mapping(self, source_note_id: int, managed_note_id: int, entry_text: str, source_deck: str, model_name: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO source_to_managed (source_note_id, managed_note_id, entry_text, entry_hash, source_deck, model_name)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_note_id) DO UPDATE SET
                managed_note_id=excluded.managed_note_id,
                entry_text=excluded.entry_text,
                entry_hash=excluded.entry_hash,
                source_deck=excluded.source_deck,
                model_name=excluded.model_name
            """,
            (source_note_id, managed_note_id, entry_text, hash_entry(entry_text), source_deck, model_name),
        )
        conn.commit()
        conn.close()

    def delete_mapping(self, source_note_id: int) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM source_to_managed WHERE source_note_id = ?", (source_note_id,))
        conn.commit()
        conn.close()

    def all_mappings(self) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT source_note_id, managed_note_id, entry_text, entry_hash, source_deck, model_name FROM source_to_managed")
        rows = [
            {
                "source_note_id": r[0],
                "managed_note_id": r[1],
                "entry_text": r[2],
                "entry_hash": r[3],
                "source_deck": r[4],
                "model_name": r[5],
            }
            for r in cursor.fetchall()
        ]
        conn.close()
        return rows

    def get_semantic(self, note_key: str) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT entry_hash, mimetic, expression_type, semantic_source, classifier_schema_version FROM semantic_cache WHERE note_key = ?",
            (note_key,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return {
            "note_key": note_key,
            "entry_hash": row[0],
            "mimetic": bool(row[1]),
            "expression_type": row[2],
            "semantic_source": row[3],
            "classifier_schema_version": row[4],
        }

    def set_semantic(
        self,
        note_key: str,
        entry_text: str,
        mimetic: bool,
        expression_type: str | None,
        semantic_source: str | None,
        schema_version: int = STATE_SCHEMA_VERSION,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO semantic_cache (note_key, entry_hash, mimetic, expression_type, semantic_source, classifier_schema_version)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(note_key) DO UPDATE SET
                entry_hash=excluded.entry_hash,
                mimetic=excluded.mimetic,
                expression_type=excluded.expression_type,
                semantic_source=excluded.semantic_source,
                classifier_schema_version=excluded.classifier_schema_version,
                created_at=strftime('%s', 'now')
            """,
            (note_key, hash_entry(entry_text), int(mimetic), expression_type, semantic_source, schema_version),
        )
        conn.commit()
        conn.close()

    def delete_semantic(self, note_key: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM semantic_cache WHERE note_key = ?", (note_key,))
        conn.commit()
        conn.close()

    def get_all_semantic(self) -> dict[str, dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT note_key, entry_hash, mimetic, expression_type, semantic_source, classifier_schema_version FROM semantic_cache")
        result = {}
        for row in cursor.fetchall():
            result[row[0]] = {
                "note_key": row[0],
                "entry_hash": row[1],
                "mimetic": bool(row[2]),
                "expression_type": row[3],
                "semantic_source": row[4],
                "classifier_schema_version": row[5],
            }
        conn.close()
        return result
