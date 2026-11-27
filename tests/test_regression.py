import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from config.settings import settings
from app.pdf.metadata import AcademicHierarchy
from app.pdf.reader import PDFReader
from app.extraction.extractor import PDFTextExtractor
from app.extraction.chunker import SemanticChunker
from app.summarization.engine import SummarizationEngine
from app.summarization.schemas import StructuredPage, SubSection, ExamCallout, TableData, MultiPageNotePlan
from app.html.generator import HTMLNoteGenerator
from app.database.connection import get_db, init_db
from tests.create_large_sample_pdf import generate_large_sample_pdf

def test_db_isolation(tmp_path):
    """Verify that running pipeline tests never modifies storage/uninotes.db."""
    prod_db = Path("storage/uninotes.db")
    assert prod_db.exists(), "Production DB should exist"
    
    # Calculate sha256 before
    sha_before = hashlib.sha256(prod_db.read_bytes()).hexdigest()

    # Perform operations in test environment (which is isolated by conftest)
    test_db = tmp_path / "isolation_check.db"
    init_db(test_db)
    
    gen = HTMLNoteGenerator(db_path=test_db)
    hierarchy = AcademicHierarchy(
        university="IGNOU",
        course="BCA",
        subject_code="BCS-011",
        subject_name="Test Isolation",
        block_number=1,
        block_title="Test Block",
        unit_number=99,
        unit_title="Test Unit"
    )
    plan = MultiPageNotePlan(
        unit_number=99,
        unit_title="Test Unit",
        target_page_count=1,
        pages=[StructuredPage(
            page_number=1,
            page_title="Page 1",
            intro_paragraph="Intro",
            sections=[SubSection(heading="H1", explanation="E1")]
        )]
    )
    gen.render_and_export_unit(hierarchy, plan, export_dir=tmp_path / "exports")

    # Verify production DB is completely untouched
    sha_after = hashlib.sha256(prod_db.read_bytes()).hexdigest()
    assert sha_before == sha_after, "Production database was modified during testing!"

def test_large_document_no_truncation(tmp_path):
    """
    Synthesize a 50-page document with identifiable markers on every page.
    Verify that 100% of chunks and markers are accounted for without truncation.
    """
    large_pdf_path = tmp_path / "large_50p.pdf"
    generate_large_sample_pdf(large_pdf_path, num_pages=50)

    extractor = PDFTextExtractor()
    pages = extractor.extract_document(large_pdf_path)
    assert len(pages) == 50

    chunker = SemanticChunker(max_chars=4000)
    chunks = chunker.create_chunks(pages)
    assert len(chunks) >= 5, f"Expected at least 5 chunks from 50 pages, got {len(chunks)}"

    engine = SummarizationEngine(chunker=chunker, db_path=tmp_path / "test.db")
    target_pages = engine.calculate_target_page_count(len(pages), len(chunks))
    assert 8 <= target_pages <= 12

    clusters = engine._cluster_chunks(chunks, target_pages)
    assert len(clusters) == target_pages

    # Verify that every single marker from page 1 to 50 is accounted for across chunk clusters
    all_cluster_text = "\n".join([
        "\n".join([c.content for c in cluster])
        for cluster in clusters
    ])

    for p in range(1, 51):
        expected_marker = f"ACADEMIC_TOPIC_MARKER_PAGE_{p:02d}"
        assert expected_marker in all_cluster_text, f"Marker {expected_marker} was dropped in chunking!"

