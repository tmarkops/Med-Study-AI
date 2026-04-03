# med-study-ai

Generates structured study notes from your own course materials, organized by learning objectives. Includes a web interface for admins to ingest PDFs and generate notes, and a clean student-facing page to browse and download them.

## How it works

**1. Ingest** — PDFs are parsed page-by-page and embedded into a local LlamaIndex vector store. Each chunk is tagged with metadata (block, source type, language). Deduplication is done by MD5 hash so re-ingesting the same file is a no-op.

**2. Retrieve** — For each learning objective, the most relevant chunks are pulled from the index using semantic similarity. Metadata filters (block, source type, language) narrow retrieval to the right subset of your materials.

**3. Adaptive top_k** — The number of chunks retrieved is inferred from the objective's complexity using four signals:

| Signal | Effect |
|---|---|
| Leading verb (`define`, `list` → narrow; `explain`, `describe`, `compare` → broad) | ±1–2 |
| Breadth keywords in objective (`mechanisms`, `complications`, `types`, …) | +1 per hit, max +2 |
| Conjunctions (`and`/`et`/`or`/`ou`) | +1 |
| Word count (≤6 words → short; ≥12 words → long) | ±1 |

Score ≥ 2 → `top_k=16` · Score ≤ −2 → `top_k=4` · Otherwise → `top_k=10`. Override with `--top-k N`.

**4. Generate** — Retrieved chunks are passed to Claude (`claude-opus-4-6`) with a prompt tailored to language (`EN`/`FR`/`MIXED`) and style (`detailed`/`concise`). Prompts live in `prompts/` as plain markdown files and can be edited directly.

**5. Serve** — A FastAPI server exposes a student-facing notes page and a password-protected admin panel.

## Project structure

```
app/
  ingest.py         — PDF ingestion and vector index management
  query.py          — Retrieval with metadata filtering
  notes.py          — Note generation (adaptive top_k + Claude API)
  objectives.py     — Parse objectives from .txt / .pdf / .docx
  export.py         — Convert markdown notes to .docx
  adaptive_top_k.py — Infer top_k from objective complexity
  reset_index.py    — Wipe and rebuild the index
prompts/
  fr_detailed.md, en_detailed.md, …   — Prompt templates per language/style
static/
  index.html        — Student-facing notes page
  admin.html        — Admin panel (ingest PDFs, generate notes)
outputs/            — Generated .docx notes served for download
server.py           — FastAPI web server
```

## Running the server

```bash
source venv/bin/activate
ADMIN_USER=admin ADMIN_PASS=yourpassword python server.py
```

- Student page: `http://localhost:8000`
- Admin panel: `http://localhost:8000/admin` (HTTP Basic Auth)

The admin panel lets you upload PDFs to ingest and upload an objectives file to trigger note generation. Generation runs as a background job; the page polls for completion and shows a download link when done.

## CLI usage

```bash
# Ingest a PDF
python app/ingest.py path/to/lecture.pdf --block GI --source-type lecture --language FR

# Generate notes for a single objective
python app/notes.py --objective "3. Describe the pathophysiology of H. pylori" --language FR

# Generate notes from an objectives file
python app/notes.py --objectives-file objectifs.pdf --block GI --language FR --output notes.md
```

## TODO

- [ ] Add per-file delete to `ingest.py` (remove chunks by `file_hash` without resetting the whole index)
- [x] Fix concise prompt output length: added explicit length targets to all prompts (detailed: 8–15 bullets / 1–2 pages; concise: 5–10 bullets / ~1 page) and added a "don't repeat the same point" rule to combat RAG duplication.
- [ ] Deploy to Railway with persistent disk volume for the vector index
- [x] Fix notes formatting: (a) `export.py` now renders `*italic*` for French terms (previously bare asterisks); (b) sub-bullets (`  - item`) now correctly use `List Bullet 2` style for proper indentation instead of rendering flat; (c) added hard length caps per objective in all prompts.
- [x] Fix stale index bug: `load_index()` now constructs fresh `SimpleDocumentStore`, `SimpleIndexStore`, and `SimpleVectorStore` instances from disk on every call, bypassing LlamaIndex's in-process singleton cache.
