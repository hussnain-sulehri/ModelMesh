# ModelMesh

Intelligent routing layer for LLMs that automatically picks the best model for each request based on **cost, speed, and quality**.

> Built for the AI Infrastructure Hackathon, September 2026.

**Live Demo:** _TBD_
**Repository:** _TBD_

---

## The Problem

Most AI applications send every request to a single, powerful (expensive) model — whether the task is "What is the capital of France?" or "Design a scalable distributed AI system." This wastes cost, adds latency, and ignores the fact that different providers (OpenAI, Anthropic, Gemini, Groq, open-source) excel at different things.

**The real question:** *Which model is good enough for this request?*

## What ModelMesh Does

Instead of one model handling everything, ModelMesh sits between your app and multiple LLM providers:

```
User Request → Request Intelligence → Routing Engine (Cost / Speed / Quality) → Best Model → Response
```

For every request, it:
- Analyzes complexity
- Determines the required quality level
- Scores available models on cost, speed, and quality
- Selects and returns the optimal model — with an explanation

## How It Works

### 1. Complexity Analyzer
Determines how much "intelligence" a request needs.
- **Keyword-based** (fast, free): flags terms like *analyze, architecture, strategy* (high) vs. *write, explain, summarize* (medium)
- **LLM-based** (optional): a small model classifies intent as `low` / `medium` / `high`

### 2. Intelligent Router
The core decision engine. Each model is scored on quality, cost, latency, provider, and capability tier:

| Model | Provider | Quality | Cost | Speed |
|---|---|---|---|---|
| Llama 8B | Groq | Low | Cheapest | Fast |
| Llama 70B | Groq | Medium | Medium | Fast |
| Gemini Flash | Google | High | Medium | Moderate |
| Gemini Pro | Google | Highest | Expensive | Slower |

Routing logic applies a **quality floor** (no weak model on hard questions) and a **quality ceiling** (no overkill on simple ones), then picks the highest weighted score.

### 3. Multi-Provider Support
- **Groq** — fast, low-cost inference
- **Google Gemini** — structured output, complex reasoning
- Built with a provider abstraction layer for adding OpenAI, Anthropic, Mistral, and local Ollama models

### 4. Cost Tracking
Compares the selected model's cost against always using the largest model:

```
Selected model:  $0.000034
Largest model:   $0.000210
Savings:         83%
```

Goal: **not** the cheapest model — the cheapest model that can do the job.

## Development Journey

| Version | Addition | Outcome |
|---|---|---|
| v1 | Basic router, manual rules, Streamlit demo | Not actually optimizing anything |
| v2 | Cost/latency/quality scoring, rejection reasons | Router became explainable |
| v3 | Complexity bands (low/medium/high) with quality floors & ceilings | Avoids both underpowered and overkill answers |
| v4 | Provider failure handling | Automatic fallback to next suitable model |
| v5 | Cost verification | Checks live availability, usage metadata, token/latency drift |

## Architecture

```
app.py         → Streamlit interface
analyzer.py    → Request complexity detection
router.py      → Model selection engine
models.py      → Model catalogue & cost calculation
providers.py   → API communication
config.py      → Environment & secrets
verify_models.py → Model availability checks
        ↓
   Gemini / Groq
```

## Getting Started

```bash
git clone https://github.com/username/modelmesh.git
cd modelmesh

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file:
```
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
```

Run:
```bash
streamlit run app.py
```

## Project Structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit application interface |
| `analyzer.py` | Request complexity detection |
| `router.py` | Model selection algorithm |
| `models.py` | Model catalogue and cost calculation |
| `providers.py` | Provider API communication |
| `config.py` | Environment and secret management |
| `verify_models.py` | Model availability verification |

## Current Limitations

- **Quality scores are manual estimates** — no automated benchmarking yet
- **No feedback loop** — routing doesn't yet learn from outcomes
- **Limited providers** — only Gemini and Groq today
- **No semantic caching** — repeated questions re-hit the model

## Roadmap

1. **Benchmark-Driven Routing** — replace manual scores with measured accuracy
2. **Learning Router** — incorporate user ratings and automatic weight tuning
3. **Enterprise Features** — team dashboards, usage analytics, budget limits, API gateway
4. **Full AI Infrastructure Layer** — ModelMesh as the traffic controller between apps and all AI providers

## Built With

- Python
- Streamlit
- Google Gemini API
- Groq API

## Security

API keys are loaded from environment variables / Streamlit secrets only — never stored in code. **Never commit `.env` to GitHub.**

---

*ModelMesh doesn't ask "Which is the strongest model?" — it asks "Which model is right for this request?"*