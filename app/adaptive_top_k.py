import re

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

TOP_K_NARROW  = 4
TOP_K_DEFAULT = 10
TOP_K_BROAD   = 16


def adaptive_top_k(objective: str) -> int:
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
    text = re.sub(r"^\s*\d+[\.\)]\s*", "", objective).strip()
    lower = text.lower()
    words = re.split(r"[\s,;:]+", lower)
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
        return TOP_K_BROAD
    if score <= -2:
        return TOP_K_NARROW
    return TOP_K_DEFAULT
