"""
Provider execution layer for ModelMesh.

Responsibilities:
- call Gemini and Groq models
- measure latency
- track provider token usage
- account for Gemini thinking tokens
- estimate API cost
- detect quota failures
- automatically fall back to another eligible model
"""

import time

from models import MODELS, estimate_cost, estimate_tokens


# --------------------------------------------------
# Exceptions
# --------------------------------------------------

class QuotaError(RuntimeError):
    """Raised when a provider/model quota or rate limit is exhausted."""
    pass


class ProviderError(RuntimeError):
    """Raised for non-quota provider execution failures."""
    pass


# --------------------------------------------------
# Error detection
# --------------------------------------------------

QUOTA_MARKERS = (
    "429",
    "quota",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "too many requests",
)


def _is_quota(error) -> bool:
    text = str(error).lower()

    return any(
        marker in text
        for marker in QUOTA_MARKERS
    )


# --------------------------------------------------
# Cached provider clients
# --------------------------------------------------

_GEMINI_CLIENTS = {}
_GROQ_CLIENTS = {}


def _gemini_client(api_key: str):

    from google import genai

    if api_key not in _GEMINI_CLIENTS:
        _GEMINI_CLIENTS[api_key] = genai.Client(
            api_key=api_key
        )

    return _GEMINI_CLIENTS[api_key]


def _groq_client(api_key: str):

    from groq import Groq

    if api_key not in _GROQ_CLIENTS:
        _GROQ_CLIENTS[api_key] = Groq(
            api_key=api_key
        )

    return _GROQ_CLIENTS[api_key]


# --------------------------------------------------
# Single model execution
# --------------------------------------------------

def call_model(
    model_key: str,
    prompt: str,
    keys: dict,
) -> dict:
    """
    Execute one model request.

    Returns actual provider usage when available.

    For Gemini:
    - output_tokens = visible generated tokens
    - thinking_tokens = hidden reasoning tokens
    - billable_output_tokens = visible + thinking

    Cost calculations use billable_output_tokens.
    """

    if model_key not in MODELS:
        raise ProviderError(
            f"Unknown model key: {model_key}"
        )

    spec = MODELS[model_key]

    provider = spec["provider"]

    api_key = keys.get(provider)

    if not api_key:
        raise ProviderError(
            f"{provider} API key missing"
        )

    start = time.perf_counter()

    usage = None

    input_tokens = None

    visible_output_tokens = None

    thinking_tokens = 0

    text = ""

    try:

        # --------------------------------------------------
        # Google Gemini
        # --------------------------------------------------

        if provider == "gemini":

            response = (
                _gemini_client(api_key)
                .models
                .generate_content(
                    model=spec["model"],
                    contents=prompt,
                )
            )

            text = response.text or ""

            usage = getattr(
                response,
                "usage_metadata",
                None,
            )

            if usage is not None:

                input_tokens = getattr(
                    usage,
                    "prompt_token_count",
                    None,
                )

                visible_output_tokens = getattr(
                    usage,
                    "candidates_token_count",
                    None,
                )

                thinking_tokens = (
                    getattr(
                        usage,
                        "thoughts_token_count",
                        None,
                    )
                    or 0
                )

        # --------------------------------------------------
        # Groq
        # --------------------------------------------------

        elif provider == "groq":

            response = (
                _groq_client(api_key)
                .chat
                .completions
                .create(
                    model=spec["model"],
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )
            )

            text = (
                response
                .choices[0]
                .message
                .content
                or ""
            )

            usage = getattr(
                response,
                "usage",
                None,
            )

            if usage is not None:

                input_tokens = getattr(
                    usage,
                    "prompt_tokens",
                    None,
                )

                visible_output_tokens = getattr(
                    usage,
                    "completion_tokens",
                    None,
                )

        else:

            raise ProviderError(
                f"Unknown provider: {provider}"
            )

    except QuotaError:
        raise

    except ProviderError:
        raise

    except Exception as error:

        if _is_quota(error):

            raise QuotaError(
                f"{model_key}: quota or rate limit reached"
            ) from error

        raise ProviderError(
            f"{model_key}: {error}"
        ) from error


    latency = time.perf_counter() - start


    # --------------------------------------------------
    # Token fallback estimates
    # --------------------------------------------------

    input_was_estimated = (
        input_tokens is None
    )

    output_was_estimated = (
        visible_output_tokens is None
    )

    if input_tokens is None:
        input_tokens = estimate_tokens(prompt)

    if visible_output_tokens is None:
        visible_output_tokens = estimate_tokens(text)


    # Gemini thinking tokens are billable output tokens.
    billable_output_tokens = (
        visible_output_tokens
        + thinking_tokens
    )


    estimated_cost = estimate_cost(
        model_key,
        input_tokens,
        billable_output_tokens,
    )


    return {

        "model_key": model_key,

        "model": spec["model"],

        "provider": provider,

        "answer": text.strip(),

        "latency": round(
            latency,
            2,
        ),

        "input_tokens": input_tokens,

        # Visible response tokens
        "output_tokens": visible_output_tokens,

        # Hidden Gemini reasoning tokens
        "thinking_tokens": thinking_tokens,

        # Used for price calculation
        "billable_output_tokens":
            billable_output_tokens,

        "cost": round(
            estimated_cost,
            6,
        ),

        "tokens_estimated": (
            input_was_estimated
            or output_was_estimated
        ),
    }


# --------------------------------------------------
# Execution with fallback
# --------------------------------------------------

def call_with_fallback(
    model_key: str,
    prompt: str,
    keys: dict,
    unavailable: set,
    order: list,
    simulate_failure_for: str | None = None,
) -> dict:
    """
    Execute the selected model.

    If it fails, try the remaining eligible models in
    the fallback order supplied by app.py.

    Quota failures are remembered for the current session.

    simulate_failure_for is used only for demonstrating
    real fallback behavior in the Streamlit demo.
    """

    tried = []

    # Avoid duplicate candidates.
    candidates = []

    for candidate in [model_key] + list(order):

        if candidate not in candidates:
            candidates.append(candidate)


    for candidate in candidates:

        # Skip models already known to be unavailable.
        if candidate in unavailable:
            continue


        # --------------------------------------------------
        # Demo-only simulated failure
        # --------------------------------------------------

        if (
            simulate_failure_for
            and candidate == simulate_failure_for
        ):

            tried.append(
                f"{candidate}: simulated provider failure"
            )

            continue


        try:

            result = call_model(
                candidate,
                prompt,
                keys,
            )

            result["tried"] = tried

            result["fell_back"] = (
                candidate != model_key
            )

            result["original_model_key"] = (
                model_key
            )

            return result


        except QuotaError as error:

            # Quota failures are sticky for this
            # Streamlit session.
            unavailable.add(candidate)

            tried.append(
                str(error)
            )


        except ProviderError as error:

            # Normal provider failures are not made
            # permanently unavailable because they may
            # be transient.
            tried.append(
                str(error)
            )


    details = (
        "\n".join(tried)
        if tried
        else "No eligible model could be executed."
    )

    raise ProviderError(
        "Every eligible model failed:\n"
        + details
    )