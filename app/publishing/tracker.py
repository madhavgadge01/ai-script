import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from config.settings import settings
from app.database.connection import get_db

class CourseProgressTracker:
    """
    Persistent SQLite progress tracker for the course-wide BCA content pipeline.
    Maintains status for every semester, subject, block, and unit.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self._ensure_table()

    def _ensure_table(self):
        """Creates the course_progress_tracker table if it does not exist."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS course_progress_tracker (
                    unit_key TEXT PRIMARY KEY,
                    semester INTEGER NOT NULL,
                    subject_code TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    block_number INTEGER NOT NULL,
                    block_title TEXT NOT NULL,
                    unit_number INTEGER NOT NULL,
                    unit_title TEXT NOT NULL,
                    source_status TEXT DEFAULT 'PENDING_SOURCE',
                    license_status TEXT DEFAULT 'ORIGINAL_ACADEMIC_SYNTHESIS',
                    commercial_allowed INTEGER DEFAULT 1,
                    extraction_status TEXT DEFAULT 'NOT_STARTED',
                    summarization_status TEXT DEFAULT 'NOT_STARTED',
                    qa_status TEXT DEFAULT 'PENDING',
                    qa_details TEXT,
                    publishing_status TEXT DEFAULT 'NOT_STARTED',
                    notes_guru_course_id TEXT,
                    notes_guru_semester_id TEXT,
                    notes_guru_subject_id TEXT,
                    notes_guru_block_id TEXT,
                    notes_guru_unit_id TEXT,
                    notes_guru_note_id TEXT,
                    public_url TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def initialize_from_inventory(self, inventory_path: str = "config/bca_syllabus_inventory.json"):
        """Populates the tracker with all units from the inventory if not present."""
        inv_file = Path(inventory_path)
        if not inv_file.exists():
            raise FileNotFoundError(f"Inventory '{inventory_path}' not found.")
        data = json.loads(inv_file.read_text(encoding="utf-8"))

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            for sem in data.get("semesters", []):
                s_num = sem["semester_number"]
                for subj in sem.get("subjects", []):
                    s_code = subj["code"]
                    s_name = subj["name"]
                    for blk in subj.get("blocks", []):
                        b_num = blk["block_number"]
                        b_title = blk["title"]
                        for u in blk.get("units", []):
                            u_num = u["unit_number"]
                            u_title = u["title"]
                            unit_key = f"BCA_SEM{s_num}_{s_code}_B{b_num}_U{u_num}"

                            cursor.execute("""
                                INSERT OR IGNORE INTO course_progress_tracker (
                                    unit_key, semester, subject_code, subject_name,
                                    block_number, block_title, unit_number, unit_title
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                unit_key, s_num, s_code, s_name, b_num, b_title, u_num, u_title
                            ))

    def update_unit_status(self, unit_key: str, **kwargs):
        """Updates fields for a specific unit in the tracker."""
        if not kwargs:
            return
        allowed_cols = {
            "source_status", "license_status", "commercial_allowed",
            "extraction_status", "summarization_status", "qa_status",
            "qa_details", "publishing_status", "notes_guru_course_id",
            "notes_guru_semester_id", "notes_guru_subject_id",
            "notes_guru_block_id", "notes_guru_unit_id", "notes_guru_note_id",
            "public_url"
        }
        updates = []
        params = []
        for col, val in kwargs.items():
            if col in allowed_cols:
                updates.append(f"{col} = ?")
                params.append(val)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(unit_key)

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            query = f"UPDATE course_progress_tracker SET {', '.join(updates)} WHERE unit_key = ?"
            cursor.execute(query, params)

    def get_unit_status(self, unit_key: str) -> Optional[Dict[str, Any]]:
        """Fetch status dictionary for a specific unit."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM course_progress_tracker WHERE unit_key = ?", (unit_key,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_units(self, semester: Optional[int] = None, subject_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all tracked units with optional filtering."""
        query = "SELECT * FROM course_progress_tracker"
        params = []
        conditions = []
        if semester is not None:
            conditions.append("semester = ?")
            params.append(semester)
        if subject_code is not None:
            conditions.append("subject_code = ?")
            params.append(subject_code.upper())
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY semester, subject_code, block_number, unit_number"

        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Calculates course-wide completion metrics."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT semester) FROM course_progress_tracker")
            total_semesters = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(DISTINCT subject_code) FROM course_progress_tracker")
            total_subjects = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(DISTINCT subject_code || '_B' || block_number) FROM course_progress_tracker")
            total_blocks = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM course_progress_tracker")
            total_units = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM course_progress_tracker WHERE publishing_status = 'PUBLISHED'")
            completed_notes = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM course_progress_tracker WHERE publishing_status LIKE '%BLOCKED%'")
            blocked_units = cursor.fetchone()[0] or 0

            pending_notes = total_units - completed_notes - blocked_units

            # Semester breakdown
            cursor.execute("""
                SELECT semester, COUNT(*) as units_count,
                       SUM(CASE WHEN publishing_status = 'PUBLISHED' THEN 1 ELSE 0 END) as published_count,
                       SUM(CASE WHEN publishing_status LIKE '%BLOCKED%' THEN 1 ELSE 0 END) as blocked_count
                FROM course_progress_tracker
                GROUP BY semester
                ORDER BY semester
            """)
            sem_breakdown = [dict(r) for r in cursor.fetchall()]

            return {
                "total_semesters": total_semesters,
                "total_subjects": total_subjects,
                "total_blocks": total_blocks,
                "total_units": total_units,
                "completed_notes": completed_notes,
                "pending_notes": pending_notes,
                "blocked_units": blocked_units,
                "semesters_breakdown": sem_breakdown
            }
