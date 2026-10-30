# Security

SHRED TECH is a public demo: anyone on the internet can chat with it, no login. That is the whole
risk. This document explains what could go wrong, what the code does about it, and what is still
left. The controls are meant to be simple enough to explain without any tooling.

## Reporting a vulnerability

Please use GitHub's private reporting: **Security tab -> Report a vulnerability** on this repository.
Do not open a public issue for a security problem.

## What is exposed

| Surface | What it does | Who can call it |
|---|---|---|
| `POST /api/agent` | Sends one chat message through the Gemini-backed agents | Anyone |
| `GET /health` | Returns `{"status": "ok", ...}` | Anyone |
| Frontend (static) | React chat UI | Anyone |

There are no accounts, no database of user data, and no file uploads. The agent's tools are
read-only lookup tables. The only secret is the Gemini API key, which lives in the backend's Vercel
environment and never reaches the browser.

## Threat model

Each row is one thing an attacker might try, what stops it, and what can still happen.

| Abuse case | Mitigation | Residual risk |
|---|---|---|
| **Burn my Gemini quota or bill** by scripting thousands of requests | Layered limits: a Vercel Firewall rate-limit rule (blocks before my code runs), then in code 10 requests/min and 100/day per IP, a **global daily cap** (default 300, env `GLOBAL_DAILY_LIMIT`), 30 messages per session. Per-call cap of 4096 output tokens and at most 10 model calls per turn. A 25 s timeout per request. | A botnet with many IPs can still use up the global cap, which stops the demo for the day (an *availability* problem, not a bill problem). Real spend protection also needs a quota/budget set on the Google side (see checklist). |
| **Use the endpoint as a free general-purpose chatbot** | Every agent is told to refuse non-guitar requests. Obvious jailbreak phrases are refused with no model call. Message length (2000 chars) and per-session message caps bound how much value anyone gets. | The model can occasionally be talked into an off-topic answer. Rules in a prompt are advice to the model, not a guarantee. The caps limit the damage. |
| **Prompt injection / get the system prompt** | User text is declared untrusted data in a shared instruction. A regex check refuses common extraction phrases without calling the model. A reply containing prompt section headers is replaced before it is returned. | A cleverly rephrased request may still coax out part of the prompt. The prompt contains no secrets (only guitar setup rules), so the impact is low. |
| **Make the agent do something harmful via its tools** | Tools are pure functions over built-in tables: no files, network, shell or environment access. A test fails if that changes. | None known. If a write-capable tool is ever added, this needs a fresh review. |
| **Dodge the rate limit** by omitting or rotating the session id | The limiter keys on the client **IP**, not the session id. Session ids are issued by the server and only honoured if they exist in the store. IPv6 addresses are grouped by /64 so rotating addresses inside one network does not help. | Someone with many unrelated IPs (proxies, botnet) is rate-limited per IP only. Vercel's firewall counters are also tracked per region. |
| **Spoof an IP** to evade or poison limits | The IP comes only from `x-real-ip` / `x-vercel-forwarded-for`, which Vercel sets itself and overwrites. A raw `X-Forwarded-For` is never trusted. | Depends on Vercel's header behaviour as documented. |
| **Take the limiter down** so protection fails open | The limiter **fails closed**: if Redis is unreachable or not configured, requests get a friendly 503 instead of passing unmetered. Strict behaviour is the default; relaxing it needs an explicit `SHRED_LOCAL_DEV=1`, which must never be set in Vercel (the code does not try to guess whether it is on Vercel, because Vercel only exposes its `VERCEL` variable when a project setting is on). | The demo is unavailable while Redis is down. Chosen deliberately: cost protection should never silently turn off. |
| **Oversized or slow requests** | Body capped at 16 KiB before parsing; message 2000 chars; model call timeout 25 s. | Platform limits (Vercel) still apply on top. |
| **XSS via model output** | The UI renders replies as plain text (no HTML, no markdown). A test fails if `innerHTML`/`dangerouslySetInnerHTML` appear in the frontend. A strict Content-Security-Policy (no inline script, no `eval`) is a second layer. | If markdown rendering is added later, it needs a sanitizer such as DOMPurify. |
| **Leaked secrets** | `.env` and `logs/` are gitignored. The full git history was scanned for key patterns: nothing found. gitleaks runs in CI on every push. The frontend's only `VITE_` variable is the public API URL. GitHub secret scanning + push protection should be on (checklist). | A key pasted into a commit message or issue by hand. If a key is ever exposed, rotate it. |
| **Error messages reveal internals** | Clients get friendly generic messages; the real exception is logged server-side by type only. `/docs` and `/openapi.json` are disabled. | None known. |
| **Another site calls the API from a visitor's browser** | CORS allows only `https://shred-tech.vercel.app` (and localhost during development), credentials off. | CORS only constrains browsers; it does nothing against scripts or curl. That is what the rate limits are for. |
| **Logs expose what visitors typed** | Logs are metadata only (lengths, a short hash, agent/tool names, latency). Full text is opt-in (`LOG_USER_TEXT=1`) and tool arguments are never logged. Logs are gitignored. | When opted in locally, logs contain user text: treat them as private. |
| **Vulnerable dependencies** | Python deps pinned exactly; `pip-audit`, `npm audit` and Dependabot run in CI/weekly. | See "Accepted dependency risk" below. |
| **Bots and scrapers** | Rate limits and the global cap. | No bot detection (CAPTCHA) yet. Cloudflare Turnstile is a possible next step. |

