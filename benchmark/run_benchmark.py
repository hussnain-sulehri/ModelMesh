import csv
import json
import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)
from analyzer import analyze_request
from config import get_key
from models import MODELS, estimate_cost
from providers import call_with_fallback
from router import select_model, DEFAULT_WEIGHTS


keys = {
    "gemini": get_key("GEMINI_API_KEY"),
    "groq": get_key("GROQ_API_KEY")
}


with open("benchmark/prompts.json", "r", encoding="utf-8") as file:
    prompts = json.load(file)


results = []


unavailable = set()


for item in prompts:

    prompt = item["prompt"]

    analysis = analyze_request(prompt)


    decision = select_model(
        analysis,
        prompt=prompt,
        weights=DEFAULT_WEIGHTS,
        unavailable=unavailable
    )


    try:

        result = call_with_fallback(
            decision["key"],
            prompt,
            keys,
            unavailable,
            [k for k in MODELS
             if MODELS[k]["quality"] >= decision["quality_floor"]]
        )


        results.append({

            "id": item["id"],
            "category": item["category"],
            "prompt": prompt,

            "complexity":
                analysis["complexity"],

            "model":
                result["model"],

            "provider":
                result["provider"],

            "latency":
                result["latency"],

            "input_tokens":
                result["input_tokens"],

            "output_tokens":
                result["output_tokens"],

            "cost":
                result["cost"]

        })


    except Exception as e:

        results.append({

            "id": item["id"],
            "category": item["category"],
            "prompt": prompt,
            "error": str(e)

        })



with open(
    "benchmark/results.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=results[0].keys()
    )

    writer.writeheader()
    writer.writerows(results)


print("Benchmark completed")
print("Saved: benchmark/results.csv")