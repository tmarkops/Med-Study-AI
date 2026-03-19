"""Reset the shared vector index. Use this during development to start fresh."""
import shutil
from pathlib import Path

SHARED_INDEX_DIR = Path(__file__).parent / "indexes" / "shared"


def reset():
    if not SHARED_INDEX_DIR.exists():
        print("No index found. Nothing to delete.")
        return

    confirm = input(f"Delete index at '{SHARED_INDEX_DIR}'? [y/N] ")
    if confirm.strip().lower() != "y":
        print("Aborted.")
        return

    shutil.rmtree(SHARED_INDEX_DIR)
    print("Index deleted. You can now re-ingest your files.")


if __name__ == "__main__":
    reset()