## Current limits

| Limit | Value | Where |
|---|---|---|
| Requests per IP | 10 per minute, 100 per day | `guards/ratelimit.py` |
| Requests per day, all users | 300 (override with `GLOBAL_DAILY_LIMIT`) | `guards/ratelimit.py` |
| Messages per session | 30 (session lasts 24 h) | `guards/ratelimit.py` |
| Request body | 16 KiB | `guards/limits.py` |
| Message length | 2000 characters | `api/main.py` |
| Model call timeout | 25 seconds | `api/main.py` |
| Output tokens per model call | 4096 | `agent/agent.py` |
| Model calls per user turn | 10 | `agent/runner_utils.py` |

## How the rate limiter works (plain version)

Vercel runs the API as short-lived serverless functions. Two requests may be handled by different
copies, and each copy forgets everything when it shuts down, so counting in Python memory does not
work. Counts live in Upstash Redis instead, which every copy shares.

For each limit we count requests in a fixed time window: the window number is part of the key
(for example `rl:ip:1.2.3.4:min:29481234`), and each request increments it. When the minute rolls
over, the key name changes, so the old count simply stops mattering. Cleanup (`EXPIRE`) is only
housekeeping, so a missed cleanup can never lock anyone out forever. Tradeoff: a fixed window lets
a client send up to twice the limit across a window boundary; that is acceptable here and much
simpler than a sliding window.

## Accepted dependency risk

`google-adk 2.1.0` requires `starlette<1` and `opentelemetry-api<=1.41.1`, so the fixed releases of
those two packages cannot be installed yet. `pip-audit` reports six advisories, which are ignored in
CI after review. None touches code this app runs:

| Advisory | Package | Why it does not apply here |
|---|---|---|
| PYSEC-2026-161, PYSEC-2026-248 | starlette | Concern code that rebuilds `request.url` from the Host header/path. The app never reads `request.url`. |
| PYSEC-2026-249 | starlette | `request.form()` limits on URL-encoded forms. The app accepts JSON only and never parses forms. |
| PYSEC-2026-2280 | starlette | `HTTPEndpoint` method dispatch. The app uses FastAPI function routes. |
| PYSEC-2026-2281 | starlette | Windows `StaticFiles` UNC paths. No static file serving, and Vercel runs Linux. |
| CVE-2026-114603 | opentelemetry-api | Slow regex on an inbound `tracestate` header. The app does not accept or parse trace headers. |

Revisit when `google-adk` raises its caps. Dependabot will propose the upgrade.

## Known gaps and follow-ups

- **vite 5 -> 8 major bump.** `npm audit` still reports `vite`/`esbuild` advisories. Both are build
  and dev-server tooling, not shipped to browsers, and production dependencies audit clean. The
  upgrade is a breaking change, so it is left as a separate task.
- **Regex heuristics are best effort.** They catch common attacks and save quota; they are not a
  security boundary. Run `python -m eval.adversarial_check` on a fresh-quota day to test the model
  side, and read the replies.
- **No bot challenge.** Optional next step: Cloudflare Turnstile.
- **In-memory conversation state.** The ADK session store is per function instance, so conversation
  memory can reset on a cold start. This is a reliability limitation, not a security one.

## Verifying the controls

```bash
pip install -r requirements-dev.txt
python -m pytest              # 100+ offline tests: limits, fail-closed, CORS, headers, log privacy
ruff check .                  # correctness + security lint
python -m eval.adversarial_check   # manual; needs live Gemini quota
```
