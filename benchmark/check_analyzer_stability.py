import json, sys, importlib
from pathlib import Path

# Works from anywhere: finds analyzer.py in the project root and
# prompts.json / test_analyzer_variants.py next to this script.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "analyzer")  # run: python benchmark/check_analyzer_stability.py
from test_analyzer_variants import VARIANTS
bench_bad = 0
for p in json.load(open(HERE / "prompts.json", encoding="utf-8")):
    r = mod.analyze_rules(p["prompt"])
    if r["complexity"] != p["category"]:
        bench_bad += 1; print(f"  bench #{p['id']:>2} want {p['category']:<6} got {r['complexity']:<6} ({r['score']})")
print(f"benchmark: {20-bench_bad}/20 correct")
wrong = unstable = total = 0
for want, groups in VARIANTS.items():
    for g in groups:
        got = [(mod.analyze_rules(x)["complexity"], mod.analyze_rules(x)["score"]) for x in g]
        if len({c for c,_ in got}) > 1: unstable += 1
        for x,(c,s) in zip(g,got):
            total += 1
            if c != want: wrong += 1; print(f"  var want {want:<6} got {c:<6} ({s:>3}) {x}")
print(f"variants: {total-wrong}/{total} correct, {unstable} unstable groups of {sum(map(len,VARIANTS.values()))}")