from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import uuid
import zipfile
from xml.etree import ElementTree

import fitz
from weasyprint import HTML

from .filename_utils import build_safe_filename


class EbookConversionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConversionResult:
    path: Path
    filename: str
    mime: str


class EbookConverter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def epub_to_pdf(self, epub_path: Path) -> ConversionResult:
        safe_stem = self._safe_stem(epub_path.name, ".pdf")
        output_path = self.output_dir / f"{safe_stem}.pdf"

        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            extract_dir = tmp_dir / "epub"
            extract_dir.mkdir()
            with zipfile.ZipFile(epub_path) as epub_zip:
                epub_zip.extractall(extract_dir)

            opf_path = self._find_opf_path(extract_dir)
            chapters = self._collect_spine_documents(opf_path)
            if not chapters:
                raise EbookConversionError("Nao encontrei capitulos HTML no EPUB.")

            html_parts = []
            for chapter_path in chapters:
                body = self._extract_body(chapter_path.read_text(encoding="utf-8", errors="ignore"))
                html_parts.append(self._rewrite_relative_assets(body, chapter_path, opf_path.parent))

            html = self._wrap_epub_html(epub_path.stem, "\n".join(html_parts))
            HTML(string=html, base_url=str(opf_path.parent)).write_pdf(output_path)

        return ConversionResult(output_path, output_path.name, "application/pdf")

    def pdf_to_epub(self, pdf_path: Path) -> ConversionResult:
        safe_stem = self._safe_stem(pdf_path.name, ".epub")
        output_path = self.output_dir / f"{safe_stem}.epub"
        book_id = f"urn:uuid:{uuid.uuid4()}"

        pages = self._extract_pdf_pages(pdf_path)
        if not pages:
            raise EbookConversionError("Nao consegui extrair texto desse PDF.")

        chapter_items = []
        for index, text in pages:
            chapter_filename = f"chapter_{index:04d}.xhtml"
            chapter_items.append((index, chapter_filename, self._page_to_xhtml(index, text)))

        with zipfile.ZipFile(output_path, "w") as epub:
            epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            epub.writestr("META-INF/container.xml", self._container_xml())
            epub.writestr("OEBPS/content.opf", self._content_opf(pdf_path.stem, book_id, chapter_items))
            epub.writestr("OEBPS/nav.xhtml", self._nav_xhtml(pdf_path.stem, chapter_items))
            epub.writestr("OEBPS/styles.css", self._epub_css())
            for _index, chapter_filename, chapter_html in chapter_items:
                epub.writestr(f"OEBPS/{chapter_filename}", chapter_html)

        return ConversionResult(output_path, output_path.name, "application/epub+zip")

    def _find_opf_path(self, extract_dir: Path) -> Path:
        container_path = extract_dir / "META-INF" / "container.xml"
        if not container_path.exists():
            raise EbookConversionError("EPUB invalido: arquivo META-INF/container.xml nao encontrado.")

        root = ElementTree.fromstring(container_path.read_text(encoding="utf-8", errors="ignore"))
        rootfile = root.find(".//{*}rootfile")
        if rootfile is None or not rootfile.attrib.get("full-path"):
            raise EbookConversionError("EPUB invalido: caminho do pacote OPF nao encontrado.")

        opf_path = extract_dir / rootfile.attrib["full-path"]
        if not opf_path.exists():
            raise EbookConversionError("EPUB invalido: arquivo OPF nao encontrado.")
        return opf_path

    def _collect_spine_documents(self, opf_path: Path) -> list[Path]:
        opf_root = ElementTree.fromstring(opf_path.read_text(encoding="utf-8", errors="ignore"))
        manifest = {
            item.attrib["id"]: item.attrib
            for item in opf_root.findall(".//{*}manifest/{*}item")
            if item.attrib.get("id") and item.attrib.get("href")
        }

        chapters = []
        for itemref in opf_root.findall(".//{*}spine/{*}itemref"):
            item = manifest.get(itemref.attrib.get("idref", ""))
            if not item:
                continue
            media_type = item.get("media-type", "")
            href = item.get("href", "")
            if media_type not in {"application/xhtml+xml", "text/html"} and not href.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            chapter_path = (opf_path.parent / href).resolve()
            if chapter_path.exists() and opf_path.parent.resolve() in chapter_path.parents:
                chapters.append(chapter_path)
        return chapters

    def _extract_body(self, html: str) -> str:
        match = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else html

    def _rewrite_relative_assets(self, html: str, chapter_path: Path, base_dir: Path) -> str:
        try:
            chapter_dir = chapter_path.parent.resolve().relative_to(base_dir.resolve()).as_posix()
        except ValueError:
            return html
        if chapter_dir == ".":
            return html

        def replace(match: re.Match[str]) -> str:
            attr, quote, value = match.groups()
            if self._is_external_or_special_url(value):
                return match.group(0)
            rewritten = f"{chapter_dir}/{value}"
            return f'{attr}={quote}{rewritten}{quote}'

        return re.sub(r'\b(src|href)=(["\'])([^"\']+)\2', replace, html, flags=re.IGNORECASE)

    def _is_external_or_special_url(self, value: str) -> bool:
        lower = value.lower()
        return (
            lower.startswith(("http://", "https://", "data:", "mailto:", "tel:"))
            or lower.startswith("#")
            or "://" in lower
        )

    def _wrap_epub_html(self, title: str, body: str) -> str:
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    @page {{ margin: 20mm 16mm; }}
    body {{ font-family: serif; font-size: 11pt; line-height: 1.5; color: #1f2933; }}
    img {{ max-width: 100%; height: auto; }}
    h1, h2, h3 {{ page-break-after: avoid; }}
    p {{ margin: 0 0 0.75rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""

    def _extract_pdf_pages(self, pdf_path: Path) -> list[tuple[int, str]]:
        pages = []
        with fitz.open(pdf_path) as doc:
            for page_index, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append((page_index, text))
        return pages

    def _page_to_xhtml(self, page_number: int, text: str) -> str:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
        if not paragraphs:
            paragraphs = [text]
        rendered_paragraphs = "\n".join(
            f"    <p>{escape(' '.join(paragraph.split()))}</p>" for paragraph in paragraphs
        )
        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="pt-BR">
<head>
  <title>Pagina {page_number}</title>
  <link rel="stylesheet" href="styles.css" type="text/css"/>
</head>
<body>
  <section>
    <h1>Pagina {page_number}</h1>
{rendered_paragraphs}
  </section>
</body>
</html>"""

    def _container_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    def _content_opf(self, title: str, book_id: str, chapter_items: list[tuple[int, str, str]]) -> str:
        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="css" href="styles.css" media-type="text/css"/>',
        ]
        spine_items = []
        for index, chapter_filename, _chapter_html in chapter_items:
            manifest_items.append(
                f'<item id="chapter_{index:04d}" href="{chapter_filename}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="chapter_{index:04d}"/>')

        return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{escape(book_id)}</dc:identifier>
    <dc:title>{escape(title)}</dc:title>
    <dc:language>pt-BR</dc:language>
  </metadata>
  <manifest>
    {' '.join(manifest_items)}
  </manifest>
  <spine>
    {' '.join(spine_items)}
  </spine>
</package>"""

    def _nav_xhtml(self, title: str, chapter_items: list[tuple[int, str, str]]) -> str:
        links = "\n".join(
            f'      <li><a href="{escape(chapter_filename)}">Pagina {index}</a></li>'
            for index, chapter_filename, _chapter_html in chapter_items
        )
        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
  <title>{escape(title)}</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{escape(title)}</h1>
    <ol>
{links}
    </ol>
  </nav>
</body>
</html>"""

    def _epub_css(self) -> str:
        return """body {
  font-family: serif;
  line-height: 1.5;
}

h1 {
  font-size: 1.4rem;
}

p {
  margin: 0 0 0.8rem;
}
"""

    def _safe_stem(self, filename: str, output_suffix: str) -> str:
        safe_name = build_safe_filename(
            filename,
            default_stem="conversao",
            default_suffix=output_suffix,
        )
        return Path(safe_name).stem
