from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import BilingualChunk, Book


class HTMLRenderer:
    def __init__(self, templates_dir: Path) -> None:
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_book(self, book: Book, chunks: list[BilingualChunk]) -> str:
        grouped: dict[int, list[BilingualChunk]] = defaultdict(list)
        for chunk in chunks:
            grouped[chunk.page_number].append(chunk)

        pages = [
            {"number": page_number, "chunks": page_chunks}
            for page_number, page_chunks in sorted(grouped.items())
        ]
        template = self.env.get_template("bilingual_book.html")
        return template.render(book=book, pages=pages)
