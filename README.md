# ModelMesh

Intelligent LLM routing infrastructure that automatically selects the best AI model for each request based on **complexity, cost, latency, and quality requirements**.

> Built for the AI Infrastructure Hackathon, September 2026.

**Live Demo:** _TBD_
**Repository:** _TBD_

---

## The Problem

Modern AI applications usually send every request to the same powerful model.

A simple request like *"Explain what HTML is"* does not require the same model as *"Design a distributed AI inference platform with dynamic routing, fallback handling, and optimization."*

Using one model for everything creates:
- Unnecessary API cost
- Increased latency
- Inefficient resource usage
- Poor utilization of different models' strengths — some are fast and cheap, some reason better, some handle complex architecture or multimodal tasks best

**The real challenge:** *How do we automatically select the right model for every request?*

## What ModelMesh Does

ModelMesh sits between an application and multiple AI providers, replacing "always use the biggest model" with an intelligent decision layer:

```
User Request → Complexity Intelligence → Routing Engine (Cost + Speed + Quality) → Best Available Model → Response
```

For every request, it:
- Analyzes complexity and required intelligence level
- Evaluates available models
- Selects the optimal one and **explains why**
- Measures latency and cost
- Calculates savings vs. always using the largest model

---

## Key Features

### 1. Hybrid Complexity Intelligence

Pure keyword matching misses complex requests phrased in unfamiliar ways (e.g. *"Design a production AI inference gateway with model locality optimization and fault-tolerant routing"* — clearly complex, but with no obvious trigger words).

The hybrid analyzer solves this:

```
User Request
   → Fast rule-based analyzer
      → High confidence?  → YES → Route directly
                          → NO  → Semantic classifier (small LLM) → Final complexity: LOW / MEDIUM / HIGH
```

**Benefits:**
- Simple requests skip the extra classification call (fast, free)
- Complex unseen requests are still understood semantically
- Every decision stays explainable

### 2. Complexity Levels

| Level | Example Prompts | Routed To |
|---|---|---|
| **LOW** | "Explain HTML", "What is Python?", "Define API" | Cheaper, faster models |
| **MEDIUM** | "Write a JWT authentication API", "Create database integration" | Models with stronger reasoning/implementation ability |
| **HIGH** | "Design scalable AI SaaS architecture", "Design multimodal routing with LVLM fallback and latency optimization" | Advanced reasoning models |

### 3. Intelligent Routing Engine

Models are scored on quality capability, cost, latency, complexity requirement, and live availability, then filtered by:

- **Quality Floor** — blocks complex requests from reaching weak/lightweight models
- **Quality Ceiling** — blocks simple requests from reaching expensive premium models

### 4. Reliability & Fallback

A production router can't fail just because one provider does.

```
Selected Model → Failure → Next Suitable Model → Successful Response
```

Tested against invalid API keys, unavailable models, provider errors, and simulated failures.

---

## Model Catalogue

| Tier | Model | Provider | Best For | Cost | Speed |
|---|---|---|---|---|---|
| Fast | Allam 2 7B | Groq | Simple explanations, lightweight tasks | Lowest | Fastest |
| Balanced | Qwen 3.8 27B | Groq | Coding, analysis, general technical tasks | Medium | Fast |
| Reasoning | GPT-OSS 120B | Groq | Architecture, complex reasoning, system design | Higher | Moderate |
| Advanced | Gemini 3.6 Flash | Google | Long context, advanced analysis | Medium | Moderate |
| Premium | Gemini 3.1 Pro Preview | Google | Highest-quality reasoning tasks | Highest | Slower |

## Multi-Provider Architecture

- **Groq** — fast inference, low-cost execution
- **Google Gemini** — advanced reasoning, long-context, complex analysis

A provider abstraction layer allows future support for **OpenAI, Anthropic, Mistral, and local models** without rewriting routing logic.

## Cost Optimization

Every response is measured against the cost of always using the largest model:

```
Selected model:  $0.000034
Largest model:   $0.000210
Savings:         83%
```

This makes the optimization claim measurable, not just asserted.

---

## Development Journey

| Version | Improvement | Result |
|---|---|---|
| v1 | Basic Streamlit router prototype | Initial routing concept |
| v2 | Cost, latency, quality scoring | Routing became explainable |
| v3 | LOW / MEDIUM / HIGH complexity levels | Models matched task difficulty |
| v4 | Provider execution layer | Requests reached real models |
| v5 | Fallback handling | System survived provider failures |
| v6 | Cost tracking and savings calculation | Optimization became measurable |
| v7 | Improved session management | Removed duplicate executions and stale responses |
| v8 | Hybrid complexity analyzer | Better handling of unseen complex requests |

## Challenges Faced

**Model availability changes** — provider model IDs (e.g. `gemini-2.5-flash`, older Groq IDs) became unavailable mid-development.
→ *Solved with a provider abstraction layer, so model ID changes don't touch routing logic.*

**Keyword-only complexity detection** — missed complex requests phrased without obvious trigger words.
→ *Solved with the hybrid rule-based + semantic classifier approach.*

**Streamlit session state bugs** — changing the prompt sometimes left the old response visible.
→ *Solved with prompt-change detection, result clearing, and controlled session state.*

**Router calibration** — early versions over-used expensive models or under-served hard requests.
→ *Solved by tuning complexity scoring, quality requirements, and routing thresholds.*

---

## Architecture

```
app.py            → Streamlit UI
analyzer.py       → Complexity intelligence (hybrid classifier)
router.py         → Model selection logic
models.py         → Model catalogue + cost calculation
providers.py      → Gemini / Groq API calls + fallback handling
config.py         → Secrets management
verify_models.py  → Provider availability testing
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
| `app.py` | Streamlit interface and demo workflow |
| `analyzer.py` | Hybrid complexity analysis |
| `router.py` | Model selection engine |
| `models.py` | Model catalogue and cost calculation |
| `providers.py` | API execution and fallback handling |
| `config.py` | Environment and secret loading |
| `verify_models.py` | Provider availability checks |

---

## Current Limitations

- Model quality scores are manually assigned — no automatic benchmark-based measurement yet
- Routing does not learn from user feedback
- Only Groq and Gemini are currently integrated
- No semantic caching for repeated requests
- Complexity classification depends on current heuristic/classifier quality

## Roadmap

1. **Benchmark-Driven Routing** — replace manual quality scores with accuracy benchmarks, latency measurements, and real-world evaluation data
2. **Learning Router** — use feedback and historical success rates to auto-tune routing decisions
3. **Enterprise AI Gateway** — team dashboards, usage analytics, budget controls, API gateway deployment
4. **More Providers** — OpenAI, Anthropic, Mistral, local inference models

## Built With

Python · Streamlit · Google Gemini API · Groq API · Plotly

---

*ModelMesh doesn't ask "Which is the strongest AI model?" — it asks "Which model is the right choice for this request?"*