def test_checkpoint_and_resumption(tmp_path):
    """
    Simulate an API failure on page 2.
    Verify that on resumption, page 1 is NOT reprocessed and resumes from page 2.
    """
    test_db = tmp_path / "resume_test.db"
    init_db(test_db)

    # Mock client with stateful failure simulation
    mock_client = MagicMock()
    call_counts = {"page_calls": 0}

    def fake_generate(prompt, response_schema, system_instruction, **kwargs):
        call_counts["page_calls"] += 1
        # Extract page number requested from prompt
        if "Page 2 of" in prompt and call_counts["page_calls"] == 2:
            raise RuntimeError("Simulated API 503 Transient Failure on Page 2")

        return StructuredPage(
            page_number=1,
            page_title="Generated Page",
            intro_paragraph="Academic overview",
            sections=[SubSection(heading="Section A", explanation="Detailed explanation")]
        )

    mock_client.generate_structured.side_effect = fake_generate
    mock_client.tracker.get_metrics.return_value = MagicMock(
        model="gemini-3.8-flash", input_tokens=100, output_tokens=100,
        total_tokens=200, estimated_cost_usd=0.0001, duration_seconds=1.0, retries=0
    )

    hierarchy = AcademicHierarchy(
        university="IGNOU", course="BCA", subject_code="BCS-011",
        subject_name="Test", block_number=1, block_title="B1",
        unit_number=1, unit_title="Unit 1"
    )

    # Synthesize small 4-page doc
    from tests.create_sample_pdf import generate_sample_academic_pdf
    pdf_path = tmp_path / "small.pdf"
    generate_sample_academic_pdf(pdf_path)

    extractor = PDFTextExtractor()
    extracted_pages = extractor.extract_document(pdf_path)

    engine = SummarizationEngine(client=mock_client, db_path=test_db)

    # Run 1: Must fail on Page 2
    with pytest.raises(RuntimeError, match="Simulated API 503"):
        engine.process_unit(hierarchy, extracted_pages, pdf_hash="hash_123", force_reprocess=False)

    # Verify Page 1 was checkpointed successfully
    unit_id = f"{hierarchy.course}_{hierarchy.subject_code}_B{hierarchy.block_number}_U{hierarchy.unit_number}"
    with get_db(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, chunk_index, status FROM chunk_checkpoints WHERE unit_id = ?", (unit_id,))
        checkpoints = cursor.fetchall()
        assert len(checkpoints) >= 1
        assert checkpoints[0]["status"] == "COMPLETED"

    # Run 2: Reset failure behavior. Call counts before resume:
    calls_before_resume = call_counts["page_calls"]

    def fake_generate_success(prompt, response_schema, system_instruction, **kwargs):
        call_counts["page_calls"] += 1
        return StructuredPage(
            page_number=2,
            page_title="Resumed Page 2",
            intro_paragraph="Academic overview",
            sections=[SubSection(heading="Section B", explanation="Detailed explanation")]
        )

    mock_client.generate_structured.side_effect = fake_generate_success

    plan = engine.process_unit(hierarchy, extracted_pages, pdf_hash="hash_123", force_reprocess=False)
    assert plan is not None
    assert len(plan.pages) >= 2

    # Checkpoint verification: Page 1 was NOT called again; only remaining pages were generated
    # Total calls in Run 2 should be (target_pages - 1)
    new_calls = call_counts["page_calls"] - calls_before_resume
    assert new_calls == (len(plan.pages) - 1), f"Expected {len(plan.pages) - 1} calls on resume, got {new_calls}"

def test_idempotent_duplicate_skip(tmp_path):
    """
    Verify that processing an identical unit twice makes ZERO API calls on the second attempt.
    """
    test_db = tmp_path / "dup_test.db"
    init_db(test_db)

    mock_client = MagicMock()
    def fake_dup_generate(prompt, response_schema, **kwargs):
        import re
        m = re.search(r'Page (\d+) of', prompt)
        p_num = int(m.group(1)) if m else 1
        return StructuredPage(
            page_number=p_num,
            page_title=f"Page {p_num}",
            intro_paragraph="Intro",
            sections=[SubSection(heading="Sec", explanation="Exp")]
        )

    mock_client.generate_structured.side_effect = fake_dup_generate
    mock_client.tracker.get_metrics.return_value = MagicMock(
        model="gemini-3.8-flash", input_tokens=100, output_tokens=100,
        total_tokens=200, estimated_cost_usd=0.0001, duration_seconds=1.0, retries=0
    )

    from tests.create_sample_pdf import generate_sample_academic_pdf
    pdf_path = tmp_path / "dup_sample.pdf"
    generate_sample_academic_pdf(pdf_path)

    extractor = PDFTextExtractor()
    pages = extractor.extract_document(pdf_path)

    hierarchy = AcademicHierarchy(
        university="IGNOU", course="BCA", subject_code="BCS-011",
        subject_name="Test", block_number=1, block_title="B1",
        unit_number=2, unit_title="Unit 2"
    )

    engine = SummarizationEngine(client=mock_client, db_path=test_db)

    # First attempt: generates and populates DB
    plan1 = engine.process_unit(hierarchy, pages, pdf_hash="dup_hash_abc", force_reprocess=False)
    generator = HTMLNoteGenerator(db_path=test_db)
    generator.render_and_export_unit(hierarchy, plan1, export_dir=tmp_path / "exports")

    first_run_calls = mock_client.generate_structured.call_count
    assert first_run_calls > 0

    # Second attempt with identical hash: MUST make ZERO new API calls
    mock_client.generate_structured.reset_mock()
    plan2 = engine.process_unit(hierarchy, pages, pdf_hash="dup_hash_abc", force_reprocess=False)

    assert mock_client.generate_structured.call_count == 0, "Duplicate run made unexpected Gemini API calls!"
    assert plan2 is not None
    assert len(plan2.pages) == len(plan1.pages)

def test_table_rendering():
    """Verify TableData schema renders semantic HTML table with existing styling."""
    gen = HTMLNoteGenerator()
    page = StructuredPage(
        page_number=1,
        page_title="Page 1: Architecture Comparison",
        category_badge="TECHNICAL COMPARISON",
        intro_paragraph="Comparative evaluation of computer transfer architectures.",
        sections=[
            SubSection(
                heading="I/O Modes Comparison",
                explanation="Analysis of CPU utilization across transfer modes.",
                table=TableData(
                    headers=["Mode", "CPU Utilization", "Transfer Rate", "Hardware Complexity"],
                    rows=[
                        ["Programmed I/O", "100% (Busy Waiting)", "Low", "Low"],
                        ["Interrupt-Driven I/O", "Moderate", "Medium", "Moderate"],
                        ["DMA Controller", "Near 0%", "High (Bus Speed)", "High"]
                    ],
                    caption="Table 1.1: I/O Data Transfer Mechanism Comparison"
                ),
                callouts=[
                    ExamCallout(
                        callout_type="imp_exam_point",
                        title="[IMP] 10-Mark Table Question",
                        content="Draw and populate this table in the examination."
                    )
                ]
            )
        ]
    )

    rendered = gen.render_single_page(page)

    assert "<table" in rendered
    assert "Table 1.1: I/O Data Transfer Mechanism Comparison" in rendered
    assert ">Mode</th>" in rendered
    assert ">CPU Utilization</th>" in rendered
    assert ">Programmed I/O</td>" in rendered
    assert ">DMA Controller</td>" in rendered
    # Verify no double [IMP]
    assert "[IMP] [IMP]" not in rendered
    assert "[IMP] 10-Mark Table Question" in rendered
