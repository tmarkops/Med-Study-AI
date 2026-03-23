# med-study-ai

Generates structured study notes from your own course materials, organized by learning objectives.

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

## Project structure

```
app/
  ingest.py       — PDF ingestion and vector index management
  query.py        — Retrieval with metadata filtering
  notes.py        — Note generation (adaptive top_k + Claude API)
  objectives.py   — Parse objectives from .txt / .pdf / .docx
  reset_index.py  — Wipe and rebuild the index
prompts/
  fr_detailed.md, en_detailed.md, …   — Prompt templates per language/style
```

## Usage

```bash
# Ingest a PDF
python app/ingest.py path/to/lecture.pdf --block GI --source-type lecture --language FR

# Generate notes for a single objective
python app/notes.py --objective "3. Describe the pathophysiology of H. pylori" --language FR

# Generate notes from an objectives file
python app/notes.py --objectives-file objectifs.pdf --block GI --language FR --output notes.md
```
