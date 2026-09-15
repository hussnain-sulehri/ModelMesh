"""
ModelMesh request complexity analyzer.

Classifies requests into:
LOW
MEDIUM
HIGH

Hybrid strategy:
1. Fast local heuristic analysis
2. Semantic LLM classification only for uncertain requests

This avoids unnecessary classifier calls while handling
complex prompts that do not contain predefined keywords.
"""

import re


# --------------------------------------------------
# Complexity signals
# --------------------------------------------------

HIGH_KEYWORDS = {
    "deep search",
    "research",
    "investigate",
    "benchmark",
    "evaluate",
    "compare",
    "analyze",
    "analysis",
    "tradeoff",

    "architecture",
    "system design",
    "scalable architecture",
    "technical architecture",
    "distributed system",
    "infrastructure",

    "enterprise",
    "production",
    "migration",
    "strategy",

    "optimization",
    "optimize",
    "high availability",
    "fault tolerance",
    "reliability",

    "orchestration",
    "fallback",
    "cascade",
}


MEDIUM_KEYWORDS = {
    "code",
    "write",
    "create",
    "build",
    "implement",
    "develop",

    "api",
    "database",
    "authentication",
    "jwt",

    "framework",
    "deployment",
    "integration",
    "algorithm",

    "function",
    "script",
    "application",

    "debug",
    "fix",
    "modify",
}


TECHNICAL_KEYWORDS = {
    "python",
    "javascript",
    "java",

    "api",
    "database",
    "sql",

    "docker",
    "kubernetes",
    "cloud",

    "security",
    "authentication",

    "machine learning",
    "deep learning",
    "artificial intelligence",
    "ai",

    "llm",
    "model",
    "router",

    "backend",
    "frontend",

    "distributed",
    "architecture",
    "infrastructure",
    "pipeline",
}


LOW_PATTERNS = (
    r"^what is\b",
    r"^who is\b",
    r"^define\b",
    r"^explain\b",
    r"^what does\b",
)


DESIGN_PATTERNS = (
    r"\bdesign\b",
    r"\barchitect\b",
    r"\bpropose\b",
    r"\bdevise\b",
    r"\bplan\b",
)


CONSTRAINT_WORDS = {
    "must",
    "should",
    "while",
    "however",
    "if",
    "when",
    "without",
    "minimize",
    "maximize",
    "maintain",
    "ensure",
}


# --------------------------------------------------
# Local heuristic analyzer
# --------------------------------------------------

def analyze_rules(prompt: str) -> dict:

    text = prompt.lower().strip()
    words = len(text.split())

    score = 0
    signals = []

    found_high = sorted(
        word for word in HIGH_KEYWORDS
        if word in text
    )

    found_medium = sorted(
        word for word in MEDIUM_KEYWORDS
        if word in text
    )

    found_technical = sorted(
        word for word in TECHNICAL_KEYWORDS
        if word in text
    )

    # --------------------------------------------------
    # High-level reasoning
    # --------------------------------------------------

    if found_high:
        score += 45

        signals.append(
            "high-level reasoning: "
            + ", ".join(found_high[:4])
        )

    # --------------------------------------------------
    # Implementation work
    # --------------------------------------------------

    if found_medium:
        score += 20

        signals.append(
            "implementation task: "
            + ", ".join(found_medium[:4])
        )

    # --------------------------------------------------
    # Technical density
    # --------------------------------------------------

    technical_count = len(found_technical)

    if technical_count:
        score += min(
            30,
            10 + technical_count * 5
        )

        signals.append(
            "technical domain signals: "
            + ", ".join(found_technical[:5])
        )

    # --------------------------------------------------
    # Architectural/design intent
    # --------------------------------------------------

    design_intent = any(
        re.search(pattern, text)
        for pattern in DESIGN_PATTERNS
    )

    if design_intent:

        score += 20

        signals.append(
            "system/design intent detected"
        )

    # --------------------------------------------------
    # Request length
    # --------------------------------------------------

    if words <= 7:

        score -= 10

        signals.append(
            "short request"
        )

    elif words >= 30:

        score += 15

        signals.append(
            "detailed request"
        )

    elif words >= 15:

        score += 5

    # --------------------------------------------------
    # Constraints
    # --------------------------------------------------

    constraint_hits = [
        word for word in CONSTRAINT_WORDS
        if word in text
    ]

    if len(constraint_hits) >= 2:

        score += 10

        signals.append(
            "multiple constraints detected"
        )

    # --------------------------------------------------
    # Multi-part structure
    # --------------------------------------------------

    clauses = len(
        re.findall(
            r"[.;:]|\b(?:and|but|however|while|then)\b",
            text
        )
    )

    if clauses >= 4:

        score += 10

        signals.append(
            "multi-part reasoning"
        )

    # --------------------------------------------------
    # Clear simple question
    # --------------------------------------------------

    simple_pattern = any(
        re.search(pattern, text)
        for pattern in LOW_PATTERNS
    )

    if (
        simple_pattern
        and not found_high
        and technical_count <= 1
        and words < 15
    ):

        score -= 15

        signals.append(
            "simple informational request"
        )

    # --------------------------------------------------
    # Normalize
    # --------------------------------------------------

    score = max(
        0,
        min(score, 100)
    )

    if score >= 70:
        complexity = "high"

    elif score >= 35:
        complexity = "medium"

    else:
        complexity = "low"

    return {
        "complexity": complexity,
        "score": score,
        "signals": signals,
        "method": "heuristic",
        "words": words,
    }


