from __future__ import annotations

from collections import Counter
from io import BytesIO
import os

import fitz
from PIL import Image

from .models import ExtractedBlock


class PDFTextExtractionError(RuntimeError):
    pass


class PDFExtractor:
    def __init__(self) -> None:
        self.ocr_enabled = os.getenv("OCR_ENABLED", "1") != "0"
        self.ocr_zoom = float(os.getenv("OCR_ZOOM", "2.0"))

    def count_pages(self, pdf_path: str) -> int:
        with fitz.open(pdf_path) as doc:
            return doc.page_count

    def extract_page_text(self, pdf_path: str, page_number: int) -> str:
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_number - 1)
            return page.get_text("text").strip()

    def extract_page_blocks(
        self,
        pdf_path: str,
        page_number: int,
        book_id: str = "",
        ignored_margin_texts: set[str] | None = None,
        source_lang: str = "en",
    ) -> list[ExtractedBlock]:
        ignored_margin_texts = ignored_margin_texts or set()
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_number - 1)
            raw_blocks = page.get_text("blocks")
            page_height = page.rect.height

            if not raw_blocks and self.ocr_enabled:
                return self._extract_ocr_blocks(page, book_id, page_number, source_lang)

        blocks: list[tuple[float, float, float, float, str, int]] = []
        for raw in raw_blocks:
            x0, y0, x1, y1, text, block_no, *_ = raw
            clean_text = " ".join(text.split())
            block_type = self._classify_block(y0, y1, page_height, clean_text)
            if clean_text and not self._should_ignore_margin_text(clean_text, block_type, ignored_margin_texts):
                blocks.append((x0, y0, x1, y1, clean_text, block_no))

        blocks.sort(key=lambda item: (round(item[1], 1), round(item[0], 1)))
        extracted: list[ExtractedBlock] = []
        for index, (x0, y0, x1, y1, text, _block_no) in enumerate(blocks):
            block_type = self._classify_block(y0, y1, page_height, text)
            extracted.append(
                ExtractedBlock(
                    book_id=book_id,
                    page_number=page_number,
                    block_index=index,
                    original_text=text,
                    bbox=(x0, y0, x1, y1),
                    block_type=block_type,
                )
            )
        return extracted

    def _extract_ocr_blocks(
        self,
        page: fitz.Page,
        book_id: str,
        page_number: int,
        source_lang: str,
    ) -> list[ExtractedBlock]:
        try:
            import pytesseract
        except ImportError as exc:
            raise PDFTextExtractionError(
                "Este PDF parece ser escaneado. Instale pytesseract e Tesseract OCR para extrair texto."
            ) from exc

        matrix = fitz.Matrix(self.ocr_zoom, self.ocr_zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        ocr_lang = self._tesseract_language(source_lang)

        try:
            text = pytesseract.image_to_string(image, lang=ocr_lang)
        except pytesseract.TesseractNotFoundError as exc:
            raise PDFTextExtractionError(
                "Tesseract OCR nao esta instalado no sistema. Instale tesseract-ocr e o idioma necessario."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise PDFTextExtractionError(
                f"O Tesseract nao conseguiu executar OCR com o idioma '{ocr_lang}'. "
                "Confira se o pacote de idioma esta instalado."
            ) from exc

        paragraphs = [
            " ".join(paragraph.split())
            for paragraph in text.split("\n\n")
            if " ".join(paragraph.split())
        ]
        return [
            ExtractedBlock(
                book_id=book_id,
                page_number=page_number,
                block_index=index,
                original_text=paragraph,
                bbox=(0, 0, page.rect.width, page.rect.height),
                block_type="paragraph",
            )
            for index, paragraph in enumerate(paragraphs)
        ]

    def _tesseract_language(self, source_lang: str) -> str:
        if source_lang in {"pt", "pt-BR", "pt_BR"}:
            return "por"
        return "eng"

    def find_repeated_margin_texts(self, pdf_path: str, start_page: int, end_page: int) -> set[str]:
        counts: Counter[str] = Counter()
        total_pages = end_page - start_page + 1
        if total_pages < 3:
            return set()

        with fitz.open(pdf_path) as doc:
            for page_number in range(start_page, end_page + 1):
                page = doc.load_page(page_number - 1)
                page_height = page.rect.height
                for raw in page.get_text("blocks"):
                    x0, y0, x1, y1, text, *_ = raw
                    clean_text = " ".join(text.split())
                    if not clean_text or len(clean_text) > 120:
                        continue
                    block_type = self._classify_block(y0, y1, page_height, clean_text)
                    if block_type in {"header", "footer"}:
                        counts[self._normalize_repeated_text(clean_text)] += 1

        threshold = max(2, total_pages // 2)
        return {text for text, count in counts.items() if count >= threshold}

    def _classify_block(self, y0: float, y1: float, page_height: float, text: str) -> str:
        if y1 < page_height * 0.12:
            return "header"
        if y0 > page_height * 0.88:
            return "footer"
        if len(text) < 80 and text.isupper():
            return "header"
        return "paragraph"

    def _should_ignore_margin_text(
        self,
        text: str,
        block_type: str,
        ignored_margin_texts: set[str],
    ) -> bool:
        if block_type not in {"header", "footer"}:
            return False
        return self._normalize_repeated_text(text) in ignored_margin_texts

    def _normalize_repeated_text(self, text: str) -> str:
        return " ".join(text.split()).casefold()
