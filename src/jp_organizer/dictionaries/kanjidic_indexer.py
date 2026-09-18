from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from lxml import etree

from jp_organizer.config import get_config

logger = logging.getLogger(__name__)

KANJIDIC_SCHEMA_VERSION = 1


class KanjidicIndexer:
    def __init__(self, xml_path: Path | str, db_path: Path | None = None) -> None:
        self.xml_path = Path(xml_path)
        self.db_path = db_path or get_config().kanjidic_index_path

    def build(self, force: bool = False) -> dict:
        if not force and self.db_path.exists():
            meta = self._read_metadata()
            if meta and meta.get("schema_version") == KANJIDIC_SCHEMA_VERSION:
                return {"status": "skipped", "reason": "index already exists"}

        logger.info("Building KANJIDIC index from %s", self.xml_path)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema(conn)

        context = etree.iterparse(str(self.xml_path), events=("end",), tag="character")
        kanji_buffer = []
        meaning_buffer = []
        reading_buffer = []
        kanji_count = 0

        for event, elem in context:
            literal = elem.findtext("literal", default="")
            if not literal:
                elem.clear()
                continue
            kanji_buffer.append((literal,))

            rm = elem.find("reading_meaning")
            if rm is not None:
                rmgroup = rm.find("rmgroup")
                if rmgroup is not None:
                    ord_m = 0
                    for meaning in rmgroup.findall("meaning"):
                        lang = meaning.get("m_lang", "en")
                        if lang == "en":
                            meaning_buffer.append((literal, meaning.text or "", lang, ord_m))
                            ord_m += 1
                    ord_r = 0
                    for reading in rmgroup.findall("reading"):
                        r_type = reading.get("r_type", "")
                        if r_type in ("ja_on", "ja_kun", "nanori"):
                            rt = r_type.replace("ja_", "")
                            reading_buffer.append((literal, reading.text or "", rt, ord_r))
                            ord_r += 1
                else:
                    ord_m = 0
                    for meaning in rm.findall("meaning"):
                        lang = meaning.get("m_lang", "en")
                        if lang == "en":
                            meaning_buffer.append((literal, meaning.text or "", lang, ord_m))
                            ord_m += 1
                    ord_r = 0
                    for reading in rm.findall("reading"):
                        r_type = reading.get("r_type", "")
                        if r_type in ("ja_on", "ja_kun", "nanori"):
                            rt = r_type.replace("ja_", "")
                            reading_buffer.append((literal, reading.text or "", rt, ord_r))
                            ord_r += 1

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            kanji_count += 1
            if kanji_count % 1000 == 0:
                self._flush(conn, kanji_buffer, meaning_buffer, reading_buffer)
                logger.debug("Indexed %d kanji", kanji_count)

        self._flush(conn, kanji_buffer, meaning_buffer, reading_buffer)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kanji_literal ON kanji(literal)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meanings_literal ON meanings(literal)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_literal ON readings(literal)")
        conn.commit()

        stat = self.xml_path.stat()
        self._write_metadata(conn, stat)
        conn.commit()
        conn.close()

        logger.info("KANJIDIC index complete: %d kanji", kanji_count)
        return {"status": "ok", "kanji": kanji_count}

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP TABLE IF EXISTS kanji;
            DROP TABLE IF EXISTS meanings;
            DROP TABLE IF EXISTS readings;
            DROP TABLE IF EXISTS index_metadata;

            CREATE TABLE kanji (
                literal TEXT PRIMARY KEY
            );
            CREATE TABLE meanings (
                literal TEXT,
                meaning TEXT,
                language TEXT,
                ordinal INTEGER
            );
            CREATE TABLE readings (
                literal TEXT,
                reading TEXT,
                reading_type TEXT,
                ordinal INTEGER
            );
            CREATE TABLE index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )

    def _flush(self, conn: sqlite3.Connection, kanji: list, meanings: list, readings: list) -> None:
        if kanji:
            conn.executemany("INSERT INTO kanji (literal) VALUES (?)", kanji)
            kanji.clear()
        if meanings:
            conn.executemany("INSERT INTO meanings (literal, meaning, language, ordinal) VALUES (?, ?, ?, ?)", meanings)
            meanings.clear()
        if readings:
            conn.executemany("INSERT INTO readings (literal, reading, reading_type, ordinal) VALUES (?, ?, ?, ?)", readings)
            readings.clear()

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
                ("schema_version", str(KANJIDIC_SCHEMA_VERSION)),
                ("source_path", str(self.xml_path)),
                ("source_mtime", str(stat.st_mtime)),
                ("source_size", str(stat.st_size)),
            ],
        )
