from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    id: str
    filename: str
    file_hash: str
    total_pages: int
    created_at: str


@dataclass(frozen=True)
class ExtractedBlock:
    book_id: str
    page_number: int
    block_index: int
    original_text: str
    bbox: tuple[float, float, float, float] | None = None
    block_type: str = "unknown"


@dataclass(frozen=True)
class TextChunk:
    book_id: str
    page_number: int
    block_index: int
    original_text: str
    original_hash: str


@dataclass(frozen=True)
class BilingualChunk:
    id: int
    book_id: str
    page_number: int
    block_index: int
    original_text: str
    original_hash: str
    translated_text: str | None
    status: str
