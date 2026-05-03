from __future__ import annotations

import hashlib
import re

from .models import ExtractedBlock, TextChunk


class TextChunker:
    def __init__(self, max_chars: int = 1800) -> None:
        self.max_chars = max_chars

    def chunk_blocks(self, blocks: list[ExtractedBlock]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        running_index = 0
        for block in blocks:
            normalized = self.normalize(block.original_text)
            if not normalized:
                continue
            for part in self._split_large_text(normalized):
                chunks.append(
                    TextChunk(
                        book_id=block.book_id,
                        page_number=block.page_number,
                        block_index=(block.block_index * 1000) + running_index,
                        original_text=part,
                        original_hash=self.hash_text(part),
                    )
                )
                running_index += 1
        return chunks

    def normalize(self, text: str) -> str:
        text = text.replace("-\n", "")
        text = re.sub(r"\s*\n\s*", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def hash_text(self, text: str) -> str:
        normalized = self.normalize(text).casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _split_large_text(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > self.max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_by_size(sentence))
                continue
            candidate = f"{current} {sentence}".strip()
            if len(candidate) > self.max_chars and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current.strip())
        return chunks

    def _split_by_size(self, text: str) -> list[str]:
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            if end < len(text):
                space = text.rfind(" ", start, end)
                if space > start + 100:
                    end = space
            parts.append(text[start:end].strip())
            start = end
        return [part for part in parts if part]
