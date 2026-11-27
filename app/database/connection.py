import sqlite3
from pathlib import Path
from contextlib import contextmanager
from config.settings import settings

def init_db(db_path: Path = None) -> None:
    """Initialize SQLite database schema."""
    target_path = db_path or settings.db_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(target_path)) as conn:
        cursor = conn.cursor()
        
        # Table 1: Unit Academic Metadata & Processing Status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS units (
                id TEXT PRIMARY KEY,
                university TEXT NOT NULL,
                course TEXT NOT NULL,
                semester TEXT,
                subject_code TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                block_number INTEGER NOT NULL,
                block_title TEXT NOT NULL,
                unit_number INTEGER NOT NULL,
                unit_title TEXT NOT NULL,
                source_pdf_path TEXT,
                source_pdf_hash TEXT,
                status TEXT NOT NULL,
                total_pages INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 2: Processing Runs & Token/Cost Metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_runs (
                id TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                model_used TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                duration_seconds REAL DEFAULT 0.0,
                retry_count INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES units(id)
            )
        """)

        # Table 3: Chunks & Checkpoints for Resume Support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunk_checkpoints (
                id TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                heading TEXT,
                raw_text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                summarized_json TEXT,
                status TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES units(id)
            )
        """)

        # Table 4: Generated Structured HTML Pages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_pages (
                id TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                page_title TEXT NOT NULL,
                content_html TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES units(id)
            )
        """)

        conn.commit()

@contextmanager
def get_db(db_path: Path = None):
    """Context manager for SQLite connections with row dict support."""
    target_path = db_path or settings.db_path
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
