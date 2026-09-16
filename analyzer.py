"""
ModelMesh request complexity analyzer.

Classifies requests into LOW, MEDIUM, HIGH using:
- keyword signals
- technical domain detection
- request structure
- semantic fallback for uncertain cases

The goal is to avoid unnecessary classifier calls while still
handling complex requests written in different ways.
"""

import re
from functools import lru_cache


HIGH_KEYWORDS = {
    "deep search", "research", "investigate", "benchmark",
    "evaluate", "compare", "analyze", "analysis", "tradeoff",

    "architecture", "system design", "scalable architecture",
    "technical architecture", "distributed system",
    "infrastructure", "enterprise architecture",

    "strategy", "optimization", "optimize",
    "production grade", "large scale", "millions of users",

    "multi model", "multi-model", "model router",
    "dynamic routing", "fallback", "cascade",
    "fault tolerant", "fault tolerance",
    "high availability", "reliability",
    "orchestration", "pipeline"
}


MEDIUM_KEYWORDS = {
    "code", "write", "create", "build",
    "implement", "develop",

    "api", "rest api", "database",
    "authentication", "jwt",

    "docker", "container", "flask",
    "django", "deployment",
    "cloud deployment",

    "framework", "integration",
    "algorithm", "function",
    "script", "application",

    "debug", "fix", "modify",
    "schema", "backend",
    "frontend", "crud",
    "endpoint", "microservice"
}


TECHNICAL_KEYWORDS = {
    "python", "javascript", "java",

    "api", "database", "sql",
    "docker", "kubernetes",
    "cloud",

    "security", "authentication",

    "machine learning",
    "deep learning",
    "artificial intelligence",
    "ai",

    "llm", "model", "router",
    "multimodal", "ocr",

    "backend", "frontend",
    "distributed",
    "architecture",
    "infrastructure",
    "pipeline"
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
    r"\bplan\b",
)


CONSTRAINT_WORDS = {
    "must", "should", "while",
    "however", "if", "when",
    "without", "minimize",
    "maximize", "maintain",
    "ensure"
}


BANDS = ("low", "medium", "high")


