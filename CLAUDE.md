# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medical study AI that generates structured notes for a first-year medical student. Workflow: ingest PDFs → vector retrieval → adaptive top_k → Claude-generated markdown/docx notes.

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

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

3. **Adaptive top_k** (`app/notes.py:_adaptive_top_k()`): Determines how many chunks to retrieve per objective based on four signals:
   - Leading verb (narrow: define/list/identify → lower; broad: explain/describe/compare → higher)
   - Breadth keywords (mechanisms/types/complications → +2 max)
   - Conjunctions (and/et/or/ou → +1)
   - Word count (≤6 → -1; ≥12 → +1)
   - Score ≥2 → top_k=16; score ≤-2 → top_k=4; default top_k=10

4. **Note generation** (`app/notes.py`): Claude Opus 4.6 generates notes using language/style-specific prompts from `prompts/` directory. Supports `--style detailed|concise`. Outputs markdown and/or `.docx`.

5. **Objectives parsing** (`app/objectives.py`): Parses learning objectives from `.txt`, `.pdf`, or `.docx` files. Cleans blank lines and single-char artifacts.

### Prompt Templates (`prompts/`)
Six templates named `{language}_{style}.md` where language ∈ {en, fr, mixed} and style ∈ {detailed, concise}. Templates use `{context}` and `{objective}` placeholders. Rules: bullets only (no tables), `→` for causality, `↑`/`↓` for changes, **bold** for key terms and drugs.

### Valid Metadata Values
- `--block`: `GI`, `cardio`, `respiratory`, `neuro`, `renal`, `hematology`, `pharmacology`, `anatomy`, `general`
- `--source-type`: `lecture`, `textbook`, `review`, `other`
- `--language`: `FR`, `EN`

### Key Files
- `app/notes.py` — main entry point for note generation
- `app/ingest.py` — PDF ingestion pipeline
- `app/query.py` — retrieval layer
- `prompts/` — edit these to change note style/format
- `app/indexes/shared/` — vector store (gitignored, rebuilt with `reset_index.py`)
