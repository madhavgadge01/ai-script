import os
import pytest
from pathlib import Path
from tests.create_sample_pdf import generate_sample_academic_pdf
from config.settings import settings
from app.pdf.metadata import AcademicHierarchy
from app.pdf.reader import PDFReader
from app.extraction.extractor import PDFTextExtractor
from app.summarization.engine import SummarizationEngine
from app.html.generator import HTMLNoteGenerator

@pytest.mark.skipif(not os.getenv("RUN_LIVE_API_TESTS"), reason="Live Gemini tests only run when RUN_LIVE_API_TESTS=1 is set")
def test_full_pipeline_with_gemini(tmp_path):
    # Ensure sample PDF exists
    sample_pdf = tmp_path / "bcs011_u1.pdf"
    generate_sample_academic_pdf(sample_pdf)

    # 1. Academic Hierarchy
    hierarchy = AcademicHierarchy(
        university="IGNOU",
        course="BCA",
        semester="Semester 1",
        subject_code="BCS-011",
        subject_name="Computer Basics and PC Software",
        block_number=1,
        block_title="Basics of Computer Hardware",
        unit_number=1,
        unit_title="Computer Architecture and Data Organization"
    )

    # 2. PDF Extraction & Hashing
    with PDFReader(sample_pdf) as reader:
        pdf_hash = reader.get_sha256()
        assert len(pdf_hash) == 64

    extractor = PDFTextExtractor()
    extracted_pages = extractor.extract_document(sample_pdf)
    assert len(extracted_pages) == 4

    # 3. Gemini Summarization with Structured Output
    engine = SummarizationEngine()
    plan = engine.process_unit(
        hierarchy=hierarchy,
        extracted_pages=extracted_pages,
        pdf_hash=pdf_hash,
        force_reprocess=True
    )

    assert plan is not None
    assert len(plan.pages) >= 2
    metrics = engine.client.tracker.get_metrics()
    assert metrics.input_tokens > 0
    assert metrics.output_tokens > 0
    print(f"\n[Test Metrics] Model: {metrics.model} | Input Tokens: {metrics.input_tokens} | Output Tokens: {metrics.output_tokens} | Est. Cost: ${metrics.estimated_cost_usd:.6f}")

    # 4. HTML Generation & Export
    generator = HTMLNoteGenerator()
    export_result = generator.render_and_export_unit(hierarchy, plan, export_dir=tmp_path / "exports")

    assert export_result["total_pages"] == len(plan.pages)
    assert Path(export_result["preview_file"]).exists()

    # Check Page 1 HTML content
    p1_file = Path(export_result["pages"][0]["file_path"])
    assert p1_file.exists()
    p1_html = p1_file.read_text(encoding="utf-8")
    assert "class=\"note-chapter\"" in p1_html
    assert "class=\"chapter-badge ng-tag\"" in p1_html
