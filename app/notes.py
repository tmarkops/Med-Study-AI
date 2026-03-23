import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
import anthropic

from query import retrieve
from objectives import parse_objectives

load_dotenv()

CLAUDE_MODEL = "claude-opus-4-6"

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

PROMPT_FILES = {
    ("EN", "detailed"): "en_detailed.md",
    ("EN", "concise"):  "en_concise.md",
    ("FR", "detailed"): "fr_detailed.md",
    ("FR", "concise"):  "fr_concise.md",
    ("MIXED", "detailed"): "mixed_detailed.md",
    ("MIXED", "concise"):  "mixed_concise.md",
}


def _retrieval_query(objective: str) -> str:
    """Strip leading numbering (e.g. '3.', '1)') from an objective before using it as a retrieval query."""
    return _re.sub(r"^\s*\d+[\.\)]\s*", "", objective).strip()


import re as _re

# Verbs that push score toward narrow
_NARROW_VERBS = {
    "define", "définir", "list", "lister", "énumérer", "enumerate",
    "name", "nommer", "identify", "identifier", "state", "énoncer",
}

# Verbs that push score toward broad
_BROAD_VERBS = {
    "explain", "expliquer", "describe", "décrire", "discuss", "discuter",
    "compare", "comparer", "contrast", "distinguish", "distinguer",
    "analyze", "analyser", "outline", "présenter", "summarize", "résumer",
    "evaluate", "évaluer", "elaborate", "développer",
}

# Words that signal multiple sub-topics within one objective
_BREADTH_KEYWORDS = {
    "mechanisms", "mécanismes", "types", "stages", "stades", "steps", "étapes",
    "complications", "causes", "factors", "facteurs", "features", "manifestations",
    "classification", "classes", "categories", "catégories", "roles", "rôles",
    "indications", "contraindications", "contre-indications", "effects", "effets",
    "management", "prise en charge", "treatment", "traitement", "diagnosis", "diagnostic",
}

_TOP_K_NARROW  = 4
_TOP_K_DEFAULT = 10
_TOP_K_BROAD   = 16


def _adaptive_top_k(objective: str) -> int:
    """
    Score the objective's breadth using four signals and map to top_k:
      - Leading verb (narrow / broad)
      - Presence of breadth keywords (mechanisms, types, complications, …)
      - Conjunctions implying multiple sub-topics (and/et/or/ou)
      - Objective length (word count)

    Score >= 2  → broad  (top_k=16)
    Score <= -2 → narrow (top_k=4)
    Otherwise   → default (top_k=10)
    """
    text = _re.sub(r"^\s*\d+[\.\)]\s*", "", objective).strip()
    lower = text.lower()
    words = _re.split(r"[\s,;:]+", lower)
    score = 0

    # Signal 1: leading verb
    first_word = words[0] if words else ""
    if first_word in _NARROW_VERBS:
        score -= 2
    elif first_word in _BROAD_VERBS:
        score += 1

    # Signal 2: breadth keywords anywhere in the objective
    keyword_hits = sum(1 for kw in _BREADTH_KEYWORDS if kw in lower)
    score += min(keyword_hits, 2)  # cap at +2 to avoid runaway scores

    # Signal 3: conjunctions suggesting multiple sub-topics
    conjunctions = {"and", "et", "or", "ou"}
    if any(w in conjunctions for w in words):
        score += 1

    # Signal 4: word count (short = specific, long = multi-part)
    word_count = len(words)
    if word_count <= 6:
        score -= 1
    elif word_count >= 12:
        score += 1

    if score >= 2:
        return _TOP_K_BROAD
    if score <= -2:
        return _TOP_K_NARROW
    return _TOP_K_DEFAULT


