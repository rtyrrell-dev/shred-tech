# SHRED TECH — Guitar Setup Assistant

A professional guitar setup assistant built with Google ADK (Python) + Gemini 2.5 Flash, FastAPI, and React. Covers full mechanical setup workflows, diagnostics, electronics troubleshooting, and string recommendations.

---

## What It Does

SHRED TECH is a conversational AI agent that helps guitarists get their instruments playing perfectly. It covers:

- **Full setup walkthroughs** — step-by-step for Strat/Tele style guitars (Path A: adjustable saddles) and Gibson/Les Paul style guitars (Path B: Tune-O-Matic bridge)
- **Mechanical diagnostics** — fret buzz, tuning instability, intonation issues, dead notes
- **Electronics diagnostics** — hum, crackling, dead signal, noisy pots and switches
- **String recommendations** — gauge suggestions by tuning, scale length, and playing style
- **Experience-adaptive responses** — infers beginner/intermediate/advanced from the first message and adjusts language accordingly

---

## Prerequisites

- Python 3.12
- Node 18 or higher
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com)

---

## Getting a Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with a Google account
2. Click **Get API key** in the left sidebar
3. Click **Create API key** → **Create API key in new project**
4. Copy the key that appears

> **Important:** Use model `gemini-2.5-flash`. Other Gemini model versions (including `gemini-2.0-flash` and `gemini-2.0-flash-lite`) have their free tier disabled and will return quota errors even with a valid key. The model is already set correctly in `agent/agent.py` — don't change it.

> **Note on key format:** Google AI Studio now issues API keys starting with `AQ.` instead of the legacy `AIzaSy...` format. Both formats work — just copy whatever key AI Studio gives you.

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd shred-tech
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and paste your API key:

```
GEMINI_API_KEY="your_key_here"
```

### 3. Set up the Python backend

```bash
# Create a virtual environment
python -m venv .venv

# Activate it
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Set up the React frontend

```bash
cd frontend
npm install
cd ..
```

---

## Running Locally

You need two terminals running simultaneously.

**Terminal 1 — Backend:**

```bash
# From the project root, with venv activated
uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`.
Confirm it's running: `http://localhost:8000/health` should return `{"status":"ok","agent":"shred_tech"}`.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser. The Vite dev server proxies `/api` calls to the backend automatically — no extra configuration needed.

---

## Testing the Agent Directly with `adk web`

Before running the full stack, you can interact with the agent using ADK's built-in dev interface:

```bash
# From the project root, with venv activated
adk web
```

This starts a local UI in your browser. Select **agent** from the agent dropdown (not "api" or "frontend" — those are just folders ADK scanned) and start chatting. This is useful for testing tool calls and iterating on the agent without involving the frontend.

> **Note:** `adk web` discovers agents by looking for a variable named exactly `root_agent`. The agent in `agent/agent.py` exports this variable to satisfy that requirement.

---

## Project Structure

```
shred-tech/
├── agent/
│   ├── agent.py          # ADK LlmAgent definition (root_agent)
│   ├── tools.py          # Four FunctionTools
│   └── knowledge.py      # MusicNomad KISS guide embedded as a string
├── api/
│   └── main.py           # FastAPI wrapper around the ADK runner
├── frontend/
│   ├── src/
│   │   ├── App.tsx        # Chat UI with welcome screen and message bubbles
│   │   ├── main.tsx
│   │   └── index.css      # Dark industrial styles with amber accents
│   ├── index.html
│   ├── vercel.json        # Vercel config for the frontend project
│   ├── vite.config.ts
│   └── package.json
├── .python-version        # Pins Python 3.12 for Vercel deployment
├── requirements.txt
├── vercel.json            # Vercel config for the backend project
├── .env.example
└── README.md
```

---

## How the Agent Works

### Setup paths

The agent routes guitars to one of two setup sequences based on bridge type:

| Path | Bridge types | Step order |
|------|-------------|------------|
| **A** | Strat, Tele, hardtail, non-Floyd trem | Pre-Setup → Truss Rod → **Action → Radius** → Nut → Intonation → Pickup Height |
| **B** | Tune-O-Matic bridge (Gibson, Les Paul, Epiphone) | Pre-Setup → Truss Rod → **Radius → Action** → Nut → Intonation → Pickup Height |

