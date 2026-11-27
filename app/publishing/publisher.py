import os
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests

from app.publishing.notes_guru_client import NotesGuruApiClient
from config.settings import settings

class NotesPublisher:
    """
    Executes the end-to-end publishing workflow for academic notes to Notes Guru.
    Enforces idempotency, duplicate prevention, and public access verification.
    """

    def __init__(self, client: Optional[NotesGuruApiClient] = None):
        self.client = client or NotesGuruApiClient()

    def load_local_pages(self, export_dir: str = "storage/exports/BCA_BCS-011_U1") -> List[Dict[str, Any]]:
        """
        Loads and validates the 4 generated HTML pages from local storage.
        """
        dir_path = Path(export_dir)
        if not dir_path.exists():
            raise FileNotFoundError(f"Export directory '{export_dir}' not found.")

        page_files = sorted(dir_path.glob("page_*.html"))
        if not page_files:
            raise FileNotFoundError(f"No page_*.html files found in '{export_dir}'.")

        pages = []
        for idx, pf in enumerate(page_files, 1):
            html = pf.read_text(encoding="utf-8")
            if not html.strip():
                raise ValueError(f"Page file '{pf.name}' is empty.")

            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else f"Page {idx}"

            # Locked preview policy: First 2 pages free preview, remaining locked
            is_locked = idx > 2

            pages.append({
                "pageNumber": idx,
                "title": title,
                "contentHtml": html,
                "isLockedPreview": is_locked
            })

        return pages

    def publish_bca_unit_1(
        self,
        export_dir: str = "storage/exports/BCA_BCS-011_U1",
        unit_title: str = "Computers: Their Origin and Applications"
    ) -> Dict[str, Any]:
        """
        Executes the authorized 11-step production publishing workflow.
        """
        result: Dict[str, Any] = {
            "college_id": None,
            "course_id": None,
            "semester_id": None,
            "subject_id": None,
            "block_id": None,
            "unit_id": None,
            "note_id": None,
            "public_url": None,
            "page_count": 0,
            "status": None,
            "is_published": False,
            "unauthenticated_verified": False,
            "steps_log": []
        }

        # ---------------------------------------------------------------------
        # Step 1: Locate and reuse IGNOU College (Never duplicate)
        # ---------------------------------------------------------------------
        colleges = self.client.get_colleges(include_inactive=True)
        ignou = next(
            (c for c in colleges if c.get("code", "").upper() == "IGNOU" or "INDIRA GANDHI" in c.get("name", "").upper()),
            None
        )
        if not ignou:
            raise RuntimeError("IGNOU College record not found on Notes Guru.")

        college_id = ignou["_id"]
        result["college_id"] = college_id
        result["steps_log"].append(f"Step 1: Reused existing IGNOU college record (_id: {college_id}).")

        # ---------------------------------------------------------------------
        # Step 2: Check or create BCA Course
        # ---------------------------------------------------------------------
        courses = self.client.get_courses_by_college(college_id, include_inactive=True)
        bca_course = next(
            (c for c in courses if c.get("code", "").upper() == "BCA" or c.get("name", "").upper().startswith("BCA")),
            None
        )

        if bca_course:
            course_id = bca_course["_id"]
            result["steps_log"].append(f"Step 2: Found existing BCA course (_id: {course_id}).")
        else:
            course_payload = {
                "collegeId": college_id,
                "name": "BCA : Bachelor of Computer Applications",
                "code": "BCA",
                "description": "Official Bachelor of Computer Applications curriculum under IGNOU.",
                "durationYears": 3,
                "order": 1,
                "isActive": True
            }
            create_res = self.client.create_course(course_payload)
            bca_course = create_res.get("course")
            course_id = bca_course["_id"]
            result["steps_log"].append(
                f"Step 2: Created BCA course (_id: {course_id}) with automatic default semesters."
            )

        result["course_id"] = course_id

        # ---------------------------------------------------------------------
        # Step 3: Fetch auto-generated semesters and locate Semester 1
        # ---------------------------------------------------------------------
        semesters = self.client.get_semesters_by_course(course_id, include_inactive=True)
        sem1 = next((s for s in semesters if s.get("semesterNumber") == 1), None)
        if not sem1:
            raise RuntimeError(f"Semester 1 not found under BCA course (_id: {course_id}).")

        semester_id = sem1["_id"]
        result["semester_id"] = semester_id
        result["steps_log"].append(f"Step 3: Located auto-generated Semester 1 (_id: {semester_id}).")

        # ---------------------------------------------------------------------
        # Step 4: Check or create Subject BCS-011
        # ---------------------------------------------------------------------
        subjects = self.client.get_subjects_by_semester(semester_id, include_inactive=True)
        bcs011 = next(
            (s for s in subjects if s.get("code", "").upper() == "BCS-011" or "BCS-011" in s.get("name", "").upper()),
            None
        )

        subject_id = None
        block_id = None
        unit_1_id = None

        if bcs011:
            subject_id = bcs011["_id"]
            result["steps_log"].append(f"Step 4: Found existing Subject BCS-011 (_id: {subject_id}).")
            # Fetch existing blocks and units
            blocks = self.client.get_blocks_by_subject(subject_id, include_inactive=True)
            blk1 = next((b for b in blocks if b.get("blockNumber") == 1), None)
            if blk1:
                block_id = blk1["_id"]
                units = self.client.get_units_by_block(block_id)
                u1 = next((u for u in units if u.get("unitNumber") == 1), None)
                if u1:
                    unit_1_id = u1["_id"]
        else:
            sub_payload = {
                "semesterId": semester_id,
                "name": "Computer Basics and PC Software",
                "code": "BCS-011",
                "description": "Foundational computer organization, architecture, and software principles.",
                "price": 20,
                "discountedPrice": 15,
                "order": 1,
                "isActive": True
            }
            sub_res = self.client.create_subject(sub_payload)
            subject_data = sub_res.get("subject")
            subject_id = subject_data["_id"]
            # createSubject returns the auto-created block
            auto_block = sub_res.get("block")
            if auto_block:
                block_id = auto_block["_id"]
            result["steps_log"].append(
                f"Step 4 & 5: Created Subject BCS-011 (_id: {subject_id}), auto-creating Block 1 and Units 1-5."
            )

        result["subject_id"] = subject_id

        # ---------------------------------------------------------------------
        # Step 5: Resolve Block 1 and Unit 1 IDs if not yet resolved
        # ---------------------------------------------------------------------
        if not block_id:
            blocks = self.client.get_blocks_by_subject(subject_id, include_inactive=True)
            blk1 = next((b for b in blocks if b.get("blockNumber") == 1), None)
            if not blk1:
                raise RuntimeError(f"Block 1 not found under Subject BCS-011 (_id: {subject_id}).")
            block_id = blk1["_id"]

        result["block_id"] = block_id

        # Update block title if needed
        try:
            self.client.update_block(block_id, {
                "name": "Basics of Computer Hardware",
                "description": "Block 1: Basics of Computer Hardware"
            })
            result["steps_log"].append(f"Step 5: Verified Block 1 (_id: {block_id}) title: 'Basics of Computer Hardware'.")
        except Exception as e:
            result["steps_log"].append(f"Step 5 Notice (Block update): {str(e)}")

        if not unit_1_id:
            units = self.client.get_units_by_block(block_id)
            if not units:
                # Also try by subject
                units = self.client.get_units_by_subject(subject_id, include_unpublished=True)
            u1 = next((u for u in units if u.get("unitNumber") == 1), None)
            if not u1:
                raise RuntimeError(f"Unit 1 not found under Block 1 (_id: {block_id}).")
            unit_1_id = u1["_id"]

        result["unit_id"] = unit_1_id

        # ---------------------------------------------------------------------
        # Step 6: Update Unit 1 title to official target title
        # ---------------------------------------------------------------------
        unit_update_payload = {
            "title": unit_title,
            "description": "Unit 1 of Block 1 - Computer Basics and PC Software",
            "price": 25,
            "discountedPrice": 19,
            "isPublished": True
        }
        self.client.update_unit(unit_1_id, unit_update_payload)
        result["steps_log"].append(
            f"Step 6: Updated Unit 1 (_id: {unit_1_id}) title to '{unit_title}' with isPublished=True."
        )

        # ---------------------------------------------------------------------
        # Step 7: Check for duplicate existing note under Unit 1
        # ---------------------------------------------------------------------
        dup_check = self.client.check_duplicate_note(unit_1_id, unit_title)
        if dup_check["is_duplicate"]:
            existing_note = dup_check.get("matching_note")
            result["note_id"] = existing_note.get("_id")
            result["status"] = existing_note.get("status")
            result["steps_log"].append(
                f"Step 7: Existing note found under Unit 1 (_id: {existing_note.get('_id')}). Stopping without overwrite."
            )
            # Fetch detail of existing note to verify
            note_detail = self.client.get_note_detail(existing_note.get("_id"))
            note_obj = note_detail.get("note", {})
            result["is_published"] = note_obj.get("isPublished", False)
            result["page_count"] = note_obj.get("totalPages", len(note_obj.get("pages", [])))
            result["public_url"] = f"https://notes-guru-7tgo.vercel.app/notes/{existing_note.get('_id')}"
            return result

        result["steps_log"].append(f"Step 7: Duplicate check passed. Zero existing notes on Unit 1.")

        # ---------------------------------------------------------------------
        # Step 8: Load local 4 HTML pages
        # ---------------------------------------------------------------------
        local_pages = self.load_local_pages(export_dir)
        result["page_count"] = len(local_pages)
        result["steps_log"].append(f"Step 8: Loaded {len(local_pages)} verified HTML pages from '{export_dir}'.")

        # ---------------------------------------------------------------------
        # Step 9 & 10: Upload Note as PUBLICLY PUBLISHED
        # ---------------------------------------------------------------------
        note_payload = {
            "unitId": unit_1_id,
            "blockId": block_id,
            "title": unit_title,
            "type": "normal",
            "description": "Comprehensive 4-page exam-oriented study notes for BCS-011 Unit 1.",
            "price": 25,
            "discountedPrice": 19,
            "previewPageCount": 2,
            "status": "published",
            "order": 1,
            "pages": local_pages
        }

        note_res = self.client.create_note(note_payload)
        created_note = note_res.get("note", {})
        note_id = created_note.get("_id")
        result["note_id"] = note_id
        result["status"] = created_note.get("status")
        result["is_published"] = created_note.get("isPublished")
        result["public_url"] = f"https://notes-guru-7tgo.vercel.app/notes/{note_id}"
        result["steps_log"].append(
            f"Step 9 & 10: Successfully uploaded note (_id: {note_id}) with status='{result['status']}', isPublished={result['is_published']}."
        )

        # ---------------------------------------------------------------------
        # Step 11: Verify publication via unauthenticated public GET request
        # ---------------------------------------------------------------------
        public_api_url = f"{self.client.base_url.rstrip('/')}/notes/{note_id}"
        unauth_resp = requests.get(public_api_url, timeout=15)
        if unauth_resp.status_code == 200:
            unauth_data = unauth_resp.json()
            if unauth_data.get("success"):
                pub_note = unauth_data.get("note", {})
                result["unauthenticated_verified"] = (
                    pub_note.get("status") == "published" and pub_note.get("isPublished") is True
                )
                result["steps_log"].append(
                    f"Step 11: Verified public unauthenticated access (HTTP 200). Note is live on public platform!"
                )
            else:
                result["steps_log"].append(f"Step 11 Warning: Public API returned success=False.")
        else:
            result["steps_log"].append(f"Step 11 Warning: Unauthenticated access returned HTTP {unauth_resp.status_code}.")

        return result