def _load_prompt(language: str, style: str) -> str:
    key = (language.upper(), style.lower())
    filename = PROMPT_FILES.get(key)
    if not filename:
        raise ValueError(f"No prompt found for language={language}, style={style}. "
                         f"Valid combinations: {list(PROMPT_FILES.keys())}")
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def generate_notes(
    objective: str,
    block: str = None,
    source_type: str = None,
    language: str = "EN",
    style: str = "detailed",
    top_k: int = 0,
) -> str:
    """
    Retrieve relevant chunks and generate study notes for a single learning objective.

    Args:
        objective: The learning objective verbatim.
        block: Optional block filter to narrow retrieval (e.g. "GI").
        source_type: Optional source type filter (e.g. "textbook").
        language: Output language — "EN", "FR", or "MIXED".
        style: Prompt style — "detailed" or "concise".
        top_k: Number of source chunks to retrieve. Pass 0 (default) to infer
               automatically from the objective's complexity.

    Returns:
        Generated notes as a string.
    """
    resolved_top_k = top_k if top_k > 0 else _adaptive_top_k(objective)
    print(f"  Retrieving source material (top_k={resolved_top_k})...")
    lang_filter = language if language in ("EN", "FR") else None
    results = retrieve(_retrieval_query(objective), top_k=resolved_top_k, block=block, source_type=source_type, language=lang_filter)

    if not results:
        return f"## {objective}\n\n> No relevant source material found for this objective.\n"

    context_parts = []
    for i, node in enumerate(results, 1):
        title = node.node.metadata.get("title", "Unknown source")
        text = node.node.text.strip()
        context_parts.append(f"[Source {i} — {title}]\n{text}")

    context = "\n\n---\n\n".join(context_parts)

    prompt_template = _load_prompt(language, style)
    prompt = prompt_template.format(objective=objective, context=context)

    print(f"  Generating notes...")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def generate_notes_from_objectives(
    objectives: list[str],
    block: str = None,
    source_type: str = None,
    language: str = "EN",
    style: str = "detailed",
    top_k: int = 0,
) -> str:
    """
    Generate notes for a list of objectives and return them as a single combined string.
    """
    sections = []
    total = len(objectives)
    for i, objective in enumerate(objectives, 1):
        print(f"\n[{i}/{total}] {objective}")
        notes = generate_notes(
            objective=objective,
            block=block,
            source_type=source_type,
            language=language,
            style=style,
            top_k=top_k,
        )
        sections.append(notes)

    return "\n\n---\n\n".join(sections)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate study notes from learning objectives using ingested PDFs."
    )

    # Objective input — mutually exclusive: single string or file
    obj_group = parser.add_mutually_exclusive_group(required=True)
    obj_group.add_argument(
        "--objective", "-o",
        help='Single learning objective (e.g. "3. Describe the pathophysiology of H. pylori")',
    )
    obj_group.add_argument(
        "--objectives-file", "-f",
        help="Path to a .txt, .pdf, or .docx file containing one objective per line",
    )

    parser.add_argument("--block", default=None, help="Medical block to filter sources (e.g. GI)")
    parser.add_argument("--source-type", default=None, help="Source type filter (textbook, lecture, notes)")
    parser.add_argument("--language", default="EN", choices=["EN", "FR", "MIXED"], help="Output language")
    parser.add_argument("--style", default="detailed", choices=["detailed", "concise"], help="Prompt style")
    parser.add_argument("--top-k", type=int, default=0,
                        help="Number of source chunks to retrieve (0 = infer from objective complexity)")
    parser.add_argument("--output", default=None, help="Optional path to save the notes (e.g. notes.md)")
    args = parser.parse_args()

    # Resolve objectives list
    if args.objectives_file:
        objectives = parse_objectives(args.objectives_file)
        print(f"Loaded {len(objectives)} objectives from {args.objectives_file}")
    else:
        objectives = [args.objective]

    notes = generate_notes_from_objectives(
        objectives=objectives,
        block=args.block,
        source_type=args.source_type,
        language=args.language,
        style=args.style,
        top_k=args.top_k,
    )

    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")
        print(f"\nNotes saved to {args.output}")
    else:
        print("\n" + "=" * 60 + "\n")
        print(notes)
