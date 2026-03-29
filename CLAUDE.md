# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medical study AI that generates structured notes for a first-year medical student. Workflow: ingest PDFs → vector retrieval → adaptive top_k → Claude-generated markdown/docx notes. Served via a FastAPI web app with a student-facing download page and a password-protected admin panel.

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run the web server
ADMIN_USER=admin ADMIN_PASS=yourpassword python server.py
# Student page:  http://localhost:8000
# Admin panel:   http://localhost:8000/admin

# Ingest a PDF into the shared vector index
python app/ingest.py <pdf_path> --block GI --source-type lecture --language FR

# Generate notes for a single objective
python app/notes.py --objective "Describe the mechanisms of acute pancreatitis" --language FR --output notes.md

# Generate notes from an objectives file (txt/pdf/docx)
python app/notes.py --objectives-file objectives.docx --language FR --output notes.md

# Reset (delete and rebuild) the vector index
python app/reset_index.py

# Test retrieval
python app/test_query.py
python app/test_chunks.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

### Data Flow
1. **Ingest** (`app/ingest.py`): PDFs → text chunks → HuggingFace embeddings (`paraphrase-multilingual-mpnet-base-v2`) → LlamaIndex vector store at `app/indexes/shared/`. Deduplication via MD5 hash. Rich metadata tagging: `block`, `source_type`, `language`, `topic`, `title`, `filename`, `file_hash`, `page`.

2. **Query** (`app/query.py`): `retrieve()` performs semantic similarity search with optional metadata filters on `block`, `source_type`, `language`. Returns `NodeWithScore` list.

3. **Adaptive top_k** (`app/adaptive_top_k.py`): Determines how many chunks to retrieve per objective based on four signals:
   - Leading verb (narrow: define/list/identify → lower; broad: explain/describe/compare → higher)
   - Breadth keywords (mechanisms/types/complications → +2 max)
   - Conjunctions (and/et/or/ou → +1)
   - Word count (≤6 → -1; ≥12 → +1)
   - Score ≥2 → top_k=16; score ≤-2 → top_k=4; default top_k=10

4. **Note generation** (`app/notes.py`): Claude Opus 4.6 generates notes using language/style-specific prompts from `prompts/` directory. Supports `--style detailed|concise`. Outputs markdown and/or `.docx`.

5. **Objectives parsing** (`app/objectives.py`): Uses Claude to extract learning objectives from `.txt`, `.pdf`, or `.docx` files, ignoring headers, resource lists, and other noise.

6. **Export** (`app/export.py`): Converts markdown notes to formatted `.docx` with proper headings, bullet lists, bold formatting, and blockquotes.

7. **Web server** (`server.py`): FastAPI app serving the student page, admin panel, and API routes. Generated `.docx` files are saved to `outputs/` and served for download. Note generation runs as a background thread; the admin page polls `/api/jobs/{job_id}` for status.

### Web Server Routes
- `GET /` — student notes page (browse + download)
- `GET /admin` — admin panel (HTTP Basic Auth)
- `GET /api/notes` — list available `.docx` files in `outputs/`
- `GET /download/{filename}` — download a `.docx` file
- `POST /api/ingest` — upload and ingest a PDF (admin only)
- `POST /api/generate` — upload objectives file and trigger generation (admin only)
- `GET /api/jobs/{job_id}` — poll generation job status

### Auth
Admin credentials are set via environment variables `ADMIN_USER` (default: `admin`) and `ADMIN_PASS` (default: `changeme`). Always override `ADMIN_PASS` in production.

### Prompt Templates (`prompts/`)
Six templates named `{language}_{style}.md` where language ∈ {en, fr, mixed} and style ∈ {detailed, concise}. Templates use `{context}` and `{objective}` placeholders. Rules: bullets only (no tables), `→` for causality, `↑`/`↓` for changes, **bold** for key terms and drugs.

### Valid Metadata Values
- `--block`: `GI`, `cardio`, `respiratory`, `neuro`, `renal`, `hematology`, `pharmacology`, `anatomy`, `general`
- `--source-type`: `lecture`, `textbook`, `notes`, `objectives`
- `--language`: `FR`, `EN`

### Key Files
- `server.py` — FastAPI web server (main entry point for the web app)
- `app/notes.py` — note generation logic
- `app/ingest.py` — PDF ingestion pipeline
- `app/query.py` — retrieval layer
- `app/export.py` — markdown → .docx conversion
- `prompts/` — edit these to change note style/format
- `static/` — frontend HTML pages
- `outputs/` — generated .docx files (gitignored)
- `app/indexes/shared/` — vector store (gitignored, rebuilt with `reset_index.py`)
