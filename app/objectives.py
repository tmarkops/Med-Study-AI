"""
Parse a list of learning objectives from a .txt, .pdf, or .docx file.

Uses Claude to intelligently extract only the numbered learning objectives,
merging sub-items (a/b/c) into their parent objective. This handles messy
PDF layouts, section headers, resource lists, and other non-objective content.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def parse_objectives(path: str | Path) -> list[str]:
    """
    Read objectives from a file and return them as a list of strings.

    Supports .txt, .pdf, and .docx files. Uses Claude to extract only the
    actual learning objectives, ignoring headers, resource lists, and other noise.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        raw_text = path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        raw_text = _text_from_pdf(path)
    elif suffix in (".docx", ".doc"):
        raw_text = _text_from_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .txt, .pdf, or .docx.")

    return _extract_with_claude(raw_text)


def _text_from_pdf(path: Path) -> str:
    import pdfplumber
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n".join(pages)


def _text_from_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required to read .docx files. "
            "Install it with: pip install python-docx"
        )
    doc = Document(str(path))
    return "\n".join(para.text for para in doc.paragraphs)


def _extract_with_claude(raw_text: str) -> list[str]:
    """Use Claude to extract learning objectives from raw document text."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are given the raw text of a medical school objectives document.
Extract ONLY the numbered learning objectives. Return them as a JSON array of strings.

Rules:
- Include only actual learning objectives (numbered items students must achieve)
- Skip section headers (e.g. "Principes de nutrition", "Hématologie :")
- Skip resource lists, textbook references, video links, and any preparatory material sections
- If an objective has sub-items (a, b, c...), merge them into the parent objective as a single string
- Preserve the original wording of each objective verbatim
- Do not add numbering — include it only if it was in the original text

Return ONLY a valid JSON array, no explanation. Example:
["Objective one text", "Objective two text with sub-items merged in"]

Document text:
{raw_text}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response = message.content[0].text.strip()
    # Strip markdown code fences if present
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("json"):
            response = response[4:]
        response = response.strip()

    return json.loads(response)
