import re
from typing import List, Dict, Set
from collections import Counter

class HeaderFooterCleaner:
    """
    Identifies and removes repeating headers and footers across pages.
    Analyzes lines in the top 10% and bottom 10% vertical margins.
    """

    def __init__(self, repetition_threshold: float = 0.5):
        self.repetition_threshold = repetition_threshold

    def identify_boilerplate_lines(self, pages_lines: List[List[str]]) -> Set[str]:
        """
        Identify lines that appear repeatedly in header/footer zones across multiple pages.
        """
        total_pages = len(pages_lines)
        if total_pages < 2:
            return set()

        line_counts = Counter()
        for lines in pages_lines:
            # Look at top 3 and bottom 3 lines of each page
            candidate_lines = set()
            if lines:
                candidate_lines.update([l.strip() for l in lines[:3] if len(l.strip()) > 3])
                candidate_lines.update([l.strip() for l in lines[-3:] if len(l.strip()) > 3])
            for l in candidate_lines:
                # Ignore pure page numbers like '1', '2', 'Page 1'
                normalized = re.sub(r'^\s*(?:page\s*)?\d+\s*$', '', l, flags=re.IGNORECASE).strip()
                if normalized:
                    line_counts[normalized] += 1

        boilerplate = set()
        for line, count in line_counts.items():
            if (count / total_pages) >= self.repetition_threshold:
                boilerplate.add(line)

        return boilerplate

    def clean_page_text(self, text: str, boilerplate: Set[str]) -> str:
        """
        Removes identified boilerplate lines and standalone page number indicators.
        """
        cleaned_lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            # Check if line matches boilerplate
            norm = re.sub(r'^\s*(?:page\s*)?\d+\s*$', '', stripped, flags=re.IGNORECASE).strip()
            if norm in boilerplate:
                continue
            # Remove isolated page number lines
            if re.match(r'^\s*(?:page\s*)?\d+\s*$', stripped, flags=re.IGNORECASE):
                continue
            cleaned_lines.append(line)

        # Normalize multiple blank lines
        result = "\n".join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result).strip()
        return result
