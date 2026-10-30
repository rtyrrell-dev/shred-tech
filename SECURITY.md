# Security

SHRED TECH is a public demo: anyone on the internet can chat with it, no login. That is the main
risk. This document describes what the code in this repository does about it and what is left.
It covers the application code only. Settings made outside the repository (hosting, firewall,
provider quotas and billing) are not described here and are not relied on by the code.

## Reporting a vulnerability

Please report security issues privately using GitHub's private vulnerability reporting:
**Security tab -> Report a vulnerability** on this repository. Please do not open a public issue
for a security problem. This is a personal project, so responses are best effort.

## What is exposed

| Surface | What it does | Who can call it |
|---|---|---|
| `POST /api/agent` | Sends one chat message through the Gemini-backed agents | Anyone |
| `GET /health` | Returns `{"status": "ok", ...}` | Anyone |
| Frontend (static) | React chat UI | Anyone |

There are no accounts and no file uploads, and the app uses no database or external store. The only
state is per-instance, in-memory conversation state (see "Sessions"). The agent's tools are read-only
lookup tables. The one secret (the Gemini API key) is read from the backend's environment; the
frontend's only environment variable is the public API URL.

## Threat model

Each row is one thing an attacker might try, what the code does about it, and what can still happen.

| Abuse case | Mitigation | Residual risk |
|---|---|---|
| **Burn the Gemini quota or bill** by scripting many requests | The app does not count or limit requests itself. The Gemini key is on the free tier, whose quota is a hard ceiling: once it is spent Gemini returns 429 and the API turns that into a friendly 503 (see "Free-tier quota"). Per model call: at most 4096 output tokens. Per user turn: at most 4 model calls. A 25 s timeout per request. Rate limiting per client is expected to be handled at the edge, outside this repository; the code does not rely on it and does not verify it. | One visitor or bot can use the whole daily free-tier quota; see "Accepted operational risks". The impact is demo downtime until Google's reset, not spend, as long as the key stays on the free tier. If the key is ever moved to a billed project, this row must be revisited first: nothing in the application limits spend. |
| **Use the endpoint as a free general-purpose chatbot** | A shared instruction (added to every agent's prompt) tells the model to refuse non-guitar requests. Obvious jailbreak phrases are refused without calling the model. Messages are capped at 2000 characters. | The model can occasionally be talked into an off-topic answer. A prompt rule is guidance to the model, not a guarantee. The caps and the free-tier ceiling limit the damage. |
| **Prompt injection / extracting the system prompt** | User text is declared untrusted in the shared instruction. A regex check refuses common extraction phrases without calling the model. A reply containing system-prompt section headers is replaced before it is returned. | A rephrased request may still coax out part of the prompt. The prompts contain no secrets (only guitar-setup rules and routing instructions), so the impact is low. |
| **Misusing the agent's tools** | Tools are pure functions over built-in tables. A test checks that `agent/tools.py` imports nothing but ADK and calls none of `open`, `exec`, `eval`, `compile`, `__import__`, `input`, `system` or `popen`. | If a tool with side effects is ever added, this needs a fresh review. |
| **Guessing or choosing a session id** to join someone else's conversation | Session ids are generated on the server from the `secrets` module (128 random bits) and are honoured only if this instance's session service already holds them. An unknown or lost id is not an error: the client is given a fresh server-issued id in the response and starts a new conversation. A client cannot mint an id of its choosing. | Ids are bearer tokens: anyone who obtains one can continue that conversation on the instance that holds it. |
| **Oversized or slow requests** | Request body capped at 16 KiB before parsing; message capped at 2000 characters; model call timeout of 25 s. | Platform limits apply on top. |
| **XSS through model output** | The UI renders replies as plain text (no HTML, no markdown). A test fails if `innerHTML`, `dangerouslySetInnerHTML` and similar appear in the frontend source. The frontend's `vercel.json` sets a Content-Security-Policy without `unsafe-inline` or `unsafe-eval`; tests check the configuration. | The CSP is checked as configuration in this repository, not against a live deployment. If markdown rendering is added later it needs a sanitizer. |
| **Leaked secrets** | `.env` and `logs/` are gitignored (tested). A pattern scan of the full git history for common API-key formats found nothing. A gitleaks scan is configured in CI for pushes to `main`, pull requests and weekly. The frontend reads one environment variable, `VITE_API_URL` (a test fails if another `VITE_` variable is used). | A key pasted by hand into a commit message, issue or chat. If a key is ever exposed, rotate it. |
| **Error messages reveal internals** | Server errors return a short generic message; the exception text is not sent to clients. The real error is logged by exception type and provider status code only. `/docs`, `/redoc` and `/openapi.json` are disabled. | Request-validation errors (HTTP 422) describe the rejected field, and may echo the submitted value back to the sender. |
| **Another site calls the API from a visitor's browser** | CORS allows only the project's own frontend origin (plus the Vite dev server in local development), with credentials off. | CORS only constrains browsers. It does nothing against scripts or curl; only the free-tier ceiling and any edge limits cover that. |
| **Logs exposing what visitors typed** | Application logs are metadata only: message length, a short hash, agent and tool names, state keys, response sizes, latency. User text is logged only when `LOG_USER_TEXT=1` is set, and tool arguments are never logged. `logs/` is gitignored. | With `LOG_USER_TEXT=1`, logs contain user text and should be treated as private. Logs kept by the hosting platform are outside this repository. |
| **Vulnerable dependencies** | Python dependencies are pinned to exact versions. `pip-audit` and `npm audit` run in CI on pushes to `main`, pull requests and weekly. Dependabot is configured for pip, npm and GitHub Actions. | See "Accepted dependency risk". |
| **Bots and scrapers** | Nothing in the application code; see the first row. | There is no bot challenge (CAPTCHA) and no per-client limit in the code. Cloudflare Turnstile would be a possible next step. |

## Current limits

| Limit | Value | Where |
|---|---|---|
| Request body | 16 KiB | `guards/limits.py` |
| Message length | 2000 characters | `api/main.py` |
| Model call timeout | 25 seconds | `api/main.py` |
| Output tokens per model call | 4096 | `agent/agent.py` |
| Model calls per user turn | 4 | `guards/quota.py` |

There is no per-IP, per-session or daily counter in the application.

## Free-tier quota

The binding constraint for the demo is the free-tier daily request quota, not money. The app does
not meter it. When Gemini refuses a request with a 429, `guards/errors.py` classifies the error and
returns a friendly 503 that never contains the provider's text:

- If the error names a per-day quota, users see: "SHRED TECH's shared free-tier demo budget is used up
  for today. It will be back after the daily reset at midnight Pacific time." The response carries a
  `Retry-After` with the seconds to that reset, because Google documents that daily request quotas
  reset at midnight Pacific time. It does not say how daylight saving is handled, so the code follows
  the wall clock in `America/Los_Angeles`. The time-zone rules come from the pinned `tzdata` package,
  which is kept only for this message.
- Any other 429 (for example a per-minute limit) gets a neutral "try again in a minute" message and
  **no** `Retry-After`, because the app has no source for how long to wait and does not invent one.

**What costs what.** A chat turn costs the model requests it makes. These were measured by running
the real agents against a scripted model (`tests/test_llm_call_budget.py`):

| Turn | Gemini requests |
|---|---|
| Blocked by the injection pre-check, or rejected by validation | 0 |
| Coordinator answers directly | 1 |
| Coordinator, then a specialist | 2 |
| Coordinator, then a specialist with one tool round | 3 |
| Specialist hands off to a second specialist, with a tool round | 4 (the per-turn cap) |
| A follow-up in the same conversation (the specialist answers directly) | 1 to 2 |

The eval harness, the adversarial script and local development spend the same Google project quota,
so run them when the demo is idle.

## Sessions

Session ids are server-issued and bound to ADK's in-memory session service (see the threat model).
The service lives in each serverless instance's memory, so **a session exists on one instance only**.
If the next request is served by another instance, or the instance was recycled, the id is unknown
there and the client silently receives a new id and a fresh conversation. The frontend adopts
whatever id the server returns, so users see no error, only a conversation that has lost its
context. This is a reliability limitation, not a security one.

## Accepted operational risks

| Risk | Impact | Why it is accepted |
|---|---|---|
| **A single visitor or bot can consume the whole daily free-tier quota.** The app has no per-visitor or per-IP limit of its own. | **Demo downtime only**, until Google's reset at midnight Pacific time. No spend while the key is on a free tier, no data exposure, no effect on anything else. | It is a free demo on a small free-tier quota. A shared counter and per-IP limits needed Redis, which was removed because an in-memory limiter is not protection on stateless serverless instances and the quota already caps the damage. The demo may be unavailable late in the day. |
| **Unmetered callers.** The eval harness, adversarial script and local development use the same Google project quota. | They can use up quota the demo expected to have, shortening the demo's day. | They are run by the maintainer, on purpose. Run them while the demo is idle. |
| **No request-rate limit in the code.** Compute per request is bounded (body size, message length, 25 s timeout, 4 model calls), but the number of requests is not. | A flood costs hosting resources at the host's own rates and, once the quota is gone, every chat gets the friendly 503 without calling Gemini. | Rate limiting at the edge is handled outside the application and is not described or relied on here. If the deployment loses it, there is no second line in the code. |
| **Conversation state may reset between requests.** The ADK session store is in memory on each serverless instance. | A follow-up can land on a fresh instance, lose the conversation, and pay for the coordinator again. | It is a reliability limitation, not a security one. A shared session store was considered and left out to keep the demo small. |

## Accepted dependency risk

`google-adk 2.1.0` declares `starlette<1` and `opentelemetry-api<=1.41.1`, so the patched releases
of those two packages cannot be installed alongside it at the moment. `pip-audit` reports six
advisories against the pinned versions. They are ignored in CI after review, because each concerns
a code path this application does not use. This was checked against the pinned versions and
should be re-checked when dependencies change.

| Advisory | Package (fixed in) | What it concerns | Why it does not apply here |
|---|---|---|---|
| PYSEC-2026-161 | starlette (1.0.1) | The request URL is rebuilt from the Host header; the advisory's impact is on code that trusts that URL, for example for authentication. | The app has no authentication and does not read `request.url`. The only framework feature that builds a URL from a request is Starlette's automatic trailing-slash redirect, which is enabled by default and carries no access decision. |
| PYSEC-2026-248 | starlette (1.3.0) | The request path is not validated when `request.url` is rebuilt, so `request.url.hostname` can be attacker-influenced. | Same as above: nothing in the app reads `request.url`. |
| PYSEC-2026-249 | starlette (1.3.1) | `request.form()` ignores its field-count and size limits for URL-encoded bodies. | The API accepts JSON only. No route calls `request.form()` or declares form or file parameters. |
| PYSEC-2026-2280 | starlette (1.1.0) | `HTTPEndpoint` can dispatch non-standard HTTP methods to unintended methods on the class. | The app defines no `HTTPEndpoint` classes, only function routes. |
| PYSEC-2026-2281 | starlette (1.1.0) | `StaticFiles` on Windows can be made to resolve a UNC path. The advisory states POSIX systems are not affected. | The app does not use `StaticFiles`. |
| CVE-2026-114603 | opentelemetry-api (1.45.1) | A very large inbound `tracestate` header is parsed with a slow regular expression when server instrumentation calls `propagate.extract()`. | No OpenTelemetry server instrumentation is installed, and neither the app nor `google-adk 2.1.0` calls `propagate.extract()` (checked by searching the installed package). |

Dependabot will propose upgrades once `google-adk` allows them.

## Known gaps and follow-ups

- **vite 5 to 8.** `npm audit` still reports `vite` and `esbuild` advisories. Both are build and
  dev-server tooling (dev dependencies, not shipped to browsers), and the production dependencies
  audit clean. The upgrade is a breaking change, so it is a separate task.
- **Regex heuristics are best effort.** They catch common attacks and save quota; they are not a
  security boundary. `python -m eval.adversarial_check` exercises the model side and needs live
  Gemini quota; its replies need a human read.
- **No bot challenge.** See above.
- **Conversation state may reset between requests.** The ADK session store is in memory on each
  function instance, and a serverless host can serve the next request from a different instance. A
  multi-turn conversation can therefore lose its context (see "Sessions"). That is a reliability
  limitation, not a security one.

## Verifying the controls

```bash
pip install -r requirements-dev.txt
python -m pytest                   # offline tests: limits, sessions, 429 handling, CORS, headers, log privacy
ruff check .                       # correctness + security lint
python -m eval.adversarial_check   # manual; needs live Gemini quota
```
