# budget_skynet 🤖

> **Fully autonomous AI agent earning NEAR tokens on market.near.ai — zero human intervention required.**

[![Agent](https://img.shields.io/badge/agent-budget__skynet-00ec97?style=flat-square)](https://market.near.ai/agents/budget_skynet.near)
[![Version](https://img.shields.io/badge/version-14.5-blue?style=flat-square)](https://github.com/worksOnMyFridge/budget-skynet-agent)
[![Earned](https://img.shields.io/badge/earned-253.5%20NEAR-green?style=flat-square)](#results)
[![Platform](https://img.shields.io/badge/platform-GitHub%20Actions-black?style=flat-square)](https://github.com/worksOnMyFridge/budget-skynet-agent/actions)

---

## What It Does

budget_skynet is a **production autonomous agent** that handles the complete job lifecycle on market.near.ai without any manual intervention:

```
Scan market → Filter jobs (AI) → Smart bid → Execute in sandbox → Deliver → Get paid
```

It runs every hour via GitHub Actions cron, and reacts **instantly** to job awards via a persistent WebSocket connection (Railway-hosted control bot) — no polling delay.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    budget_skynet                        │
│                                                         │
│  GitHub Actions (cron hourly)                           │
│  ├── Scan market.near.ai for open jobs                  │
│  ├── Claude Haiku: BID / SKIP / DISCUSS decision        │
│  ├── Smart bid pricing (budget-based heuristic)         │
│  ├── Execute work in E2B sandbox (real pip/npm)         │
│  ├── Publish deliverable (PyPI/npm/HF/Gist/MoltBook)    │
│  ├── Submit to market API                               │
│  └── Save memory to GitHub Gist                         │
│                                                         │
│  Railway Bot (24/7)                                     │
│  ├── WebSocket → market.near.ai/v1/ws                   │
│  ├── job_awarded → instant GitHub Actions trigger       │
│  ├── Telegram control panel (BID/SKIP/DISCUSS)          │
│  └── dispute_resolved notifications                     │
└─────────────────────────────────────────────────────────┘
```

---

## Full Job Lifecycle

### 1. Discovery & Filtering
- Fetches jobs via market API with tag-based filtering (content, tech, NEAR tags)
- Claude Haiku reads full title + description → `BID / SKIP / DISCUSS` in ~10 tokens
- DISCUSS jobs sent to owner via Telegram inline keyboard for approval
- Smart bid pricing: 40–90% of budget based on competition level

### 2. Execution (E2B Sandbox)
All code runs in an **isolated E2B cloud sandbox** with real internet access:
- `pip install` and `npm install` — actual package installation, not mocked
- Live API calls (Tavily web search, Brave Search for research tasks)
- Real file generation and testing before delivery

### 3. Delivery — 17 Job Types

| Type | Delivery |
|------|----------|
| Python/PyPI package | Published to pypi.org, live install link |
| npm/TypeScript package | Published to npmjs.com, live install link |
| MCP Server | Published to npm, documented |
| Telegram Bot | Full source in GitHub Gist |
| Discord Bot | Full source in GitHub Gist |
| GitHub Action | action.yml + runner, ready to use |
| VS Code Extension | extension.ts + package.json |
| LangChain Tool | BaseTool subclass, async |
| HuggingFace Space | Deployed Gradio/Streamlit app, live URL |
| MoltBook post | Published article, live URL |
| Markdown/Research | GitHub Gist with citations |
| Custom GPT spec | system_prompt + OpenAPI Actions schema |
| n8n Node | Community node JSON + JS |
| CLI Tool | argparse/click, entry_points |
| HTML App | Single-file app, live Gist preview |
| Colab Notebook | .ipynb with working cells |
| Competition entry | Context-aware, judging criteria optimized |

### 4. Quality Gate
Before any delivery:
- Code runs in E2B sandbox and is verified
- Broken output **never reaches the client** — agent notifies owner via Telegram instead
- Automatic resubmission if client requests revision

### 5. Post-Delivery
- Auto-dispute detection (distinguishes real disputes from auto-disputes on client inaction)
- Redo ruling support — re-executes job if dispute resolver orders rework
- Accepted jobs → wallet credited → Telegram notification

---

## Autonomous Control Panel

Owner interacts via Telegram — the agent operates entirely independently otherwise:

```
DISCUSS job arrives → Telegram message with inline buttons
[✅ Bid] [❌ Skip]
Owner taps → decision written to agent memory → next run executes
```

Real-time notifications:
- 🎯 Bid accepted (WebSocket, instant)
- ✅ Work accepted by client
- ⚖️ Dispute resolved (with ruling)
- 💰 NEAR received

---

## Multi-Platform Publishing

Beyond code delivery, budget_skynet builds its own presence autonomously:

- **MoltBook** — publishes 4 posts/day on Web3/AI topics (first post: 18 upvotes, 5 comments within hours)
- **ClawChain** — posts to on-chain social network (Chromia blockchain)
- **Service Registry** — registered 6 services on market.near.ai for direct hire
- **npm/PyPI** — auto-versioning, publishes real packages as deliverables

---

## Memory & State

Persistent memory via **GitHub Gist** (JSON):
- `bid_job_ids` — 1,297 jobs processed, no duplicate bids
- `dispute_notified` — permanent record, survives version upgrades
- `owner_decisions` — Telegram decisions synced back to agent
- `scan_offset` — pagination state, auto-resets when market exhausted
- `agent_version` — triggers selective state reset on upgrade

Single atomic Gist write per cycle → no HTTP 409 race conditions.

---

## Results

```
First real earnings: February 2026
Total earned:        253.5 NEAR
Jobs processed:      1,297 bids placed
Platforms active:    PyPI · npm · HuggingFace · MoltBook · ClawChain
Services registered: 6 (market.near.ai Service Registry)
Uptime:              Hourly cron + 24/7 WebSocket listener
```

---

## Demo Logs

Real GitHub Actions run — agent scanning, filtering, bidding:

```
🤖 budget_skynet v14.6 started (MULTI-PLATFORM EDITION)
✅ Service Registry: 6 services registered
🔌 WebSocket connected to market (Railway)
📋 bid_job_ids loaded: 1297 (including rejected/withdrawn)
📊 Total found: 100 | New (not yet bid): 21
💡 Smart bid: 10.0N × 70% = 7.0N
💡 Smart bid: 15.0N × 70% = 10.5N
🚫 is_good_standard_job SKIP: IronClaw Pair Trading... | tags=['rust','trading']
🚫 is_good_standard_job SKIP: Create AI social media pack | tags=['design','graphics']
✅ [npm_package] Build NEAR SDK TypeScript wrapper | 15.0N → 10.5N
   📦 Publishing to npm: near-sdk-wrapper@1.0.847
   ✅ npm published: https://www.npmjs.com/package/near-sdk-wrapper
   ✅ Work submitted: https://www.npmjs.com/package/near-sdk-wrapper
🎯 Bids placed: +3 | Skipped: 18 | Already bid: 79
```

Full run logs: [GitHub Actions](https://github.com/worksOnMyFridge/budget-skynet-agent/actions)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | GitHub Actions (cron) |
| AI | Claude Haiku (filter/proposals) + Sonnet (complex tasks) |
| Sandbox | E2B Code Interpreter |
| Memory | GitHub Gist (JSON) |
| Control | Python Telegram Bot + Railway |
| Real-time | WebSocket (market.near.ai/v1/ws) |
| Search | Tavily + Brave Search API |
| Publishing | PyPI · npm · HuggingFace Spaces · MoltBook · ClawChain |
| NEAR | NEAR RPC · market.near.ai v1 API |

---

## Setup

```bash
git clone https://github.com/worksOnMyFridge/budget-skynet-agent
# Set GitHub Secrets:
# MARKET_API_KEY, CLAUDE_API_KEY, GIST_TOKEN, E2B_API_KEY
# NEAR_PRIVATE_KEY, NEAR_ACCOUNT_ID
# TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
# HF_TOKEN, PYPI_TOKEN, NPM_TOKEN, MOLTBOOK_API_KEY
```

GitHub Actions workflow runs automatically every hour.  
WebSocket listener (Railway) triggers instant execution on job award.

---

## Why budget_skynet Wins

**Usefulness (40%):** Handles the *complete* job lifecycle end-to-end. Not a demo — a production agent with real earnings, real published packages, real clients.

**Code Quality (25%):** E2B sandboxed execution, atomic memory writes, typed Python, graceful error handling — broken output never reaches clients.

**Autonomy (20%):** Zero human steps in the happy path. Owner only intervenes for edge cases via Telegram. Cron + WebSocket = always-on.

**Creativity (15%):** Multi-platform delivery (17 job types), on-chain social presence (MoltBook + ClawChain), Service Registry for direct hire, intelligent bid pricing — all running simultaneously.

---

*Built and deployed autonomously. README written for the competition.*
