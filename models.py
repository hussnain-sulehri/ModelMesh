"""
Model catalogue.

Provider-neutral model definitions.
The router uses quality, cost and latency values to select
the best model for each request.
"""


MODELS = {

    # -------------------------
    # Groq Fast Model
    # -------------------------

    "groq-fast": {
        "provider": "groq",
        "model": "allam-2-7b",
        "quality": 5,
        "output_cost": 0.08,
        "typical_latency": 0.5,
    },


    # -------------------------
    # Groq Medium Model
    # -------------------------

    "groq-medium": {
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "quality": 7,
        "output_cost": 0.40,
        "typical_latency": 1.0,
    },


    # -------------------------
    # Groq Reasoning Model
    # -------------------------

    "groq-reasoning": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "quality": 9,
        "output_cost": 0.80,
        "typical_latency": 1.5,
    },


    # -------------------------
    # Gemini Fast
    # -------------------------

    "gemini-flash": {
        "provider": "gemini",
        "model": "gemini-3.6-flash",
        "quality": 8,
        "output_cost": 2.50,
        "typical_latency": 1.5,
    },


    # -------------------------
    # Gemini Pro
    # -------------------------

    "gemini-pro": {
        "provider": "gemini",
        "model": "gemini-3.1-pro-preview",
        "quality": 10,
        "output_cost": 5.00,
        "typical_latency": 4.0,
    },

}



def estimate_tokens(text: str) -> int:
    """
    Rough token estimation.
    Used when providers do not return usage metadata.
    """

    words = len(text.split())

    return max(1, int(words * 1.3))



def estimate_cost(
    model_key: str,
    input_tokens: int,
    output_tokens: int
) -> float:

    spec = MODELS[model_key]

    input_cost = spec.get(
        "input_cost",
        spec["output_cost"] / 2
    )


    return (
        input_tokens / 1_000_000 * input_cost
        +
        output_tokens / 1_000_000 * spec["output_cost"]
    )