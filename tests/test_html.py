import pytest
from pathlib import Path
from app.summarization.schemas import StructuredPage, SubSection, ExamCallout, MultiPageNotePlan
from app.html.generator import HTMLNoteGenerator
from app.pdf.metadata import AcademicHierarchy

def test_html_single_page_rendering():
    gen = HTMLNoteGenerator()
    page = StructuredPage(
        page_number=1,
        page_title="Page 1: Foundations of Computer Architecture",
        category_badge="ACADEMIC FOUNDATION",
        intro_paragraph="A computer is a high-speed calculating device executing stored instructions.",
        sections=[
            SubSection(
                heading="Von Neumann Principles",
                explanation="Detailed explanation of unified memory for instructions and data.",
                callouts=[
                    ExamCallout(
                        callout_type="definition",
                        title="Von Neumann Stored Program",
                        content="Architecture where program instructions and runtime operands share memory."
                    ),
                    ExamCallout(
                        callout_type="imp_exam_point",
                        title="Block Diagram Question",
                        content="Always draw the 4 major components: ALU, CU, Memory, and I/O."
                    )
                ],
                bullet_points=["Unified Memory", "Sequential Fetch-Decode-Execute"]
            )
        ],
        exam_summary="Master the Von Neumann architecture for 10-mark examination questions."
    )

    rendered = gen.render_single_page(page)

    assert 'class="note-chapter"' in rendered
    assert 'class="chapter-badge ng-tag"' in rendered
    assert "ACADEMIC FOUNDATION" in rendered
    assert "Page 1: Foundations of Computer Architecture" in rendered
    assert "class=\"callout callout-info ng-highlight" in rendered
    assert "[IMP] Block Diagram Question" in rendered

def test_html_sanitizer():
    gen = HTMLNoteGenerator()
    unsafe_content = """
    <div class="note-chapter">
      <h1>Safe Heading</h1>
      <script>alert('malicious')</script>
      <iframe src="http://evil.com"></iframe>
      <p onclick="steal()">Normal paragraph</p>
    </div>
    """
    clean = gen.sanitize_html(unsafe_content)
    assert "<script>" not in clean
    assert "alert" not in clean
    assert "<iframe" not in clean
    assert "onclick" not in clean
    assert "<h1>Safe Heading</h1>" in clean

def test_render_and_export_unit(tmp_path):
    gen = HTMLNoteGenerator()
    hierarchy = AcademicHierarchy(
        university="IGNOU",
        course="BCA",
        semester="Semester 1",
        subject_code="BCS-011",
        subject_name="Computer Basics",
        block_number=1,
        block_title="Hardware",
        unit_number=1,
        unit_title="Computer Architecture"
    )

    plan = MultiPageNotePlan(
        unit_number=1,
        unit_title="Computer Architecture",
        target_page_count=2,
        pages=[
            StructuredPage(
                page_number=1,
                page_title="Page 1: Intro",
                intro_paragraph="Intro text",
                sections=[SubSection(heading="Sec 1", explanation="Expl 1")]
            ),
            StructuredPage(
                page_number=2,
                page_title="Page 2: Components",
                intro_paragraph="Components text",
                sections=[SubSection(heading="Sec 2", explanation="Expl 2")]
            ),
        ]
    )

    result = gen.render_and_export_unit(hierarchy, plan, export_dir=tmp_path)

    assert result["total_pages"] == 2
    assert Path(result["preview_file"]).exists()
    assert (tmp_path / "BCA_BCS-011_U1" / "page_01.html").exists()
    assert (tmp_path / "BCA_BCS-011_U1" / "page_02.html").exists()
