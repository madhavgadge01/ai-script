"""
Generates a synthesized 50-page academic PDF with identifiable markers
distributed across pages to verify zero-truncation processing.
"""
from pathlib import Path
import pymupdf as fitz

def generate_large_sample_pdf(output_path: Path, num_pages: int = 50) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    for p in range(1, num_pages + 1):
        page = doc.new_page(width=595, height=842)
        # Running header
        page.insert_text((50, 40), "IGNOU BCA — BCS-011: Advanced Computer Systems", fontsize=9, color=(0.4, 0.4, 0.4))
        page.draw_line((50, 48), (545, 48), color=(0.8, 0.8, 0.8), width=0.5)

        # Unique marker per page
        marker = f"ACADEMIC_TOPIC_MARKER_PAGE_{p:02d}"
        body_text = f"""SECTION {p}.0 TOPIC STUDY UNIT {p}

{marker}
This is the official course text for section {p}.0 of the university curriculum.
Every concept covered on page {p} represents vital syllabus material.
Topic description: Detailed academic discourse on system component {p}, including architecture, bus timing, signal processing, and memory bandwidth considerations.

Key Definition for Page {p}:
Definition {p}: The technical specification {p} dictates system behavior under workload {p}.

Formula for Page {p}:
Performance_{p} = Clock_Speed_{p} * Efficiency_{p} / Latency_{p}
"""
        page.insert_textbox((50, 70, 545, 780), body_text, fontsize=10.5, fontname="helv", lineheight=1.4)

        # Running footer
        page.draw_line((50, 800), (545, 800), color=(0.8, 0.8, 0.8), width=0.5)
        page.insert_text((270, 818), f"Page {p}", fontsize=9, color=(0.4, 0.4, 0.4))

    doc.save(str(output_path))
    doc.close()
    return output_path

if __name__ == "__main__":
    p = generate_large_sample_pdf(Path("storage/raw_pdfs/large_sample_50p.pdf"), 50)
    print(f"50-page sample PDF created at: {p} ({p.stat().st_size} bytes)")