Action and Radius are swapped between paths — this is intentional and matters. Floyd Rose, Bigsby, and acoustic are flagged as special cases.

### Tools

| Tool | Triggered when |
|------|---------------|
| `get_setup_flow(bridge_type)` | User wants a full setup or asks about step order |
| `diagnose_issue(symptom)` | User describes a mechanical problem |
| `diagnose_electrical_issue(symptom)` | User describes an electrical problem |
| `get_string_recommendations(tuning, scale_length, playing_style)` | User asks about strings or gauge |

### Knowledge sources

- **KISS Guide** (embedded in system prompt): Primary reference for mechanical setup specs and step ordering
- **Agent's own knowledge**: Used for electronics, Floyd Rose, acoustic setups, and anything not in the KISS Guide. The agent is instructed to say so when it's drawing on its own knowledge rather than the guide.

---

## Deploying to Vercel

This project uses **two separate Vercel projects** from the same GitHub repo — one for the frontend, one for the backend API. Both live on the same Vercel account.

### Step 1 — Deploy the backend (shred-tech-api)

1. Go to [vercel.com/new](https://vercel.com/new) → import your GitHub repo
2. **Before deploying**, configure Build & Development Settings:
   - **Framework Preset:** `Other`
   - **Root Directory:** *(leave blank)*
   - **Build Command:** *(leave blank)*
   - **Output Directory:** *(leave blank)*
3. Add environment variable: `GEMINI_API_KEY` = your key
4. Name the project `shred-tech-api` → **Deploy**

Vercel auto-detects `api/main.py` as a Python serverless function. Once deployed, verify it's working by visiting `https://shred-tech-api.vercel.app/health` — should return `{"status":"ok","agent":"shred_tech"}`.

### Step 2 — Deploy the frontend (shred-tech)

1. Go to [vercel.com/new](https://vercel.com/new) → import the same GitHub repo again
2. Set **Root Directory** to `frontend`
3. Framework will auto-detect as Vite
4. Add environment variable: `VITE_API_URL` = `https://shred-tech-api.vercel.app`
5. Name the project `shred-tech` → **Deploy**

> **Important:** `VITE_API_URL` is baked in at build time by Vite. If you change it, you must redeploy the frontend for the change to take effect.

### Redeployment

Both projects auto-redeploy when you push to `main`. If you update the backend URL, remember to redeploy the frontend manually after updating the env var.

---

## AgentOps Logging

Every request through the API and eval harness is appended to `logs/agentops.jsonl` (JSONL — one JSON object per line). The file is gitignored and written locally only.

Each record captures:

```json
{
  "timestamp": "2026-06-24T01:41:13Z",
  "session_id": "abc123",
  "invocation_id": "...",
  "user_message": "my strat has a buzz on the low E",
  "agents_involved": ["shred_tech", "TroubleshootingAgent"],
  "transfers": [{"from_agent": "shred_tech", "to_agent": "TroubleshootingAgent"}],
  "tool_calls": [{"agent": "TroubleshootingAgent", "tool": "diagnose_issue", "args": {"symptom": "buzzing"}}],
  "tool_results": [{"tool": "diagnose_issue", "response_summary": "..."}],
  "state_changes": [{"bridge_type": "strat", "symptoms_mentioned": ["buzzing"]}],
  "latency_ms": 1340,
  "final_response_preview": "first 200 chars..."
}
```

Eval runs use `eval-<uuid>` session IDs so they're easy to filter out from production traffic.

### Querying with jq

```bash
# Count turns handled by each specialist
jq -r '.agents_involved[-1]' logs/agentops.jsonl | sort | uniq -c | sort -rn

# List all transfer events (from → to)
jq '[.transfers[]]' logs/agentops.jsonl

# Average latency across all turns (ms)
jq -s '[.[].latency_ms] | add/length' logs/agentops.jsonl

# Average latency by final specialist
jq -s 'group_by(.agents_involved[-1])[] | {agent: .[0].agents_involved[-1], avg_ms: ([.[].latency_ms] | add/length)}' logs/agentops.jsonl

# Find slow turns (latency > 3000ms)
jq 'select(.latency_ms > 3000)' logs/agentops.jsonl

# Show all state changes (bridge_type, guitar_model, symptoms_mentioned)
jq '.state_changes[]' logs/agentops.jsonl

# Separate eval traffic from production traffic
jq 'select(.session_id | startswith("eval-"))' logs/agentops.jsonl
jq 'select(.session_id | startswith("eval-") | not)' logs/agentops.jsonl
```

---

## Evaluation

SHRED TECH ships with a custom LLM-as-a-Judge eval harness built on top of the live agent.

### Running the eval

```bash
# Full suite (18 cases, ~10 min on free tier)
python -m eval.run_eval

# Specific cases only
python -m eval.run_eval --ids setup-02 trouble-elec-01 gear-01

# Custom delay between cases (default 8s — manages free-tier RPM limits)
python -m eval.run_eval --delay 15
```

### What the output looks like

```
SHRED TECH eval harness — 18 case(s), 8s delay between cases

STATUS  ID                     ROUTING                          ACC  TONE  SAFE  REASONING
------------------------------------------------------------------------
[PASS] setup-02              SetupAgent                       | acc=5 tone=4 safety=5 | Accurate step-by-step Strat setup...
[PASS] trouble-mech-01       TroubleshootingAgent             | acc=5 tone=5 safety=5 | Correctly identifies truss rod...
[FAIL] ambiguous-01          SetupAgent != shred_tech         | acc=4 tone=4 safety=5 | Routed without clarifying question

================================================================================
AGGREGATE RESULTS
  Total cases   : 18
  Passed        : 15  (83.3%)
  Routing acc.  : 88.9%
  Avg accuracy  : 4.6/5
  Avg tone      : 4.4/5
  Avg safety    : 4.8/5
```

Full per-case scores and reasoning are saved to `eval/results/scorecard_<timestamp>.json`.

### How it works

The harness runs each test case through the live multi-agent pipeline (`root_agent` → coordinator → specialist) using the same `Runner`/session pattern as the API. Responses are then scored by a separate Gemini call acting as judge, with no shared context between the agent and the judge.

Three scoring dimensions (1–5 each):
- **Accuracy** — technical correctness of the guitar advice
- **Tone** — calibration to the user's experience level, one question at a time
- **Safety** — appropriate warnings before irreversible steps (nut filing, TOM saddle filing)

A case passes if all three dimensions score > 2 AND the correct specialist handled the query.

### Why a custom harness alongside ADK's built-in evaluators

ADK ships with `rubric_based_final_response_quality_v1` and `safety_v1` as built-in evaluators. This custom harness complements them with domain-specific rubrics: guitar accuracy requires lutherie knowledge the generic quality rubric doesn't encode, and the safety dimension specifically flags missing warnings for guitar-destructive steps that `safety_v1` isn't calibrated for. The routing accuracy metric also doesn't exist in the built-in evaluators since it's specific to the multi-agent coordinator/specialist architecture.

> **Note on free-tier quota:** `gemini-2.5-flash` has a 20 RPD daily limit on the free tier. Each eval case uses 2–3 API calls (coordinator + specialist + judge). Run the full 18-case suite on a fresh day, or use `--ids` to run a smaller subset within the daily budget.

---

## Troubleshooting

**`limit: 0` quota error**
The model doesn't have a free tier enabled. Make sure `agent/agent.py` uses `gemini-2.5-flash`. Do not change it to `gemini-2.0-flash-lite` or `gemini-2.0-flash`.

**`API key not valid` error**
The key in `.env` is a placeholder or malformed. Open `.env` and paste the key directly from AI Studio.

**`adk web` doesn't show the shred_tech agent**
Run `adk web` from the project root (the `shred-tech/` directory) with the virtual environment activated. Select **agent** from the dropdown — not "api" or "frontend".

**Frontend shows "Connection error" in production**
Check that `VITE_API_URL` is set correctly in the frontend Vercel project and that the frontend was redeployed after the variable was added. Verify the backend is live at `https://your-api-url/health`.

**Frontend shows "Connection error" locally**
The backend isn't running. Start `uvicorn api.main:app --reload` in a separate terminal first.

**Port conflict**
If port 8000 is in use: `uvicorn api.main:app --reload --port 8001`, then update the proxy target in `frontend/vite.config.ts` to match.
