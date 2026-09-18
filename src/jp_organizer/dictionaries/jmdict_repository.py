from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)


class JmdictRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_config().jmdict_index_path

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
            return row is not None and row[0] == "2"
        except Exception:
            return False

    def lookup(self, entry: str) -> list[str]:
        if not self.is_ready():
            return []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            SELECT DISTINCT p.pos_category
            FROM forms f
            JOIN pos p ON p.entry_id = f.entry_id
            WHERE f.form = ?
            """,
            (entry,),
        )
        rows = [row[0] for row in cursor.fetchall()]
        conn.close()
        return rows

    def lookup_semantic(self, entry: str) -> list[str]:
        """Return distinct semantic entity codes (e.g. on-mim, id, exp) for the entry."""
        if not self.is_ready():
            return []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            SELECT DISTINCT s.semantic_code
            FROM forms f
            JOIN semantic_metadata s ON s.entry_id = f.entry_id
            WHERE f.form = ?
            """,
            (entry,),
        )
        rows = [row[0] for row in cursor.fetchall()]
        conn.close()
        return rows

    def status(self) -> dict:
        if not self.is_ready():
            return {"present": False}
        conn = sqlite3.connect(self.db_path)
        entry_count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        form_count = conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
        meta = {}
        for row in conn.execute("SELECT key, value FROM index_metadata"):
            meta[row[0]] = row[1]
        conn.close()
        return {
            "present": True,
            "schema_version": int(meta.get("schema_version", 2)),
            "entry_count": entry_count,
            "form_count": form_count,
            "source_path": meta.get("source_path"),
            "source_mtime": float(meta.get("source_mtime", 0)) or None,
            "source_size": int(meta.get("source_size", 0)) or None,
        }
