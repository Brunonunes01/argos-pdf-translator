from __future__ import annotations

import re
from pathlib import Path

from weasyprint import HTML


class PDFGenerator:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def make_output_name(self, original_filename: str, start_page: int, end_page: int, suffix: str) -> str:
        stem = Path(original_filename).stem
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "livro"
        return f"{safe_stem}_bilingue_pag_{start_page}_{end_page}.{suffix}"

    def save_html(self, html: str, original_filename: str, start_page: int, end_page: int) -> Path:
        path = self.output_dir / self.make_output_name(original_filename, start_page, end_page, "html")
        path.write_text(html, encoding="utf-8")
        return path

    def generate_pdf(self, html: str, original_filename: str, start_page: int, end_page: int) -> Path:
        path = self.output_dir / self.make_output_name(original_filename, start_page, end_page, "pdf")
        HTML(string=html, base_url=str(self.output_dir)).write_pdf(path)
        return path
