from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)


class KanjidicRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_config().kanjidic_index_path

    def is_ready(self) -> bool:
        if not self.db_path.exists():
            return False
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT value FROM index_metadata WHERE key = 'schema_version'"
            )
            row = cursor.fetchone()
            conn.close()
            return row is not None and row[0] == "1"
        except Exception:
            return False

    def lookup(self, literal: str) -> dict | None:
        if not self.is_ready():
            return None
        conn = sqlite3.connect(self.db_path)
        exists = conn.execute(
            "SELECT 1 FROM kanji WHERE literal = ?", (literal,)
        ).fetchone()
        if not exists:
            conn.close()
            return None
        meanings = [
            row[0]
            for row in conn.execute(
                "SELECT meaning FROM meanings WHERE literal = ? ORDER BY ordinal",
                (literal,),
            )
        ]
        readings: dict[str, list[str]] = {"on": [], "kun": [], "nanori": []}
        for row in conn.execute(
            "SELECT reading, reading_type FROM readings WHERE literal = ? ORDER BY ordinal",
            (literal,),
        ):
            rt = row[1]
            if rt in readings:
                readings[rt].append(row[0])
        conn.close()
        return {
            "literal": literal,
            "meanings": meanings,
            "readings": readings,
        }

    def batch_lookup(self, literals: list[str]) -> dict[str, dict]:
        if not self.is_ready():
            return {}
        conn = sqlite3.connect(self.db_path)
        placeholders = ",".join("?" for _ in literals)
        cursor = conn.execute(
            f"SELECT literal FROM kanji WHERE literal IN ({placeholders})", literals
        )
        found = {row[0] for row in cursor.fetchall()}
        result = {}
        for lit in literals:
            if lit in found:
                meanings = [
                    row[0]
                    for row in conn.execute(
                        "SELECT meaning FROM meanings WHERE literal = ? ORDER BY ordinal",
                        (lit,),
                    )
                ]
                readings: dict[str, list[str]] = {"on": [], "kun": [], "nanori": []}
                for row in conn.execute(
                    "SELECT reading, reading_type FROM readings WHERE literal = ? ORDER BY ordinal",
                    (lit,),
                ):
                    rt = row[1]
                    if rt in readings:
                        readings[rt].append(row[0])
                result[lit] = {
                    "literal": lit,
                    "meanings": meanings,
                    "readings": readings,
                }
        conn.close()
        return result

    def status(self) -> dict:
        if not self.is_ready():
            return {"present": False}
        conn = sqlite3.connect(self.db_path)
        kanji_count = conn.execute("SELECT COUNT(*) FROM kanji").fetchone()[0]
        meta = {}
        for row in conn.execute("SELECT key, value FROM index_metadata"):
            meta[row[0]] = row[1]
        conn.close()
        return {
            "present": True,
            "schema_version": int(meta.get("schema_version", 1)),
            "kanji_count": kanji_count,
            "source_path": meta.get("source_path"),
            "source_mtime": float(meta.get("source_mtime", 0)) or None,
            "source_size": int(meta.get("source_size", 0)) or None,
        }
