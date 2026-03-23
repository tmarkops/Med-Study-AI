"""
Parse a list of learning objectives from a .txt, .pdf, or .docx file.

Each non-empty line (after stripping) is treated as one objective.
Lines that are clearly just whitespace or page artifacts (single characters,
pure numbers) are skipped.
"""

import re
from pathlib import Path


def parse_objectives(path: str | Path) -> list[str]:
    """
    Read objectives from a file and return them as a list of strings.

    Supports .txt, .pdf, and .docx files.
    Each non-trivial line is one objective; preserves original text verbatim.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    elif suffix == ".pdf":
        raw_lines = _lines_from_pdf(path)
    elif suffix in (".docx", ".doc"):
        raw_lines = _lines_from_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .txt, .pdf, or .docx.")

    return _clean(raw_lines)


def _lines_from_pdf(path: Path) -> list[str]:
    import pdfplumber
    lines = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
    return lines


def _lines_from_docx(path: Path) -> list[str]:
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required to read .docx files. "
            "Install it with: pip install python-docx"
        )
    doc = Document(str(path))
    return [para.text for para in doc.paragraphs]


def _clean(lines: list[str]) -> list[str]:
    """Strip whitespace, drop blank lines and single-character/number-only artifacts."""
    objectives = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines that are just a number or a single character (page numbers, etc.)
        if re.fullmatch(r"[\d\W]", line):
            continue
        objectives.append(line)
    return objectives
