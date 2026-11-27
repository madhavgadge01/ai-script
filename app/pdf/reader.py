import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple
import pymupdf as fitz

class PDFReader:
    """Handles PyMuPDF document loading, validation, and SHA-256 computation."""

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found at: {self.file_path}")
        self._doc = None

    def __enter__(self):
        self._doc = fitz.open(str(self.file_path))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._doc:
            self._doc.close()

    @property
    def doc(self) -> fitz.Document:
        if self._doc is None or self._doc.is_closed:
            self._doc = fitz.open(str(self.file_path))
        return self._doc

    def get_sha256(self) -> str:
        """Compute SHA-256 hash of the source PDF for duplicate detection."""
        hasher = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_metadata(self) -> Dict[str, Any]:
        """Extract native PDF metadata."""
        meta = self.doc.metadata or {}
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "page_count": len(self.doc),
            "file_size_bytes": self.file_path.stat().st_size,
        }

    def close(self):
        if self._doc and not self._doc.is_closed:
            self._doc.close()
