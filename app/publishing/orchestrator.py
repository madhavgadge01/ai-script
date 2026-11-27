import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from app.publishing.notes_guru_client import NotesGuruApiClient
from app.publishing.tracker import CourseProgressTracker
from app.publishing.licensing import LicensingAuditor
from app.publishing.qa import QualityAssuranceEngine
from app.publishing.reconciliation import BCAHierarchyReconciler
from app.publishing.publisher import NotesPublisher
from app.ai.client import GeminiClient, GeminiQuotaExhaustedError
from app.summarization.schemas import StructuredPage, SubSection, ExamCallout, TableData
from app.html.generator import HTMLNoteGenerator
from config.settings import settings

class BCACourseOrchestrator:
    """
    Master pipeline orchestrator for the complete IGNOU BCA degree curriculum.
    Automates syllabus inventory, hierarchy reconciliation, licensing audit,
    Gemini-powered note generation, quality assurance, batch publishing, and progress tracking.
    """

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
        self.publisher = NotesPublisher(client=self.client)
        self.html_gen = HTMLNoteGenerator()
        self.reconciler = BCAHierarchyReconciler(inventory_path=str(self.inventory_path), client=self.client)
        
        try:
            self.gemini = gemini_client or GeminiClient()
        except Exception:
            self.gemini = None

        # Initialize tracker with full syllabus
        self.tracker.initialize_from_inventory(str(self.inventory_path))
        self._record_existing_unit_1_publication()

    def _record_existing_unit_1_publication(self):
        """Records the already published Unit 1 note into the persistent tracker."""
        unit_1_key = "BCA_SEM1_BCS-011_B1_U1"
        self.tracker.update_unit_status(
            unit_1_key,
            source_status="AVAILABLE",
            license_status="ORIGINAL_ACADEMIC_SYNTHESIS",
            commercial_allowed=1,
            extraction_status="EXTRACTED",
            summarization_status="SUMMARIZED",
            qa_status="PASSED",
            qa_details=json.dumps({"pages": 4, "checks": "Passed full pre-flight QA"}),
            publishing_status="PUBLISHED",
            notes_guru_course_id="6b01657ce1a606d1dcb623de",
            notes_guru_semester_id="6b01657de1a606d1dcb623e2",
            notes_guru_subject_id="6b016582e1a606d1dcb623f3",
            notes_guru_block_id="6b016582e1a606d1dcb623f6",
            notes_guru_unit_id="6b016583e1a606d1dcb623f9",
            notes_guru_note_id="6b01658be1a606d1dcb62410",
            public_url="https://notes-guru-7tgo.vercel.app/notes/6b01658be1a606d1dcb62410"
        )

    def run_reconciliation(self) -> Dict[str, Any]:
        """Runs and returns the full hierarchy reconciliation report."""
        return self.reconciler.reconcile_full_bca()

    def audit_all_licenses(self, default_intended_price: float = 25.0) -> Dict[str, Any]:
        """Audits all units across the course for commercial & republication rights."""
        units = self.tracker.get_all_units()
        summary = {
            "total_units": len(units),
            "authorized_commercial": 0,
            "blocked_commercial": 0,
            "blocked_unauthorized": 0,
            "audit_records": []
        }

        for u in units:
            unit_key = u["unit_key"]
            subj_code = u["subject_code"]
            u_num = u["unit_number"]

            verdict = LicensingAuditor.audit_unit_licensing(
                subj_code, u_num,
                content_source_type=LicensingAuditor.LICENSE_ORIGINAL_SYNTHESIS,
                intended_price=default_intended_price
            )

            if verdict["commercial_allowed"]:
                summary["authorized_commercial"] += 1
            elif verdict["requires_free_pricing"]:
                summary["blocked_commercial"] += 1
            else:
                summary["blocked_unauthorized"] += 1

            self.tracker.update_unit_status(
                unit_key,
                license_status=verdict["audit_verdict"],
                commercial_allowed=1 if verdict["commercial_allowed"] else 0
            )

            summary["audit_records"].append(verdict)

        return summary

    def generate_unit_pages_with_gemini(
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
        Uses Gemini (free tier) to author exhaustive, exam-oriented 5-page StructuredPage notes
        strictly based on official syllabus topics, definitions, formulas, and model exam questions.
        """
        if not self.gemini:
            raise RuntimeError("Gemini Client not initialized. Check GEMINI_API_KEY in .env.")

        total_pages = 5
        pages_data = []

        blueprints = [
            {
                "page_num": 1,
                "badge": "FOUNDATIONS & CONCEPTS",
                "focus": "Conceptual Foundations, Core Principles, and Formal Definitions",
                "reqs": "Detailed academic introduction, learning objectives, foundational axioms, standard formal definitions, key technical terminology with definition callouts."
            },
            {
                "page_num": 2,
                "badge": "ARCHITECTURE & MECHANISMS",
                "focus": "Internal Architecture, Technical Subsystems, and Operational Mechanisms",
                "reqs": "Component-by-component architectural breakdown, execution data paths, logical structures, operational workflows, and functional block diagrams/descriptions."
            },
            {
                "page_num": 3,
                "badge": "PROCEDURES & COMPARISONS",
                "focus": "Procedural Workflows, Algorithms, Configurations, and Comparative Analysis",
                "reqs": "Step-by-step algorithms, calculations, mathematical procedures or configurations, plus a structured comparative trade-off table comparing alternative approaches/technologies."
            },
            {
                "page_num": 4,
                "badge": "APPLICATIONS & TRADE-OFFS",
                "focus": "Practical Applications, Industry Standards, and Architectural Trade-Offs",
                "reqs": "Real-world industrial use cases, modern implementations, system limitations, performance trade-offs, advantages, and disadvantages."
            },
            {
                "page_num": 5,
                "badge": "EXAM REVIEW & MODEL Q&A",
                "focus": "Examination Review, Step-by-Step Model Solutions, and High-Yield Revision",
                "reqs": "Frequent university term-end examination question types, step-by-step model exam solutions with scoring tips, key formula/rule checklist, and high-yield takeaway summary."
            }
        ]

        # Subject-specific guidelines
        s_upper = subject_code.upper()
        n_upper = subject_name.upper()
        subject_guidelines = ""
        if "MCS-011" in s_upper or "PROG" in n_upper:
            subject_guidelines = "Provide complete, executable standard C code examples with step-by-step memory explanations."
        elif "MCS-012" in s_upper or "ORGANIZATION" in n_upper:
            subject_guidelines = "Provide detailed hardware block diagrams, 8086 registers, K-maps, and valid 8086 assembly snippets."
        elif "MCS-013" in s_upper or "BCS-012" in s_upper or "MATH" in n_upper:
            subject_guidelines = "Provide rigorous mathematical derivations, truth tables, combinatorics steps, and graph proofs."
        elif "ECO-02" in s_upper or "ECO-01" in s_upper or "ACCOUNT" in n_upper:
            subject_guidelines = "Provide standard journal format tables, ledger T-accounts, trial balance formats, and final accounts."
        elif "MCS-015" in s_upper or "FEG" in s_upper or "COMMUNICATION" in n_upper:
            subject_guidelines = "Provide practical business communication templates, memos, emails, and interview practice scenarios."

        system_instruction = (
            "You are a distinguished university professor and academic author specializing in undergraduate "
            f"Computer Applications (IGNOU BCA curriculum: {subject_code} - {subject_name}). Your task is to author exhaustive, high-yield, "
            "exam-oriented study notes. Strictly preserve all technical definitions, formulas, algorithms, "
            f"comparative tables, and realistic exam review questions. {subject_guidelines}"
        )

        for bp in blueprints:
            page_num = bp["page_num"]
            focus = bp["focus"]
            badge = bp["badge"]
            reqs = bp["reqs"]

            prompt = f"""Author Page {page_num} of {total_pages} for an official university course unit:
Course: BCA ({subject_code} - {subject_name})
Block {block_number}: {block_title}
Unit {unit_number}: {unit_title}

PRIMARY SECTION FOCUS: {focus}
PEDAGOGICAL REQUIREMENTS: {reqs}
SYLLABUS TOPICS TO COVER: {', '.join(topics)}

Generate Page {page_num} as a comprehensive StructuredPage:
- page_title: A clear academic title (e.g. 'Page {page_num}: {focus}')
- category_badge: '{badge}'
- intro_paragraph: 2-3 thorough sentences setting academic context
- sections: At least 2 deep-dive sections with thorough explanations, bullet points, callouts (with at least 1 'definition' and 1 'imp_exam_point'), and a comparison table if relevant.
- exam_summary: High-yield takeaway for term-end examinations.
"""

            structured_page: StructuredPage = self.gemini.generate_structured(
                prompt=prompt,
                response_schema=StructuredPage,
                system_instruction=system_instruction
            )
            structured_page.page_number = page_num
            structured_page.category_badge = badge

            # Render through HTML generator for GenZnotes
            page_html = self.html_gen.render_single_page(structured_page)

            pages_data.append({
                "pageNumber": page_num,
                "title": structured_page.page_title,
                "contentHtml": page_html,
                "isLockedPreview": page_num > 2
            })

            # Polite rate-limit spacing between page generations
            time.sleep(1.0)

        return pages_data

    def process_next_pending_units(
        self,
        max_units: int = 3,
        semester: Optional[int] = None,
        subject_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resumes processing from the first genuinely incomplete unit.
        Processes units in manageable batches, stops immediately on quota errors,
        and saves persistent state.
        """
        all_units = self.tracker.get_all_units(semester=semester, subject_code=subject_code)
        pending_units = [u for u in all_units if u["publishing_status"] != "PUBLISHED"]

        report: Dict[str, Any] = {
            "total_pending_before": len(pending_units),
            "units_attempted": 0,
            "units_completed": 0,
            "quota_exhausted": False,
            "stopped_at_unit": None,
            "error_message": None,
            "processed_records": []
        }

        if not pending_units:
            return report

        # Load inventory to lookup topics
        inv_data = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        topics_map = {}
        for s in inv_data.get("semesters", []):
            for sub in s.get("subjects", []):
                for blk in sub.get("blocks", []):
                    for u in blk.get("units", []):
                        key = f"BCA_SEM{s['semester_number']}_{sub['code']}_B{blk['block_number']}_U{u['unit_number']}"
                        topics_map[key] = {
                            "topics": u.get("topics", []),
                            "sub_name": sub["name"],
                            "blk_title": blk["title"],
                            "sem_num": s["semester_number"]
                        }

        # Fetch live BCA tree for course/semester IDs
        live_tree = self.client.fetch_ignou_hierarchy_tree(target_course_code="BCA")
        bca_live = live_tree.get("target_course_tree")
        if not bca_live:
            raise RuntimeError("Live BCA course tree not found on Notes Guru.")
        
        course_id = bca_live["_id"]
        semesters_map = {s.get("semesterNumber"): s for s in bca_live.get("semesters", [])}

        for u_track in pending_units:
            if report["units_completed"] >= max_units:
                break

            unit_key = u_track["unit_key"]
            s_code = u_track["subject_code"]
            b_num = u_track["block_number"]
            u_num = u_track["unit_number"]
            u_title = u_track["unit_title"]
            sem_num = u_track["semester"]

            print(f"\n[{report['units_completed'] + 1}/{max_units}] Processing {unit_key} ({s_code} B{b_num} U{u_num}: {u_title})...", flush=True)

            report["units_attempted"] += 1
            live_sem = semesters_map.get(sem_num)
            if not live_sem:
                report["processed_records"].append({"unit_key": unit_key, "status": "FAILED", "reason": f"Semester {sem_num} missing"})
                continue

            sem_id = live_sem["_id"]

            try:
                # 1. Resolve or Create Subject
                live_subjects = self.client.get_subjects_by_semester(sem_id, include_inactive=True)
                target_sub = next((s for s in live_subjects if s.get("code", "").upper() == s_code.upper()), None)

                if not target_sub:
                    sub_meta = topics_map.get(unit_key, {})
                    sub_name = sub_meta.get("sub_name", u_track["subject_name"])
                    create_sub_res = self.client.create_subject({
                        "semesterId": sem_id,
                        "name": sub_name,
                        "code": s_code,
                        "description": f"Curriculum for {s_code}: {sub_name}",
                        "price": 20,
                        "discountedPrice": 15,
                        "order": 1,
                        "isActive": True
                    })
                    target_sub = create_sub_res.get("subject")
                
                subject_id = target_sub["_id"]

                # 2. Resolve or Create Block
                live_blocks = self.client.get_blocks_by_subject(subject_id, include_inactive=True)
                target_block = next((b for b in live_blocks if b.get("blockNumber") == b_num), None)

                if not target_block:
                    sub_meta = topics_map.get(unit_key, {})
                    blk_title = sub_meta.get("blk_title", u_track["block_title"])
                    create_blk_res = self.client.create_block({
                        "subjectId": subject_id,
                        "blockNumber": b_num,
                        "name": blk_title,
                        "description": f"Block {b_num}: {blk_title}",
                        "order": b_num,
                        "isActive": True
                    })
                    target_block = create_blk_res.get("block")
                else:
                    sub_meta = topics_map.get(unit_key, {})
                    blk_title = sub_meta.get("blk_title", u_track["block_title"])
                    if blk_title and target_block.get("name") != blk_title:
                        try:
                            self.client.update_block(target_block["_id"], {
                                "name": blk_title,
                                "description": f"Block {b_num}: {blk_title}",
                                "isActive": True
                            })
                            target_block["name"] = blk_title
                        except Exception:
                            pass

                block_id = target_block["_id"]

                # 3. Resolve or Create/Update Unit
                live_units = self.client.get_units_by_block(block_id)
                target_unit = next((u for u in live_units if u.get("unitNumber") == u_num), None)

                if not target_unit:
                    create_unit_res = self.client.create_unit({
                        "subjectId": subject_id,
                        "blockId": block_id,
                        "unitNumber": u_num,
                        "title": u_title,
                        "description": f"Unit {u_num}: {u_title}",
                        "price": 25,
                        "discountedPrice": 19,
                        "order": u_num,
                        "isPublished": True
                    })
                    target_unit = create_unit_res.get("unit")
                else:
                    self.client.update_unit(target_unit["_id"], {
                        "title": u_title,
                        "description": f"Unit {u_num}: {u_title}",
                        "price": 25,
                        "discountedPrice": 19,
                        "isPublished": True
                    })

                unit_id = target_unit["_id"]

                # 4. Duplicate Note Check
                dup_res = self.client.check_duplicate_note(unit_id, u_title)
                if dup_res["is_duplicate"]:
                    matching = dup_res.get("matching_note", {})
                    note_id = matching.get("_id")
                    pub_url = f"https://notes-guru-7tgo.vercel.app/notes/{note_id}"
                    self.tracker.update_unit_status(
                        unit_key,
                        publishing_status="PUBLISHED",
                        notes_guru_course_id=course_id,
                        notes_guru_semester_id=sem_id,
                        notes_guru_subject_id=subject_id,
                        notes_guru_block_id=block_id,
                        notes_guru_unit_id=unit_id,
                        notes_guru_note_id=note_id,
                        public_url=pub_url
                    )
                    report["units_completed"] += 1
                    report["processed_records"].append({"unit_key": unit_key, "status": "REUSED_EXISTING", "url": pub_url})
                    continue

                # 5. Licensing Verification
                lic_verdict = LicensingAuditor.audit_unit_licensing(s_code, u_num)
                if not lic_verdict["public_publication_allowed"]:
                    self.tracker.update_unit_status(
                        unit_key,
                        publishing_status="LOCAL_REVIEW_BLOCKED",
                        license_status=lic_verdict["audit_verdict"]
                    )
                    report["processed_records"].append({"unit_key": unit_key, "status": "BLOCKED_LICENSING", "reason": lic_verdict["reason"]})
                    continue

                # 6. Generate Exam-Oriented Notes with Gemini
                unit_meta = topics_map.get(unit_key, {})
                unit_topics = unit_meta.get("topics", [u_title])
                self.tracker.update_unit_status(unit_key, summarization_status="IN_PROGRESS")
                print(f"   -> Generating {len(unit_topics)} syllabus topics with Gemini...", flush=True)

                pages = self.generate_unit_pages_with_gemini(
                    subject_code=s_code,
                    subject_name=unit_meta.get("sub_name", u_track["subject_name"]),
                    block_number=b_num,
                    block_title=unit_meta.get("blk_title", u_track["block_title"]),
                    unit_number=u_num,
                    unit_title=u_title,
                    topics=unit_topics
                )

                # 7. Quality Assurance Audit
                qa_res = QualityAssuranceEngine.audit_pages(pages, expected_topics=unit_topics)
                if not qa_res["passed"]:
                    print(f"   -> QA FAILED: {qa_res['issues']}", flush=True)
                    self.tracker.update_unit_status(
                        unit_key,
                        qa_status="FAILED",
                        qa_details=json.dumps(qa_res)
                    )
                    report["processed_records"].append({"unit_key": unit_key, "status": "QA_FAILED", "issues": qa_res["issues"]})
                    continue

                print(f"   -> QA PASSED (Coverage: {qa_res['topic_coverage_percent']}%, {len(pages)} pages). Uploading to Notes Guru...", flush=True)

                # 8. Upload to Notes Guru as Published Note
                note_payload = {
                    "unitId": unit_id,
                    "blockId": block_id,
                    "title": u_title,
                    "type": "normal",
                    "description": f"Comprehensive exam-oriented study notes for {s_code} Unit {u_num}: {u_title}.",
                    "price": 25,
                    "discountedPrice": 19,
                    "previewPageCount": 2,
                    "status": "published",
                    "order": u_num,
                    "pages": pages
                }

                create_note_res = self.client.create_note(note_payload)
                created_note = create_note_res.get("note", {})
                note_id = created_note.get("_id")
                pub_url = f"https://notes-guru-7tgo.vercel.app/notes/{note_id}"

                # 9. Verify Public Unauthenticated Access
                unauth_resp = requests.get(f"{self.client.base_url.rstrip('/')}/notes/{note_id}", timeout=15)
                verified_public = unauth_resp.status_code == 200 and unauth_resp.json().get("success", False)

                self.tracker.update_unit_status(
                    unit_key,
                    source_status="SYNTHESIZED",
                    license_status="ORIGINAL_ACADEMIC_SYNTHESIS",
                    commercial_allowed=1,
                    extraction_status="EXTRACTED",
                    summarization_status="SUMMARIZED",
                    qa_status="PASSED",
                    qa_details=json.dumps({"total_pages": len(pages), "topic_coverage": qa_res["topic_coverage_percent"]}),
                    publishing_status="PUBLISHED" if verified_public else "UPLOADED_PENDING_VERIFICATION",
                    notes_guru_course_id=course_id,
                    notes_guru_semester_id=sem_id,
                    notes_guru_subject_id=subject_id,
                    notes_guru_block_id=block_id,
                    notes_guru_unit_id=unit_id,
                    notes_guru_note_id=note_id,
                    public_url=pub_url
                )

                try:
                    shutil.copyfile("storage/uninotes.db", "storage/uninotes.db.backup")
                except Exception:
                    pass

                report["units_completed"] += 1
                print(f"   -> PUBLISHED successfully! Note ID: {note_id} | URL: {pub_url}", flush=True)
                report["processed_records"].append({
                    "unit_key": unit_key,
                    "status": "PUBLISHED",
                    "note_id": note_id,
                    "url": pub_url,
                    "pages": len(pages),
                    "unauthenticated_verified": verified_public
                })

            except GeminiQuotaExhaustedError as q_err:
                report["quota_exhausted"] = True
                report["stopped_at_unit"] = unit_key
                report["error_message"] = str(q_err)
                self.tracker.update_unit_status(
                    unit_key,
                    summarization_status="QUOTA_EXHAUSTED",
                    qa_status="STOPPED_QUOTA"
                )
                print(f"[Quota Notice] Stopped at {unit_key}: {str(q_err)}")
                break

            except Exception as e:
                err_str = str(e)
                report["processed_records"].append({"unit_key": unit_key, "status": "FAILED", "reason": err_str})
                print(f"   -> ERROR processing {unit_key}: {err_str}", flush=True)
                if "Failed to resolve" in err_str or "nodename nor servname" in err_str or "Connection refused" in err_str or "ConnectionError" in err_str:
                    print(f"   [Network Alert] Stopping batch run due to connection interruption: {err_str}", flush=True)
                    report["stopped_at_unit"] = unit_key
                    report["error_message"] = err_str
                    break

        return report

    def get_dashboard(self) -> Dict[str, Any]:
        """Returns the course-wide completion dashboard."""
        return self.tracker.get_dashboard_summary()
