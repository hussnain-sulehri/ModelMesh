"""
Model catalogue for the router.

Costs are US dollars per one million tokens, taken from each provider's
public pricing page. VERIFY THESE BEFORE SUBMITTING. Provider pricing moves,
and a router that optimises cost with stale numbers optimises nothing.

quality is a 1-10 judgement, not a benchmark score. It is the number the
router trades against cost, so it should be replaced with measured scores
from the benchmark once that has been run.
"""

MODELS: dict[str, dict] = {
    "llama-8b": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "input_cost": 0.05,
        "output_cost": 0.08,
        "typical_latency": 0.4,
        "quality": 5,
        "tier": "small",
        "notes": "Cheapest and fastest. Fine for lookups and short rewrites.",
    },
    "llama-70b": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "input_cost": 0.59,
        "output_cost": 0.79,
        "typical_latency": 1.2,
        "quality": 7,
        "tier": "medium",
        "notes": "Good general model, still fast on Groq hardware.",
    },
    "gemini-flash": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "input_cost": 0.30,
        "output_cost": 2.50,
        "typical_latency": 1.5,
        "quality": 8,
        "tier": "medium",
        "notes": "Long context, reliable structured output.",
    },
    "gemini-pro": {
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "input_cost": 1.25,
        "output_cost": 10.00,
        "typical_latency": 4.0,
        "quality": 10,
        "tier": "large",
        "notes": "Reasoning and long analysis. 25x the output cost of 8B.",
    },
}


def estimate_tokens(text: str) -> int:
    """Rough token count. Good enough for cost comparison, not for billing."""
    return max(1, int(len(text.split()) * 1.3))


def estimate_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """Dollar cost of one call, given token counts."""
    spec = MODELS[model_key]
    return (
        input_tokens / 1_000_000 * spec["input_cost"]
        + output_tokens / 1_000_000 * spec["output_cost"]
    )