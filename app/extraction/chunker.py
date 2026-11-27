import re
from typing import List, Optional
from pydantic import BaseModel, Field
from app.pdf.metadata import ExtractedPage

class Chunk(BaseModel):
    chunk_index: int
    heading: str
    content: str
    page_numbers: List[int]
    word_count: int
    char_count: int

class SemanticChunker:
    """
    Chunks extracted unit text logically along sections and headings.
    Ensures chunks do not exceed max_chars while preserving atomic topic context.
    """

    def __init__(self, max_chars: int = 4000, overlap_chars: int = 200):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def create_chunks(self, pages: List[ExtractedPage]) -> List[Chunk]:
        """
        Consolidates pages into section-aware chunks.
        Never drops content.
        """
        chunks: List[Chunk] = []
        current_chunk_pages: List[int] = []
        current_heading: str = "Overview"
        current_text_segments: List[str] = []
        current_char_count = 0
        chunk_idx = 1

        # Section start pattern: e.g. "1.0 INTRODUCTION", "2.1 MEMORY SYSTEM"
        heading_regex = re.compile(r'^(?:(?:\d+\.\d+(?:\.\d+)?)|(?:Unit\s+\d+)|(?:Section\s+\d+))\s+.*$', re.IGNORECASE)

        for page in pages:
            if page.is_empty or not page.cleaned_text.strip():
                continue

            page_lines = page.cleaned_text.split("\n")
            for line in page_lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Detect if this line represents a major topic boundary
                is_heading = heading_regex.match(stripped) or (stripped in page.headings)

                if is_heading and current_char_count >= 1500:
                    # Flush current chunk
                    full_content = "\n".join(current_text_segments).strip()
                    if full_content:
                        chunks.append(
                            Chunk(
                                chunk_index=chunk_idx,
                                heading=current_heading,
                                content=full_content,
                                page_numbers=sorted(list(set(current_chunk_pages))),
                                word_count=len(full_content.split()),
                                char_count=len(full_content),
                            )
                        )
                        chunk_idx += 1

                    # Reset for next chunk
                    current_heading = stripped
                    current_text_segments = [stripped]
                    current_chunk_pages = [page.page_number]
                    current_char_count = len(stripped)
                    continue

                # Check if adding this line would exceed max_chars
                if current_char_count + len(stripped) > self.max_chars and current_char_count >= 1000:
                    full_content = "\n".join(current_text_segments).strip()
                    if full_content:
                        chunks.append(
                            Chunk(
                                chunk_index=chunk_idx,
                                heading=current_heading,
                                content=full_content,
                                page_numbers=sorted(list(set(current_chunk_pages))),
                                word_count=len(full_content.split()),
                                char_count=len(full_content),
                            )
                        )
                        chunk_idx += 1

                    # Keep heading context
                    current_text_segments = [f"[Continued from {current_heading}]", stripped]
                    current_chunk_pages = [page.page_number]
                    current_char_count = len(stripped)
                else:
                    current_text_segments.append(line)
                    if page.page_number not in current_chunk_pages:
                        current_chunk_pages.append(page.page_number)
                    current_char_count += len(line) + 1

        # Flush final remaining chunk
        full_content = "\n".join(current_text_segments).strip()
        if full_content:
            chunks.append(
                Chunk(
                    chunk_index=chunk_idx,
                    heading=current_heading,
                    content=full_content,
                    page_numbers=sorted(list(set(current_chunk_pages))),
                    word_count=len(full_content.split()),
                    char_count=len(full_content),
                )
            )

        return chunks
