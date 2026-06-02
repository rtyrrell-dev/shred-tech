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

- Python 3.11 or higher
- Node 18 or higher
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com)

---

## Getting a Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with a Google account
2. Click **Get API key** in the left sidebar
3. Click **Create API key** → **Create API key in new project**
4. Copy the key that appears

> **Important:** Use model `gemini-2.5-flash`. Some other Gemini model versions (including `gemini-2.0-flash` and `gemini-2.0-flash-lite`) have their free tier disabled and will return quota errors even with a valid key. The model is already set correctly in `agent/agent.py` — just make sure you don't change it.

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
│   ├── vite.config.ts
│   └── package.json
├── requirements.txt
├── vercel.json
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

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### Step 2 — Import to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click **Add New Project** → import your GitHub repo
3. Vercel will detect the `vercel.json` configuration automatically

### Step 3 — Add the environment variable

In your Vercel project: **Settings → Environment Variables**

Add:
```
GEMINI_API_KEY = your_key_here
```

### Step 4 — Deploy

Click **Deploy**. Vercel builds the React frontend as a static site and serves the FastAPI backend as a serverless function. The `vercel.json` routes `/api/*` to the Python backend and everything else to the frontend.

> **Note on the Vercel secret:** `vercel.json` references `@gemini_api_key` for the env var. You can either add the variable directly in the Vercel dashboard (recommended) or create a Vercel secret with that name using the Vercel CLI: `vercel secrets add gemini_api_key your_key_here`.

---

## Troubleshooting

**`limit: 0` quota error**
This means the model you're using doesn't have a free tier. Make sure the model in `agent/agent.py` is set to `gemini-2.5-flash`. Do not change it to `gemini-2.0-flash-lite` or `gemini-2.0-flash`.

**`API key not valid` error**
The key in `.env` is a placeholder or malformed. Open `.env` and paste the key directly from AI Studio.

**`adk web` doesn't show the shred_tech agent**
Make sure you're running `adk web` from the project root (the `shred-tech/` directory) with the virtual environment activated.

**Frontend shows connection error**
The backend isn't running. Start `uvicorn api.main:app --reload` in a separate terminal first.

**Port conflict**
If port 8000 is in use: `uvicorn api.main:app --reload --port 8001`, then update the proxy in `frontend/vite.config.ts` to match.