def _norm(text: str) -> str:
    # "fine-tuning" == "fine tuning", "multi-model" == "multi model"
    text = re.sub(r"[-_/]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=None)
def _term_re(term: str):
    # whole words only, tolerate simple plurals: "container" matches "containers"
    # but "ai" no longer matches "explain" and "rag" no longer matches "storage"
    return re.compile(rf"\b{re.escape(_norm(term))}(?:s|es)?\b")


def _hits(terms, text: str) -> list:
    return sorted({t for t in terms if _term_re(t).search(text)})


# Intent: what kind of answer is being asked for, independent of topic words.
DEFINITIONAL_PATTERNS = (
    r"\bwhat(?: is|'s| are)\b", r"\bdefine\b", r"\bexplain\b", r"\bdescribe\b",
    r"\bdifference between\b", r"\bdifferent from\b", r"\btell me (?:what|about)\b",
    r"\bmeaning of\b", r"\bin (?:simple|plain)\b", r"\bexplained\b",
)
MECHANISM_PATTERNS = (
    r"\bhow (?:does|do|is|are)\b.*\bwork", r"\b(?:with|give|some) (?:\w+ )?examples?\b",
    r"\bwalk me through\b",
)
PROCEDURAL_PATTERNS = (
    r"\bhow (?:to|do i|can i|should i)\b", r"\bsteps (?:to|for)\b",
)
BUILD_VERBS = {
    "write", "create", "build", "implement", "develop", "code",
    "debug", "fix", "refactor", "design", "architect", "sketch",
}
ARTIFACT_NOUNS = {
    "app", "application", "system", "service", "engine", "endpoint",
    "script", "api", "schema", "function", "tool", "bot",
}
SMALL_SCOPE = {
    "small", "simple", "basic", "beginner", "toy", "side project",
    "prototype", "simple terms", "plain english", "briefly",
}
LARGE_SCOPE = {
    "enterprise", "millions of users", "large scale", "production",
    "production grade", "at scale", "global",
}
OBJECTIVE_GROUPS = (
    {"cost", "spend", "price", "cheap", "cheapest", "budget"},
    {"latency", "speed", "fast", "throughput"},
    {"quality", "accuracy", "reliability", "reliable"},
)


def analyze_rules(prompt: str) -> dict:

    text = _norm(prompt)
    words = len(text.split())

    score = 0
    signals = []

    found_high = _hits(HIGH_KEYWORDS, text)

    found_medium = _hits(MEDIUM_KEYWORDS, text)

    found_technical = [
        x for x in _hits(TECHNICAL_KEYWORDS, text)
        if x not in found_high and x not in found_medium
    ]


    if found_high:
        score += 45
        signals.append(
            "high-level reasoning: " +
            ", ".join(found_high[:4])
        )


    if found_medium:
        score += 20
        signals.append(
            "implementation task: " +
            ", ".join(found_medium[:4])
        )


    if found_technical:
        score += min(30, 10 + len(found_technical) * 5)
        signals.append(
            "technical domain: " +
            ", ".join(found_technical[:5])
        )


    # Technical coding tasks should not be classified as simple
    coding_terms = {
        "code", "write", "create",
        "build", "implement"
    }

    security_terms = {
        "api", "jwt", "authentication",
        "database", "backend",
        "security"
    }

    coding_hits = len(_hits(coding_terms, text))

    technical_coding_hits = len(_hits(security_terms, text))

    if coding_hits and technical_coding_hits >= 2:
        score += 25
        signals.append(
            "technical implementation task"
        )


    # Advanced comparison/reasoning
    comparison = bool(_hits(
        ["compare", "comparison", "versus", "vs", "tradeoff", "trade off"], text
    ))

    advanced_topics = len(_hits(
        [
            "rag",
            "fine tuning",
            "fine-tuning",
            "agent",
            "architecture",
            "enterprise"
        ],
        text,
    ))

    if comparison and advanced_topics >= 2:
        score += 25
        signals.append(
            "advanced comparison reasoning"
        )


    if any(
        re.search(pattern, text)
        for pattern in DESIGN_PATTERNS
    ):
        score += 15
        signals.append(
            "system design intent"
        )


    if words <= 7:
        score -= 10
        signals.append("short request")

    elif words >= 30:
        score += 15
        signals.append("detailed request")


    constraint_hits = len(_hits(CONSTRAINT_WORDS, text))

    if constraint_hits >= 2:
        score += 10
        signals.append(
            "multiple constraints detected"
        )


    clauses = len(
        re.findall(
            r"[.;:]|\b(and|but|however|while|then)\b",
            text
        )
    )

    if clauses >= 4:
        score += 10
        signals.append(
            "multi-part reasoning"
        )


    simple = any(
        re.search(pattern, text)
        for pattern in LOW_PATTERNS + DEFINITIONAL_PATTERNS
    )

    if simple and not found_high and len(found_technical) <= 1 and words < 15:
        score -= 15
        signals.append(
            "simple informational request"
        )


    # ---- scope and competing objectives ----------------------------------
    small = _hits(SMALL_SCOPE, text)
    large = _hits(LARGE_SCOPE, text)
    objectives = sum(bool(_hits(g, text)) for g in OBJECTIVE_GROUPS)

    if large:
        score += 15
        signals.append("large scope: " + ", ".join(large[:3]))

    if objectives >= 2:
        score += 20
        signals.append("competing objectives")

    # ---- intent: cap or floor the score by the kind of answer wanted -----
    # Topic words say what a prompt is about; intent says how much work the
    # answer takes. Rewording mostly changes topic words, rarely intent.
    definitional = any(re.search(p, text) for p in DEFINITIONAL_PATTERNS)
    mechanism = any(re.search(p, text) for p in MECHANISM_PATTERNS)
    procedural = any(re.search(p, text) for p in PROCEDURAL_PATTERNS)
    builds = bool(_hits(BUILD_VERBS, text))
    artifact = bool(_hits(ARTIFACT_NOUNS, text) or found_technical
                    or set(found_medium) - BUILD_VERBS - {"script"})
    heavy = len(found_high) >= 2 or bool(large) or objectives >= 2

    score = max(0, min(score, 100))
    adjusted = False

    # Bands the intent evidence allows. The semantic classifier may move the
    # result within these, never outside: "explain how Docker works with
    # examples" can be MEDIUM or HIGH, but not LOW.
    min_band, max_band = "low", "high"

    impl_intent = builds and artifact
    dense_intent = len(found_medium) >= 3 and not definitional
    howto_intent = (mechanism or procedural) and artifact and not builds

    if impl_intent or dense_intent or howto_intent:
        min_band = "medium"

    if impl_intent and score < 40:
        score, adjusted = 40, True
        signals.append("intent: build/fix a technical artifact (floor MEDIUM)")

    if dense_intent and score < 40:
        score, adjusted = 40, True
        signals.append("intent: dense implementation vocabulary (floor MEDIUM)")

    if howto_intent and score < 40:
        score, adjusted = 40, True
        signals.append("intent: how-it-works / how-to (floor MEDIUM)")

    design_intent = any(re.search(p, text) for p in DESIGN_PATTERNS)
    if design_intent and found_high and not (small or procedural or definitional):
        min_band = "high"
        if score < 85:
            # topic and intent agree here, so this is a confident HIGH, not a conflict
            score = 85
            signals.append("intent: design at system level (floor HIGH)")

    if (procedural or definitional or small) and not heavy:
        max_band = "medium"
        if score >= 70:
            score, adjusted = 60, True
            signals.append("intent: bounded scope (cap MEDIUM)")

    if definitional and not (mechanism or procedural or builds or heavy):
        max_band = "low"
        if score >= 35:
            score, adjusted = 30, True
            signals.append("intent: definition / conceptual question (cap LOW)")

    if BANDS.index(min_band) > BANDS.index(max_band):
        min_band, max_band = "low", "high"


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
        "min_band": min_band,
        "max_band": max_band,
        # conflicting cues: topic words pulled one way, intent/scope another
        "conflict": (
            (adjusted and (bool(found_high) or bool(small)))
            or (heavy and complexity != "high")
            or (builds and words <= 4)  # "Design Uber": too terse to score
        ),
    }


