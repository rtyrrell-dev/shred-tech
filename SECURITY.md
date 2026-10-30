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

There are no accounts and no file uploads. Stored data is limited to short-lived counters in Redis
(per-minute counts keyed by client IP address, random session ids, and one shared counter for the day's
Gemini requests; all expire automatically, within roughly a day), plus per-instance in-memory
conversation state. The agent's tools are
read-only lookup tables. Secrets (the Gemini API key and the Redis token) are read from the
backend's environment; the frontend's only environment variable is the public API URL.

## Threat model

Each row is one thing an attacker might try, what the code does about it, and what can still happen.

| Abuse case | Mitigation | Residual risk |
|---|---|---|
| **Burn the Gemini quota or bill** by scripting many requests | In code: one **shared daily budget of Gemini requests** (`GEMINI_DAILY_QUOTA` x `GEMINI_QUOTA_SAFETY`, 18 by default), charged one unit per real model request before it is sent (see "Daily quota budget"). Also 10 requests/min per IP and 30 messages per session. Per model call: at most 4096 output tokens. Per user turn: at most 4 model calls. A 25 s timeout per request. | One visitor or bot can use the whole shared budget; see "Accepted operational risks". The impact is demo downtime until the reset, not unbounded spend. Spend limits at the API provider are configured outside this repository and are not enforced by this code. |
| **Use the endpoint as a free general-purpose chatbot** | A shared instruction (added to every agent's prompt) tells the model to refuse non-guitar requests. Obvious jailbreak phrases are refused without calling the model. Messages are capped at 2000 characters and sessions at 30 messages. | The model can occasionally be talked into an off-topic answer. A prompt rule is guidance to the model, not a guarantee. The caps limit the damage. |
| **Prompt injection / extracting the system prompt** | User text is declared untrusted in the shared instruction. A regex check refuses common extraction phrases without calling the model. A reply containing system-prompt section headers is replaced before it is returned. | A rephrased request may still coax out part of the prompt. The prompts contain no secrets (only guitar-setup rules and routing instructions), so the impact is low. |
| **Misusing the agent's tools** | Tools are pure functions over built-in tables. A test checks that `agent/tools.py` imports nothing but ADK and calls none of `open`, `exec`, `eval`, `compile`, `__import__`, `input`, `system` or `popen`. | If a tool with side effects is ever added, this needs a fresh review. |
| **Dodging the rate limit** by omitting or rotating the session id | The per-IP burst limit and the shared daily budget do not depend on the session id. Session ids are issued by the server and only honoured if they exist in the store; an unknown id is replaced with a new one. IPv6 addresses are grouped by /64, so rotating addresses inside one network does not help. | Someone with many unrelated IPs (proxies, botnet) is limited per IP only. |
| **Spoofing the client IP** | The IP is read only from `x-real-ip` / `x-vercel-forwarded-for`. Vercel documents these as carrying the client IP and states that it overwrites `X-Forwarded-For` to prevent spoofing. A raw `X-Forwarded-For` is never used. | If the app were deployed behind a different proxy, this assumption must be revisited. |
| **Taking the limiter store down** so protection fails open | The limiter **fails closed**: if Redis is unreachable or not configured, requests receive a friendly 503. Strict behaviour is the default. Relaxing it (in-memory limiter, localhost CORS, ignoring proxy IP headers) needs an explicit `SHRED_LOCAL_DEV=1`, which belongs only in a developer's local `.env`. The code does not guess its environment from platform variables. | The demo is unavailable while Redis is down. This is deliberate: cost protection should not silently turn off. |
| **Oversized or slow requests** | Request body capped at 16 KiB before parsing; message capped at 2000 characters; model call timeout of 25 s. | Platform limits apply on top. |
| **XSS through model output** | The UI renders replies as plain text (no HTML, no markdown). A test fails if `innerHTML`, `dangerouslySetInnerHTML` and similar appear in the frontend source. The frontend's `vercel.json` sets a Content-Security-Policy without `unsafe-inline` or `unsafe-eval`; tests check the configuration. | The CSP is checked as configuration in this repository, not against a live deployment. If markdown rendering is added later it needs a sanitizer. |
| **Leaked secrets** | `.env` and `logs/` are gitignored (tested). A pattern scan of the full git history for common API-key formats found nothing. A gitleaks scan is configured in CI for pushes to `main`, pull requests and weekly. The frontend reads one environment variable, `VITE_API_URL` (a test fails if another `VITE_` variable is used). | A key pasted by hand into a commit message, issue or chat. If a key is ever exposed, rotate it. |
| **Error messages reveal internals** | Server errors return a short generic message; the exception text is not sent to clients. The real error is logged by exception type and provider status code only. `/docs`, `/redoc` and `/openapi.json` are disabled. | Request-validation errors (HTTP 422) describe the rejected field, and may echo the submitted value back to the sender. |
| **Another site calls the API from a visitor's browser** | CORS allows only the project's own frontend origin (plus the Vite dev server in local development), with credentials off. | CORS only constrains browsers. It does nothing against scripts or curl; the rate limits cover that. |
| **Logs exposing what visitors typed** | Application logs are metadata only: message length, a short hash, agent and tool names, state keys, response sizes, latency. User text is logged only when `LOG_USER_TEXT=1` is set, and tool arguments are never logged. `logs/` is gitignored. | With `LOG_USER_TEXT=1`, logs contain user text and should be treated as private. Logs kept by the hosting platform are outside this repository. |
| **Vulnerable dependencies** | Python dependencies are pinned to exact versions. `pip-audit` and `npm audit` run in CI on pushes to `main`, pull requests and weekly. Dependabot is configured for pip, npm and GitHub Actions. | See "Accepted dependency risk". |
| **Bots and scrapers** | A per-IP burst limit and the shared daily budget. | There is no bot challenge (CAPTCHA). Cloudflare Turnstile would be a possible next step. |

## Current limits

| Limit | Value | Where |
|---|---|---|
| Requests per IP | 10 per minute | `guards/ratelimit.py` |
| Gemini requests per day, all visitors combined | `floor(GEMINI_DAILY_QUOTA x GEMINI_QUOTA_SAFETY)`; 18 with the defaults (20 and 0.9) | `guards/quota.py`, `guards/budget.py` |
| Messages per session | 30 (session lasts 24 h) | `guards/ratelimit.py` |
| Request body | 16 KiB | `guards/limits.py` |
| Message length | 2000 characters | `api/main.py` |
| Model call timeout | 25 seconds | `api/main.py` |
| Output tokens per model call | 4096 | `agent/agent.py` |
| Model calls per user turn | 4 | `guards/quota.py` |
| Shared budget resets | midnight Pacific time | `guards/quota.py` |

## Daily quota budget

The binding constraint for the demo is the free-tier daily request quota, not money. All visitors
share **one daily budget measured in Gemini requests**: `floor(GEMINI_DAILY_QUOTA x GEMINI_QUOTA_SAFETY)`,
which is 18 with the defaults (a quota of 20 and a safety fraction of 0.9, because the demo is meant
to run on its own Google project). The arithmetic uses exact fractions, so there is no float rounding.
There is no per-visitor daily limit.

**What costs what.** A chat turn costs exactly the model requests it makes. These were measured by
running the real agents against a scripted model (`tests/test_llm_call_budget.py`):

| Turn | Gemini requests |
|---|---|
| Blocked by the injection pre-check, or rejected by validation | 0 |
| Coordinator answers directly | 1 |
| Coordinator, then a specialist | 2 |
| Coordinator, then a specialist with one tool round | 3 |
| Specialist hands off to a second specialist, with a tool round | 4 (the per-turn cap) |
| A follow-up in the same conversation (the specialist answers directly) | 1 to 2 |

**How it is metered.** A plugin runs before every model request and spends one unit from the shared
counter first. The check and the increment are one atomic step in Redis (a Lua script), so a refused
request never inflates the counter that concurrent requests see, and the number of requests sent to
Google can never exceed the cap. The counter is keyed by the Pacific-time date and expires an hour
after the reset. If the counter is at the cap, the model request is not sent. At the start of a turn
a cheap read refuses it up front when the budget is already spent. If Redis cannot be reached, the
request is refused as well (fail closed).

**When the budget runs out mid-turn** (for example after the coordinator's request but before the
specialist's), the turn ends cleanly with the "budget used up" message and an HTTP 503 with
`Retry-After`. The design reserves nothing up front, so nothing can leak if a function is killed, and
the whole budget is usable. The tradeoff is that a turn can be cut short, and the requests it already
made stay spent.

**What is not charged.** Validation errors and injection pre-check blocks make no Gemini request and
cost 0 units. They still count toward the per-minute burst limit and the per-session message cap,
which protect compute rather than quota. A request that fails at the provider still counts as used,
because we cannot know whether Google counted it. The Gemini client is not configured to retry.

**Reset.** The counters reset at midnight Pacific time, because Google's documentation says daily
request quotas reset then (it does not say how daylight saving is handled, so the counters follow the
wall clock in `America/Los_Angeles`). Time-zone rules come from the pinned `tzdata` package.

**What users see.** When the shared budget is used up (our own counter, or a Gemini error that names
a per-day quota), users see: "SHRED TECH's shared free-tier demo budget is used up for today. It will
be back after the daily reset at midnight Pacific time." Other Gemini rate-limit errors get a neutral
"try again in a minute" message, because they may be per-minute limits that clear on their own.

**Limits of the guarantee.**

- It covers traffic through the API only. The eval harness, the adversarial script and local
  development call Gemini without going through the budget, but they spend the same Google project
  quota. The 10% safety margin is only 2 requests of 20, so running them while the demo is live can
  push the day over Google's quota. Run them when the demo is idle.
- The budget is only as accurate as `GEMINI_DAILY_QUOTA`. Google can change a free-tier quota, so set
  it to the number AI Studio shows for the project.
- Conversation state may reset between requests on the serverless host (see "Known gaps").

## How the rate limiter works

The API runs as short-lived serverless functions. Two requests may be handled by different
instances, and each instance forgets everything when it shuts down, so counting in Python memory
does not work. Counts live in Redis (Upstash), which every instance shares.

Each limit is a fixed time window: the window number is part of the key (for example
`rl:ip:1.2.3.4:min:29481234`), and each request increments it. When the minute rolls over the key
name changes, so the old count stops mattering. Cleanup (`EXPIRE`) is only housekeeping, so a missed
cleanup can never lock anyone out permanently. Tradeoff: a fixed window allows up to twice the limit
across a window boundary. That is acceptable here and much simpler than a sliding window.

## Accepted operational risks

| Risk | Impact | Why it is accepted |
|---|---|---|
| **A single visitor or bot can consume the whole shared daily budget.** The budget is shared by design, with no per-visitor daily limit. The per-minute burst limit (10 requests per IP) only slows this: a bot could spend all 18 requests within a couple of minutes. | **Demo downtime only**, until the Pacific-midnight reset. No spend (the quota is a hard ceiling on a free tier), no data exposure, no effect on anything else. | It is a free demo on a small free-tier quota. Per-visitor limits were considered and dropped in favour of letting the whole budget be used. Because the budget is small, the demo may also be unavailable late in the day. |
| **Unmetered callers.** The eval harness, adversarial script and local development use the same Google project quota without being counted. | They can use up quota the demo expected to have, shortening the demo's day. | They are run by the maintainer, on purpose. Run them while the demo is idle. |
| **Failed requests are counted as used.** | The budget can run out slightly early. | Google's documentation does not say whether failed requests count against the quota, so the safe assumption is that they do. |
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
  multi-turn conversation can therefore lose its context. That is a reliability limitation, not a
  security one.

## Verifying the controls

```bash
pip install -r requirements-dev.txt
python -m pytest                   # offline tests: limits, fail-closed, CORS, headers, log privacy
ruff check .                       # correctness + security lint
python -m eval.adversarial_check   # manual; needs live Gemini quota
```
