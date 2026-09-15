"""
ModelMesh AI Router

Intelligent LLM routing layer that selects the best model
based on cost, speed and quality.

Run:
    streamlit run app.py
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from analyzer import analyze_request
from config import get_key, mask
from models import MODELS, estimate_cost
from providers import ProviderError, call_model, call_with_fallback
from router import DEFAULT_WEIGHTS, baseline, select_model


# --------------------------------------------------
# Page Config
# --------------------------------------------------

st.set_page_config(
    page_title="ModelMesh AI Router",
    page_icon="🔀",
    layout="wide"
)


st.title("🔀 ModelMesh AI Router")

st.caption(
    "Route every request to the cheapest model that can still answer it"
)


# --------------------------------------------------
# Keys
# --------------------------------------------------

keys = {
    "gemini": get_key("GEMINI_API_KEY"),
    "groq": get_key("GROQ_API_KEY")
}
st.sidebar.write(
    "Gemini loaded:",
    bool(keys["gemini"])
)

st.sidebar.write(
    "Groq loaded:",
    bool(keys["groq"])
)

# --------------------------------------------------
# Session State
# --------------------------------------------------

defaults = {
    "unavailable": set(),
    "log": [],
    "execution_error": None,
    "demo_prompt": "",
    "force_failure": False,
    "last_logged": None,
    "last_routed_prompt": ""
}


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

def clear_current_result():

    st.session_state.pop("result", None)
    st.session_state.pop("decision", None)
    st.session_state.pop("analysis", None)
    st.session_state["execution_error"] = None

# --------------------------------------------------
# Sidebar
# --------------------------------------------------

st.sidebar.title("⚙ Router Controls")


st.sidebar.caption(
    f"Gemini: {mask(keys['gemini'])}"
)

st.sidebar.caption(
    f"Groq: {mask(keys['groq'])}"
)


st.sidebar.divider()


st.sidebar.subheader("Optimization Objective")


w_cost = st.sidebar.slider(
    "Cost",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["cost"],
    0.05
)

w_speed = st.sidebar.slider(
    "Speed",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["speed"],
    0.05
)

w_quality = st.sidebar.slider(
    "Quality",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["quality"],
    0.05
)


total = w_cost + w_speed + w_quality or 1


weights = {
    "cost": w_cost / total,
    "speed": w_speed / total,
    "quality": w_quality / total
}


st.sidebar.divider()


use_llm_classifier = st.sidebar.checkbox(
    "Classify with small model",
    value=False
)


execute = st.sidebar.checkbox(
    "Execute model response",
    value=True
)


st.sidebar.checkbox(
    "Simulate provider failure",
    key="force_failure",
    help="Demo fallback handling"
)



if st.session_state["unavailable"]:

    st.sidebar.warning(
        "Temporary unavailable this session:\n\n"
        +
        "\n".join(
            sorted(st.session_state["unavailable"])
        )
    )

    if st.sidebar.button("Reset availability"):
        st.session_state["unavailable"] = set()



# --------------------------------------------------
# Demo Prompts
# --------------------------------------------------

st.subheader("🚀 Quick Demo")


demo1, demo2, demo3 = st.columns(3)


if demo1.button("🟢 Simple Question"):

    st.session_state["demo_prompt"] = (
        "Explain what HTML is"
    )

    clear_current_result()



if demo2.button("🟡 Medium Task"):

    st.session_state["demo_prompt"] = (
        "Write Python code for JWT authentication API"
    )

    clear_current_result()



if demo3.button("🔴 Complex Reasoning"):

    st.session_state["demo_prompt"] = (
        "Design scalable architecture for AI SaaS platform"
    )

    clear_current_result()



# --------------------------------------------------
# Input
# --------------------------------------------------

prompt = st.text_area(
    "Request",
    value=st.session_state["demo_prompt"],
    height=140,
    placeholder="Ask anything..."
)
# Clear previous answer when user edits the prompt
if (
    st.session_state["last_routed_prompt"]
    and prompt != st.session_state["last_routed_prompt"]
):

    st.session_state.pop("result", None)
    st.session_state.pop("decision", None)
    st.session_state.pop("analysis", None)
    st.session_state["execution_error"] = None


# --------------------------------------------------
# Routing
# --------------------------------------------------

if st.button(
    "Route Request",
    type="primary",
    disabled=not prompt.strip()
):

    st.session_state["execution_error"] = None


    classifier = None


    if use_llm_classifier and keys["groq"]:

        cheapest = min(
            MODELS,
            key=lambda k: MODELS[k]["output_cost"]
        )

        classifier = lambda text: call_model(
            cheapest,
            text,
            keys
        )["answer"]



    with st.spinner("Analyzing request..."):

        analysis = analyze_request(
            prompt,
            call=classifier
        )

    decision = select_model(
        analysis,
        prompt=prompt,
        weights=weights,
        unavailable=st.session_state["unavailable"]
    )
    st.session_state["last_routed_prompt"] = prompt

    st.session_state["analysis"] = analysis

    st.session_state["decision"] = decision


    st.session_state.pop(
        "result",
        None
    )



    if execute:

        order = sorted(
            MODELS,
            key=lambda k: MODELS[k]["quality"],
            reverse=True
        )


        try:

            with st.spinner(
                f"Calling {decision['spec']['model']}..."
            ):


                if st.session_state["force_failure"]:

                    raise ProviderError(
                        "Simulated provider failure"
                    )


                st.session_state["result"] = call_with_fallback(
                    decision["key"],
                    prompt,
                    keys,
                    st.session_state["unavailable"],
                    order
                )


        except ProviderError as error:

            st.session_state["execution_error"] = str(error)




# --------------------------------------------------
# Output
# --------------------------------------------------

if "decision" in st.session_state:


    analysis = st.session_state["analysis"]

    decision = st.session_state["decision"]

    result = st.session_state.get("result")



    if decision["degraded"]:

        st.warning(
            "Quality requirement could not be met. "
            "Using best available fallback model."
        )



    # Metrics

    c1,c2,c3,c4,c5 = st.columns(5)


    c1.metric(
        "Complexity",
        analysis["complexity"].upper()
    )


    c2.metric(
        "Model",
        decision["spec"]["model"]
    )


    if result:

        c3.metric(
            "Latency",
            f"{result['latency']}s"
        )


        c4.metric(
            "Tokens",
            f"{result['input_tokens']} → {result['output_tokens']}"
        )


    else:

        c3.metric(
            "Est. Cost",
            f"${decision['estimated_cost']:.6f}"
        )


    large = baseline(
        "always_large"
    )


    large_cost = estimate_cost(
        large,
        decision["input_tokens"],
        result["output_tokens"] if result else 500
    )


    if result:

        saved = (
            1-result["cost"]/large_cost
        )*100

        c5.metric(
            "Savings",
            f"{saved:.1f}%"
        )



    # Tabs

    answer_tab, why_tab, savings_tab, log_tab = st.tabs(
        [
            "💬 Answer",
            "🧠 Routing Intelligence",
            "💰 Savings",
            "📊 Session Log"
        ]
    )



    # Answer

    with answer_tab:


        if result:

            st.success(
                "Response generated successfully"
            )

            st.write(
                result["answer"]
            )


            st.caption(
                f"{result['model']} | "
                f"{result['latency']}s | "
                f"{result['input_tokens']} input | "
                f"{result['output_tokens']} output"
            )


        elif st.session_state["execution_error"]:

            st.error(
                "Routing succeeded but execution failed:\n\n"
                +
                st.session_state["execution_error"]
            )


        else:

            st.info(
                "Execution disabled. Enable model execution."
            )



    # Intelligence

    with why_tab:


        st.subheader(
            "Why this model?"
        )


        for signal in analysis["signals"]:

            st.write(
                "✓",
                signal
            )


        st.write(
            f"Quality requirement: "
            f"{decision['quality_floor']}/10"
        )



        if decision["scores"]:


            rows=[]


            for model,score in decision["scores"].items():

                rows.append(
                    {
                    "Model":MODELS[model]["model"],
                    "Quality":MODELS[model]["quality"],
                    "Cost":MODELS[model]["output_cost"],
                    "Latency":MODELS[model]["typical_latency"],
                    "Score":score,
                    "Winner":
                    "🏆" if model==decision["key"] else ""
                    }
                )


            df=pd.DataFrame(rows)


            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )



        st.subheader(
            "Rejected Models"
        )


        for key,reason in decision["rejected"].items():

            st.write(
                f"❌ {MODELS[key]['model']}: {reason}"
            )



    # Savings

    with savings_tab:


        if st.session_state["log"]:


            df=pd.DataFrame(
                st.session_state["log"]
            )


            chart=df[
                [
                "Cost",
                "Always-large cost"
                ]
            ].cumsum()


            fig=px.line(
                chart,
                markers=True,
                title="ModelMesh Savings"
            )


            st.plotly_chart(
                fig,
                use_container_width=True
            )


        else:

            st.info(
                "Run multiple requests to see savings."
            )



    # Logs

    with log_tab:

        if result:

            run_id = (
                prompt,
                result["model"],
                result["cost"],
                result["latency"]
            )

            if st.session_state["last_logged"] != run_id:
                st.session_state["log"].append(
                    {
                        "Request": prompt[:60],
                        "Complexity": analysis["complexity"],
                        "Model": result["model"],
                        "Cost": result["cost"],
                        "Latency": result["latency"],
                        "Always-large cost": round(
                            large_cost,
                            6
                        )
                    }
                )
                st.session_state["log"] = (
                    st.session_state["log"][-10:]
                )
                st.session_state["last_logged"] = run_id


        if st.session_state["log"]:


            frame=pd.DataFrame(
                st.session_state["log"]
            )


            st.dataframe(
                frame,
                hide_index=True,
                use_container_width=True
            )


        else:

            st.info(
                "No requests yet."
            )