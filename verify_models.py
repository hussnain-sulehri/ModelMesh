"""
verify_models.py - preflight check for the router catalogue.

Run this before the benchmark and again on the morning of the demo.

It answers four questions:

1. Does every model id in models.py still resolve and return text?
2. Does the provider return real usage metadata, or are we estimating?
3. How far off is estimate_tokens() from the billed count?
4. Do Gemini thinking tokens materially change the cost?

Point 4 matters because providers.py reads candidates_token_count, which
excludes thoughts_token_count. Thinking tokens bill at the output rate, so
every Gemini cost the app reports is low by whatever this script prints.

It also runs static checks that need no network, so --offline is useful when
quota is gone.

Usage (PowerShell, from the project folder):

    python verify_models.py
    python verify_models.py --offline
    python verify_models.py --only gemini-pro

Budget: one call per model. On the Gemini free tier that is 1 of your 20
per model per day, so this is cheap to run twice.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import get_key
from models import MODELS, estimate_cost, estimate_tokens
from router import MAX_QUALITY, MIN_QUALITY

# Short enough to be cheap, specific enough that a wrong answer is visible.
PROBE = "Reply with exactly the two characters: ok"

OUT = Path("benchmarks")


# --------------------------------------------------------------------------
# Static checks. No network, no quota.
# --------------------------------------------------------------------------

def check_bands() -> list[str]:
    """
    How many models are eligible in each complexity band?

    A band with one member means the weighted score is inert there: the
    sliders change nothing and the score table has a single row. A band with
    zero members means select_model falls straight into the degraded path.
    """
    notes = []
    for level in ("low", "medium", "high"):
        floor, ceiling = MIN_QUALITY[level], MAX_QUALITY[level]
        members = [
            key for key, spec in MODELS.items()
            if floor <= spec["quality"] <= ceiling
        ]
        label = f"  {level:<6} [{floor}-{ceiling}]  {len(members)} eligible"
        if members:
            label += ": " + ", ".join(members)
        notes.append(label)

        if len(members) == 0:
            notes.append("         EMPTY - every request here routes degraded")
        elif len(members) == 1:
            notes.append("         single candidate - weights have no effect here")
    return notes


def check_monotonicity() -> list[str]:
    """
    Cost should rise with quality. If it does not, the router can find a
    model that is both better and cheaper, which means the catalogue is
    wrong rather than the routing being clever.
    """
    problems = []
    ranked = sorted(MODELS.items(), key=lambda kv: kv[1]["quality"])

    for (lo_key, lo), (hi_key, hi) in zip(ranked, ranked[1:]):
        if hi["output_cost"] < lo["output_cost"]:
            problems.append(
                f"  {hi_key} (q{hi['quality']}, ${hi['output_cost']}/1M out) is "
                f"both better and cheaper than {lo_key} "
                f"(q{lo['quality']}, ${lo['output_cost']}/1M out)"
            )
        if hi["typical_latency"] < lo["typical_latency"]:
            problems.append(
                f"  {hi_key} is both better and faster than {lo_key} "
                f"({hi['typical_latency']}s vs {lo['typical_latency']}s)"
            )
    return problems


def check_provenance() -> list[str]:
    """Flag any price that has no source url or verification date."""
    missing = []
    for key, spec in MODELS.items():
        if not spec.get("price_source_url") or not spec.get("price_verified_on"):
            missing.append(key)
    return missing


def spread() -> str:
    """The headline number the whole project rests on."""
    cheap = min(MODELS.values(), key=lambda s: s["output_cost"])
    dear = max(MODELS.values(), key=lambda s: s["output_cost"])
    ratio = dear["output_cost"] / cheap["output_cost"]
    return (f"  {dear['model']} costs {ratio:.0f}x {cheap['model']} on output "
            f"(${dear['output_cost']} vs ${cheap['output_cost']} per 1M)")


# --------------------------------------------------------------------------
# Live probe. One call per model.
# --------------------------------------------------------------------------

def probe_gemini(spec: dict, api_key: str) -> dict:
    from google import genai

    client = genai.Client(api_key=api_key)
    started = time.perf_counter()
    response = client.models.generate_content(model=spec["model"], contents=PROBE)
    latency = time.perf_counter() - started

    usage = getattr(response, "usage_metadata", None)
    return {
        "text": (response.text or "").strip(),
        "latency": latency,
        "usage_present": usage is not None,
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        # The field providers.py never reads. Billed at the output rate.
        "thinking_tokens": getattr(usage, "thoughts_token_count", None) or 0,
        "total_tokens": getattr(usage, "total_token_count", None),
    }


def probe_groq(spec: dict, api_key: str) -> dict:
    from groq import Groq

    client = Groq(api_key=api_key)
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=spec["model"],
        messages=[{"role": "user", "content": PROBE}],
    )
    latency = time.perf_counter() - started

    usage = getattr(response, "usage", None)
    return {
        "text": (response.choices[0].message.content or "").strip(),
        "latency": latency,
        "usage_present": usage is not None,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "thinking_tokens": 0,
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def probe(model_key: str, keys: dict) -> dict:
    spec = MODELS[model_key]
    provider = spec["provider"]
    api_key = keys.get(provider)

    record = {
        "key": model_key,
        "model_id": spec["model"],
        "provider": provider,
        "catalogue_latency": spec["typical_latency"],
    }

    if not api_key:
        return {**record, "status": "no_key",
                "detail": f"{provider.upper()}_API_KEY not set"}

    try:
        if provider == "gemini":
            raw = probe_gemini(spec, api_key)
        elif provider == "groq":
            raw = probe_groq(spec, api_key)
        else:
            return {**record, "status": "unknown_provider", "detail": provider}
    except Exception as error:
        text = f"{type(error).__name__}: {error}"
        lowered = text.lower()
        if any(m in lowered for m in ("429", "resource_exhausted", "rate limit", "quota")):
            status = "quota"
        elif any(m in lowered for m in ("404", "not found", "unsupported", "permission",
                                        "403", "not available", "deprecat")):
            # The interesting failure: the id no longer resolves, or your key
            # no longer has access to this tier.
            status = "unavailable"
        else:
            status = "error"
        return {**record, "status": status, "detail": text[:400]}

    billed_out = (raw["output_tokens"] or 0) + raw["thinking_tokens"]

    reported = estimate_cost(model_key, raw["input_tokens"] or 0,
                             raw["output_tokens"] or 0)
    actual = estimate_cost(model_key, raw["input_tokens"] or 0, billed_out)

    guessed_in = estimate_tokens(PROBE)
    drift = None
    if raw["input_tokens"]:
        drift = (guessed_in - raw["input_tokens"]) / raw["input_tokens"] * 100

    return {
        **record,
        "status": "ok",
        "answer": raw["text"][:80],
        "measured_latency": round(raw["latency"], 2),
        "usage_present": raw["usage_present"],
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
        "thinking_tokens": raw["thinking_tokens"],
        "cost_as_app_reports_it": round(reported, 8),
        "cost_with_thinking": round(actual, 8),
        "thinking_cost_gap_pct": (
            round((actual / reported - 1) * 100, 1) if reported else 0.0
        ),
        "estimate_tokens_drift_pct": round(drift, 1) if drift is not None else None,
    }


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="static checks only, no API calls")
    parser.add_argument("--only", metavar="KEY",
                        help="probe a single model key")
    args = parser.parse_args()

    print("=" * 68)
    print("CATALOGUE CHECKS (no network)")
    print("=" * 68)

    print("\nBand occupancy")
    for line in check_bands():
        print(line)

    print("\nCost and latency monotonicity")
    problems = check_monotonicity()
    if problems:
        for line in problems:
            print(line)
    else:
        print("  ok: cost and latency both rise with quality")

    print("\nSpread")
    print(spread())

    print("\nPrice provenance")
    missing = check_provenance()
    if missing:
        print("  no price_source_url / price_verified_on on: " + ", ".join(missing))
        print("  add both fields before submitting; undated prices are unciteable")
    else:
        print("  ok: every price is dated and sourced")

    if args.offline:
        return 0

    keys = {"gemini": get_key("GEMINI_API_KEY"), "groq": get_key("GROQ_API_KEY")}
    targets = [args.only] if args.only else list(MODELS)

    print("\n" + "=" * 68)
    print(f"LIVE PROBE ({len(targets)} calls)")
    print("=" * 68)

    results = []
    for model_key in targets:
        if model_key not in MODELS:
            print(f"\n{model_key}: not in catalogue")
            continue

        print(f"\n{model_key}  ({MODELS[model_key]['model']})")
        record = probe(model_key, keys)
        results.append(record)

        if record["status"] != "ok":
            print(f"  STATUS   {record['status'].upper()}")
            print(f"  {record.get('detail', '')}")
            if record["status"] == "unavailable":
                print("  -> the id or your tier changed. Fix models.py before"
                      " running the benchmark.")
            continue

        print(f"  STATUS   ok")
        print(f"  answer   {record['answer']!r}")
        print(f"  latency  {record['measured_latency']}s measured vs "
              f"{record['catalogue_latency']}s in catalogue")
        print(f"  tokens   {record['input_tokens']} in / "
              f"{record['output_tokens']} out"
              + (f" / {record['thinking_tokens']} thinking"
                 if record["thinking_tokens"] else ""))

        if not record["usage_present"]:
            print("  WARN     no usage metadata; every cost for this model is"
                  " an estimate")

        if record["thinking_tokens"]:
            print(f"  WARN     app under-reports this model's cost by "
                  f"{record['thinking_cost_gap_pct']}% on this probe "
                  f"(thinking tokens bill as output)")

        drift = record["estimate_tokens_drift_pct"]
        if drift is not None and abs(drift) > 25:
            print(f"  WARN     estimate_tokens is off by {drift:+.0f}% here; "
                  f"projected costs in the benchmark will inherit this")

    OUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"verify_{stamp}.json"
    path.write_text(json.dumps(
        {"checked_at": stamp, "probe": PROBE, "results": results},
        indent=2,
    ), encoding="utf-8")

    ok = [r for r in results if r["status"] == "ok"]
    broken = [r for r in results if r["status"] in ("unavailable", "unknown_provider")]

    print("\n" + "=" * 68)
    print(f"{len(ok)}/{len(results)} models reachable. Written to {path}")
    if broken:
        print("BLOCKER: " + ", ".join(r["key"] for r in broken) +
              " will not answer. The benchmark cannot run until these are"
              " replaced or removed from the catalogue.")
    print("=" * 68)

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
