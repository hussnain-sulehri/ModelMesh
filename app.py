"""
Smart AI Model Router

Analyses a request, picks a model against a cost, speed and quality
objective, sends it, and reports what the call actually cost against what
the same request would have cost on the largest model.

Run:
    streamlit run app.py
"""

import pandas as pd
import streamlit as st

from analyzer import analyze_request
from config import get_key, mask
from models import MODELS, estimate_cost, estimate_tokens
from providers import ProviderError, call_model, call_with_fallback
from router import DEFAULT_WEIGHTS, baseline, select_model

st.set_page_config(page_title="AI Model Router", page_icon="🔀", layout="wide")
st.title("Smart AI Model Router")
st.caption("Route each request to the cheapest model that can still answer it")

keys = {"gemini": get_key("GEMINI_API_KEY"), "groq": get_key("GROQ_API_KEY")}

if "unavailable" not in st.session_state:
    st.session_state["unavailable"] = set()
if "log" not in st.session_state:
    st.session_state["log"] = []

# --- Sidebar ---

st.sidebar.caption(f"Gemini: {mask(keys['gemini'])}")
st.sidebar.caption(f"Groq: {mask(keys['groq'])}")
st.sidebar.divider()

st.sidebar.subheader("Objective")
st.sidebar.caption("What the router optimises for. These weights are read by "
                   "the scoring function, not decoration.")

w_cost = st.sidebar.slider("Cost", 0.0, 1.0, DEFAULT_WEIGHTS["cost"], 0.05)
w_speed = st.sidebar.slider("Speed", 0.0, 1.0, DEFAULT_WEIGHTS["speed"], 0.05)
w_quality = st.sidebar.slider("Quality", 0.0, 1.0, DEFAULT_WEIGHTS["quality"], 0.05)

total = w_cost + w_speed + w_quality or 1.0
weights = {"cost": w_cost / total, "speed": w_speed / total, "quality": w_quality / total}

st.sidebar.divider()

use_llm_classifier = st.sidebar.checkbox(
    "Classify with a small model",
    value=False,
    help="Costs one extra cheap call. Compare against the free keyword version.",
)

execute = st.sidebar.checkbox("Actually send the request", value=True)

if st.session_state["unavailable"]:
    st.sidebar.warning(
        "Out of quota: " + ", ".join(sorted(st.session_state["unavailable"]))
    )
    if st.sidebar.button("Reset availability"):
        st.session_state["unavailable"] = set()

# --- Input ---

prompt = st.text_area("Request", height=140, placeholder="Ask anything")

if st.button("Route", type="primary", disabled=not prompt.strip()):

    classifier = None
    if use_llm_classifier and keys["groq"]:
        cheapest = min(MODELS, key=lambda k: MODELS[k]["output_cost"])
        classifier = lambda text: call_model(cheapest, text, keys)["answer"]

    with st.spinner("Analysing..."):
        analysis = analyze_request(prompt, call=classifier)

    decision = select_model(
        analysis,
        prompt=prompt,
        weights=weights,
        unavailable=st.session_state["unavailable"],
    )

    st.session_state["analysis"] = analysis
    st.session_state["decision"] = decision
    st.session_state.pop("result", None)

    if execute:
        order = sorted(MODELS, key=lambda k: MODELS[k]["quality"], reverse=True)
        try:
            with st.spinner(f"Calling {decision['spec']['model']}..."):
                st.session_state["result"] = call_with_fallback(
                    decision["key"], prompt, keys,
                    st.session_state["unavailable"], order,
                )
        except ProviderError as error:
            st.error(str(error))

# --- Output ---

if "decision" in st.session_state:
    analysis = st.session_state["analysis"]
    decision = st.session_state["decision"]
    result = st.session_state.get("result")

    if decision["degraded"]:
        st.warning(
            "Every model above the quality floor is unavailable. Answering "
            "with the best one left, which is below the floor for this request."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Complexity", analysis["complexity"].upper(),
                help=f"Score {analysis['score']}/100 via {analysis['method']}")
    col2.metric("Routed to", decision["spec"]["model"].split("/")[-1])

    large = baseline("always_large")
    large_cost = estimate_cost(
        large, decision["input_tokens"],
        result["output_tokens"] if result else 500,
    )

    if result:
        col3.metric("Cost", f"${result['cost']:.6f}")
        saved = (1 - result["cost"] / large_cost) * 100 if large_cost else 0
        col4.metric("vs largest model", f"{saved:.0f}% cheaper",
                    help=f"${large_cost:.6f} on {MODELS[large]['model']}")
    else:
        col3.metric("Est. cost", f"${decision['estimated_cost']:.6f}")
        col4.metric("Est. vs largest", f"${large_cost:.6f}")

    tab_answer, tab_why, tab_log = st.tabs(["Answer", "Why this model", "Session log"])

    with tab_answer:
        if result:
            st.write(result["answer"])
            st.caption(
                f"{result['model']} · {result['latency']}s · "
                f"{result['input_tokens']} in / {result['output_tokens']} out"
                + (" · tokens estimated" if result["tokens_estimated"] else "")
            )
            if result.get("fell_back"):
                st.info("First choice was unavailable. " + "; ".join(result["tried"]))
        else:
            st.info("Execution is off. Turn it on in the sidebar to get an answer.")

    with tab_why:
        st.write("**Signals found**")
        for signal in analysis["signals"]:
            st.markdown(f"- {signal}")

        st.write(f"**Quality floor for {analysis['complexity']} requests:** "
                 f"{decision['quality_floor']}/10")

        if decision["scores"]:
            rows = [
                {
                    "Model": MODELS[k]["model"],
                    "Quality": MODELS[k]["quality"],
                    "$/1M out": MODELS[k]["output_cost"],
                    "Typical latency": MODELS[k]["typical_latency"],
                    "Score": score,
                    "Chosen": "yes" if k == decision["key"] else "",
                }
                for k, score in sorted(
                    decision["scores"].items(), key=lambda x: -x[1]
                )
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True,
                         use_container_width=True)

        if decision["rejected"]:
            st.write("**Not considered**")
            for key, reason in decision["rejected"].items():
                st.markdown(f"- `{MODELS[key]['model']}`: {reason}")

    with tab_log:
        if result:
            st.session_state["log"].append({
                "Request": prompt[:60] + ("..." if len(prompt) > 60 else ""),
                "Complexity": analysis["complexity"],
                "Model": result["model"],
                "Cost": result["cost"],
                "Latency": result["latency"],
                "Always-large cost": round(large_cost, 6),
            })
            st.session_state.pop("result", None)

        if st.session_state["log"]:
            frame = pd.DataFrame(st.session_state["log"])
            st.dataframe(frame, hide_index=True, use_container_width=True)

            routed = frame["Cost"].sum()
            always = frame["Always-large cost"].sum()

            a, b, c = st.columns(3)
            a.metric("Routed total", f"${routed:.6f}")
            b.metric("Always-large total", f"${always:.6f}")
            c.metric("Saved", f"{(1 - routed / always) * 100:.0f}%" if always else "0%")

            st.caption(
                "Cost saving is measured. Whether quality held up is not, and "
                "that needs the benchmark, not this log."
            )
        else:
            st.info("Route a few requests to build up a comparison.")