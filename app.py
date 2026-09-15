"""
ModelMesh AI Router

Intelligent LLM routing layer that selects the best model
for each request using:

- complexity
- quality
- estimated API cost
- latency
- provider availability

Run locally:

    streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from analyzer import analyze_request
from config import get_key, mask
from models import MODELS, estimate_cost
from providers import (
    ProviderError,
    QuotaError,
    call_model,
    call_with_fallback,
)
from router import (
    DEFAULT_WEIGHTS,
    baseline,
    select_model,
)


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="ModelMesh AI Router",
    page_icon="",
    layout="wide",
)
st.markdown(
"""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 1rem;
}

h1 {
    margin-bottom: 0.2rem;
}

h2 {
    margin-top: 0.8rem;
}

[data-testid="stSidebar"] {
    padding-top: 1rem;
}

</style>
""",
unsafe_allow_html=True
)

st.title("ModelMesh AI Router")

st.caption(
    "Intelligent LLM routing based on cost, speed, quality and request complexity."
)


# --------------------------------------------------
# API keys
# --------------------------------------------------

keys = {
    "gemini": get_key("GEMINI_API_KEY"),
    "groq": get_key("GROQ_API_KEY"),
}


# --------------------------------------------------
# Session state
# --------------------------------------------------

defaults = {

    "unavailable": set(),

    "log": [],

    "execution_error": None,

    "force_failure": False,

    "last_routed_prompt": "",

    "prompt_input": "",
}


for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def clear_current_result():
    """
    Clear output associated with the previous prompt.
    """

    st.session_state.pop(
        "result",
        None,
    )

    st.session_state.pop(
        "decision",
        None,
    )

    st.session_state.pop(
        "analysis",
        None,
    )

    st.session_state["execution_error"] = None


def set_demo_prompt(text: str):
    """
    Set a demo prompt and remove stale results.
    """

    st.session_state["prompt_input"] = text

    clear_current_result()


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

st.sidebar.title(
    "Router Controls"
)


st.sidebar.caption(
    f"Gemini: {mask(keys['gemini'])}"
)

st.sidebar.caption(
    f"Groq: {mask(keys['groq'])}"
)


st.sidebar.divider()


# --------------------------------------------------
# Optimization weights
# --------------------------------------------------

st.sidebar.header("Optimization Objective")
st.sidebar.caption(
    "Adjust the routing strategy between cost efficiency, "
    "response speed and answer quality."
)

w_cost = st.sidebar.slider(
    "Cost",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["cost"],
    0.05,
)


w_speed = st.sidebar.slider(
    "Speed",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["speed"],
    0.05,
)


w_quality = st.sidebar.slider(
    "Quality",
    0.0,
    1.0,
    DEFAULT_WEIGHTS["quality"],
    0.05,
)


total = (
    w_cost
    + w_speed
    + w_quality
) or 1.0


weights = {

    "cost":
        w_cost / total,

    "speed":
        w_speed / total,

    "quality":
        w_quality / total,
}


st.sidebar.divider()


# --------------------------------------------------
# Execution controls
# --------------------------------------------------

execute = st.sidebar.checkbox(
    "Execute model response",
    value=True,
)


st.sidebar.checkbox(
    "Simulate selected-model failure",
    key="force_failure",
    help=(
        "The selected model is intentionally skipped "
        "so ModelMesh demonstrates automatic fallback."
    ),
)


# --------------------------------------------------
# Temporary unavailable models
# --------------------------------------------------

if st.session_state["unavailable"]:

    st.sidebar.warning(
        "Temporary unavailable this session:\n\n"
        +
        "\n".join(
            sorted(
                st.session_state["unavailable"]
            )
        )
    )


    if st.sidebar.button(
        "Reset availability"
    ):

        st.session_state["unavailable"] = set()

        st.rerun()


# --------------------------------------------------
# Session log control
# --------------------------------------------------

if st.sidebar.button(
    "Clear session log"
):

    st.session_state["log"] = []

    st.rerun()


# --------------------------------------------------
# Quick demo prompts
# --------------------------------------------------

st.subheader(
    "Quick Demo"
)


demo1, demo2, demo3 = st.columns(3)


demo1.button(
    "🟢 Simple Question",
    on_click=set_demo_prompt,
    args=(
        "Explain what HTML is",
    ),
)


demo2.button(
    "🟡 Medium Task",
    on_click=set_demo_prompt,
    args=(
        "Write Python code for JWT authentication API",
    ),
)


demo3.button(
    "🔴 Complex Reasoning",
    on_click=set_demo_prompt,
    args=(
        "Design scalable architecture for AI SaaS platform",
    ),
)


# --------------------------------------------------
# Prompt input
# --------------------------------------------------

prompt = st.text_area(
    "Request",
    key="prompt_input",
    height=140,
    placeholder="Ask anything...",
    on_change=clear_current_result,
)


# --------------------------------------------------
# Route request
# --------------------------------------------------

if st.button(
    "Route Request",
    type="primary",
    disabled=not prompt.strip(),
):

    st.session_state["execution_error"] = None


    # --------------------------------------------------
    # Semantic classifier
    # --------------------------------------------------
    #
    # The analyzer itself decides whether it needs this.
    # Obvious LOW/HIGH prompts do not necessarily call it.
    # --------------------------------------------------

    classifier = None


    if keys["groq"]:

        # Prefer Qwen for English semantic classification.
        if (
            "groq-medium"
            not in st.session_state["unavailable"]
        ):

            classifier_model = "groq-medium"

        else:

            classifier_model = "groq-fast"


        def classifier(text):

            try:

                return call_model(
                    classifier_model,
                    text,
                    keys,
                )["answer"]

            except QuotaError:

                st.session_state[
                    "unavailable"
                ].add(
                    classifier_model
                )

                raise


    # --------------------------------------------------
    # Analyze request
    # --------------------------------------------------

    with st.spinner(
        "Analyzing request..."
    ):

        analysis = analyze_request(
            prompt,
            call=classifier,
        )


    # --------------------------------------------------
    # Select model
    # --------------------------------------------------

    decision = select_model(
        analysis,
        prompt=prompt,
        weights=weights,
        unavailable=
            st.session_state["unavailable"],
    )


    st.session_state[
        "last_routed_prompt"
    ] = prompt


    st.session_state[
        "analysis"
    ] = analysis


    st.session_state[
        "decision"
    ] = decision


    st.session_state.pop(
        "result",
        None,
    )


    # --------------------------------------------------
    # Execute model
    # --------------------------------------------------

    if execute:

        # --------------------------------------------------
        # Quality-aware fallback candidates
        # --------------------------------------------------
        #
        # Fallback may move upward in quality,
        # but must never go below the complexity floor.
        # --------------------------------------------------

        floor = decision[
            "quality_floor"
        ]


        eligible_fallbacks = [

            key

            for key, spec
            in MODELS.items()

            if (
                spec["quality"] >= floor
                and key
                not in st.session_state[
                    "unavailable"
                ]
            )
        ]


        # Prefer models closest in quality to the selected
        # model, then cheaper/faster alternatives.

        selected_quality = (
            decision["spec"]["quality"]
        )


        order = sorted(

            eligible_fallbacks,

            key=lambda key: (

                abs(
                    MODELS[key]["quality"]
                    - selected_quality
                ),

                MODELS[key]["output_cost"],

                MODELS[key]["typical_latency"],
            ),
        )


        simulate_failure_for = (

            decision["key"]

            if st.session_state[
                "force_failure"
            ]

            else None
        )


        try:

            with st.spinner(
                f"Calling "
                f"{decision['spec']['model']}..."
            ):

                result = call_with_fallback(

                    decision["key"],

                    prompt,

                    keys,

                    st.session_state[
                        "unavailable"
                    ],

                    order,

                    simulate_failure_for=
                        simulate_failure_for,
                )


            st.session_state[
                "result"
            ] = result


            # --------------------------------------------------
            # Premium-model baseline
            # --------------------------------------------------

            large = baseline(
                "always_large"
            )


            baseline_cost = estimate_cost(

                large,

                result["input_tokens"],

                result.get(
                    "billable_output_tokens",
                    result["output_tokens"],
                ),
            )


            # --------------------------------------------------
            # Log only once, at execution time
            # --------------------------------------------------

            st.session_state[
                "log"
            ].append(
                {
                    "Request":
                        prompt[:60],

                    "Complexity":
                        analysis["complexity"],

                    "Model":
                        result["model"],

                    "Estimated Cost":
                        result["cost"],

                    "Latency":
                        result["latency"],

                    "Premium baseline cost":
                        round(
                            baseline_cost,
                            6,
                        ),
                }
            )


            # Keep latest 10 requests.
            st.session_state[
                "log"
            ] = (
                st.session_state[
                    "log"
                ][-10:]
            )


        except ProviderError as error:

            st.session_state[
                "execution_error"
            ] = str(error)


# --------------------------------------------------
# Output
# --------------------------------------------------

if "decision" in st.session_state:

    analysis = st.session_state[
        "analysis"
    ]

    decision = st.session_state[
        "decision"
    ]

    result = st.session_state.get(
        "result"
    )


    # --------------------------------------------------
    # Degraded routing warning
    # --------------------------------------------------

    if decision["degraded"]:

        st.warning(
            "Requested quality band was unavailable. "
            "ModelMesh selected the best remaining model."
        )


    # --------------------------------------------------
    # Metrics
    # --------------------------------------------------

    c1, c2, c3, c4, c5 = st.columns(5)


    c1.metric(
        "Complexity",
        analysis["complexity"].upper(),
    )


    actual_model = (

        result["model"]

        if result

        else decision[
            "spec"
        ]["model"]
    )


    c2.metric(
        "Model",
        actual_model,
    )


    if result:

        c3.metric(
            "Latency",
            f"{result['latency']}s",
        )


        c4.metric(
            "Tokens",
            (
                f"{result['input_tokens']} → "
                f"{result['output_tokens']}"
            ),
        )


        large = baseline(
            "always_large"
        )


        large_cost = estimate_cost(

            large,

            result["input_tokens"],

            result.get(
                "billable_output_tokens",
                result["output_tokens"],
            ),
        )


        if large_cost > 0:

            savings = (
                1
                -
                result["cost"]
                /
                large_cost
            ) * 100

        else:

            savings = 0


        c5.metric(
            "Est. Savings",
            f"{savings:.1f}%",
        )


    else:

        c3.metric(
            "Est. API Cost",
            (
                f"${decision['estimated_cost']:.6f}"
            ),
        )


    # --------------------------------------------------
    # Tabs
    # --------------------------------------------------

    (
        answer_tab,
        why_tab,
        savings_tab,
        log_tab,
    ) = st.tabs(
        [
            "💬 Answer",
            "🧠 Routing Intelligence",
            "💰 Savings",
            "📊 Session Log",
        ]
    )


    # --------------------------------------------------
    # Answer tab
    # --------------------------------------------------

    with answer_tab:

        if result:

            if result.get(
                "fell_back"
            ):

                st.warning(
                    "Selected model failed. "
                    "ModelMesh automatically used "
                    f"{result['model']} instead."
                )


                if result.get(
                    "tried"
                ):

                    with st.expander(
                        "Fallback details"
                    ):

                        for failure in result[
                            "tried"
                        ]:

                            st.write(
                                f"• {failure}"
                            )


            st.success(
                "Response generated successfully"
            )


            st.write(
                result["answer"]
            )


            caption = (
                f"{result['model']} | "
                f"{result['latency']}s | "
                f"{result['input_tokens']} input | "
                f"{result['output_tokens']} visible output"
            )


            if result.get(
                "thinking_tokens",
                0,
            ):

                caption += (
                    " | "
                    f"{result['thinking_tokens']} "
                    "thinking"
                )


            st.caption(
                caption
            )


            st.caption(
                "Cost values are estimated from "
                "configured provider list prices; "
                "free-tier execution may incur no "
                "actual charge."
            )


        elif st.session_state[
            "execution_error"
        ]:

            st.error(
                "Routing succeeded but execution failed:\n\n"
                +
                st.session_state[
                    "execution_error"
                ]
            )


        else:

            st.info(
                "Execution disabled. "
                "Enable model execution in the sidebar."
            )


    # --------------------------------------------------
    # Routing intelligence tab
    # --------------------------------------------------

    with why_tab:

        st.subheader(
            "Why this model?"
        )


        st.write(
            f"Analyzer method: "
            f"`{analysis.get('method', 'unknown')}`"
        )


        if "score" in analysis:

            st.write(
                f"Complexity score: "
                f"**{analysis['score']}/100**"
            )


        for signal in analysis.get(
            "signals",
            [],
        ):

            st.write(
                "✓",
                signal,
            )


        st.write(
            "Quality requirement: "
            f"**{decision['quality_floor']}–"
            f"{decision['quality_ceiling']}/10**"
        )


        if decision["scores"]:

            rows = []


            for (
                model_key,
                score,
            ) in decision[
                "scores"
            ].items():

                spec = MODELS[
                    model_key
                ]


                rows.append(
                    {
                        "Model":
                            spec["model"],

                        "Quality":
                            spec["quality"],

                        "Input $/1M":
                            spec["input_cost"],

                        "Output $/1M":
                            spec["output_cost"],

                        "Typical Latency":
                            spec[
                                "typical_latency"
                            ],

                        "Router Score":
                            score,

                        "Winner":
                            (
                                "🏆"
                                if model_key
                                == decision["key"]
                                else ""
                            ),
                    }
                )


            df = pd.DataFrame(
                rows
            )


            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )


        st.subheader(
            "Rejected Models"
        )


        if decision["rejected"]:

            for (
                key,
                reason,
            ) in decision[
                "rejected"
            ].items():

                st.write(
                    f"❌ "
                    f"{MODELS[key]['model']}: "
                    f"{reason}"
                )


        else:

            st.caption(
                "No models were rejected."
            )


    # --------------------------------------------------
    # Savings tab
    # --------------------------------------------------

    with savings_tab:

        if st.session_state[
            "log"
        ]:

            savings_df = pd.DataFrame(
                st.session_state[
                    "log"
                ]
            )


            chart = savings_df[
                [
                    "Estimated Cost",
                    "Premium baseline cost",
                ]
            ].cumsum()


            fig = px.line(
                chart,
                markers=True,
                title=(
                    "Cumulative Estimated "
                    "API Cost"
                ),
            )


            st.plotly_chart(
                fig,
                use_container_width=True,
            )


            total_router = savings_df[
                "Estimated Cost"
            ].sum()


            total_baseline = savings_df[
                "Premium baseline cost"
            ].sum()


            if total_baseline > 0:

                total_saved = (
                    1
                    -
                    total_router
                    /
                    total_baseline
                ) * 100


                st.metric(
                    "Estimated Session Savings",
                    f"{total_saved:.1f}%",
                )


        else:

            st.info(
                "Run multiple requests to "
                "see cumulative savings."
            )


    # --------------------------------------------------
    # Session log tab
    # --------------------------------------------------

    with log_tab:

        if st.session_state[
            "log"
        ]:

            frame = pd.DataFrame(
                st.session_state[
                    "log"
                ]
            )


            st.dataframe(
                frame,
                hide_index=True,
                use_container_width=True,
            )


        else:

            st.info(
                "No executed requests yet."
            )