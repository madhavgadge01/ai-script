from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    SUMMARIZING = "SUMMARIZING"
    SUMMARIZED = "SUMMARIZED"
    HTML_GENERATED = "HTML_GENERATED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"

class UnitMetadata(BaseModel):
    id: str
    university: str = "IGNOU"
    course: str                          # e.g., "BCA", "BA"
    semester: Optional[str] = None       # e.g., "Semester 1" or None
    subject_code: str                    # e.g., "BCS-011"
    subject_name: str                    # e.g., "Computer Basics and PC Software"
    block_number: int                    # e.g., 1
    block_title: str                     # e.g., "Basics of Computer Hardware"
    unit_number: int                     # e.g., 1
    unit_title: str                      # e.g., "Computers, their Origin and Applications"
    source_pdf_path: Optional[str] = None
    source_pdf_hash: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    total_pages: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ProcessingRun(BaseModel):
    id: str
    unit_id: str
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    retry_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

class ChunkCheckpoint(BaseModel):
    id: str
    unit_id: str
    chunk_index: int
    heading: Optional[str] = None
    raw_text: str
    cleaned_text: str
    summarized_json: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    updated_at: Optional[datetime] = None

class GeneratedPageRecord(BaseModel):
    id: str
    unit_id: str
    page_number: int
    page_title: str
    content_html: str
    created_at: Optional[datetime] = None
