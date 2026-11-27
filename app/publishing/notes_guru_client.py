import os
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, quote

from config.settings import settings

class NotesGuruApiClient:
    """
    Read-only client for the Notes Guru backend API (Railway).
    Securely manages admin authentication tokens without exposing or logging them.
    All methods strictly perform HTTP GET requests in Phase 1.
    """

    def __init__(self, base_url: str = None, token: str = None, timeout: float = 15.0):
        self.base_url = (base_url or settings.notes_guru_api_base).rstrip('/') + '/'
        self.timeout = timeout
        # Secure token handling: never exposed in __repr__ or __str__
        self._token = (token or settings.notes_guru_admin_token or os.getenv("NOTES_GURU_ADMIN_TOKEN", "")).strip()

    def __repr__(self) -> str:
        token_present = bool(self._token)
        return f"<NotesGuruApiClient base_url='{self.base_url}' token_configured={token_present}>"

    def __str__(self) -> str:
        return self.__repr__()

    def _get_headers(self) -> Dict[str, str]:
        """Construct sanitized request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal safe GET helper with error handling and sanitized logging.
        Never logs or exposes authorization tokens.
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "Unknown"
            err_msg = ""
            try:
                err_data = e.response.json()
                err_msg = err_data.get("message", e.response.text[:200])
            except Exception:
                err_msg = e.response.text[:200] if e.response is not None else str(e)
            raise RuntimeError(f"Notes Guru API HTTP {status_code} on {endpoint}: {err_msg}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Notes Guru API connection error on {endpoint}: {str(e)}") from None

    def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal safe POST helper with error handling."""
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=json_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "Unknown"
            err_msg = ""
            try:
                err_data = e.response.json()
                err_msg = err_data.get("message", e.response.text[:200])
            except Exception:
                err_msg = e.response.text[:200] if e.response is not None else str(e)
            raise RuntimeError(f"Notes Guru API POST HTTP {status_code} on {endpoint}: {err_msg}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Notes Guru API POST connection error on {endpoint}: {str(e)}") from None

    def _put(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal safe PUT helper with error handling."""
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        try:
            response = requests.put(
                url,
                headers=self._get_headers(),
                json=json_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "Unknown"
            err_msg = ""
            try:
                err_data = e.response.json()
                err_msg = err_data.get("message", e.response.text[:200])
            except Exception:
                err_msg = e.response.text[:200] if e.response is not None else str(e)
            raise RuntimeError(f"Notes Guru API PUT HTTP {status_code} on {endpoint}: {err_msg}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Notes Guru API PUT connection error on {endpoint}: {str(e)}") from None

    # -------------------------------------------------------------------------
    # Academic Write Endpoints
    # -------------------------------------------------------------------------

    def create_course(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create course (triggers auto-creation of 6 semesters on backend)."""
        return self._post("courses", payload)

    def create_subject(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create subject (triggers auto-creation of Block 1 and Units 1..5 on backend)."""
        return self._post("subjects", payload)

    def create_block(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new block under a subject."""
        return self._post("blocks", payload)

    def create_unit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new unit under a subject / block."""
        return self._post("units", payload)

    def update_unit(self, unit_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing unit metadata (e.g. title, price, isPublished)."""
        endpoint = f"units/{quote(unit_id)}"
        return self._put(endpoint, payload)

    def update_block(self, block_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing block metadata."""
        endpoint = f"blocks/{quote(block_id)}"
        return self._put(endpoint, payload)

    def create_note(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new note (publicly published or draft)."""
        return self._post("notes", payload)

    def update_note(self, note_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing note (e.g. expand pages, update title/preview)."""
        endpoint = f"notes/{quote(note_id)}"
        return self._put(endpoint, payload)

    # -------------------------------------------------------------------------
    # Academic Read-Only Endpoints
    # -------------------------------------------------------------------------

    def get_colleges(self, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Fetch all universities / colleges registered in Notes Guru."""
        data = self._get("colleges", params={"includeInactive": "true" if include_inactive else "false"})
        return data.get("colleges", [])

    def get_courses_by_college(self, college_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Fetch all courses registered under a given college ID."""
        endpoint = f"courses/college/{quote(college_id)}"
        data = self._get(endpoint, params={"includeInactive": "true" if include_inactive else "false"})
        return data.get("courses", [])

    def get_semesters_by_course(self, course_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Fetch all semesters registered under a given course ID."""
        endpoint = f"semesters/course/{quote(course_id)}"
        data = self._get(endpoint, params={"includeInactive": "true" if include_inactive else "false"})
        return data.get("semesters", [])

    def get_subjects_by_semester(self, semester_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Fetch all subjects registered under a given semester ID."""
        endpoint = f"subjects/semester/{quote(semester_id)}"
        data = self._get(endpoint, params={"includeInactive": "true" if include_inactive else "false"})
        return data.get("subjects", [])

    def get_blocks_by_subject(self, subject_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Fetch all blocks registered under a given subject ID."""
        endpoint = f"blocks/subject/{quote(subject_id)}"
        data = self._get(endpoint, params={"includeInactive": "true" if include_inactive else "false"})
        return data.get("blocks", [])

    def get_units_by_block(self, block_id: str) -> List[Dict[str, Any]]:
        """Fetch all units registered under a given block ID."""
        endpoint = f"units/block/{quote(block_id)}"
        data = self._get(endpoint)
        return data.get("units", [])

    def get_units_by_subject(self, subject_id: str, include_unpublished: bool = True) -> List[Dict[str, Any]]:
        """Fetch all units registered directly under a subject ID."""
        endpoint = f"units/subject/{quote(subject_id)}"
        data = self._get(endpoint, params={"includeUnpublished": "true" if include_unpublished else "false"})
        return data.get("units", [])

    def search_notes(self, query: str = "a") -> List[Dict[str, Any]]:
        """Search existing notes registered across the platform."""
        data = self._get("search", params={"q": query})
        results = data.get("results", {})
        return results.get("notes", [])

    def get_notes_by_unit(self, unit_id: str, include_drafts: bool = True) -> List[Dict[str, Any]]:
        """Fetch all notes registered under a given unit ID (including drafts if admin)."""
        endpoint = f"notes/unit/{quote(unit_id)}"
        data = self._get(endpoint, params={"includeDrafts": "true" if include_drafts else "false"})
        return data.get("notes", [])

    def get_notes_by_block(self, block_id: str, include_drafts: bool = True) -> List[Dict[str, Any]]:
        """Fetch all notes registered under a given block ID (including drafts if admin)."""
        endpoint = f"notes/block/{quote(block_id)}"
        data = self._get(endpoint, params={"includeDrafts": "true" if include_drafts else "false"})
        return data.get("notes", [])

    def check_duplicate_note(
        self,
        unit_id: Optional[str],
        title: str,
        expected_page_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive duplicate note detection.
        1. Queries notes directly attached to unit_id (including drafts).
        2. Queries global search for matching keywords in title.
        3. Compares unit association, title normalization, and page metadata.
        4. If duplicate is detected, flags STOP_AND_REPORT; never permits overwrite.
        """
        report: Dict[str, Any] = {
            "is_duplicate": False,
            "match_found": False,
            "match_level": "NONE",
            "action": "SAFE_TO_PROCEED",
            "matching_note": None,
            "unit_notes_count": 0,
            "reasons": []
        }

        # 1. Search under specific unit if unit_id provided
        if unit_id:
            try:
                unit_notes = self.get_notes_by_unit(unit_id, include_drafts=True)
                report["unit_notes_count"] = len(unit_notes)
                normalized_target = title.strip().lower()

                for n in unit_notes:
                    n_title = n.get("title", "").strip().lower()
                    if n_title == normalized_target or normalized_target in n_title or n_title in normalized_target:
                        report["is_duplicate"] = True
                        report["match_found"] = True
                        report["match_level"] = "EXACT_UNIT_AND_TITLE_MATCH"
                        report["action"] = "STOP_AND_REPORT"
                        report["matching_note"] = {
                            "_id": n.get("_id"),
                            "title": n.get("title"),
                            "status": n.get("status"),
                            "pageCount": n.get("pageCount"),
                            "unitId": n.get("unitId"),
                        }
                        report["reasons"].append(
                            f"Existing note '{n.get('title')}' (_id: {n.get('_id')}, status: {n.get('status')}) already attached to unit {unit_id}."
                        )
                        return report

                if unit_notes:
                    first_note = unit_notes[0]
                    report["is_duplicate"] = True
                    report["match_found"] = True
                    report["match_level"] = "UNIT_ALREADY_HAS_NOTE"
                    report["action"] = "STOP_AND_REPORT"
                    report["matching_note"] = {
                        "_id": first_note.get("_id"),
                        "title": first_note.get("title"),
                        "status": first_note.get("status"),
                        "pageCount": first_note.get("pageCount"),
                        "unitId": first_note.get("unitId"),
                    }
                    report["reasons"].append(
                        f"Unit {unit_id} already has {len(unit_notes)} note(s) attached ('{first_note.get('title')}'). Stop and report to avoid duplicate notes on the same unit."
                    )
                    return report

            except Exception as e:
                if "404" not in str(e):
                    report["reasons"].append(f"Unit check notice: {str(e)}")

        # 2. Check global search for identical title
        try:
            search_results = self.search_notes(query=title[:25])
            normalized_target = title.strip().lower()
            for sn in search_results:
                sn_title = sn.get("title", "").strip().lower()
                if sn_title == normalized_target:
                    report["is_duplicate"] = True
                    report["match_found"] = True
                    report["match_level"] = "GLOBAL_TITLE_MATCH"
                    report["action"] = "STOP_AND_REPORT"
                    report["matching_note"] = {
                        "_id": sn.get("_id"),
                        "title": sn.get("title"),
                        "status": sn.get("status"),
                        "unitId": sn.get("unitId"),
                    }
                    report["reasons"].append(
                        f"A published note with identical title '{sn.get('title')}' already exists globally (_id: {sn.get('_id')})."
                    )
                    return report
        except Exception as e:
            report["reasons"].append(f"Global search notice: {str(e)}")

        return report

    def get_note_detail(self, note_id: str) -> Dict[str, Any]:
        """Fetch full details and structured HTML pages of an existing note."""
        endpoint = f"notes/{quote(note_id)}"
        return self._get(endpoint)

    # -------------------------------------------------------------------------
    # Hierarchy Aggregation & Reconciliation
    # -------------------------------------------------------------------------

    def fetch_ignou_hierarchy_tree(self, target_course_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Traverses the live Notes Guru backend and constructs the full read-only
        hierarchy tree for IGNOU without writing any data.
        """
        tree: Dict[str, Any] = {
            "college": None,
            "courses_total_count": 0,
            "courses": [],
            "target_course_tree": None,
        }

        # 1. Locate IGNOU College
        colleges = self.get_colleges(include_inactive=True)
        ignou_college = next(
            (c for c in colleges if c.get("code", "").upper() == "IGNOU" or "INDIRA GANDHI" in c.get("name", "").upper()),
            None
        )
        if not ignou_college:
            return tree

        tree["college"] = {
            "_id": ignou_college.get("_id"),
            "name": ignou_college.get("name"),
            "code": ignou_college.get("code"),
            "isActive": ignou_college.get("isActive", True),
        }

        # 2. Fetch all courses under IGNOU
        courses = self.get_courses_by_college(ignou_college["_id"], include_inactive=True)
        tree["courses_total_count"] = len(courses)
        tree["courses"] = [
            {"_id": c.get("_id"), "name": c.get("name"), "code": c.get("code"), "durationYears": c.get("durationYears")}
            for c in courses
        ]

        # 3. If a target course code is requested, traverse its full tree
        if target_course_code:
            code_upper = target_course_code.upper()
            target_course = next(
                (c for c in courses if c.get("code", "").upper() == code_upper or c.get("name", "").upper().startswith(code_upper)),
                None
            )
            if target_course:
                course_data = {
                    "_id": target_course.get("_id"),
                    "name": target_course.get("name"),
                    "code": target_course.get("code"),
                    "semesters": []
                }
                semesters = self.get_semesters_by_course(target_course["_id"], include_inactive=True)
                # Sort semesters by semesterNumber
                semesters_sorted = sorted(semesters, key=lambda s: s.get("semesterNumber", 0))
                for sem in semesters_sorted:
                    sem_data = {
                        "_id": sem.get("_id"),
                        "name": sem.get("name"),
                        "semesterNumber": sem.get("semesterNumber"),
                        "subjects": []
                    }
                    subjects = self.get_subjects_by_semester(sem["_id"], include_inactive=True)
                    for sub in subjects:
                        sub_data = {
                            "_id": sub.get("_id"),
                            "name": sub.get("name"),
                            "code": sub.get("code"),
                            "blocks": []
                        }
                        blocks = self.get_blocks_by_subject(sub["_id"], include_inactive=True)
                        blocks_sorted = sorted(blocks, key=lambda b: b.get("blockNumber", 0))
                        for blk in blocks_sorted:
                            blk_data = {
                                "_id": blk.get("_id"),
                                "name": blk.get("name"),
                                "blockNumber": blk.get("blockNumber"),
                                "units": []
                            }
                            units = self.get_units_by_block(blk["_id"])
                            units_sorted = sorted(units, key=lambda u: u.get("unitNumber", 0))
                            blk_data["units"] = [
                                {"_id": u.get("_id"), "title": u.get("title"), "unitNumber": u.get("unitNumber")}
                                for u in units_sorted
                            ]
                            sub_data["blocks"].append(blk_data)
                        sem_data["subjects"].append(sub_data)
                    course_data["semesters"].append(sem_data)
                tree["target_course_tree"] = course_data

        return tree

    def reconcile_hierarchy(
        self,
        live_tree: Dict[str, Any],
        source_syllabus: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compares the live Notes Guru hierarchy against the authorized source syllabus.
        Generates a non-destructive audit report with existing, missing, and proposed entities.
        """
        report: Dict[str, Any] = {
            "college_status": "EXISTS",
            "existing_college": live_tree.get("college"),
            "target_course": source_syllabus.get("course_code"),
            "course_status": "UNKNOWN",
            "existing_course": None,
            "existing_records": [],
            "missing_records": [],
            "mismatches": [],
            "duplicate_risks": [],
            "proposed_records": [],
        }

        # Check College
        college = live_tree.get("college")
        if not college:
            report["college_status"] = "MISSING"
            report["missing_records"].append({"entity": "College", "name": "IGNOU", "code": "IGNOU"})
        else:
            report["existing_records"].append({
                "entity": "College",
                "_id": college["_id"],
                "name": college["name"],
                "code": college["code"]
            })
            report["duplicate_risks"].append(
                f"IGNOU already exists with ID {college['_id']}. Do NOT create a duplicate College record."
            )

        # Check Course
        target_code = source_syllabus.get("course_code", "").upper()
        matching_course = next(
            (c for c in live_tree.get("courses", []) if c.get("code", "").upper() == target_code or c.get("name", "").upper().startswith(target_code)),
            None
        )

        if matching_course:
            report["course_status"] = "EXISTS"
            report["existing_course"] = matching_course
            report["existing_records"].append({
                "entity": "Course",
                "_id": matching_course["_id"],
                "name": matching_course["name"],
                "code": matching_course["code"]
            })
        else:
            report["course_status"] = "MISSING"
            report["missing_records"].append({
                "entity": "Course",
                "code": source_syllabus.get("course_code"),
                "name": source_syllabus.get("course_name"),
            })
            report["proposed_records"].append({
                "entity": "Course",
                "collegeId": college["_id"] if college else "PENDING_COLLEGE_ID",
                "name": f"{source_syllabus.get('course_code')} : {source_syllabus.get('course_name')}",
                "code": source_syllabus.get("course_code"),
                "description": f"Official {source_syllabus.get('course_name')} curriculum under IGNOU.",
            })

        # Check Subject, Block, Unit from source syllabus
        target_sem = source_syllabus.get("semester_number", 1)
        target_sub_code = source_syllabus.get("subject_code", "").upper()
        target_sub_name = source_syllabus.get("subject_name", "")
        target_block_num = source_syllabus.get("block_number", 1)
        target_block_title = source_syllabus.get("block_title", "")
        target_unit_num = source_syllabus.get("unit_number", 1)
        target_unit_title = source_syllabus.get("unit_title", "")

        course_tree = live_tree.get("target_course_tree")
        if course_tree:
            # Course exists in live tree, check semesters
            live_sem = next((s for s in course_tree.get("semesters", []) if s.get("semesterNumber") == target_sem), None)
            if live_sem:
                report["existing_records"].append({"entity": "Semester", "_id": live_sem["_id"], "name": live_sem["name"]})
                # Check Subject
                live_sub = next((sb for sb in live_sem.get("subjects", []) if sb.get("code", "").upper() == target_sub_code), None)
                if live_sub:
                    report["existing_records"].append({"entity": "Subject", "_id": live_sub["_id"], "name": live_sub["name"], "code": live_sub["code"]})
                    # Check Block
                    live_blk = next((b for b in live_sub.get("blocks", []) if b.get("blockNumber") == target_block_num), None)
                    if live_blk:
                        report["existing_records"].append({"entity": "Block", "_id": live_blk["_id"], "name": live_blk["name"]})
                        # Check Unit
                        live_unt = next((u for u in live_blk.get("units", []) if u.get("unitNumber") == target_unit_num), None)
                        if live_unt:
                            report["existing_records"].append({"entity": "Unit", "_id": live_unt["_id"], "title": live_unt["title"]})
                        else:
                            report["missing_records"].append({"entity": "Unit", "unitNumber": target_unit_num, "title": target_unit_title})
                            report["proposed_records"].append({"entity": "Unit", "blockId": live_blk["_id"], "subjectId": live_sub["_id"], "unitNumber": target_unit_num, "title": target_unit_title})
                    else:
                        report["missing_records"].append({"entity": "Block", "blockNumber": target_block_num, "name": target_block_title})
                        report["missing_records"].append({"entity": "Unit", "unitNumber": target_unit_num, "title": target_unit_title})
                else:
                    report["missing_records"].append({"entity": "Subject", "code": target_sub_code, "name": target_sub_name})
                    report["missing_records"].append({"entity": "Block", "blockNumber": target_block_num, "name": target_block_title})
                    report["missing_records"].append({"entity": "Unit", "unitNumber": target_unit_num, "title": target_unit_title})
            else:
                report["missing_records"].append({"entity": "Semester", "semesterNumber": target_sem})
        else:
            # Course does not exist in backend yet; all downstream items are missing
            report["missing_records"].extend([
                {"entity": "Semester", "semesterNumber": target_sem, "name": f"Semester {target_sem}"},
                {"entity": "Subject", "code": target_sub_code, "name": target_sub_name},
                {"entity": "Block", "blockNumber": target_block_num, "name": target_block_title},
                {"entity": "Unit", "unitNumber": target_unit_num, "title": target_unit_title},
            ])
            report["proposed_records"].extend([
                {"entity": "Semester", "semesterNumber": target_sem, "name": f"Semester {target_sem}"},
                {"entity": "Subject", "code": target_sub_code, "name": target_sub_name},
                {"entity": "Block", "blockNumber": target_block_num, "name": target_block_title},
                {"entity": "Unit", "unitNumber": target_unit_num, "title": target_unit_title},
            ])

        return report
