from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from lxml import etree

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)

JMDICT_SCHEMA_VERSION = 2

_ENTITY_RE = re.compile(r'<!ENTITY\s+(\S+)\s+"([^"]+)">')


class JmdictIndexer:
    def __init__(self, xml_path: Path | str, db_path: Path | None = None) -> None:
        self.xml_path = Path(xml_path)
        self.db_path = db_path or get_config().jmdict_index_path

    def _build_entity_reverse_map(self) -> dict[str, str]:
        text = self.xml_path.read_text(encoding="utf-8")
        # Only read the DTD portion (before the first <JMdict> or root element)
        dtd_end = text.find("<JMdict>")
        if dtd_end == -1:
            dtd_end = text.find("<entry>")
        dtd = text[:dtd_end] if dtd_end != -1 else text
        return {m.group(2): m.group(1) for m in _ENTITY_RE.finditer(dtd)}

    def build(self, force: bool = False) -> dict:
        if not force and self.db_path.exists():
            meta = self._read_metadata()
            if meta and meta.get("schema_version") == str(JMDICT_SCHEMA_VERSION):
                return {"status": "skipped", "reason": "index already exists"}

        logger.info("Building JMdict index from %s", self.xml_path)
        entity_map = self._build_entity_reverse_map()
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema(conn)

        context = etree.iterparse(str(self.xml_path), events=("end",), tag="entry")

        entry_buffer = []
        form_buffer = []
        pos_buffer = []
        semantic_buffer = []
        entry_count = 0

        for event, elem in context:
            ent_seq = int(elem.findtext("ent_seq", default="0"))
            entry_buffer.append((ent_seq,))

            for keb in elem.findall("k_ele/keb"):
                form_buffer.append((ent_seq, keb.text or "", "keb"))
            for reb in elem.findall("r_ele/reb"):
                form_buffer.append((ent_seq, reb.text or "", "reb"))

            for sense in elem.findall("sense"):
                for pos in sense.findall("pos"):
                    text = pos.text or ""
                    # Map resolved entity text back to canonical entity code
                    code = entity_map.get(text, text)
                    pos_buffer.append((ent_seq, code))
                for misc in sense.findall("misc"):
                    text = misc.text or ""
                    code = entity_map.get(text, text)
                    semantic_buffer.append((ent_seq, code))

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            entry_count += 1
            if entry_count % 5000 == 0:
                self._flush(conn, entry_buffer, form_buffer, pos_buffer, semantic_buffer)
                logger.debug("Indexed %d entries", entry_count)

        self._flush(conn, entry_buffer, form_buffer, pos_buffer, semantic_buffer)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forms_form ON forms(form)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pos_entry ON pos(entry_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_entry ON semantic_metadata(entry_id)")
        conn.commit()

        stat = self.xml_path.stat()
        self._write_metadata(conn, stat)
        conn.commit()
        conn.close()

        logger.info("JMdict index complete: %d entries", entry_count)
        return {"status": "ok", "entries": entry_count}

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP TABLE IF EXISTS entries;
            DROP TABLE IF EXISTS forms;
            DROP TABLE IF EXISTS pos;
            DROP TABLE IF EXISTS semantic_metadata;
            DROP TABLE IF EXISTS index_metadata;

            CREATE TABLE entries (
                entry_id INTEGER PRIMARY KEY
            );
            CREATE TABLE forms (
                entry_id INTEGER,
                form TEXT,
                form_type TEXT
            );
            CREATE TABLE pos (
                entry_id INTEGER,
                pos_category TEXT
            );
            CREATE TABLE semantic_metadata (
                entry_id INTEGER,
                semantic_code TEXT
            );
            CREATE TABLE index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )

    def _flush(self, conn: sqlite3.Connection, entries: list, forms: list, pos: list, semantic: list) -> None:
        if entries:
            conn.executemany("INSERT INTO entries (entry_id) VALUES (?)", entries)
            entries.clear()
        if forms:
            conn.executemany("INSERT INTO forms (entry_id, form, form_type) VALUES (?, ?, ?)", forms)
            forms.clear()
        if pos:
            conn.executemany("INSERT INTO pos (entry_id, pos_category) VALUES (?, ?)", pos)
            pos.clear()
        if semantic:
            conn.executemany("INSERT INTO semantic_metadata (entry_id, semantic_code) VALUES (?, ?)", semantic)
            semantic.clear()

    def _read_metadata(self) -> dict | None:
        if not self.db_path.exists():
            return None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT key, value FROM index_metadata")
        meta = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return meta

    def _write_metadata(self, conn: sqlite3.Connection, stat) -> None:
        conn.executemany(
            "INSERT INTO index_metadata (key, value) VALUES (?, ?)",
            [
                ("schema_version", str(JMDICT_SCHEMA_VERSION)),
                ("source_path", str(self.xml_path)),
                ("source_mtime", str(stat.st_mtime)),
                ("source_size", str(stat.st_size)),
            ],
        )
