import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Base project paths
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
RAW_PDFS_DIR = STORAGE_DIR / "raw_pdfs"
CHECKPOINTS_DIR = STORAGE_DIR / "checkpoints"
EXPORTS_DIR = STORAGE_DIR / "exports"
TEMPLATES_DIR = BASE_DIR / "templates"

# Load environment variables
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    # Gemini Configuration
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))

    # Cost & Rate Limiting Controls
    max_tokens_per_doc: int = Field(default_factory=lambda: int(os.getenv("MAX_TOKENS_PER_DOC", "100000")))
    max_cost_usd_per_doc: float = Field(default_factory=lambda: float(os.getenv("MAX_COST_USD_PER_DOC", "0.25")))
    auto_approve_cost: bool = Field(default_factory=lambda: os.getenv("AUTO_APPROVE_COST", "false").lower() == "true")

    # Storage Paths
    base_dir: Path = BASE_DIR
    storage_dir: Path = STORAGE_DIR
    raw_pdfs_dir: Path = RAW_PDFS_DIR
    checkpoints_dir: Path = CHECKPOINTS_DIR
    exports_dir: Path = EXPORTS_DIR
    templates_dir: Path = TEMPLATES_DIR
    db_path: Path = STORAGE_DIR / "uninotes.db"

    # Notes Guru Admin Backend
    notes_guru_api_base: str = Field(
        default_factory=lambda: os.getenv("NOTES_GURU_API_BASE", "https://notes-guru-production.up.railway.app/api")
    )
    notes_guru_admin_token: str = Field(default_factory=lambda: os.getenv("NOTES_GURU_ADMIN_TOKEN", ""))

    def ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.raw_pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
