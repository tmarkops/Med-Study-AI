import os
import argparse
from dotenv import load_dotenv
import anthropic

from query import retrieve

load_dotenv()

CLAUDE_MODEL = "claude-opus-4-6"

NOTES_PROMPT = """\
You are a medical school study assistant. Using ONLY the source material provided below, write thorough, well-organized study notes on the following topic:

Topic: {topic}

Source material:
{context}

Instructions:
- Organize the notes with clear headings and bullet points.
- Cover key definitions, mechanisms, clinical features, and anything high-yield for exams.
- Do not add information not present in the source material.
- If the source material is insufficient to cover the topic well, say so explicitly.
- Write in {language}.
"""


def generate_notes(
    topic: str,
    block: str = None,
    source_type: str = None,
    language: str = "EN",
    top_k: int = 10,
) -> str:
    """
    Retrieve relevant chunks and generate study notes on a topic.

    Args:
        topic: The topic to generate notes on (e.g. "H. pylori infection").
        block: Optional block filter to narrow retrieval (e.g. "GI").
        source_type: Optional source type filter (e.g. "textbook").
        language: Language for the output notes ("EN" or "FR").
        top_k: Number of source chunks to retrieve.

    Returns:
        Generated notes as a string.
    """
    print(f"Retrieving source material for: {topic}...")
    results = retrieve(topic, top_k=top_k, block=block, source_type=source_type, language=language)

    if not results:
        return "No relevant source material found. Make sure you have ingested PDFs for this topic."

    context_parts = []
    for i, node in enumerate(results, 1):
        title = node.node.metadata.get("title", "Unknown source")
        text = node.node.text.strip()
        context_parts.append(f"[Source {i} — {title}]\n{text}")

    context = "\n\n---\n\n".join(context_parts)

    prompt = NOTES_PROMPT.format(
        topic=topic,
        context=context,
        language="French" if language == "FR" else "English",
    )

    print("Generating notes...")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate study notes on a topic using ingested PDFs.")
    parser.add_argument("topic", help='Topic to generate notes on (e.g. "H. pylori")')
    parser.add_argument("--block", default=None, help="Medical block to filter sources (e.g. GI)")
    parser.add_argument("--source-type", default=None, help="Source type filter (textbook, lecture, notes)")
    parser.add_argument("--language", default="EN", choices=["EN", "FR"], help="Output language")
    parser.add_argument("--top-k", type=int, default=10, help="Number of source chunks to retrieve")
    args = parser.parse_args()

    notes = generate_notes(
        topic=args.topic,
        block=args.block,
        source_type=args.source_type,
        language=args.language,
        top_k=args.top_k,
    )
    print("\n" + "=" * 60 + "\n")
    print(notes)
