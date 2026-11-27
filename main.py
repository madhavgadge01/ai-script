import sys
import argparse
from pathlib import Path

from config.settings import settings
from app.database.connection import init_db, get_db
from app.pdf.metadata import AcademicHierarchy
from app.pdf.reader import PDFReader
from app.extraction.cleaner import HeaderFooterCleaner
from app.extraction.extractor import PDFTextExtractor
from app.extraction.chunker import SemanticChunker
from app.summarization.engine import SummarizationEngine
from app.html.generator import HTMLNoteGenerator
from app.publishing.notes_guru_client import NotesGuruApiClient

def main():
    parser = argparse.ArgumentParser(description="UniNotes Content Engine — Academic Notes Processing CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: init
    subparsers.add_parser("init", help="Initialize database schema and storage directories")

    # Command: process
    proc_parser = subparsers.add_parser("process", help="Process a PDF into multi-page structured HTML notes")
    proc_parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    proc_parser.add_argument("--university", type=str, default="IGNOU", help="University name")
    proc_parser.add_argument("--course", type=str, required=True, help="Course code (e.g., BCA, BA)")
    proc_parser.add_argument("--semester", type=str, default=None, help="Semester (e.g., 'Semester 1')")
    proc_parser.add_argument("--subject-code", type=str, required=True, help="Subject code (e.g., BCS-011)")
    proc_parser.add_argument("--subject-name", type=str, required=True, help="Subject name")
    proc_parser.add_argument("--block-number", type=int, default=1, help="Block number")
    proc_parser.add_argument("--block-title", type=str, default="Foundation", help="Block title")
    proc_parser.add_argument("--unit-number", type=int, default=1, help="Unit number")
    proc_parser.add_argument("--unit-title", type=str, required=True, help="Unit title")
    proc_parser.add_argument("--force", action="store_true", help="Force re-processing even if hash matches")

    # Command: list
    subparsers.add_parser("list", help="List all processed units in the database")

    # Command: inspect-notesguru (Read-only Phase 1)
    insp_parser = subparsers.add_parser(
        "inspect-notesguru",
        help="Perform read-only inspection of live Notes Guru backend and generate reconciliation report"
    )
    insp_parser.add_argument("--course", type=str, default="BCA", help="Target course code to reconcile (default: BCA)")
    insp_parser.add_argument("--subject-code", type=str, default="BCS-011", help="Target subject code (default: BCS-011)")
    insp_parser.add_argument("--subject-name", type=str, default="Computer Basics and PC Software", help="Target subject name")
    insp_parser.add_argument("--unit-number", type=int, default=1, help="Target unit number (default: 1)")
    insp_parser.add_argument("--unit-title", type=str, default="Computers: Origin and Architecture", help="Target unit title")

    # Command: publish-notesguru (Production Publishing)
    pub_parser = subparsers.add_parser(
        "publish-notesguru",
        help="Execute controlled production publishing workflow to register hierarchy and publish 4-page note"
    )
    pub_parser.add_argument(
        "--export-dir",
        type=str,
        default="storage/exports/BCA_BCS-011_U1",
        help="Directory containing verified HTML pages"
    )
    pub_parser.add_argument(
        "--unit-title",
        type=str,
        default="Computers: Their Origin and Applications",
        help="Official target unit title"
    )

    # Command: bca-inventory
    subparsers.add_parser("bca-inventory", help="Display full machine-readable BCA syllabus inventory")

    # Command: bca-reconcile
    subparsers.add_parser("bca-reconcile", help="Reconcile complete BCA course hierarchy against Notes Guru backend")

    # Command: bca-license-audit
    subparsers.add_parser("bca-license-audit", help="Audit licensing permissions for all BCA units")

    # Command: bca-batch-process
    batch_parser = subparsers.add_parser("bca-batch-process", help="Process and publish BCA units in manageable batches")
    batch_parser.add_argument("--batch-size", type=int, default=3, help="Number of units to process in this batch (default: 3)")
    batch_parser.add_argument("--semester", type=int, default=None, help="Optionally target a specific semester (1-6)")
    batch_parser.add_argument("--subject-code", type=str, default=None, help="Optionally target a specific subject code (e.g. BCS-011)")

    # Command: bca-dashboard
    subparsers.add_parser("bca-dashboard", help="Display course-wide completion metrics and dashboard")

    # Command: bca-expand-sem1
    expand_parser = subparsers.add_parser("bca-expand-sem1", help="Expand Semester 1 study notes to meet 5-page depth rules")
    expand_parser.add_argument("--subject-code", type=str, default="BCS-011", help="Subject to expand (default: BCS-011)")
    expand_parser.add_argument("--semester", type=int, default=1, help="Semester number (1-6, default: 1)")
    expand_parser.add_argument("--batch-size", type=int, default=3, help="Max units to expand in this run (default: 3)")
    expand_parser.add_argument("--unit-key", type=str, default=None, help="Target specific unit key to expand")

    # Command: bca-expand-sem2
    expand_sem2_parser = subparsers.add_parser("bca-expand-sem2", help="Expand Semester 2 study notes to meet 5-page depth rules")
    expand_sem2_parser.add_argument("--subject-code", type=str, default="ECO-02", help="Subject to expand (default: ECO-02)")
    expand_sem2_parser.add_argument("--batch-size", type=int, default=3, help="Max units to expand in this run (default: 3)")
    expand_sem2_parser.add_argument("--unit-key", type=str, default=None, help="Target specific unit key to expand")

    args = parser.parse_args()

    # Ensure directories & database exist
    settings.ensure_directories()
    init_db()

    if args.command == "init":
        print("[✓] UniNotes Content Engine initialized successfully.")
        print(f"    Database: {settings.db_path}")
        print(f"    Exports:  {settings.exports_dir}")
        return

    if args.command == "list":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, course, subject_code, unit_number, unit_title, status, total_pages FROM units")
            units = cursor.fetchall()
            if not units:
                print("No units processed yet. Run 'python main.py process ...' to begin.")
                return
            print(f"\n{'Unit ID':<25} | {'Course':<8} | {'Subject':<10} | {'Status':<12} | {'Pages':<6}")
            print("-" * 75)
            for u in units:
                print(f"{u['id']:<25} | {u['course']:<8} | {u['subject_code']:<10} | {u['status']:<12} | {u['total_pages']:<6}")
        return

    if args.command == "inspect-notesguru":
        print("=" * 70)
        print("  Notes Guru Backend — Read-Only Inspection & Reconciliation Report")
        print("=" * 70)
        client = NotesGuruApiClient()
        print(f"  Target Base API: {client.base_url}")
        print(f"  Auth Token Set:  {bool(client._token)}")
        print("\n[1/3] Querying live academic hierarchy for IGNOU...")

        try:
            live_tree = client.fetch_ignou_hierarchy_tree(target_course_code=args.course)
        except Exception as e:
            print(f"Error querying Notes Guru API: {e}")
            sys.exit(1)

        college = live_tree.get("college")
        if not college:
            print("[-] IGNOU College record not found in Notes Guru backend!")
            return

        print(f"[+] College Found: {college['name']} (Code: {college['code']})")
        print(f"    Database _id:  {college['_id']}")
        print(f"    Active Status: {college.get('isActive')}")
        print(f"    Total Courses Under IGNOU: {live_tree['courses_total_count']}")

        print("\n[2/3] Checking registered courses under IGNOU:")
        for c in live_tree["courses"][:10]:
            print(f"    - [{c.get('code')}] {c.get('name')}")
        if live_tree["courses_total_count"] > 10:
            print(f"    ... and {live_tree['courses_total_count'] - 10} more courses.")

        source_syllabus = {
            "course_code": args.course,
            "course_name": "Bachelor of Computer Applications" if args.course.upper() == "BCA" else args.course,
            "semester_number": 1,
            "subject_code": args.subject_code,
            "subject_name": args.subject_name,
            "block_number": 1,
            "block_title": "Basics of Computer Hardware",
            "unit_number": args.unit_number,
            "unit_title": args.unit_title,
        }

        print("\n[3/3] Generating Local Hierarchy Reconciliation Report...")
        report = client.reconcile_hierarchy(live_tree, source_syllabus)

        print("\n" + "-" * 70)
        print("RECONCILIATION AUDIT SUMMARY:")
        print("-" * 70)
        print(f"1. Target Course [{args.course}]: Status = {report['course_status']}")
        if report['course_status'] == "MISSING":
            print(f"   Notice: '{args.course}' is not yet registered under IGNOU in Notes Guru.")
            print("   Action Needed Later: Create Course 'BCA : Bachelor of Computer Applications'")
            print("   (Note: Backend creates 6 default semesters upon course creation).")

        print("\n2. Existing Entities in Live Backend:")
        for er in report["existing_records"]:
            print(f"   [EXISTS] {er['entity']:<10}: {er.get('name') or er.get('title')} (_id: {er.get('_id')})")

        print("\n3. Missing Entities in Live Backend (Will require creation in later phase):")
        for mr in report["missing_records"]:
            details = mr.get("code") or mr.get("title") or mr.get("name") or f"Semester {mr.get('semesterNumber')}"
            print(f"   [MISSING] {mr['entity']:<10}: {details}")

        print("\n4. Safeguards & Duplicate Prevention Warnings:")
        for dr in report["duplicate_risks"]:
            print(f"   [WARNING] {dr}")

        print("\n" + "=" * 70)
        print("READ-ONLY INSPECTION COMPLETE.")
        print("Zero write operations executed. No records created, modified, or published.")
        print("=" * 70)
        return

    if args.command == "publish-notesguru":
        from app.publishing.publisher import NotesPublisher
        print("=" * 70)
        print("EXECUTING NOTES GURU PRODUCTION PUBLISHING WORKFLOW")
        print("=" * 70)
        publisher = NotesPublisher()
        result = publisher.publish_bca_unit_1(
            export_dir=args.export_dir,
            unit_title=args.unit_title
        )

        print("\nWorkflow Execution Log:")
        for log_entry in result["steps_log"]:
            print(f"  • {log_entry}")

        print("\n" + "=" * 70)
        print("PUBLICATION REPORT:")
        print("=" * 70)
        print(f"  College ID:      {result['college_id']}")
        print(f"  Course ID:       {result['course_id']} (BCA)")
        print(f"  Semester ID:     {result['semester_id']} (Semester 1)")
        print(f"  Subject ID:      {result['subject_id']} (BCS-011)")
        print(f"  Block ID:        {result['block_id']} (Block 1)")
        print(f"  Unit ID:         {result['unit_id']} (Unit 1)")
        print(f"  Note ID:         {result['note_id']}")
        print(f"  Pages Uploaded:  {result['page_count']}")
        print(f"  Status:          {result['status']}")
        print(f"  Is Published:    {result['is_published']}")
        print(f"  Public Note URL: {result['public_url']}")
        print(f"  Public Access:   {'VERIFIED (Accessible unauthenticated)' if result['unauthenticated_verified'] else 'CHECKING'}")
        print("=" * 70)
        return

    if args.command == "bca-inventory":
        import json
        inv_path = Path("config/bca_syllabus_inventory.json")
        if not inv_path.exists():
            print("Inventory not found. Generating...")
            from scripts.generate_bca_inventory import bca_curriculum
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        print("=" * 70)
        print("IGNOU BCA COMPLETE SYLLABUS INVENTORY")
        print("=" * 70)
        for s in data["semesters"]:
            print(f"\n[SEMESTER {s['semester_number']}]")
            for sub in s["subjects"]:
                u_cnt = sum(len(b['units']) for b in sub['blocks'])
                print(f"  • {sub['code']}: {sub['name']} ({sub['type']}, {sub['credits']} cr, {len(sub['blocks'])} blocks, {u_cnt} units)")
        return

    if args.command == "bca-reconcile":
        from app.publishing.orchestrator import BCACourseOrchestrator
        orch = BCACourseOrchestrator()
        print("=" * 70)
        print("RECONCILING BCA HIERARCHY AGAINST NOTES GURU BACKEND")
        print("=" * 70)
        rep = orch.run_reconciliation()
        print(f"Course: {rep['course']['code']} (_id: {rep['course']['_id']}) - Status: {rep['course']['status']}")
        print(f"Total Inventory Subjects: {rep['total_inventory_subjects']}")
        print(f"Existing in Notes Guru:   {rep['total_existing_subjects']}")
        print(f"Missing in Notes Guru:    {rep['total_missing_subjects']}")
        print("\nSemester Breakdown:")
        for sem in rep["semesters_summary"]:
            print(f"  Semester {sem['semester_number']} (ID: {sem['semester_id']}):")
            for sub in sem["subjects"]:
                tag = "[EXISTS]" if sub["status"] == "EXISTS" else "[MISSING]"
                print(f"    {tag} {sub['code']}: {sub['name']} (ID: {sub.get('existing_subject_id') or 'PENDING'})")
        return

    if args.command == "bca-license-audit":
        from app.publishing.orchestrator import BCACourseOrchestrator
        orch = BCACourseOrchestrator()
        print("=" * 70)
        print("BCA SYLLABUS SOURCE LICENSING & REPUBLICATION AUDIT")
        print("=" * 70)
        audit = orch.audit_all_licenses()
        print(f"Total Units Audited:      {audit['total_units']}")
        print(f"Authorized for Platform:  {audit['authorized_commercial']}")
        print(f"Blocked (Commercial/Paid): {audit['blocked_commercial']}")
        print(f"Blocked (Unauthorized):   {audit['blocked_unauthorized']}")
        print("\nCompliance Guidelines:")
        print("  1. Original Academic Synthesis: Permitted for full platform distribution with pricing.")
        print("  2. eGyanKosh (CC BY-NC-SA 4.0): Non-commercial only; cannot be sold behind a paid paywall.")
        return

    if args.command == "bca-batch-process":
        from app.publishing.orchestrator import BCACourseOrchestrator
        orch = BCACourseOrchestrator()
        print("=" * 70)
        target_info = f"Batch Size: {args.batch_size}"
        if args.semester:
            target_info += f" | Semester: {args.semester}"
        if args.subject_code:
            target_info += f" | Subject: {args.subject_code}"
        print(f"EXECUTING BCA BATCH PROCESSING ({target_info})")
        print("=" * 70)
        report = orch.process_next_pending_units(
            max_units=args.batch_size,
            semester=args.semester,
            subject_code=args.subject_code
        )
        print(f"\nBatch Summary:")
        print(f"  Attempted: {report['units_attempted']}")
        print(f"  Completed: {report['units_completed']}")
        if report.get("quota_exhausted"):
            print(f"  [QUOTA NOTICE] Stopped at: {report['stopped_at_unit']}")
            print(f"  Reason: {report['error_message']}")
        print("\nProcessed Units:")
        for r in report["processed_records"]:
            print(f"  • {r.get('unit_key')}: Status={r.get('status')} | URL={r.get('url')} | Reason={r.get('reason')}")
        return

    if args.command == "bca-dashboard":
        from app.publishing.orchestrator import BCACourseOrchestrator
        orch = BCACourseOrchestrator()
        dash = orch.get_dashboard()
        print("=" * 70)
        print("COURSE-WIDE COMPLETION DASHBOARD: IGNOU BCA")
        print("=" * 70)
        print(f"  Total Semesters:  {dash['total_semesters']}")
        print(f"  Total Subjects:   {dash['total_subjects']}")
        print(f"  Total Blocks:     {dash['total_blocks']}")
        print(f"  Total Units:      {dash['total_units']}")
        print(f"  Completed Notes:  {dash['completed_notes']}")
        print(f"  Pending Notes:    {dash['pending_notes']}")
        print(f"  Blocked Units:    {dash['blocked_units']}")
        print("\nSemester Progress Breakdown:")
        for s in dash["semesters_breakdown"]:
            print(f"  Semester {s['semester']}: {s['published_count']} Published / {s['units_count']} Total Units")
        print("=" * 70)
        return

    if args.command in ("bca-expand-sem1", "bca-expand-sem2"):
        from app.publishing.expansion_engine import SemesterContentExpander
        expander = SemesterContentExpander()
        sem = getattr(args, "semester", 2 if args.command == "bca-expand-sem2" else 1)
        if args.unit_key:
            print("=" * 70)
            print(f"EXPANDING TARGET UNIT: {args.unit_key}")
            print("=" * 70)
            res = expander.expand_unit(args.unit_key, min_pages=5)
            print(f"Result: {res}")
            return

        report = expander.expand_subject(subject_code=args.subject_code, semester=sem, max_units=args.batch_size)
        print("\n" + "=" * 70)
        print(f"EXPANSION BATCH SUMMARY ({args.subject_code} | Semester {sem}):")
        print("=" * 70)
        print(f"  Total Units in Subject:    {report['total_units']}")
        print(f"  Units Expanded This Run:   {report['units_expanded']}")
        print(f"  Units Already Compliant:   {report['units_already_compliant']}")
        if report.get("quota_exhausted"):
            print(f"  [QUOTA NOTICE] Stopped at: {report['stopped_at_unit']}")
            print(f"  Reason: {report['error_message']}")
        return

    if args.command == "process":
        pdf_path = Path(args.pdf_path)
        if not pdf_path.exists():
            print(f"Error: File not found at {pdf_path}")
            sys.exit(1)

        hierarchy = AcademicHierarchy(
            university=args.university,
            course=args.course,
            semester=args.semester,
            subject_code=args.subject_code,
            subject_name=args.subject_name,
            block_number=args.block_number,
            block_title=args.block_title,
            unit_number=args.unit_number,
            unit_title=args.unit_title,
        )

        print(f"\n[1/4] Inspecting PDF: {pdf_path.name}")
        with PDFReader(pdf_path) as reader:
            pdf_hash = reader.get_sha256()
            meta = reader.get_metadata()
            print(f"      Pages: {meta['page_count']} | Hash: {pdf_hash[:12]}...")

        print("[2/4] Extracting text and cleaning running headers/footers...")
        extractor = PDFTextExtractor()
        extracted_pages = extractor.extract_document(pdf_path)
        chunker = SemanticChunker()
        chunks = chunker.create_chunks(extracted_pages)
        print(f"      Extracted {len(extracted_pages)} pages into {len(chunks)} semantic chunks.")

        print("[3/4] Running AI Multi-Page Summarization with Gemini...")
        engine = SummarizationEngine()
        plan = engine.process_unit(hierarchy, extracted_pages, pdf_hash, force_reprocess=args.force)
        print(f"      Generated {len(plan.pages)} structured academic pages.")

        print("[4/4] Rendering Semantic HTML Notes with Notes Guru styling...")
        html_gen = HTMLNoteGenerator()
        export_result = html_gen.render_and_export_unit(hierarchy, plan)

        print("\n" + "=" * 60)
        print("✓ SUCCESS: Unit processed and structured HTML notes generated!")
        print("=" * 60)
        print(f"  Unit:         {hierarchy.subject_code} Unit {hierarchy.unit_number}: {hierarchy.unit_title}")
        print(f"  Total Pages:  {export_result['total_pages']} structured HTML pages")
        print(f"  Preview Book: {export_result['preview_file']}")
        print(f"  Export Dir:   {export_result['export_dir']}")
        print("\nEach generated HTML page is ready for insertion into Notes Guru Structured Page Content.")

if __name__ == "__main__":
    main()
