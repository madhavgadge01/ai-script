import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

class QualityAssuranceEngine:
    """
    Automated verification of generated study notes prior to publishing.
    Validates completeness, academic density, formula preservation, and HTML compliance.
    """

    FORBIDDEN_PLACEHOLDERS = [
        "lorem ipsum", "placeholder", "todo", "tbd", "sample content",
        "page content...", "insert here", "coming soon", "asdf"
    ]

    REQUIRED_HTML_CLASSES = [
        "note-chapter",
        "chapter-badge",
        "ng-tag"
    ]

    @classmethod
    def audit_pages(
        cls,
        pages: List[Dict[str, Any]],
        expected_topics: Optional[List[str]] = None,
        min_chars_per_page: int = 500
    ) -> Dict[str, Any]:
        """
        Executes comprehensive QA check across all pages of a unit note.
        """
        report: Dict[str, Any] = {
            "passed": True,
            "total_pages": len(pages),
            "topic_coverage_percent": 100.0,
            "missing_topics": [],
            "issues": [],
            "warnings": [],
            "pages_stats": []
        }

        if not pages:
            report["passed"] = False
            report["issues"].append("Zero pages provided for QA audit.")
            return report

        all_text_combined = ""
        expected_page_num = 1

        for p in pages:
            p_num = p.get("pageNumber", 0)
            p_title = p.get("title", "")
            html = p.get("contentHtml", "")

            p_stat = {
                "pageNumber": p_num,
                "title": p_title,
                "length_chars": len(html),
                "has_h1": False,
                "has_h2": False,
                "has_callouts": False,
                "has_formulas": False,
                "placeholders_found": []
            }

            # Check sequential page numbering
            if p_num != expected_page_num:
                report["passed"] = False
                report["issues"].append(f"Non-sequential page number: expected {expected_page_num}, got {p_num}.")
            expected_page_num += 1

            # Check minimum density
            if len(html) < min_chars_per_page:
                report["passed"] = False
                report["issues"].append(
                    f"Page {p_num} is too short ({len(html)} chars; minimum required is {min_chars_per_page})."
                )

            # Check placeholders
            lower_html = html.lower()
            for ph in cls.FORBIDDEN_PLACEHOLDERS:
                if ph in lower_html:
                    report["passed"] = False
                    report["issues"].append(f"Forbidden placeholder '{ph}' detected in Page {p_num}.")
                    p_stat["placeholders_found"].append(ph)

            # Check HTML structure and classes
            soup = BeautifulSoup(html, "html.parser")
            p_stat["has_h1"] = bool(soup.find("h1"))
            p_stat["has_h2"] = bool(soup.find("h2"))
            p_stat["has_callouts"] = bool(soup.find_all("div", class_=re.compile(r"callout|ng-highlight")))
            p_stat["has_formulas"] = any(sym in html for sym in ["=", "*", "/", "\\(", "\\[", "$", "CPI", "AMAT", "O("])

            for req_cls in cls.REQUIRED_HTML_CLASSES:
                if not soup.find(class_=req_cls):
                    report["warnings"].append(f"Page {p_num} missing standard class '{req_cls}'.")

            all_text_combined += " " + soup.get_text()
            p_stat["char_count"] = len(html)
            report["pages_stats"].append(p_stat)

        # Check topic coverage if expected topics supplied
        if expected_topics:
            combined_lower = all_text_combined.lower()
            covered = 0
            for topic in expected_topics:
                # Basic token match
                tokens = [t.lower() for t in topic.split() if len(t) > 3]
                if any(tok in combined_lower for tok in tokens):
                    covered += 1
                else:
                    report["missing_topics"].append(topic)

            report["topic_coverage_percent"] = round((covered / len(expected_topics)) * 100, 1) if expected_topics else 100.0
            if report["topic_coverage_percent"] < 60.0:
                report["warnings"].append(
                    f"Low syllabus topic coverage: {report['topic_coverage_percent']}% of expected topics detected."
                )

        return report
