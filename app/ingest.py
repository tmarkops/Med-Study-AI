import sys
import hashlib
import argparse
from pathlib import Path
from dotenv import load_dotenv
import pdfplumber

from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.schema import Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings

load_dotenv()

EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
SHARED_INDEX_DIR = Path(__file__).parent / "indexes" / "shared"

BLOCKS = ["GI", "cardio", "respiratory", "neuro", "renal", "hematology", "pharmacology", "anatomy", "general"]
SOURCE_TYPES = ["textbook", "lecture", "notes", "objectives"]
LANGUAGES = ["FR", "EN"]


def _load_embed_model():
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
    Settings.llm = None


def load_index() -> VectorStoreIndex:
    """Load the shared index from disk."""
    _load_embed_model()
    if not SHARED_INDEX_DIR.exists():
        raise FileNotFoundError("No shared index found. Run ingest.py on at least one PDF first.")
    storage_context = StorageContext.from_defaults(persist_dir=str(SHARED_INDEX_DIR))
    return load_index_from_storage(storage_context)


def ingest(pdf_path: str, metadata: dict = {}) -> VectorStoreIndex:
    """Ingest a PDF into the shared vector index."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    _load_embed_model()

    file_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()

    doc_metadata = {
        "source_type": metadata.get("source_type", "unknown"),
        "block": metadata.get("block", "general"),
        "topic": metadata.get("topic", "general"),
        "language": metadata.get("language", "EN"),
        "title": metadata.get("title", pdf_path.stem),
        "filename": pdf_path.name,
        "file_hash": file_hash,
    }

    print(f"Ingesting '{pdf_path.name}'...")
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]

    documents = [
        Document(text=text, metadata={**doc_metadata, "page": i + 1})
        for i, text in enumerate(pages_text)
        if text.strip()
    ]

    SHARED_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if SHARED_INDEX_DIR.exists() and any(SHARED_INDEX_DIR.iterdir()):
        # Index exists — load it and insert new documents
        storage_context = StorageContext.from_defaults(persist_dir=str(SHARED_INDEX_DIR))
        index = load_index_from_storage(storage_context)

        # Deduplication: check if this file's content hash is already in the index
        existing_hashes = {
            node.metadata.get("file_hash")
            for node in index.docstore.docs.values()
        }
        if file_hash in existing_hashes:
            print(f"'{pdf_path.name}' is already in the index (duplicate content). Skipping.")
            return index

        for doc in documents:
            index.insert(doc)
        print(f"Inserted {len(documents)} chunks from '{pdf_path.name}' into shared index.")
    else:
        # First ingest — create the index
        index = VectorStoreIndex.from_documents(documents, show_progress=True)
        print(f"Created shared index with '{pdf_path.name}'.")

    index.storage_context.persist(persist_dir=str(SHARED_INDEX_DIR))
    print(f"Shared index saved to {SHARED_INDEX_DIR}")

    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF into the shared vector index.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--block", default="general", choices=BLOCKS, help="Medical block (default: general)")
    parser.add_argument("--source-type", default="unknown", choices=SOURCE_TYPES, help="Source type")
    parser.add_argument("--language", default="EN", choices=LANGUAGES, help="Language (default: EN)")
    parser.add_argument("--topic", default="general", help="Specific topic (e.g. colon_cancer)")
    parser.add_argument("--title", default=None, help="Human-readable title (defaults to filename)")
    args = parser.parse_args()

    metadata = {
        "block": args.block,
        "source_type": args.source_type,
        "language": args.language,
        "topic": args.topic,
        "title": args.title or Path(args.pdf_path).stem,
    }
    ingest(args.pdf_path, metadata=metadata)
