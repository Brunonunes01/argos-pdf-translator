from __future__ import annotations

import hashlib
import os
import time
import uuid
from pathlib import Path
from typing import Callable

from .config import DB_PATH, OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR, ensure_directories
from .database import Database
from .filename_utils import build_safe_filename, normalize_original_name
from .html_renderer import HTMLRenderer
from .models import BilingualChunk, Book
from .pdf_extractor import PDFExtractor
from .pdf_generator import PDFGenerator
from .text_chunker import TextChunker
from .translator import ArgosTranslator, GeminiTranslator, MockTranslator, OpenAITranslator, Translator


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


class BilingualService:
    def __init__(self) -> None:
        ensure_directories()
        self.db = Database(DB_PATH)
        self.extractor = PDFExtractor()
        self.chunker = TextChunker()
        self.renderer = HTMLRenderer(TEMPLATES_DIR)
        self.generator = PDFGenerator(OUTPUTS_DIR)
        self.api_delay = float(os.getenv("API_DELAY_SECONDS", "2.0"))

    def register_upload(self, uploaded_file) -> tuple[Book, Path]:
        file_bytes = uploaded_file.getbuffer()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing_book = self.db.get_book_by_hash(file_hash)
        book_id = existing_book.id if existing_book else str(uuid.uuid4())
        original_name = normalize_original_name(uploaded_file.name, "livro.pdf")
        storage_name = build_safe_filename(
            original_name,
            prefix=book_id,
            default_stem="livro",
            default_suffix=".pdf",
        )
        pdf_path = UPLOADS_DIR / storage_name

        if not pdf_path.exists():
            with pdf_path.open("wb") as target:
                target.write(file_bytes)

        total_pages = self.extractor.count_pages(str(pdf_path))
        book = self.db.upsert_book(book_id, original_name, file_hash, total_pages)
        return book, pdf_path

    def build_translator(self, translator_name: str) -> Translator:
        if translator_name == "OpenAI":
            return OpenAITranslator()
        if translator_name == "Gemini":
            return GeminiTranslator()
        if translator_name == "Argos":
            return ArgosTranslator()
        return MockTranslator()

    def validate_range(self, start_page: int, end_page: int, total_pages: int) -> None:
        if start_page < 1 or end_page < 1:
            raise ValueError("As paginas devem comecar em 1.")
        if start_page > end_page:
            raise ValueError("O intervalo e invalido: a pagina inicial nao pode ser maior que a final.")
        if end_page > total_pages:
            raise ValueError(f"O PDF tem apenas {total_pages} paginas.")
        if end_page - start_page + 1 > 50:
            raise ValueError("Para livros grandes, processe lotes menores. Recomenda-se 10 a 30 paginas por vez.")

    def process_pages(
        self,
        book: Book,
        pdf_path: Path,
        start_page: int,
        end_page: int,
        translator_name: str,
        source_lang: str = "en",
        target_lang: str = "pt-BR",
        reprocess: bool = False,
        log: LogCallback | None = None,
        progress: ProgressCallback | None = None,
    ) -> list[BilingualChunk]:
        self.validate_range(start_page, end_page, book.total_pages)
        if reprocess:
            self.db.reset_range(book.id, start_page, end_page)

        ignored_margin_texts = self.extractor.find_repeated_margin_texts(
            str(pdf_path), start_page, end_page
        )
        if ignored_margin_texts:
            self._log(log, f"{len(ignored_margin_texts)} cabecalhos/rodapes repetidos serao ignorados.")

        for page_number in range(start_page, end_page + 1):
            blocks = self.extractor.extract_page_blocks(
                str(pdf_path), page_number, book.id, ignored_margin_texts, source_lang
            )
            chunks = self.chunker.chunk_blocks(blocks)
            if not chunks:
                self.db.mark_page_status(book.id, page_number, "empty", 0)
                self._log(log, f"Pagina {page_number}: nenhum texto extraivel encontrado.")
                continue
            inserted = self.db.insert_chunks_if_missing(chunks)
            self.db.mark_page_status(book.id, page_number, "extracted", len(chunks))
            self._log(log, f"Pagina {page_number} extraida: {len(chunks)} chunks ({inserted} novos).")

        if translator_name != "Mock":
            reset_count = self.db.reset_mock_translations(book.id, start_page, end_page)
            if reset_count:
                self._log(
                    log,
                    f"{reset_count} chunks com traducao Mock foram marcados para traducao real com {translator_name}.",
                )

        translator = self.build_translator(translator_name)
        pending = self.db.get_pending_chunks(book.id, start_page, end_page)
        total = len(pending)
        if total == 0:
            self._log(log, "Todos os chunks deste intervalo ja estavam traduzidos no cache.")

        for index, chunk in enumerate(pending, start=1):
            try:
                translated = translator.translate(chunk.original_text, source_lang, target_lang)
                self.db.mark_translated(chunk.id, translated)
                self._log(log, f"Chunk {chunk.block_index} da pagina {chunk.page_number} traduzido.")
            except Exception as exc:
                self.db.mark_failed(chunk.id, str(exc))
                self._log(log, f"Falha no chunk {chunk.block_index} da pagina {chunk.page_number}: {exc}")
                if self._is_rate_limit_error(exc):
                    self._log(
                        log,
                        "Quota da API atingida. A rodada foi pausada para evitar marcar o restante como falha.",
                    )
                    break
            
            if translator_name in {"OpenAI", "Gemini"} and index < total:
                time.sleep(self.api_delay)
                
            if progress:
                progress(index, total)

        return self.get_preview(book.id, start_page, end_page)

    def get_preview(self, book_id: str, start_page: int | None = None, end_page: int | None = None) -> list[BilingualChunk]:
        return self.db.get_chunks(book_id, start_page, end_page)

    def get_progress(self, book_id: str) -> dict[str, int]:
        return self.db.get_progress(book_id)

    def get_next_batch_range(
        self,
        book: Book,
        batch_size: int,
        max_page: int | None = None,
    ) -> tuple[int, int] | None:
        batch_size = max(1, min(batch_size, 50))
        max_page = min(max_page or book.total_pages, book.total_pages)
        page_statuses = self.db.get_page_statuses(book.id)
        status_pages = sorted(page for page in page_statuses if page <= max_page)

        if not status_pages:
            start_page = 1
        else:
            start_page = max(status_pages) + 1
            for page_number in status_pages:
                status = page_statuses[page_number]
                if not self._is_page_completed(status):
                    start_page = page_number
                    break

        if start_page > max_page:
            return None

        start_status = page_statuses.get(start_page)
        if start_status and start_status["failed_chunks"] > 0:
            end_page = start_page
        else:
            end_page = min(max_page, start_page + batch_size - 1)
        return start_page, end_page

    def get_translated_page_bounds(self, book_id: str) -> tuple[int, int] | None:
        return self.db.get_translated_page_bounds(book_id)

    def get_batch_summary(self, book: Book, target_page: int) -> dict[str, int | None]:
        target_page = min(max(1, target_page), book.total_pages)
        page_statuses = self.db.get_page_statuses(book.id)
        status_pages = sorted(page for page in page_statuses if page <= target_page)
        last_completed: int | None = None
        first_pending: int | None = None

        for page_number in status_pages:
            status = page_statuses[page_number]
            if self._is_page_completed(status):
                last_completed = page_number
                continue
            first_pending = page_number
            break

        if first_pending is None:
            if status_pages:
                next_unprocessed = max(status_pages) + 1
                first_pending = next_unprocessed if next_unprocessed <= target_page else None
            else:
                first_pending = 1

        completed_count = 0
        failed_count = 0
        first_pending_failed = 0
        for page_number in status_pages:
            status = page_statuses[page_number]
            if self._is_page_completed(status):
                completed_count += 1
            failed_count += status["failed_chunks"]
            if first_pending is not None and page_number == first_pending:
                first_pending_failed = status["failed_chunks"]

        return {
            "target_page": target_page,
            "last_completed": last_completed,
            "first_pending": first_pending,
            "completed_count": completed_count,
            "failed_chunks": failed_count,
            "first_pending_failed": first_pending_failed,
        }

    def _is_page_completed(self, status: dict[str, int]) -> bool:
        if status.get("empty") == 1:
            return True
        if status["total_chunks"] == 0:
            return False
        return status["translated_chunks"] >= status["total_chunks"]

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc)
        return (
            "Quota do Gemini" in message
            or "Quota da OpenAI" in message
            or "RESOURCE_EXHAUSTED" in message
            or "429" in message
            or "rate limit" in message.casefold()
        )

    def render_html(self, book: Book, start_page: int, end_page: int) -> str:
        chunks = self.get_preview(book.id, start_page, end_page)
        if not chunks:
            raise ValueError(
                "Nao ha texto processado neste intervalo. Processe as paginas antes de gerar HTML/PDF."
            )
        return self.renderer.render_book(book, chunks)

    def export_html(self, book: Book, start_page: int, end_page: int) -> Path:
        html = self.render_html(book, start_page, end_page)
        return self.generator.save_html(html, book.filename, start_page, end_page)

    def export_pdf(self, book: Book, start_page: int, end_page: int) -> Path:
        html = self.render_html(book, start_page, end_page)
        return self.generator.generate_pdf(html, book.filename, start_page, end_page)

    def _log(self, log: LogCallback | None, message: str) -> None:
        if log:
            log(message)
