"""
Execution layer.

The old version decided which model should answer and then stopped, so no
request ever reached a model. This sends it, times it, and reports what the
call actually cost.

Quota errors are raised as a distinct type so the router can mark a model
unavailable and move on instead of retrying something that cannot succeed.
"""

import time

from models import MODELS, estimate_cost, estimate_tokens


class QuotaError(RuntimeError):
    """The model is rate limited or out of quota. Try a different one."""


class ProviderError(RuntimeError):
    """The call failed for a reason retrying will not fix."""


QUOTA_MARKERS = ("RESOURCE_EXHAUSTED", "429", "rate limit", "quota")

_GEMINI_CLIENTS: dict[str, object] = {}
_GROQ_CLIENTS: dict[str, object] = {}


def _is_quota(error: Exception) -> bool:
    text = str(error).lower()
    return any(marker.lower() in text for marker in QUOTA_MARKERS)


def _gemini_client(api_key: str):
    # Imported lazily so the app still runs when only one provider is set up.
    from google import genai

    if api_key not in _GEMINI_CLIENTS:
        _GEMINI_CLIENTS[api_key] = genai.Client(api_key=api_key)
    return _GEMINI_CLIENTS[api_key]


def _groq_client(api_key: str):
    from groq import Groq

    if api_key not in _GROQ_CLIENTS:
        _GROQ_CLIENTS[api_key] = Groq(api_key=api_key)
    return _GROQ_CLIENTS[api_key]


def call_model(model_key: str, prompt: str, keys: dict) -> dict:
    """
    Send a prompt to one model.

    Returns the answer, measured latency, token counts and real cost.
    Raises QuotaError when the model is out, so the caller can fall back.
    """
    spec = MODELS[model_key]
    provider = spec["provider"]

    api_key = keys.get(provider)
    if not api_key:
        raise ProviderError(f"No API key set for {provider}")

    started = time.perf_counter()

    try:
        if provider == "gemini":
            response = _gemini_client(api_key).models.generate_content(
                model=spec["model"], contents=prompt
            )
            text = (response.text or "").strip()
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", None)
            output_tokens = getattr(usage, "candidates_token_count", None)

        elif provider == "groq":
            response = _groq_client(api_key).chat.completions.create(
                model=spec["model"],
                messages=[{"role": "user", "content": prompt}],
            )
            text = (response.choices[0].message.content or "").strip()
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)

        else:
            raise ProviderError(f"Unknown provider: {provider}")

    except Exception as error:
        if _is_quota(error):
            raise QuotaError(f"{model_key} is out of quota") from error
        raise ProviderError(f"{model_key} failed") from error

    latency = time.perf_counter() - started

    # Providers do not always return usage. Estimate rather than report zero.
    input_tokens = input_tokens or estimate_tokens(prompt)
    output_tokens = output_tokens or estimate_tokens(text)

    return {
        "model_key": model_key,
        "model": spec["model"],
        "provider": provider,
        "answer": text,
        "latency": round(latency, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": round(estimate_cost(model_key, input_tokens, output_tokens), 6),
        "tokens_estimated": usage is None,
    }


def call_with_fallback(
    model_key: str, prompt: str, keys: dict, unavailable: set, order: list[str]
) -> dict:
    """
    Try the chosen model, then the rest of the order if it is out of quota.

    Availability is a routing input, not an afterthought. A router that picks
    a model and fails when it is rate limited has not routed anything.
    """
    tried: list[str] = []
    candidates = [model_key] + [k for k in order if k != model_key]

    for candidate in candidates:
        if candidate in unavailable:
            continue

        try:
            result = call_model(candidate, prompt, keys)
            result["tried"] = tried
            result["fell_back"] = candidate != model_key
            return result

        except QuotaError:
            unavailable.add(candidate)
            tried.append(f"{candidate}: out of quota")

        except ProviderError as error:
            tried.append(f"{candidate}: {error}")

    raise ProviderError(f"Every model failed. Tried: {'; '.join(tried)}")
