from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AcademicHierarchy(BaseModel):
    university: str = "IGNOU"
    course: str                          # e.g., "BCA", "BA"
    semester: Optional[str] = None       # e.g., "Semester 1"
    subject_code: str                    # e.g., "BCS-011"
    subject_name: str                    # e.g., "Computer Basics and PC Software"
    block_number: int                    # e.g., 1
    block_title: str                     # e.g., "Basics of Computer Hardware"
    unit_number: int                     # e.g., 1
    unit_title: str                      # e.g., "Computers, their Origin and Applications"

class TextSpan(BaseModel):
    text: str
    size: float
    flags: int
    font: str
    is_bold: bool = False
    is_italic: bool = False

class ExtractedPage(BaseModel):
    page_number: int
    raw_text: str
    cleaned_text: str = ""
    is_empty: bool = False
    is_unreadable: bool = False
    needs_ocr: bool = False
    headings: List[str] = Field(default_factory=list)
    char_count: int = 0
    image_count: int = 0
