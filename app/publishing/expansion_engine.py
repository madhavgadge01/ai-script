import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from app.publishing.notes_guru_client import NotesGuruApiClient
from app.publishing.tracker import CourseProgressTracker
from app.publishing.qa import QualityAssuranceEngine
from app.ai.client import GeminiClient, GeminiQuotaExhaustedError
from app.summarization.schemas import StructuredPage, SubSection, ExamCallout, TableData
from app.html.generator import HTMLNoteGenerator
from config.settings import settings


class SemesterContentExpander:
    """
    Expands and improves existing BCA study notes across semesters.
    Replaces compressed 2-page/3-page summaries with thorough, exam-ready 5-page study notes.
    Reuses existing note IDs on Notes Guru / GenZnotes via PUT /api/notes/:id, ensuring zero duplicate creation.
    """

    PAGE_BLUEPRINTS = [
        {
            "page_num": 1,
            "badge": "FOUNDATIONS & CONCEPTS",
            "focus": "Conceptual Foundations, Core Principles, and Formal Definitions",
            "requirements": "Detailed academic introduction, learning objectives, foundational axioms, standard formal definitions, key technical terminology with definition callouts."
        },
        {
            "page_num": 2,
            "badge": "ARCHITECTURE & MECHANISMS",
            "focus": "Internal Architecture, Technical Subsystems, and Operational Mechanisms",
            "requirements": "Component-by-component architectural breakdown, execution data paths, logical structures, operational workflows, and functional block diagrams/descriptions."
        },
        {
            "page_num": 3,
            "badge": "PROCEDURES & COMPARISONS",
            "focus": "Procedural Workflows, Algorithms, Configurations, and Comparative Analysis",
            "requirements": "Step-by-step algorithms, calculations, mathematical procedures or configurations, plus a structured comparative trade-off table comparing alternative approaches/technologies."
        },
        {
            "page_num": 4,
            "badge": "APPLICATIONS & TRADE-OFFS",
            "focus": "Practical Applications, Industry Standards, and Architectural Trade-Offs",
            "requirements": "Real-world industrial use cases, modern implementations, system limitations, performance trade-offs, advantages, and disadvantages."
        },
        {
            "page_num": 5,
            "badge": "EXAM REVIEW & MODEL Q&A",
            "focus": "Examination Review, Step-by-Step Model Solutions, and High-Yield Revision",
            "requirements": "Frequent university term-end examination question types, step-by-step model exam solutions with scoring tips, key formula/rule checklist, and high-yield takeaway summary."
        }
    ]

    def __init__(
        self,
        inventory_path: str = "config/bca_syllabus_inventory.json",
        client: Optional[NotesGuruApiClient] = None,
        tracker: Optional[CourseProgressTracker] = None,
        gemini_client: Optional[GeminiClient] = None
    ):
        self.inventory_path = Path(inventory_path)
        self.client = client or NotesGuruApiClient()
        self.tracker = tracker or CourseProgressTracker()
        self.html_gen = HTMLNoteGenerator()

        try:
            self.gemini = gemini_client or GeminiClient()
        except Exception:
            self.gemini = None

        # Load syllabus inventory map across all semesters
        inv_data = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        self.topics_map = {}
        for s in inv_data.get("semesters", []):
            sem_num = s.get("semester_number", 1)
            for sub in s.get("subjects", []):
                for blk in sub.get("blocks", []):
                    for u in blk.get("units", []):
                        key = f"BCA_SEM{sem_num}_{sub['code']}_B{blk['block_number']}_U{u['unit_number']}"
                        self.topics_map[key] = {
                            "topics": u.get("topics", []),
                            "sub_code": sub["code"],
                            "sub_name": sub["name"],
                            "blk_num": blk["block_number"],
                            "blk_title": blk["title"],
                            "unit_num": u["unit_number"],
                            "unit_title": u["title"],
                            "semester": sem_num,
                        }

    def generate_5_page_expanded_unit(
        self,
        subject_code: str,
        subject_name: str,
        block_number: int,
        block_title: str,
        unit_number: int,
        unit_title: str,
        topics: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generates 5 distinct, comprehensive, exam-ready StructuredPage notes using Gemini.
        Applies subject-specific pedagogical enhancements (C programming code, 8086 microprocessors,
        discrete math proofs, accounting ledger formats, or workplace communication).
        """
        if not self.gemini:
            raise RuntimeError("Gemini Client not initialized.")

        pages_data = []
        total_pages = 5

        # Subject-specific instructions
        subject_guidelines = ""
        s_upper = subject_code.upper()
        n_upper = subject_name.upper()

        if "MCS-011" in s_upper or "PROG" in n_upper:
            subject_guidelines = (
                "SPECIAL PROGRAMMING REQUIREMENTS: Provide complete, executable, clean standard ANSI C code snippets "
                "with detailed line-by-line explanations, pointer memory address diagrams/traces, and edge-case handling."
            )
        elif "MCS-012" in s_upper or "ORGANIZATION" in n_upper:
            subject_guidelines = (
                "SPECIAL COMPUTER ARCHITECTURE REQUIREMENTS: Provide detailed hardware architecture diagrams/descriptions, "
                "8086 register models (AX, BX, CX, DX, SI, DI, SP, BP, CS, DS, SS, ES), bus cycles, K-map reduction steps, "
                "and valid 8086 assembly language instructions with register traces."
            )
        elif "MCS-013" in s_upper or "BCS-012" in s_upper or "MATH" in n_upper:
            subject_guidelines = (
                "SPECIAL MATHEMATICS REQUIREMENTS: Provide rigorous step-by-step mathematical proofs, truth tables, "
                "predicate quantifiers, combinatorics calculations, graph theory theorem derivations, and fully worked solutions."
            )
        elif "ECO-02" in s_upper or "ECO-01" in s_upper or "ACCOUNT" in n_upper or "BUSINESS" in n_upper:
            subject_guidelines = (
                "SPECIAL BUSINESS & ACCOUNTING REQUIREMENTS: Provide standard double-entry journal format tables "
                "(Date, Particulars, L.F., Debit, Credit), ledger T-accounts, trial balance formats, and final accounts layouts."
            )
        elif "MCS-015" in s_upper or "FEG" in s_upper or "COMMUNICATION" in n_upper or "ENGLISH" in n_upper:
            subject_guidelines = (
                "SPECIAL LANGUAGE & COMMUNICATION REQUIREMENTS: Provide practical workplace communication templates "
                "(professional emails, memos, meeting minutes), active listening exercises, barrier analysis, and interview simulations."
            )

        system_instruction = (
            "You are a distinguished university professor and academic textbook author specializing in undergraduate "
            f"Computer Applications for IGNOU BCA ({subject_code} - {subject_name}). Your task is to author exhaustive, "
            "deeply educational, exam-oriented study notes. Strictly preserve all technical definitions, mathematical "
            "derivations, step-by-step algorithms, comparative tables, and realistic exam review questions. "
            "Do not use generic filler or superficial bullet lists. Provide rigorous academic depth on every page. "
            f"{subject_guidelines}"
        )

        for bp in self.PAGE_BLUEPRINTS:
            p_num = bp["page_num"]
            badge = bp["badge"]
            focus = bp["focus"]
            reqs = bp["requirements"]

            prompt = f"""Author Page {p_num} of {total_pages} for an official university course unit:
Course: IGNOU BCA | Subject: {subject_code} - {subject_name}
Block {block_number}: {block_title}
Unit {unit_number}: {unit_title}

PRIMARY PAGE OBJECTIVE: {focus}
SPECIFIC PEDAGOGICAL REQUIREMENTS: {reqs}
OFFICIAL SYLLABUS TOPICS: {', '.join(topics)}

Generate Page {p_num} as a StructuredPage with the following fields:
- page_title: Academic title (e.g. 'Page {p_num}: {focus}')
- category_badge: '{badge}'
- intro_paragraph: 2-4 comprehensive sentences establishing theoretical/practical context.
- sections: At least 2 deep-dive sections. Each section must have substantive explanation paragraphs, detailed bullet points, at least one definition/formula callout, and a comparative table where applicable.
- exam_summary: High-yield takeaway and memory aid for university examinations.
"""

            structured_page: StructuredPage = self.gemini.generate_structured(
                prompt=prompt,
                response_schema=StructuredPage,
                system_instruction=system_instruction
            )
            structured_page.page_number = p_num
            structured_page.category_badge = badge

            page_html = self.html_gen.render_single_page(structured_page)

            pages_data.append({
                "pageNumber": p_num,
                "title": structured_page.page_title,
                "contentHtml": page_html,
                "isLockedPreview": p_num > 2
            })

            time.sleep(1.0)  # Rate limit breathing space

        return pages_data

    def expand_unit(self, unit_key: str, min_pages: int = 5) -> Dict[str, Any]:
        """
        Audits and expands a single unit to min_pages, updating the existing note on Notes Guru.
        """
        meta = self.topics_map.get(unit_key)
        if not meta:
            raise ValueError(f"Unknown unit key: {unit_key}")

        track_rec = self.tracker.get_unit_status(unit_key)
        note_id = track_rec.get("notes_guru_note_id")
        if not note_id:
            raise RuntimeError(f"Unit {unit_key} does not have an existing note registered.")

        # Check existing note
        current_detail = self.client.get_note_detail(note_id)
        current_pages = current_detail.get("pages", [])
        current_total = current_detail.get("note", {}).get("totalPages", len(current_pages))

        # Special case: BCS-011 B1 U1 was authored from 4-page source PDF with full coverage
        if unit_key == "BCA_SEM1_BCS-011_B1_U1" and current_total >= 4:
            return {
                "unit_key": unit_key,
                "status": "ALREADY_COMPLIANT",
                "page_count": current_total,
                "note_id": note_id,
                "url": track_rec.get("public_url")
            }

        if current_total >= min_pages:
            return {
                "unit_key": unit_key,
                "status": "ALREADY_COMPLIANT",
                "page_count": current_total,
                "note_id": note_id,
                "url": track_rec.get("public_url")
            }

        print(f"Expanding {unit_key} ({meta['unit_title']}) from {current_total} pages to {min_pages} pages...", flush=True)

        # Generate 5 expanded pages
        expanded_pages = self.generate_5_page_expanded_unit(
            subject_code=meta["sub_code"],
            subject_name=meta["sub_name"],
            block_number=meta["blk_num"],
            block_title=meta["blk_title"],
            unit_number=meta["unit_num"],
            unit_title=meta["unit_title"],
            topics=meta["topics"]
        )

        # Quality Assurance Audit
        qa_res = QualityAssuranceEngine.audit_pages(expanded_pages, expected_topics=meta["topics"])
        if not qa_res["passed"]:
            raise RuntimeError(f"QA Failed on expanded pages for {unit_key}: {qa_res['issues']}")

        print(f"   -> QA Passed (Coverage: {qa_res['topic_coverage_percent']}%, {len(expanded_pages)} pages). Updating note on Notes Guru...", flush=True)

        # Update existing note via PUT /api/notes/:id
        update_payload = {
            "title": meta["unit_title"],
            "type": "normal",
            "description": f"Exhaustive exam-oriented university study notes for {meta['sub_code']} Unit {meta['unit_num']}: {meta['unit_title']}.",
            "price": 25,
            "discountedPrice": 19,
            "previewPageCount": 2,
            "status": "published",
            "isPublished": True,
            "pages": expanded_pages
        }

        update_res = self.client.update_note(note_id, update_payload)
        updated_note = update_res.get("note", {})
        pub_url = f"https://notes-guru-7tgo.vercel.app/notes/{note_id}"

        # Verify public visibility
        unauth_resp = requests.get(f"{self.client.base_url.rstrip('/')}/notes/{note_id}", timeout=15)
        verified_public = unauth_resp.status_code == 200 and unauth_resp.json().get("success", False)

        # Update Tracker in SQLite
        self.tracker.update_unit_status(
            unit_key,
            qa_status="PASSED_EXPANDED",
            qa_details=json.dumps({"total_pages": len(expanded_pages), "topic_coverage": qa_res["topic_coverage_percent"], "expanded": True}),
            publishing_status="PUBLISHED" if verified_public else "UPLOADED_PENDING_VERIFICATION",
            public_url=pub_url
        )

        try:
            shutil.copyfile("storage/uninotes.db", "storage/uninotes.db.backup")
        except Exception:
            pass

        return {
            "unit_key": unit_key,
            "status": "EXPANDED_AND_PUBLISHED",
            "note_id": note_id,
            "url": pub_url,
            "previous_pages": current_total,
            "new_pages": len(expanded_pages),
            "unauthenticated_verified": verified_public
        }

    def expand_subject(self, subject_code: str, semester: Optional[int] = None, max_units: Optional[int] = None) -> Dict[str, Any]:
        """
        Sequentially expands all units under a given subject in a specified semester (or across semesters).
        """
        units = self.tracker.get_all_units(semester=semester, subject_code=subject_code)
        report = {
            "subject_code": subject_code,
            "semester": semester,
            "total_units": len(units),
            "units_expanded": 0,
            "units_already_compliant": 0,
            "quota_exhausted": False,
            "stopped_at_unit": None,
            "error_message": None,
            "records": []
        }

        sem_label = f"Semester {semester}" if semester else "All Semesters"
        print(f"\n{'='*70}\nEXPANDING NOTES FOR {subject_code} ({sem_label} | {len(units)} units)\n{'='*70}", flush=True)

        for u in units:
            if max_units is not None and report["units_expanded"] >= max_units:
                break

            unit_key = u["unit_key"]
            try:
                res = self.expand_unit(unit_key, min_pages=5)
                if res["status"] == "EXPANDED_AND_PUBLISHED":
                    report["units_expanded"] += 1
                    print(f"   [DONE] {unit_key} expanded from {res['previous_pages']} to {res['new_pages']} pages! URL: {res['url']}", flush=True)
                else:
                    report["units_already_compliant"] += 1
                    print(f"   [OK] {unit_key} already meets depth ({res['page_count']} pages).", flush=True)
                report["records"].append(res)
            except GeminiQuotaExhaustedError as qe:
                report["quota_exhausted"] = True
                report["stopped_at_unit"] = unit_key
                report["error_message"] = str(qe)
                print(f"   [QUOTA NOTICE] Stopped at {unit_key}: {qe}", flush=True)
                break
            except Exception as e:
                err_str = str(e)
                print(f"   [ERROR] Failed to expand {unit_key}: {err_str}", flush=True)
                report["records"].append({"unit_key": unit_key, "status": "FAILED", "reason": err_str})
                if "Failed to resolve" in err_str or "nodename nor servname" in err_str:
                    print("   [Network Alert] Halting expansion batch due to network interruption.", flush=True)
                    break

        return report


# Backwards compatibility alias
Semester1ContentExpander = SemesterContentExpander
