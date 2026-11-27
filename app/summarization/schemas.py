from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class TableData(BaseModel):
    headers: List[str] = Field(description="Table column headers, e.g., ['Feature', 'Programmed I/O', 'DMA']")
    rows: List[List[str]] = Field(description="Grid rows of cell data")
    caption: Optional[str] = Field(default=None, description="Optional academic caption for the table")

class ExamCallout(BaseModel):
    callout_type: str = Field(description="One of: definition, formula, example, imp_exam_point")
    title: str = Field(description="Short label, e.g., 'Key Definition: CPU Architecture' or '[IMP] Topic'")
    content: str = Field(description="Detailed explanation with high exam yield")

class SubSection(BaseModel):
    heading: str = Field(description="Section heading, e.g., '1.2 Principles of Stored Program Architecture'")
    explanation: str = Field(description="Comprehensive academic explanation without conversational fluff")
    table: Optional[TableData] = Field(default=None, description="Optional structured comparison or analytical data table")
    callouts: List[ExamCallout] = Field(default_factory=list, description="Definitions, formulas, examples, or exam points")
    bullet_points: List[str] = Field(default_factory=list, description="Key bullet points or characteristics")

class StructuredPage(BaseModel):
    page_number: int = Field(description="1-based page index")
    page_title: str = Field(description="Descriptive page topic title, e.g., 'Page 1: Foundations of Computer Systems'")
    category_badge: str = Field(default="ACADEMIC FOUNDATION", description="Badge label like 'ACADEMIC FOUNDATION' or 'IMP - EXAM FOCUS'")
    intro_paragraph: str = Field(description="Academic opening paragraph setting the context for this page's topics")
    sections: List[SubSection] = Field(description="List of core subtopics for this page")
    exam_summary: Optional[str] = Field(default=None, description="Concise exam takeaway summary for this page")

class MultiPageNotePlan(BaseModel):
    unit_number: int
    unit_title: str
    target_page_count: int
    pages: List[StructuredPage] = Field(description="Ordered sequence of structured academic pages")
