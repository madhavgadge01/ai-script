import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Comment
from jinja2 import Environment, FileSystemLoader

from config.settings import settings
from app.pdf.metadata import AcademicHierarchy
from app.summarization.schemas import MultiPageNotePlan, StructuredPage
from app.database.connection import get_db, init_db

ALLOWED_TAGS = {
    'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'caption', 'strong', 'em', 'b', 'i', 'u', 'code', 'pre',
    'blockquote', 'br', 'hr', 'aside', 'article', 'section'
}

ALLOWED_ATTRIBUTES = {
    'class', 'id', 'colspan', 'rowspan', 'scope', 'aria-hidden'
}

class HTMLNoteGenerator:
    """
    Renders structured academic note plans into clean, semantic HTML pages
    using Jinja2 templates, Notes Guru native CSS classes, and a robust
    parser-based allowlist sanitizer.
    """

    def __init__(self, templates_dir: Path = None, db_path: Path = None):
        self.templates_dir = templates_dir or settings.templates_dir
        self.db_path = db_path or settings.db_path
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True
        )
        init_db(self.db_path)

    def sanitize_html(self, raw_html: str) -> str:
        """
        Parser-based allowlist HTML sanitizer using BeautifulSoup.
        Guarantees that no script tags, event handlers, or unsafe elements
        can execute, while preserving legitimate academic HTML, tables,
        mathematical comparison symbols, and code blocks.
        """
        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Strip comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. Decompose dangerous tags completely
        for tag in soup.find_all(['script', 'iframe', 'object', 'embed', 'applet', 'meta', 'link', 'style']):
            tag.decompose()

        # 3. Process remaining tags
        for tag in soup.find_all():
            if tag.name not in ALLOWED_TAGS:
                # Unwrap tag, keeping its inner text/content
                tag.unwrap()
            else:
                # Sanitize attributes
                allowed_attrs = {}
                for attr, val in list(tag.attrs.items()):
                    # Strip any event handler attribute like onclick, onerror
                    if attr.lower().startswith('on'):
                        continue
                    if attr.lower() in ALLOWED_ATTRIBUTES:
                        allowed_attrs[attr] = val
                tag.attrs = allowed_attrs

        # Return sanitized HTML without wrapping html/body tags
        return "".join(str(c) for c in soup.contents).strip()

    def render_single_page(self, page: StructuredPage) -> str:
        """Render a single structured page to semantic HTML."""
        template = self.env.get_template("page.html")
        rendered = template.render(page=page)
        return self.sanitize_html(rendered)

    def render_and_export_unit(
        self,
        hierarchy: AcademicHierarchy,
        plan: MultiPageNotePlan,
        export_dir: Path = None,
    ) -> Dict[str, Any]:
        """
        Renders all structured pages in the plan, saves individual HTML pages,
        creates the master preview HTML book, and persists records in SQLite.
        """
        target_dir = export_dir or settings.exports_dir
        unit_slug = f"{hierarchy.course}_{hierarchy.subject_code}_U{hierarchy.unit_number}"
        unit_dir = target_dir / unit_slug
        unit_dir.mkdir(parents=True, exist_ok=True)

        unit_id = f"{hierarchy.course}_{hierarchy.subject_code}_B{hierarchy.block_number}_U{hierarchy.unit_number}"
        rendered_pages_data = []

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            # Clear old pages if reprocessing
            cursor.execute("DELETE FROM generated_pages WHERE unit_id = ?", (unit_id,))

            for page in plan.pages:
                page_html = self.render_single_page(page)
                page_file = unit_dir / f"page_{page.page_number:02d}.html"
                page_file.write_text(page_html, encoding="utf-8")

                # Store in SQLite (replace if exists)
                cursor.execute("""
                    INSERT OR REPLACE INTO generated_pages (id, unit_id, page_number, page_title, content_html)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    f"{unit_id}_p{page.page_number}",
                    unit_id,
                    page.page_number,
                    page.page_title,
                    page_html
                ))

                rendered_pages_data.append({
                    "page_number": page.page_number,
                    "page_title": page.page_title,
                    "file_path": str(page_file),
                    "rendered_html": page_html,
                    "category_badge": page.category_badge,
                })

        # Render complete previewer document
        preview_template = self.env.get_template("preview_book.html")
        preview_html = preview_template.render(
            university=hierarchy.university,
            course=hierarchy.course,
            subject_code=hierarchy.subject_code,
            subject_name=hierarchy.subject_name,
            block_number=hierarchy.block_number,
            block_title=hierarchy.block_title,
            unit_number=hierarchy.unit_number,
            unit_title=hierarchy.unit_title,
            total_pages=len(plan.pages),
            pages=rendered_pages_data
        )

        preview_file = unit_dir / "index_preview.html"
        preview_file.write_text(preview_html, encoding="utf-8")

        return {
            "unit_id": unit_id,
            "unit_title": hierarchy.unit_title,
            "total_pages": len(rendered_pages_data),
            "pages": rendered_pages_data,
            "preview_file": str(preview_file),
            "export_dir": str(unit_dir),
        }
