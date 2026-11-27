# UniNotes Content Engine

Modular content processing and academic note generation engine for educational platforms. Transforms dense educational PDF textbooks into concise, structured, exam-oriented multi-page HTML notes.

Built specifically for distance learning curricula (e.g., IGNOU BCA, BA) with strict academic hierarchy preservation and zero hallucination.

---

## 1. Architecture Overview

```
University → Course → Semester → Subject → Block → Unit → Multiple Structured HTML Pages
```

- **Extraction:** PyMuPDF (`fitz`) with page-by-page analysis, OCR-need detection, and margin-frequency boilerplate header/footer removal.
- **AI Engine:** Google Gemini API (`google-genai` SDK) utilizing Pydantic structured schemas (`MultiPageNotePlan`, `StructuredPage`).
- **Cost & Safety:** Per-document token limits, strict spend ceilings, and exponential backoff retry handling.
- **Persistence:** Local SQLite database tracking processing runs, duplicate hash checks, chunk checkpoints, and page exports.
- **HTML & Styling:** Jinja2 templates generating semantic HTML formatted with native **Notes Guru** CSS classes (`.note-chapter`, `.chapter-badge`, `.ng-tag`, `.ng-highlight`, `.ng-card`).

---

## 2. Directory Structure

```
uninotes-content-engine/
├── .env                       # Environment variables (API keys, models, budget)
├── .env.example               # Template for configuration
├── .gitignore                 # Storage, credentials and cache exclusions
├── requirements.txt           # Python dependencies
├── main.py                    # Unified CLI tool
├── config/
│   ├── __init__.py
│   └── settings.py            # Settings, paths, and budget limits
├── app/
│   ├── database/              # SQLite connection & schema models
│   ├── pdf/                   # PyMuPDF document loader and metadata
│   ├── extraction/            # Header/footer cleaner, extractor, chunker
│   ├── ai/                    # Gemini client and token/cost tracker
│   ├── summarization/         # Prompts, schemas, and checkpointing engine
│   └── html/                  # Jinja2 renderer & HTML sanitizer
├── templates/
│   ├── page.html              # Individual structured page template
│   └── preview_book.html      # Multi-page interactive preview reader
├── storage/
│   ├── raw_pdfs/              # Downloaded/input PDFs
│   ├── exports/               # Generated HTML pages and preview book
│   └── uninotes.db            # SQLite database
└── tests/                     # Unit and integration test suite
```

---

## 3. Quick Start

### A. Environment Setup
```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. Verify dependencies
pip install -r requirements.txt

# 3. Configure .env
cp .env.example .env
# Ensure GEMINI_API_KEY is populated
```

### B. Initialize Database
```bash
python main.py init
```

### C. Process a PDF Unit
```bash
python main.py process storage/raw_pdfs/sample_unit.pdf \
  --university "IGNOU" \
  --course "BCA" \
  --semester "Semester 1" \
  --subject-code "BCS-011" \
  --subject-name "Computer Basics and PC Software" \
  --block-number 1 \
  --block-title "Basics of Computer Hardware" \
  --unit-number 1 \
  --unit-title "Computers: Origin and Architecture"
```

### D. View Processed Units
```bash
python main.py list
```

---

## 4. Notes Guru Admin Panel Integration

The generated HTML notes in `storage/exports/<unit_slug>/` are structured page-by-page (`page_01.html`, `page_02.html`, ...):
1. Navigate to `/notes` → **Add Notes**.
2. Select **IGNOU** → Course → Semester → Subject → Block → **Create Notes**.
3. Fill Unit Number and Unit Title.
4. Paste `page_01.html` into **Structured Page HTML Content**.
5. Click **Add Page**, paste `page_02.html`, and repeat for all pages.
6. Verify preview and save as **Draft**.
# ai-script