# --------------------------------------------------
# Semantic classifier
# --------------------------------------------------

def classify_with_llm(prompt: str, call):

    classifier_prompt = f"""
You are the complexity classifier for an AI model router.

Classify the USER REQUEST into exactly one category:

LOW
Simple factual questions, definitions, basic explanations,
simple transformations, or tasks requiring little reasoning.

MEDIUM
Normal programming, implementation, summarization,
technical explanation, ordinary analysis, or moderate reasoning.

HIGH
System design, architecture, advanced research,
multi-stage reasoning, optimization, infrastructure design,
distributed systems, reliability engineering, complex tradeoffs,
or requests containing several interacting technical constraints.

Judge semantic difficulty, not specific keywords.

Examples:

Request:
Explain what HTML is
Classification:
LOW

Request:
Write Python code for JWT authentication API
Classification:
MEDIUM

Request:
Design a distributed inference routing mechanism that balances
model locality, latency, cold starts and network traffic
Classification:
HIGH

USER REQUEST:
{prompt}

Return ONLY:
LOW
MEDIUM
or
HIGH
"""

    try:

        response = call(
            classifier_prompt
        )

        value = str(response).strip().lower()

        # tolerate small amounts of model formatting
        match = re.search(
            r"\b(low|medium|high)\b",
            value
        )

        if match:
            return match.group(1)

    except Exception:
        # Classification failure should never break routing
        pass

    return None


# --------------------------------------------------
# Main analyzer
# --------------------------------------------------

def analyze_request(prompt: str, call=None) -> dict:

    result = analyze_rules(prompt)

    score = result["score"]

    # --------------------------------------------------
    # Confidence gates
    # --------------------------------------------------
    #
    # Very obvious LOW or HIGH requests can be handled
    # locally without spending another API request.
    #
    # The semantic classifier is used only in the
    # ambiguous middle region.
    # --------------------------------------------------

    confident_low = score <= 20

    confident_high = score >= 80


    if confident_low or confident_high:

        result["method"] = "heuristic-confident"

        return result


    # --------------------------------------------------
    # Semantic fallback
    # --------------------------------------------------

    if call is not None:

        semantic_complexity = classify_with_llm(
            prompt,
            call
        )


        if semantic_complexity:

            previous = result["complexity"]

            result["complexity"] = (
                semantic_complexity
            )

            result["method"] = (
                "hybrid-semantic"
            )

            result["signals"].append(
                "semantic classifier: "
                f"{previous.upper()} → "
                f"{semantic_complexity.upper()}"
            )


    return result