def classify_with_llm(prompt: str, call):

    classifier_prompt = f"""
Classify this request as only LOW, MEDIUM, or HIGH.

LOW:
Simple explanations and factual questions.

MEDIUM:
Coding, implementation, normal technical tasks.

HIGH:
Architecture, research, distributed systems,
optimization, advanced reasoning, complex tradeoffs.

Request:
{prompt}

Return only LOW, MEDIUM, or HIGH.
"""

    try:
        response = call(classifier_prompt)

        reply = re.sub(
            r"<think>.*?</think>", "", str(response), flags=re.S
        ).lower()

        # the verdict is at the end; earlier mentions are often reasoning
        matches = re.findall(r"\b(low|medium|high)\b", reply)

        if matches:
            return matches[-1]

    except Exception:
        pass

    return None


CONFIDENT_MARGIN = 15


def analyze_request(prompt: str, call=None) -> dict:

    result = analyze_rules(prompt)

    # Confidence = distance to the nearest band boundary (35 / 70), not
    # distance from 0 or 100. The old gate called 80 "confident" even though
    # it sits 10 points from MEDIUM, and one reworded keyword moves 15-45.
    margin = min(abs(result["score"] - 35), abs(result["score"] - 70))

    if margin >= CONFIDENT_MARGIN and not result.get("conflict"):
        result["method"] = "heuristic-confident"
        return result


    if call:

        semantic = classify_with_llm(
            prompt,
            call
        )

        if semantic:
            previous = result["complexity"]

            lo = BANDS.index(result.get("min_band", "low"))
            hi = BANDS.index(result.get("max_band", "high"))
            clamped = BANDS[min(max(BANDS.index(semantic), lo), hi)]

            if clamped != semantic:
                result["signals"].append(
                    f"semantic said {semantic.upper()}, outside intent range "
                    f"{BANDS[lo].upper()}-{BANDS[hi].upper()}; kept {clamped.upper()}"
                )
                semantic = clamped

            result["complexity"] = semantic
            result["method"] = "hybrid-semantic"

            result["signals"].append(
                f"semantic classifier: {previous.upper()} → {semantic.upper()}"
            )

    return result