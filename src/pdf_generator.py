from __future__ import annotations

from pathlib import Path

from weasyprint import HTML

from .filename_utils import build_safe_filename


class PDFGenerator:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def make_output_name(self, original_filename: str, start_page: int, end_page: int, suffix: str) -> str:
        candidate_name = f"{Path(original_filename).stem}_bilingue_pag_{start_page}_{end_page}.{suffix}"
        return build_safe_filename(
            candidate_name,
            default_stem="livro_bilingue",
            default_suffix=f".{suffix}",
        )

    def save_html(self, html: str, original_filename: str, start_page: int, end_page: int) -> Path:
        path = self.output_dir / self.make_output_name(original_filename, start_page, end_page, "html")
        path.write_text(html, encoding="utf-8")
        return path

    def generate_pdf(self, html: str, original_filename: str, start_page: int, end_page: int) -> Path:
        path = self.output_dir / self.make_output_name(original_filename, start_page, end_page, "pdf")
        HTML(string=html, base_url=str(self.output_dir)).write_pdf(path)
        return path
