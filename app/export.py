import re
from pathlib import Path
from docx import Document


def save_as_docx(markdown_text: str, output_path: Path):
    """Convert markdown notes to a formatted .docx file."""
    doc = Document()

    for line in markdown_text.splitlines():
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("- ") or line.startswith("* "):
            p = doc.add_paragraph(style="List Bullet")
            _add_inline_formatting(p, line[2:].strip())
        elif line.startswith("> "):
            p = doc.add_paragraph(style="Quote")
            _add_inline_formatting(p, line[2:].strip())
        elif line.strip() == "" or line.strip() == "---":
            doc.add_paragraph()
        else:
            p = doc.add_paragraph()
            _add_inline_formatting(p, line.strip())

    doc.save(str(output_path))


def _add_inline_formatting(paragraph, text: str):
    """Parse **bold** and render it in a paragraph run."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)
