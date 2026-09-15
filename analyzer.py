"""
Request complexity analysis.

Two strategies, so they can be compared rather than assumed:

1. keyword  - free, instant, and wrong often enough to matter
2. llm      - costs a small model call, but reads intent instead of strings

The keyword version returns every signal it found, not just the first match.
Returning on the first hit made "write hello world" score medium because of
"write", and "compare 2 and 3" score high because of "compare".
"""

import re

HIGH_KEYWORDS = {
    "analyze", "analysis", "research", "compare", "methodology", "evaluate",
    "architecture", "strategy", "critique", "prove", "derive", "trade-off",
    "tradeoff", "why does", "explain why", "step by step", "reason about",
}

MEDIUM_KEYWORDS = {
    "write", "create", "code", "develop", "summarize", "explain", "generate",
    "refactor", "debug", "translate", "rewrite", "draft", "implement",
}

# Short factual asks. These override keyword hits, because "compare 2 and 3"
# is not a research task no matter which word it contains.
TRIVIAL_PATTERNS = [
    r"^what is \w+( \w+)?\??$",
    r"^who (is|was) [\w\s]{1,25}\??$",
    r"^when (is|was|did) [\w\s]{1,25}\??$",
    r"^(capital|population) of [\w\s]{1,20}\??$",
    r"^\d+\s*[\+\-\*/]\s*\d+",
    r"^(hi|hello|hey|thanks|thank you)\b",
]

LEVELS = ("low", "medium", "high")


def _trivial(text: str) -> bool:
    return any(re.match(pattern, text.strip()) for pattern in TRIVIAL_PATTERNS)


def analyze_keyword(prompt: str) -> dict:
    """
    Score a request from surface signals.

    Returns the level, a 0-100 score, and every signal found, so the routing
    decision can be explained instead of asserted.
    """
    text = prompt.lower().strip()
    words = len(prompt.split())

    signals: list[str] = []
    score = 0

    if _trivial(text):
        return {
            "complexity": "low",
            "score": 0,
            "signals": ["matched a short factual pattern"],
            "words": words,
            "method": "keyword",
        }

    found_high = sorted(k for k in HIGH_KEYWORDS if k in text)
    found_medium = sorted(k for k in MEDIUM_KEYWORDS if k in text)

    if found_high:
        score += 40
        signals.append(f"reasoning words: {', '.join(found_high[:3])}")

    if found_medium:
        score += 20
        signals.append(f"task words: {', '.join(found_medium[:3])}")

    # Length is a weak signal on its own but a useful tie-breaker.
    if words > 200:
        score += 30
        signals.append(f"long input ({words} words)")
    elif words > 60:
        score += 15
        signals.append(f"medium input ({words} words)")
    elif words < 8:
        score -= 15
        signals.append(f"very short input ({words} words)")

    # Multi-part requests are usually harder than their wording suggests.
    parts = len(re.findall(r"\n\s*\d+[\.\)]|\n\s*[-*]\s", prompt))
    if parts >= 3:
        score += 20
        signals.append(f"{parts} sub-requests")

    if "```" in prompt or re.search(r"\bdef \w+|\bclass \w+|SELECT .+ FROM", prompt):
        score += 15
        signals.append("contains code")

    score = max(0, min(100, score))

    if score >= 55:
        level = "high"
    elif score >= 20:
        level = "medium"
    else:
        level = "low"

    return {
        "complexity": level,
        "score": score,
        "signals": signals or ["no strong signals"],
        "words": words,
        "method": "keyword",
    }


CLASSIFIER_PROMPT = """Classify how much model capability this request needs.

low    - lookup, greeting, arithmetic, one-line answer
medium - writing, coding, summarising, explaining a concept
high   - multi-step reasoning, analysis, comparison with trade-offs,
         long documents, anything where a weak answer would be obvious

Reply with one word only: low, medium, or high.

REQUEST:
{prompt}"""


def analyze_llm(prompt: str, call) -> dict:
    """
    Classify with a small model.

    `call` is a function that takes a prompt string and returns text, so this
    module stays free of provider code and can be tested with a fake.
    """
    reply = call(CLASSIFIER_PROMPT.format(prompt=prompt[:4000])).strip().lower()

    level = next((lvl for lvl in LEVELS if lvl in reply), None)

    if level is None:
        # Fall back rather than guess. A failed classifier should not silently
        # route everything to the cheapest model.
        fallback = analyze_keyword(prompt)
        fallback["signals"].append("llm classifier reply unreadable, fell back")
        return fallback

    return {
        "complexity": level,
        "score": {"low": 10, "medium": 40, "high": 80}[level],
        "signals": [f"classifier said {level}"],
        "words": len(prompt.split()),
        "method": "llm",
    }


def analyze_request(prompt: str, call=None) -> dict:
    """Use the LLM classifier when a caller is supplied, keywords otherwise."""
    if call is not None:
        return analyze_llm(prompt, call)
    return analyze_keyword(prompt)