import pytest
from pathlib import Path
from tests.create_sample_pdf import generate_sample_academic_pdf
from app.pdf.reader import PDFReader
from app.extraction.cleaner import HeaderFooterCleaner
from app.extraction.extractor import PDFTextExtractor
from app.extraction.chunker import SemanticChunker

@pytest.fixture(scope="module")
def sample_pdf_path(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data") / "test_unit.pdf"
    generate_sample_academic_pdf(fn)
    return fn

def test_pdf_reader_loading_and_hash(sample_pdf_path):
    with PDFReader(sample_pdf_path) as reader:
        meta = reader.get_metadata()
        sha = reader.get_sha256()

        assert meta["page_count"] == 4
        assert len(sha) == 64  # SHA-256 string length

def test_extraction_and_boilerplate_removal(sample_pdf_path):
    cleaner = HeaderFooterCleaner(repetition_threshold=0.5)
    extractor = PDFTextExtractor(cleaner=cleaner)
    pages = extractor.extract_document(sample_pdf_path)

    assert len(pages) == 4
    for p in pages:
        assert not p.is_empty
        assert not p.needs_ocr
        # Header must be cleaned out from cleaned_text
        assert "IGNOU BCA — BCS-011" not in p.cleaned_text
        # Footers like 'Page 1' must be cleaned out
        assert "\nPage " not in p.cleaned_text
        # Content must remain intact
        assert len(p.cleaned_text) > 100

def test_heading_detection(sample_pdf_path):
    extractor = PDFTextExtractor()
    pages = extractor.extract_document(sample_pdf_path)

    all_headings = []
    for p in pages:
        all_headings.extend(p.headings)

    # Check that numbered sections were detected
    found_1_0 = any("1.0" in h or "INTRODUCTION" in h for h in all_headings)
    found_1_1 = any("1.1" in h or "CENTRAL PROCESSING" in h for h in all_headings)
    assert found_1_0, f"Failed to detect 1.0 in headings: {all_headings}"
    assert found_1_1, f"Failed to detect 1.1 in headings: {all_headings}"

def test_semantic_chunking(sample_pdf_path):
    extractor = PDFTextExtractor()
    pages = extractor.extract_document(sample_pdf_path)

    chunker = SemanticChunker(max_chars=2000)
    chunks = chunker.create_chunks(pages)

    assert len(chunks) >= 1
    total_chunk_words = sum(c.word_count for c in chunks)
    assert total_chunk_words > 200
    # Every chunk must have a heading and content
    for c in chunks:
        assert c.heading
        assert len(c.content.strip()) > 50
