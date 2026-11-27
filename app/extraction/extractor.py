import re
from typing import List, Tuple
from pathlib import Path
import pymupdf as fitz

from app.pdf.reader import PDFReader
from app.pdf.metadata import ExtractedPage
from app.extraction.cleaner import HeaderFooterCleaner

class PDFTextExtractor:
    """
    Extracts text page-by-page using PyMuPDF.
    Detects unreadable/empty pages, detects OCR requirement, and preserves headings.
    """

    def __init__(self, cleaner: HeaderFooterCleaner = None):
        self.cleaner = cleaner or HeaderFooterCleaner()

    def extract_document(self, file_path: Path | str) -> List[ExtractedPage]:
        """Extract all pages from a PDF document with quality checks and cleaning."""
        extracted_pages: List[ExtractedPage] = []
        raw_pages_lines: List[List[str]] = []

        with PDFReader(file_path) as reader:
            doc = reader.doc
            total_pages = len(doc)

            # Phase 1: Raw extraction & basic page statistics
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1

                # Extract plain text
                raw_text = page.get_text("text") or ""
                lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                raw_pages_lines.append(lines)

                # Count images & text characters
                images = page.get_images()
                image_count = len(images)
                char_count = len(raw_text.strip())

                is_empty = char_count == 0
                # If page has very little text (< 50 chars) but has images, it likely needs OCR
                needs_ocr = (char_count < 50 and image_count > 0)
                is_unreadable = (char_count < 20 and not is_empty and not needs_ocr)

                # Extract headings based on font size or section patterns
                headings = self._detect_headings(page, raw_text)

                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        raw_text=raw_text,
                        is_empty=is_empty,
                        is_unreadable=is_unreadable,
                        needs_ocr=needs_ocr,
                        headings=headings,
                        char_count=char_count,
                        image_count=image_count,
                    )
                )

            # Phase 2: Identify and strip repeated running headers/footers
            boilerplate = self.cleaner.identify_boilerplate_lines(raw_pages_lines)
            for page_obj in extracted_pages:
                if not page_obj.is_empty:
                    page_obj.cleaned_text = self.cleaner.clean_page_text(page_obj.raw_text, boilerplate)
                else:
                    page_obj.cleaned_text = ""

        return extracted_pages

    def _detect_headings(self, page: fitz.Page, raw_text: str) -> List[str]:
        """Detect headings using both block font sizes and regex patterns."""
        headings: List[str] = []

        # Strategy 1: Font size analysis from text blocks
        try:
            blocks = page.get_text("dict").get("blocks", [])
            for b in blocks:
                if "lines" in b:
                    for line in b["lines"]:
                        for span in line["spans"]:
                            size = span.get("size", 10.0)
                            text = span.get("text", "").strip()
                            # Standard body text is ~10-12pt. Headings are typically >= 13pt
                            if size >= 13.0 and len(text) > 3 and len(text) < 120:
                                if text not in headings:
                                    headings.append(text)
        except Exception:
            pass

        # Strategy 2: Numbered section regex patterns (e.g., "1.0 Introduction", "1.1 Objectives")
        section_pattern = re.compile(r'^\s*(\d+\.\d+(?:\.\d+)?)\s+([A-Z][A-Za-z0-9\s,\-\(\)]{3,80})$', re.MULTILINE)
        for match in section_pattern.finditer(raw_text):
            heading_text = f"{match.group(1)} {match.group(2).strip()}"
            if heading_text not in headings:
                headings.append(heading_text)

        return headings
