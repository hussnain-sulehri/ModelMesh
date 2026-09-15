MODELS = {

    "groq-fast": {
        "provider": "groq",
        "model": "allam-2-7b",
        "quality": 5,

        # Provider pricing is currently listed as pending.
        # Used only as a ModelMesh routing estimate.
        "input_cost": 0.04,
        "output_cost": 0.08,
        "pricing_status": "estimate",

        "typical_latency": 0.5,
        "price_source_url":
            "https://console.groq.com/docs/model/allam-2-7b",
        "price_verified_on": "2026-09-15",
    },

    "groq-medium": {
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "quality": 7,

        "input_cost": 0.80,
        "output_cost": 4.00,
        "pricing_status": "published",

        "typical_latency": 1.0,
        "price_source_url":
            "https://console.groq.com/docs/model/qwen/qwen3.8-27b",
        "price_verified_on": "2026-09-15",
    },

    "groq-reasoning": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "quality": 9,

        "input_cost": 0.15,
        "output_cost": 0.60,
        "pricing_status": "published",

        "typical_latency": 1.5,
        "price_source_url":
            "https://console.groq.com/docs/model/openai/gpt-oss-120b",
        "price_verified_on": "2026-09-15",
    },

    "gemini-flash": {
        "provider": "gemini",
        "model": "gemini-3.6-flash",
        "quality": 8,

        "input_cost": 0.75,
        "output_cost": 3.75,
        "pricing_status": "published",

        "typical_latency": 1.5,
        "price_source_url":
            "https://ai.google.dev/gemini-api/docs/pricing",
        "price_verified_on": "2026-09-15",
    },

    "gemini-pro": {
        "provider": "gemini",
        "model": "gemini-3.1-pro-preview",
        "quality": 10,

        "input_cost": 2.00,
        "output_cost": 12.00,
        "pricing_status": "published",

        "typical_latency": 4.0,
        "price_source_url":
            "https://ai.google.dev/gemini-api/docs/pricing",
        "price_verified_on": "2026-09-15",
    },
}


def estimate_tokens(text: str) -> int:
    words = len(text.split())
    return max(1, int(words * 1.3))


def estimate_cost(
    model_key: str,
    input_tokens: int,
    output_tokens: int
) -> float:

    spec = MODELS[model_key]

    return (
        input_tokens / 1_000_000 * spec["input_cost"]
        +
        output_tokens / 1_000_000 * spec["output_cost"]
    )