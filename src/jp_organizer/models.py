from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SemanticClassification(BaseModel):
    id: str
    mimetic: bool
    expression_type: Literal["construction", "idiom", "collocation"] | None


class JmdictIndexStatus(BaseModel):
    present: bool
    schema_version: int = 2
    entry_count: int = 0
    form_count: int = 0
    source_path: str | None = None
    source_mtime: float | None = None
    source_size: int | None = None


class KanjidicIndexStatus(BaseModel):
    present: bool
    schema_version: int = 1
    kanji_count: int = 0
    source_path: str | None = None
    source_mtime: float | None = None
    source_size: int | None = None


class IndexStatusResult(BaseModel):
    jmdict: JmdictIndexStatus
    kanjidic: KanjidicIndexStatus


class SyncResult(BaseModel):
    status: Literal["ok", "semantic_classification_required", "error"]
    message: str | None = None
    requests: list[dict] | None = None
    plan: dict | None = None
    error: dict | None = None


class VocabularyLookupResult(BaseModel):
    entry: str
    primary_class: str | None = None
    target_deck: str | None = None
    kind_tag: str | None = None
    jmdict: dict
    semantic: dict | None = None


class KanjiLookupResult(BaseModel):
    found: bool
    entry: str
    meanings: list[str]
    readings: dict[str, list[str]]
