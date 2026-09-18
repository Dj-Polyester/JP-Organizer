from __future__ import annotations

import logging

from jp_organizer.dictionaries.kanjidic_repository import KanjidicRepository

logger = logging.getLogger(__name__)


class KanjiExtractor:
    def __init__(self, kanjidic: KanjidicRepository | None = None) -> None:
        self.kanjidic = kanjidic or KanjidicRepository()

    def extract_unique_kanji(self, vocab_entries: list[str]) -> list[str]:
        if not self.kanjidic.is_ready():
            return []
        chars: set[str] = set()
        for entry in vocab_entries:
            for ch in entry:
                chars.add(ch)
        found = self.kanjidic.batch_lookup(list(chars))
        return sorted(found.keys())

    def build_readings_text(self, info: dict) -> str:
        lines: list[str] = []
        on_readings = info["readings"].get("on", [])
        kun_readings = info["readings"].get("kun", [])
        nanori = info["readings"].get("nanori", [])
        if on_readings:
            lines.append("On: " + ", ".join(on_readings))
        if kun_readings:
            lines.append("Kun: " + ", ".join(kun_readings))
        if nanori:
            lines.append("Nanori: " + ", ".join(nanori))
        return "\n".join(lines)
