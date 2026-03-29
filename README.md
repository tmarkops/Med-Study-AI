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

## TODO

- [ ] Add per-file delete to `ingest.py` (remove chunks by `file_hash` without resetting the whole index)
- [ ] Fix retrieval noise and coverage: tested on objective *"Schématiser l'absorption de la vitamine B12 et de l'acide folique"* (top_k=10) — 4/10 retrieved chunks were irrelevant (fasting metabolism, obesity, realimentation, scored ~0.39–0.40) while relevant pages on pancreatic insufficiency → ↓ trypsin → B12 malabsorption, PPIs → ↓ HCl → ↓ B12 release, and intracellular folate → THF conversion were never retrieved. Root cause: embedding space doesn't cleanly separate "vitamin absorption" from "general nutrition." Increasing top_k papers over the problem but worsens noise. Long-term fix is likely a **reranker** (second-pass relevance scoring after retrieval) rather than a higher k.
- [ ] Fix concise prompt output length: `--style concise` currently produces notes roughly the same length as `--style detailed`. The prompt says "be concise" but gives no hard constraint, so the model treats it as a style preference rather than a length target. Fix: add an explicit length heuristic (e.g. ~half the length of detailed, max 2 clinical pearls, no redundant summary sections after a pathway is already listed step-by-step).

## Usage

```bash
# Ingest a PDF
python app/ingest.py path/to/lecture.pdf --block GI --source-type lecture --language FR

# Generate notes for a single objective
python app/notes.py --objective "3. Describe the pathophysiology of H. pylori" --language FR

# Generate notes from an objectives file
python app/notes.py --objectives-file objectifs.pdf --block GI --language FR --output notes.md
```
