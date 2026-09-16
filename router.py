"""
Routing decision.

Complexity sets a floor on quality. Among the models that clear the floor and
are currently available, the one with the best weighted score wins.

This is the part the old version was missing: cost, speed and quality sat in
the catalogue and nothing read them, so the router was a hardcoded map with
decorative numbers beside it.
"""

from models import MODELS, estimate_cost, estimate_tokens

# Complexity sets a band, not just a floor.
#
# The floor stops a cost-weighted router sending hard work to a weak model.
# The ceiling stops it sending "hi" to the most expensive model available,
# which a pure weighted score will happily do whenever quality is weighted at
# all. Both halves are needed; a floor alone was measured routing trivial
# requests to a 70B model.
#
# NOTE: the LOW ceiling was raised from 6 to 7 so more than one model is
# eligible for simple requests. At 6, only groq-fast (quality 5) qualified,
# which meant the cost/speed/quality sliders had zero effect on that band --
# verify_models.py's band-occupancy check flags this as "single candidate,
# weights have no effect here" if it regresses.
MIN_QUALITY = {"low": 4, "medium": 7, "high": 9}
MAX_QUALITY = {"low": 7, "medium": 8, "high": 10}

DEFAULT_WEIGHTS = {"cost": 0.4, "speed": 0.2, "quality": 0.4}


def _normalise(values: list[float], higher_is_better: bool) -> list[float]:
    """Map a list onto 0-1. All-equal lists become all 1.0."""
    low, high = min(values), max(values)

    if high == low:
        return [1.0] * len(values)

    if higher_is_better:
        return [(v - low) / (high - low) for v in values]
    return [(high - v) / (high - low) for v in values]


def select_model(
    analysis: dict,
    prompt: str = "",
    weights: dict | None = None,
    unavailable: set[str] | None = None,
    expected_output_tokens: int = 500,
) -> dict:
    """
    Pick a model and explain why.

    Returns the key, the spec, the estimated cost of this specific call, the
    score every candidate received, and the reason each rejected model was
    rejected. The explanation is the product here, not a side effect.
    """
    weights = weights or DEFAULT_WEIGHTS
    unavailable = unavailable or set()

    floor = MIN_QUALITY[analysis["complexity"]]
    ceiling = MAX_QUALITY[analysis["complexity"]]

    eligible: list[str] = []
    rejected: dict[str, str] = {}

    # The ceiling exists to stop overpaying. A model above the ceiling that is
    # cheaper than every in-band model is not overkill, it is a better deal,
    # so it stays eligible. Priced on output cost, which dominates LLM bills.
    in_band_costs = [
        spec["output_cost"]
        for key, spec in MODELS.items()
        if key not in unavailable and floor <= spec["quality"] <= ceiling
    ]
    cheapest_in_band = min(in_band_costs) if in_band_costs else None

    for key, spec in MODELS.items():
        quality = spec["quality"]

        if key in unavailable:
            rejected[key] = "out of quota or unreachable"
        elif quality < floor:
            rejected[key] = f"quality {quality} below floor {floor}"
        elif quality > ceiling and (
            cheapest_in_band is None or spec["output_cost"] >= cheapest_in_band
        ):
            rejected[key] = f"quality {quality} above ceiling {ceiling}, overkill here"
        else:
            eligible.append(key)

    if not eligible:
        # Every model that clears the floor is down. Take the best available
        # one and say plainly that quality was degraded.
        spare = [k for k in MODELS if k not in unavailable]
        if not spare:
            raise RuntimeError("Every model is unavailable.")

        key = max(spare, key=lambda k: MODELS[k]["quality"])
        return _result(key, analysis, prompt, expected_output_tokens, {}, rejected,
                       degraded=True)

    input_tokens = estimate_tokens(prompt) if prompt else 100

    costs = [estimate_cost(k, input_tokens, expected_output_tokens) for k in eligible]
    speeds = [MODELS[k]["typical_latency"] for k in eligible]
    qualities = [float(MODELS[k]["quality"]) for k in eligible]

    cost_scores = _normalise(costs, higher_is_better=False)
    speed_scores = _normalise(speeds, higher_is_better=False)
    quality_scores = _normalise(qualities, higher_is_better=True)

    scores = {
        key: round(
            weights["cost"] * cost_scores[i]
            + weights["speed"] * speed_scores[i]
            + weights["quality"] * quality_scores[i],
            3,
        )
        for i, key in enumerate(eligible)
    }

    best = max(scores, key=scores.get)
    return _result(best, analysis, prompt, expected_output_tokens, scores, rejected)


def _result(key, analysis, prompt, output_tokens, scores, rejected, degraded=False):
    input_tokens = estimate_tokens(prompt) if prompt else 100

    return {
        "key": key,
        "spec": MODELS[key],
        "estimated_cost": round(
            estimate_cost(key, input_tokens, output_tokens), 6
        ),
        "input_tokens": input_tokens,
        "quality_floor": MIN_QUALITY[analysis["complexity"]],
        "quality_ceiling": MAX_QUALITY[analysis["complexity"]],
        "scores": scores,
        "rejected": rejected,
        "degraded": degraded,
    }


def baseline(strategy: str) -> str:
    """
    Fixed strategies to measure the router against.

    Without these there is no way to say whether routing helped.
    """
    if strategy == "always_large":
        return max(MODELS, key=lambda k: MODELS[k]["quality"])
    if strategy == "always_small":
        return min(MODELS, key=lambda k: MODELS[k]["output_cost"])
    raise ValueError(f"Unknown strategy: {strategy}")