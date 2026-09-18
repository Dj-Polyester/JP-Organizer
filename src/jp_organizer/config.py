import html
import os
import re
from pathlib import Path


class Config:
    """jp-organizer configuration."""

    anki_connect_url: str = "http://127.0.0.1:8765"
    anki_connect_timeout: float = 30.0
    anki_connect_key: str | None = None
    data_dir: Path = Path.home() / ".local" / "share" / "jp-organizer"
    managed_root_deck: str = "Japanese"
    vocabulary_deck: str = "Japanese::Vocabulary"
    # Leaf decks
    words_deck: str = "Japanese::Vocabulary::Words"
    mimetics_deck: str = "Japanese::Vocabulary::Mimetics"
    expressions_deck: str = "Japanese::Vocabulary::Expressions"
    constructions_deck: str = "Japanese::Vocabulary::Expressions::Constructions"
    idioms_deck: str = "Japanese::Vocabulary::Expressions::Idioms"
    collocations_deck: str = "Japanese::Vocabulary::Expressions::Collocations"
    other_deck: str = "Japanese::Vocabulary::Other"
    kanji_deck: str = "Japanese::Kanji"
    vocabulary_model: str = "JP Organizer Vocabulary"
    kanji_model: str = "JP Organizer Kanji"
    jmdict_index_path: Path | None = None
    kanjidic_index_path: Path | None = None
    state_db_path: Path | None = None

    def __init__(self) -> None:
        if os.environ.get("ANKI_CONNECT_KEY"):
            self.anki_connect_key = os.environ.get("ANKI_CONNECT_KEY")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.jmdict_index_path is None:
            self.jmdict_index_path = self.data_dir / "jmdict.sqlite"
        if self.kanjidic_index_path is None:
            self.kanjidic_index_path = self.data_dir / "kanjidic.sqlite"
        if self.state_db_path is None:
            self.state_db_path = self.data_dir / "organizer-state.sqlite"


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    global _config
    _config = config


def strip_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.strip()
    return text
