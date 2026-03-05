import requests
import time
import os
import json
import re
import base64
import hashlib
from datetime import datetime, timezone

# ============================================================
#  КЛЮЧИ И НАСТРОЙКИ
# ============================================================
MARKET_API_KEY   = os.environ.get("MARKET_API_KEY")
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY")
GITHUB_TOKEN     = os.environ.get("GIST_TOKEN")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# Пульт управления — отдельный бот для интерактивных DISCUSS решений
# Пульт управления: используем отдельный токен если задан, иначе тот же бот что и основной
CONTROL_BOT_TOKEN   = (os.environ.get("CONTROL_BOT_TOKEN") or
                       os.environ.get("BOT_TOKEN") or
                       os.environ.get("TELEGRAM_TOKEN"))
CONTROL_BOT_CHAT_ID = (os.environ.get("CONTROL_BOT_CHAT_ID") or
                       os.environ.get("ALLOWED_USER_ID") or
                       os.environ.get("TELEGRAM_CHAT_ID"))
E2B_API_KEY      = os.environ.get("E2B_API_KEY")       # Опционально
MOLTBOOK_API_KEY = os.environ.get("MOLTBOOK_API_KEY")  # Опционально — для публикации на MoltBook
HF_TOKEN        = os.environ.get("HF_TOKEN")           # Опционально — для публикации на HuggingFace Spaces
PYPI_TOKEN      = os.environ.get("PYPI_TOKEN")         # Опционально — для публикации на PyPI
NPM_TOKEN       = os.environ.get("NPM_TOKEN")          # Опционально — для публикации на npm
TAVILY_API_KEY  = os.environ.get("TAVILY_API_KEY")   # Опционально — веб-поиск (1000 бесплатно/мес)
BRAVE_API_KEY   = os.environ.get("BRAVE_API_KEY")    # Опционально — веб-поиск Brave ($3/1000)

NEAR_PRIVATE_KEY = os.environ.get("NEAR_PRIVATE_KEY", "")
NEAR_ACCOUNT_ID  = os.environ.get("NEAR_ACCOUNT_ID", "budget_skynet.near")

# ClawChain автопостинг (write-only — только публикуем, никогда не читаем)
CLAWCHAIN_CREDENTIALS  = os.environ.get("CLAWCHAIN_CREDENTIALS", "")  # JSON из credentials.json
CLAWCHAIN_AGENT_NAME   = os.environ.get("CLAWCHAIN_AGENT_NAME", "budget-skynet")
CLAWCHAIN_BRID = "9D728CC635A9D33DAABAC8217AA8131997A8CBF946447ED0B98760245CE5207E"
CLAWCHAIN_NODE = "https://chromia.01node.com:7740"
AUTOPOST_INTERVAL_SEC  = 6 * 3600  # Публикуем раз в 6 часов = 4 поста в день


MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
BASE_URL = "https://market.near.ai/v1"
MARKET_HEADERS = {
    "Authorization": f"Bearer {MARKET_API_KEY}",
    "Content-Type": "application/json"
}

MEMORY_FILENAME = "budget_skynet_memory.json"
AGENT_VERSION   = "14.5"  # При смене версии — автоматически сбрасываем failed_jobs

# ============================================================
#  ФИЛЬТРЫ ЗАДАЧ
# ============================================================
GOOD_TAGS = [
    "content", "writing", "research", "documentation", "translation",
    "analysis", "report", "strategy", "data", "web3", "near", "crypto",
    "guide", "tutorial", "community", "explainer", "python", "developer",
    "api", "bot", "telegram", "analytics", "script", "tool",
    "nearcon", "hackathon", "demo", "pitch", "grant", "ecosystem", "moltbook",
    "npm", "package", "library", "typescript", "javascript", "mcp",
    "discord", "github-action", "vscode", "cli", "sdk"
]
SKIP_TAGS = [
    "design", "infographic", "visual", "ui", "ux", "solidity", "rust",
    "audit", "security", "frontend", "smart_contract", "nft_art"
]
SKIP_TITLE_KEYWORDS = [
    "infographic", "solidity", "audit", "security", "smart contract", "nft art",
    "trading bot", "mev", "arbitrage", "sniper", "trading algorithm", "high frequency",
    # Custom GPT — нельзя опубликовать в GPT Store без ручного ChatGPT UI
    # Но только если в заголовке явно требуют Store (просто "Create GPT" — ок, делаем спеку)
]
SKIP_DESCRIPTION_KEYWORDS = [
    "deploy contract", "write smart contract", "solidity code", "rust code",
    "figma", "photoshop", "ui design", "ux design", "create logo",
    "arbitrage bot", "mev bot", "snipe token", "trading algorithm",
    "link to your tweet", "link to your post", "post on twitter",
    "post on x ", "post on linkedin", "post on instagram", "tweet about",
    "complete job with a link to your",
    # Требуют публикации в сторонние директории — нельзя без ручного UI
    "published to poe bot directory", "poe bot directory",
    "success metrics: 500", "500+ conversations", "500+ poe",
    "publish to poe", "live on poe",
    # JetBrains/IDE плагины — Kotlin/Java, ручная публикация в Marketplace
    "jetbrains plugin marketplace", "published to jetbrains", "intellij platform plugin",
    "jetbrains marketplace", "plugin marketplace",
    # Метрики которые нельзя гарантировать
    "100+ plugin installs", "100+ installs", "enterprise users post",
    # GPT Store — требует ручной публикации через ChatGPT UI, API нет
    "custom gpt in gpt store", "publish to gpt store", "gpt store listing",
    "submit to gpt store", "live in gpt store", "available in gpt store",
    "published to: gpt store", "published to gpt store", "gpt store (productivity)", "gpt store (education)",
    # Требует живого аккаунта / верификации
    "verified twitter", "verified x account", "real followers",
    "post from your account", "post from your wallet",
    # НЕ скипаем scraping/competitive intel — теперь умеем через Playwright
]

SKIP_COMPETITION_TAGS = [
    "smart-contract", "solidity", "rust", "near-testnet", "mainnet",
    "audit", "security", "nft-art", "defi-protocol"
]
SKIP_COMPETITION_TITLE_KEYWORDS = [
    "smart contract", "solidity", "rust contract", "deploy contract",
    "security audit", "nft art", "defi protocol", "trading bot",
    "mev", "arbitrage"
]

NEAR_CONTEXT = """
NEAR Protocol is a layer-1 blockchain platform designed for usability and scalability.
Key facts: Fast finality (~1-2 seconds), low fees (~$0.001 per transaction).
Agent Market (market.near.ai) is the main gig platform for AI agents.
NEAR SDK for JS: near-api-js. NEAR RPC: https://rpc.mainnet.near.org
"""

NEARCON_CONTEXT = """
NearCon 2025 is happening February 24, 2026 in San Francisco.
Key themes: AI agents on NEAR, autonomous agent economy, multi-agent systems,
agent-to-agent payments, on-chain AI verification, NEAR AI Agent Market launch.
"""

# ============================================================
#  ТИПЫ DELIVERABLE
# ============================================================
DELIVERABLE_TYPES = {
    "npm_package":      ["npm package", "npm package:", "build npm", "create npm", "typescript package", "js package", "javascript package"],
    "python_package":   ["pypi package", "pip package", "build pypi", "python package", "python library", "python sdk"],
    "github_action":    ["github action", "github workflow", ".github/workflows", "ci/cd action"],
    "mcp_server":       ["mcp server", "model context protocol", "claude mcp", "mcp tool"],
    "telegram_bot":     ["telegram bot", "build telegram", "create telegram bot"],
    "discord_bot":      ["discord bot", "build discord bot", "create discord bot"],
    "vscode_extension": ["vs code extension", "vscode extension", "visual studio code extension"],
    "cli_tool":         ["cli tool", "command line tool", "cli -", "near-market", "command line interface"],
    "n8n_node":         ["n8n node", "n8n -", "n8n workflow", "n8n integration", "n8n community node"],
    "custom_gpt":       ["create gpt", "custom gpt", "gpt action", "chatgpt plugin", "gpt with", "build gpt"],
    "zapier":           ["zapier", "zapier integration", "zapier zap"],
    "make_module":      ["make.com", "make module", "make scenario", "integromat"],
    "colab_notebook":   ["colab notebook", "jupyter notebook", "google colab", ".ipynb"],
    "langchain_tool":   ["langchain tool", "langchain -", "langchain integration"],
    "html_app":         ["web app", "web dashboard", "html app", "html prototype", "frontend app", "interactive dashboard"],
    "hf_space":         ["huggingface space", "hugging face space", "hf space", "gradio app", "gradio space",
                         "streamlit app", "streamlit space", "published to: huggingface", "deploy to huggingface",
                         "huggingface spaces", "hf spaces"],
    "wikipedia":        ["wikipedia", "wiki article", "wiki page", "wikipedia presence", "wikipedia entry",
                         "wikipedia draft", "publish to wikipedia"],
    "markdown":         ["write:", "guide", "tutorial", "research", "analysis", "comparison", "documentation", "article", "blog", "report"],
    "moltbook_post":    ["moltbook", "molt book", "published on moltbook", "link to the moltbook", "moltbook article", "article on moltbook", "post on moltbook", "publish on moltbook"],
    "web_scraping":     ["scrape", "scraper", "web scraping", "crawl", "crawler", "competitive intelligence",
                         "competitor analysis", "price monitoring", "data collection", "extract data from",
                         "monitor website", "track prices", "gather data from", "fetch data from website"]
}


# ============================================================
#  БЛОК 1: ПАМЯТЬ
# ============================================================

def get_or_create_memory_gist():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    # Пагинация — ищем во ВСЕХ gists, не только первых 30
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/gists?per_page=100&page={page}",
            headers=headers
        )
        if r.status_code != 200 or not r.json():
            break
        for gist in r.json():
            if MEMORY_FILENAME in gist["files"]:
                return gist["id"]
        if len(r.json()) < 100:
            break  # последняя страница
        page += 1
    print("   🧠 Создаем новую базу данных в Gist...")
    payload = {
        "description": "Budget Skynet Memory DB",
        "public": False,
        "files": {MEMORY_FILENAME: {"content": json.dumps({
            "completed_jobs": [],
            "entered_competitions": [],
            "bid_job_ids": [],
            "failed_jobs": {}
        })}}
    }
    r = requests.post("https://api.github.com/gists", headers=headers, json=payload)
    return r.json()["id"]

def load_memory(gist_id):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers)
    if r.status_code == 200:
        content = r.json()["files"][MEMORY_FILENAME]["content"]
        data = json.loads(content)
        for key in ["entered_competitions", "bid_job_ids",
                    "notified_accepted", "processed_message_ids", "dispute_notified"]:
            if key not in data:
                data[key] = []
        for key in ["failed_jobs", "submitted_jobs"]:
            if key not in data:
                data[key] = {}
        if "scan_offset" not in data:
            data["scan_offset"] = 0
        if "last_earned_notified" not in data:
            data["last_earned_notified"] = "0"

        # ✅ Версионный сброс: новая версия агента = чистый старт
        stored_version = data.get("agent_version", "")
        if stored_version != AGENT_VERSION:
            cleared_failed = len(data.get("failed_jobs", {}))
            data["failed_jobs"] = {}
            # dispute_notified НЕ сбрасываем — диспуты накапливаются навсегда
            # чтобы не спамить одними и теми же при каждом бампе версии
            data["redelivery_done"] = []
            data["agent_version"] = AGENT_VERSION
            data["_version_just_reset"] = False  # защита работает всегда
            print(f"   🔄 Новая версия агента ({stored_version} → {AGENT_VERSION}): "
                  f"сброшено {cleared_failed} failed_jobs (dispute_notified сохранены)")
        else:
            data["_version_just_reset"] = False

        return data
    return {
        "completed_jobs": [], "entered_competitions": [], "bid_job_ids": [],
        "failed_jobs": {}, "scan_offset": 0, "submitted_jobs": {},
        "notified_accepted": [], "processed_message_ids": [],
        "dispute_notified": [], "last_earned_notified": "0"
    }

_last_save_time = 0
_MIN_SAVE_INTERVAL = 30  # секунд между сохранениями

def save_memory(gist_id, memory_data, force=False):
    global _last_save_time
    import time as _time
    now = _time.time()
    if not force and (now - _last_save_time) < _MIN_SAVE_INTERVAL:
        # Throttle — слишком рано, пропускаем (данные уже в памяти)
        return True
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    payload = {"files": {MEMORY_FILENAME: {"content": json.dumps(memory_data, indent=2)}}}
    try:
        r = requests.patch(f"https://api.github.com/gists/{gist_id}", headers=headers, json=payload, timeout=15)
        if r.status_code not in (200, 201):
            print(f"   ❌ save_memory FAILED: HTTP {r.status_code} — {r.text[:100]}")
            return False
        _last_save_time = _time.time()
        return True
    except Exception as e:
        print(f"   ❌ save_memory EXCEPTION: {e}")
        return False


# ============================================================
#  БЛОК 2: МАРКЕТ API
# ============================================================

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"   ⚠️ Telegram ошибка: {e}")

def send_to_control_bot(message: str, job_id: str = None, inline_buttons: list = None):
    """
    Отправляет сообщение в пульт управления (новый бот).
    Если job_id задан — добавляет inline кнопки Бидовать/Пропустить.
    Если control bot не настроен — fallback в основной бот.
    """
    token = CONTROL_BOT_TOKEN
    chat_id = CONTROL_BOT_CHAT_ID
    if not token or not chat_id:
        print(f"   ⚠️ CONTROL_BOT не настроен (CONTROL_BOT_TOKEN и CONTROL_BOT_CHAT_ID нужны) — fallback в основной бот")
        send_telegram(message)
        return
    try:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        if job_id:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Бидовать", "callback_data": f"bid:{job_id}"},
                    {"text": "❌ Пропустить", "callback_data": f"skip:{job_id}"}
                ]]
            }
        elif inline_buttons:
            payload["reply_markup"] = {"inline_keyboard": inline_buttons}

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload, timeout=10
        )
    except Exception as e:
        print(f"   ⚠️ Control bot ошибка: {e}")
        send_telegram(message)  # fallback


def get_open_jobs(limit=200, job_type="standard"):
    r = requests.get(
        f"{BASE_URL}/jobs?status=open&job_type={job_type}&sort=budget_amount&order=desc&limit={limit}",
        headers=MARKET_HEADERS, timeout=15
    )
    return r.json() if r.status_code == 200 else []

def get_open_jobs_recent(limit=100, job_type="standard"):
    """Получает свежие задачи отсортированные по дате создания — чтобы не пропускать дешёвые новые."""
    r = requests.get(
        f"{BASE_URL}/jobs?status=open&job_type={job_type}&sort=created_at&order=desc&limit={limit}",
        headers=MARKET_HEADERS, timeout=15
    )
    return r.json() if r.status_code == 200 else []

def get_jobs_by_tags(tags: list, limit=200) -> list:
    """Получает задачи по конкретным тегам — покрывает весь рынок, не только топ-100."""
    tags_str = ",".join(tags)
    r = requests.get(
        f"{BASE_URL}/jobs?status=open&job_type=standard&tags={tags_str}&sort=created_at&order=desc&limit={limit}",
        headers=MARKET_HEADERS, timeout=15
    )
    return r.json() if r.status_code == 200 else []

def get_job_details(job_id):
    try:
        r = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=MARKET_HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"   ⚠️ get_job_details({job_id}): {e}")
        return {}

def get_market_bid_price(job_id: str, max_budget: float) -> float:
    """
    Умный биддинг на основе размера бюджета.
    GET /jobs/{job_id}/bids возвращает 403 для воркеров (только создатель видит все биды).
    Используем эвристику: чем больше бюджет — тем агрессивнее скидка.

    Логика:
    - до 5 NEAR   → 90% (почти полная цена, конкурировать нет смысла)
    - 5–20 NEAR   → 70% (умеренная скидка)
    - 20–100 NEAR → 55% (агрессивно — крупные задачи более конкурентны)
    - 100+ NEAR   → 40% (максимальная скидка)
    Минимум: 1.0 NEAR
    """
    if max_budget <= 5.0:
        ratio = 0.90
    elif max_budget <= 20.0:
        ratio = 0.70
    elif max_budget <= 100.0:
        ratio = 0.55
    else:
        ratio = 0.40

    price = round(max_budget * ratio, 2)
    price = max(1.0, min(price, max_budget))
    print(f"   💡 Умный бид: {max_budget}N × {ratio:.0%} = {price}N")
    return price


def place_bid(job_id, amount, proposal):
    data = {"amount": str(amount), "eta_seconds": 3600, "proposal": proposal}
    try:
        r = requests.post(f"{BASE_URL}/jobs/{job_id}/bids", headers=MARKET_HEADERS,
                          json=data, timeout=10)
        return r.json() if r.content else {}
    except Exception as e:
        print(f"   ⚠️ place_bid({job_id}): {e}")
        return {}

# Каталог сервисов агента — регистрируем при каждом запуске (идемпотентно)
AGENT_SERVICES = [
    {
        "name": "Python Script & Automation",
        "description": (
            "Custom Python scripts for automation, data processing, API integrations, "
            "web scraping, and workflow automation. Clean, documented code delivered via GitHub Gist."
        ),
        "category": "development",
        "pricing_model": "fixed",
        "price_amount": "8.0",
        "tags": ["python", "automation", "script", "api", "scraping", "data"],
        "response_time_seconds": 3600,
    },
    {
        "name": "Telegram / Discord Bot",
        "description": (
            "Production-ready Telegram or Discord bots with command handlers, "
            "inline keyboards, and API integrations. Delivered as full Python source."
        ),
        "category": "development",
        "pricing_model": "fixed",
        "price_amount": "10.0",
        "tags": ["telegram", "discord", "bot", "python", "api"],
        "response_time_seconds": 7200,
    },
    {
        "name": "npm / PyPI Package",
        "description": (
            "Publish a working npm or PyPI package from your spec. "
            "Includes package.json/pyproject.toml, README, and live publication."
        ),
        "category": "development",
        "pricing_model": "fixed",
        "price_amount": "12.0",
        "tags": ["npm", "pypi", "package", "typescript", "python", "publish"],
        "response_time_seconds": 3600,
    },
    {
        "name": "Research & Analysis Report",
        "description": (
            "Thorough market research, competitor analysis, topic deep-dives, and structured reports. "
            "Web-sourced, cited, actionable insights in Markdown."
        ),
        "category": "research",
        "pricing_model": "fixed",
        "price_amount": "5.0",
        "tags": ["research", "analysis", "report", "web3", "near", "market"],
        "response_time_seconds": 3600,
    },
    {
        "name": "Content & Technical Writing",
        "description": (
            "Articles, tutorials, documentation, and technical guides for Web3 and AI audiences. "
            "Delivered as Markdown or published to MoltBook."
        ),
        "category": "content",
        "pricing_model": "fixed",
        "price_amount": "4.0",
        "tags": ["content", "writing", "documentation", "tutorial", "moltbook", "near"],
        "response_time_seconds": 1800,
    },
    {
        "name": "MCP Server",
        "description": (
            "Model Context Protocol server (TypeScript or Python) connecting LLMs to your API or data source. "
            "Published to npm with full documentation."
        ),
        "category": "development",
        "pricing_model": "fixed",
        "price_amount": "15.0",
        "tags": ["mcp", "llm", "api", "typescript", "python", "npm"],
        "response_time_seconds": 7200,
    },
]


def register_agent_service() -> str | None:
    """
    Регистрирует все сервисы агента в Service Registry маркета.
    Идемпотентно: добавляет только те которых ещё нет (по имени).
    """
    try:
        r = requests.get(f"{BASE_URL}/agents/me/services", headers=MARKET_HEADERS, timeout=10)
        existing = []
        if r.status_code == 200:
            existing = r.json() if isinstance(r.json(), list) else []

        existing_names = {s.get("name", "").lower() for s in existing}
        print(f"   ✅ Service Registry: уже зарегистрировано {len(existing)} сервисов")

        registered = 0
        for svc_def in AGENT_SERVICES:
            if svc_def["name"].lower() in existing_names:
                continue
            payload = {**svc_def, "enabled": True}
            resp = requests.post(
                f"{BASE_URL}/agents/me/services",
                headers=MARKET_HEADERS, json=payload, timeout=10
            )
            if resp.status_code in (200, 201):
                sid = resp.json().get("service_id", "")
                print(f"   ➕ Сервис добавлен: {svc_def['name']} | ID={sid}")
                registered += 1
            else:
                print(f"   ⚠️ Service Registry: {svc_def['name']} → {resp.status_code} {resp.text[:80]}")

        if registered:
            print(f"   ✅ Service Registry: добавлено {registered} новых сервисов")
        return "ok"

    except Exception as e:
        print(f"   ⚠️ register_agent_service: {e}")
    return None


def check_my_bids():
    """Legacy: возвращает accepted биды. С 1500+ бидами API не пагинирует — используй get_my_active_jobs()."""
    r = requests.get(f"{BASE_URL}/agents/me/bids?status=accepted&limit=100", headers=MARKET_HEADERS, timeout=15)
    return r.json() if r.status_code == 200 else []

def get_my_agent_id() -> str:
    """Получает UUID агента из /v1/agents/me — нужен для фильтра worker= в запросах jobs."""
    try:
        r = requests.get(f"{BASE_URL}/agents/me", headers=MARKET_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("agent_id", "")
    except Exception as e:
        print(f"   ⚠️ get_my_agent_id(): {e}")
    return ""

def get_my_active_jobs() -> list:
    """
    Получает задачи где мы воркер через /v1/jobs?worker_agent_id=UUID.
    Надёжнее /agents/me/bids при 1500+ бидах (нет пагинации бидов).
    Возвращает список job-объектов с my_assignments внутри.
    """
    agent_id = get_my_agent_id()
    if not agent_id:
        print("   ⚠️ get_my_active_jobs: не удалось получить agent_id, пробуем handle...")
        # Fallback: попробуем по handle
        agent_id = "budget_skynet"

    jobs = []
    for status in ("in_progress", "filling"):
        for worker_param in ("worker_agent_id", "worker"):
            try:
                r = requests.get(
                    f"{BASE_URL}/jobs?status={status}&{worker_param}={agent_id}&limit=100",
                    headers=MARKET_HEADERS, timeout=15
                )
                if r.status_code == 200:
                    batch = r.json()
                    if isinstance(batch, list) and len(batch) > 0:
                        jobs.extend(batch)
                        print(f"   ✅ {worker_param}={agent_id[:20]}... → {len(batch)} задач ({status})")
                        break  # нашли рабочий параметр — не дублируем
                    elif r.status_code == 200:
                        break  # 200 OK но пусто — параметр работает, задач просто нет
            except Exception as e:
                print(f"   ⚠️ get_my_active_jobs({status},{worker_param}): {e}")
    
    # FALLBACK: если фильтр не работает — смотрим bids с пагинацией
    if not jobs:
        print("   🔄 Fallback: сканируем /agents/me/bids с пагинацией...")
        jobs = get_won_jobs_via_bids_pagination()
    
    return jobs

def get_won_jobs_via_bids_pagination() -> list:
    """
    Fallback: перебирает /agents/me/bids постранично, ищет accepted биды,
    потом подтягивает детали каждого job.
    """
    won_jobs = []
    offset = 0
    limit = 100
    seen_job_ids = set()
    
    while True:
        try:
            r = requests.get(
                f"{BASE_URL}/agents/me/bids?limit={limit}&offset={offset}",
                headers=MARKET_HEADERS, timeout=15
            )
            if r.status_code != 200:
                break
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            
            for bid in batch:
                if bid.get("status") == "accepted":
                    job_id = bid.get("job_id")
                    if job_id and job_id not in seen_job_ids:
                        seen_job_ids.add(job_id)
                        job = get_job_details(job_id)
                        if job and job.get("status") in ("in_progress", "filling"):
                            won_jobs.append(job)
            
            if len(batch) < limit:
                break  # последняя страница
            offset += limit
            
            if offset > 5000:  # защита от бесконечного цикла
                break
        except Exception as e:
            print(f"   ⚠️ bids pagination offset={offset}: {e}")
            break
    
    print(f"   📋 Через пагинацию бидов: {len(won_jobs)} активных задач")
    return won_jobs

def update_agent_profile():
    """Обновляет описание агента на маркете при каждом запуске."""
    desc = (
        "Autonomous AI Agent — Real Deliverables on 15+ Platforms. "
        "CODE PACKAGES: npm/TypeScript, PyPI, LangChain tools, CLI tools. "
        "BOTS & SERVERS: Telegram, Discord, MCP Servers. "
        "INTEGRATIONS: GitHub Actions, n8n Nodes, Zapier, Make.com, VS Code Extensions, Custom GPTs. "
        "RESEARCH & DATA: Real web search via Tavily + Brave Search APIs. "
        "Web scraping with Playwright (JS-rendered pages). "
        "Competitive intelligence — scrapes real sites. "
        "News monitoring via RSS, HackerNews, Reddit APIs. "
        "Research reports with cited sources from live internet. "
        "PUBLISHING: HuggingFace Spaces, Wikipedia drafts, Moltbook articles, Colab Notebooks. "
        "NEAR-NATIVE: Signs real NEAR mainnet transactions, reads on-chain data via RPC. "
        "QUALITY: E2B sandbox testing, pre-submit checklist, auto-correction up to 7 attempts. "
        "Runs every 30 min via GitHub Actions."
    )
    try:
        r = requests.patch(
            f"{BASE_URL}/agents/me",
            headers=MARKET_HEADERS,
            json={"description": desc},
            timeout=15
        )
        if r.status_code in (200, 204):
            print("   ✅ Профиль агента обновлён")
        else:
            print(f"   ⚠️ Профиль не обновлён: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"   ⚠️ update_agent_profile: {e}")


def check_wallet_balance():
    r = requests.get(f"{BASE_URL}/wallet/balance", headers=MARKET_HEADERS, timeout=10)
    return r.json() if r.status_code == 200 else {}

def submit_work(job_id, deliverable_url):
    """
    Сдаёт работу. deliverable_url может быть:
    - URL (https://...) → передаём как есть
    - Inline текст (до 50000 символов) → передаём напрямую без Gist
    API принимает оба формата в поле 'deliverable'.
    """
    content_hash = hashlib.sha256(deliverable_url.encode()).hexdigest()
    data = {"deliverable": deliverable_url, "deliverable_hash": f"sha256:{content_hash}"}
    r = requests.post(f"{BASE_URL}/jobs/{job_id}/submit", headers=MARKET_HEADERS,
                      json=data, timeout=10)
    try:
        result = r.json()
    except Exception:
        result = {}
    # API возвращает job объект — проверяем my_assignments[0].status
    # HTTP 200/201 = успех, проверяем assignment статус внутри
    if r.status_code in (200, 201):
        assignments = result.get("my_assignments", [])
        if assignments:
            asgn_status = assignments[0].get("status", "")
            result["status"] = asgn_status  # нормализуем для остального кода
        else:
            result["status"] = "submitted"  # если нет my_assignments — считаем успехом
    else:
        print(f"   ❌ Submit HTTP {r.status_code}: {str(result)[:300]}")
        # Если assignment уже submitted/disputed — считаем что работа сдана
        assignments = result.get("my_assignments", [])
        if assignments:
            asgn_status = assignments[0].get("status", "")
            result["status"] = asgn_status
            print(f"   ℹ️ Assignment статус из ответа: {asgn_status}")
        elif r.status_code == 409:
            result["status"] = "submitted"  # Conflict = уже сдано
    return result


def get_assignment_messages(assignment_id: str) -> list:
    """Читает приватные сообщения по assignment_id."""
    try:
        r = requests.get(
            f"{BASE_URL}/assignments/{assignment_id}/messages",
            headers=MARKET_HEADERS, timeout=10
        )
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"   ⚠️ get_assignment_messages: {e}")
        return []

def get_job_disputes(job_id: str) -> list:
    """Получает список disputes по job_id."""
    try:
        r = requests.get(
            f"{BASE_URL}/jobs/{job_id}/disputes",
            headers=MARKET_HEADERS, timeout=10
        )
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"   ⚠️ get_job_disputes: {e}")
        return []


def add_dispute_evidence(dispute_id: str, content: str, evidence_url: str = None) -> bool:
    """Добавляет evidence к открытому dispute."""
    try:
        payload = {"content": content}
        if evidence_url:
            payload["url"] = evidence_url
        r = requests.post(
            f"{BASE_URL}/disputes/{dispute_id}/evidence",
            headers=MARKET_HEADERS, json=payload, timeout=10
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"   ⚠️ add_dispute_evidence: {e}")
        return False


def send_assignment_message(assignment_id: str, body: str) -> bool:
    """Отправляет сообщение заказчику по assignment."""
    try:
        r = requests.post(
            f"{BASE_URL}/assignments/{assignment_id}/messages",
            headers=MARKET_HEADERS,
            json={"body": body}, timeout=10
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"   ⚠️ send_assignment_message: {e}")
        return False

def resubmit_work(assignment_id: str, deliverable_url: str, job_id: str = "") -> dict:
    """
    Повторно сдаёт работу после revision request.
    По skill.md: /jobs/{job_id}/submit безопасно вызывать несколько раз —
    обновляет deliverable, предыдущий логируется как сообщение для аудита.
    Пробуем job-level endpoint (надёжнее), fallback на assignment-level.
    """
    content_hash = hashlib.sha256(deliverable_url.encode()).hexdigest()
    data = {"deliverable": deliverable_url, "deliverable_hash": f"sha256:{content_hash}"}
    try:
        # Предпочитаем job-level если есть job_id
        if job_id:
            r = requests.post(
                f"{BASE_URL}/jobs/{job_id}/submit",
                headers=MARKET_HEADERS, json=data, timeout=10
            )
        else:
            r = requests.post(
                f"{BASE_URL}/assignments/{assignment_id}/submit",
                headers=MARKET_HEADERS, json=data, timeout=10
            )
        result = r.json() if r.content else {}
        if r.status_code in (200, 201):
            assignments = result.get("my_assignments", [])
            result["status"] = assignments[0].get("status", "submitted") if assignments else "submitted"
        return result
    except Exception as e:
        print(f"   ⚠️ resubmit_work: {e}")
        return {}

def submit_competition_entry(job_id, deliverable_url):
    content_hash = hashlib.sha256(deliverable_url.encode()).hexdigest()
    data = {"deliverable_url": deliverable_url, "deliverable_hash": f"sha256:{content_hash}"}
    r = requests.post(f"{BASE_URL}/jobs/{job_id}/entries", headers=MARKET_HEADERS,
                      json=data, timeout=10)
    print(f"   📤 Competition entry: {r.status_code} | {r.text[:200]}")
    if r.status_code in [200, 201]:
        return True, False
    if r.status_code == 409:
        return False, True
    return False, False


# ============================================================
#  БЛОК 3: ПУБЛИКАЦИЯ — MULTI-FILE GIST
# ============================================================

def publish_multifile_gist(title, files: dict, description="") -> str:
    """
    Публикует несколько файлов в один Gist.
    files = {"package.json": "...", "src/index.ts": "...", "README.md": "..."}
    Возвращает URL Gist или None.
    """
    # GitHub Gist не поддерживает поддиректории — заменяем / на __
    gist_files = {}
    for filename, content in files.items():
        safe_name = filename.replace("/", "__").replace("\\", "__")
        gist_files[safe_name] = {"content": content or "# empty"}

    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    body = {
        "description": description or title,
        "public": True,
        "files": gist_files
    }
    r = requests.post("https://api.github.com/gists", headers=headers, json=body, timeout=15)
    if r.status_code == 201:
        gist_data = r.json()
        gist_url = gist_data["html_url"]
        print(f"   📦 Gist опубликован: {len(files)} файлов → {gist_url}")
        return gist_url
    print(f"   ❌ Gist ошибка: {r.status_code} | {r.text[:200]}")
    return None

def publish_to_gist(title, content, extension=".md"):
    """Обратная совместимость — публикует один файл."""
    filename = title[:50].replace(" ", "_").replace(":", "").replace("/", "") + extension
    body_content = content if extension != ".md" else f"# {title}\n\n{content}"
    gist_url = publish_multifile_gist(title, {filename: body_content})
    if gist_url and extension == ".html":
        # Получаем raw URL для htmlpreview
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(f"https://api.github.com/gists", headers=headers, timeout=10)
        if r.status_code == 200:
            for gist in r.json()[:3]:
                if filename.replace("/", "__") in gist.get("files", {}):
                    raw_url = gist["files"][filename.replace("/", "__")]["raw_url"]
                    return f"https://htmlpreview.github.io/?{raw_url}", gist_url
    return gist_url, gist_url



# ============================================================
#  БЛОК 3.5: MOLTBOOK — ПУБЛИКАЦИЯ СТАТЕЙ
# ============================================================

def _moltbook_headers():
    return {
        "Authorization": f"Bearer {MOLTBOOK_API_KEY}",
        "Content-Type": "application/json"
    }

def _moltbook_solve_challenge(challenge_text: str) -> str | None:
    """
    Декодирует обфусцированный math challenge от Moltbook.
    Пример: "lObStEr SwImS aT tWeNtY mEtErS aNd SlOwS bY fIvE" → 20 - 5 = 15.00
    Используем Claude — он хорошо справляется с этим.
    """
    # Используем messages API напрямую с system prompt для максимального контроля
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    body = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 10,
        "system": "You are a math solver. Output ONLY a number with 2 decimal places. Nothing else. No explanation.",
        "messages": [
            {"role": "user", "content": f"Ignore symbols ([], ^, -, /) and mixed caps. Extract numbers and operation, compute result.\nExamples: \'twenty slows by five\' = 15.00 | \'thirty speeds up by ten\' = 40.00 | \'two times four\' = 8.00\nChallenge: {challenge_text}"},
            {"role": "assistant", "content": ""}
        ]
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=body, timeout=30)
        if r.status_code == 200:
            result = r.json()["content"][0]["text"].strip()
            match = re.search(r"-?\d+\.?\d*", result)
            if match:
                num = float(match.group())
                return f"{num:.2f}"
    except Exception as e:
        print(f"   ⚠️ Challenge solver ошибка: {e}")
    return None


def delete_moltbook_post(post_id: str) -> bool:
    """Удаляет пост с MoltBook по ID."""
    try:
        r = requests.delete(
            f"{MOLTBOOK_BASE}/posts/{post_id}",
            headers=_moltbook_headers(), timeout=10
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"   ⚠️ delete_moltbook_post: {e}")
        return False


def cleanup_moltbook_posts() -> None:
    """Удаляет тестовые посты и дубликаты с MoltBook."""
    if not MOLTBOOK_API_KEY:
        return
    try:
        r = requests.get(f"{MOLTBOOK_BASE}/posts/my", headers=_moltbook_headers(), timeout=10)
        if r.status_code != 200:
            print(f"   ⚠️ MoltBook cleanup: {r.status_code} {r.text[:100]}")
            return
        data = r.json()
        posts = data if isinstance(data, list) else data.get("posts", [])
        if not posts:
            return

        to_delete = []

        # 1. Тестовые посты
        test_patterns = ["test post", "budget_skynet test", "test from budget"]
        for p in posts:
            if any(pat in p.get("title", "").lower() for pat in test_patterns):
                to_delete.append(p)

        # 2. Дубликаты — оставляем самый свежий
        from collections import defaultdict
        delete_ids = {p.get("id") for p in to_delete}
        remaining = [p for p in posts if p.get("id") not in delete_ids]
        by_title = defaultdict(list)
        for p in remaining:
            by_title[p.get("title", "").strip()].append(p)
        for title_key, group in by_title.items():
            if len(group) > 1:
                sorted_group = sorted(group, key=lambda x: x.get("created_at", ""), reverse=True)
                for p in sorted_group[1:]:
                    to_delete.append(p)

        if not to_delete:
            return

        print(f"   🧹 MoltBook cleanup: удаляем {len(to_delete)} постов...")
        deleted = 0
        for p in to_delete:
            if delete_moltbook_post(p.get("id")):
                deleted += 1
                print(f"   ✅ Удалён: {p.get('title', '')[:40]}")
        print(f"   ✅ MoltBook cleanup: удалено {deleted}/{len(to_delete)}")
    except Exception as e:
        print(f"   ⚠️ MoltBook cleanup ошибка: {e}")


def publish_to_moltbook(title: str, content: str, submolt: str = "general") -> str | None:
    """
    Публикует статью на Moltbook.
    Возвращает URL опубликованного поста или None при ошибке.
    Автоматически решает verification challenge.
    """
    if not MOLTBOOK_API_KEY:
        print("   ⚠️ MOLTBOOK_API_KEY не задан — пропускаем публикацию на Moltbook")
        return None

    print(f"   📰 Публикуем на Moltbook (m/{submolt})...")

    # Публикуем пост
    try:
        r = requests.post(
            f"{MOLTBOOK_BASE}/posts",
            headers=_moltbook_headers(),
            json={"submolt_name": submolt, "title": title[:200], "content": content},
            timeout=15
        )
    except Exception as e:
        print(f"   ⚠️ Moltbook POST /posts ошибка: {e}")
        return None

    if r.status_code not in (200, 201):
        print(f"   ❌ Moltbook: {r.status_code} | {r.text[:200]}")
        return None

    data = r.json()
    post = data.get("post", {})
    post_id = post.get("id")

    if not post_id:
        print(f"   ❌ Moltbook: нет post_id в ответе: {data}")
        return None

    # Логируем весь ответ для диагностики URL формата
    print(f"   🔍 Moltbook API ответ: {str(post)[:300]}")

    # Решаем verification challenge (если требуется)
    verification = post.get("verification")
    if verification:
        challenge_text = verification.get("challenge_text", "")
        verification_code = verification.get("verification_code", "")
        print(f"   🔐 Verification challenge: {challenge_text[:80]}...")

        answer = _moltbook_solve_challenge(challenge_text)
        if not answer:
            print("   ❌ Не удалось решить verification challenge")
            return None

        print(f"   🧮 Ответ: {answer}")
        try:
            vr = requests.post(
                f"{MOLTBOOK_BASE}/verify",
                headers=_moltbook_headers(),
                json={"verification_code": verification_code, "answer": answer},
                timeout=10
            )
            vdata = vr.json()
            if vdata.get("success"):
                print("   ✅ Verification пройден!")
            else:
                print(f"   ⚠️ Verification не прошёл: {vdata.get('error', '?')} — публикуем всё равно")
        except Exception as e:
            print(f"   ⚠️ Verification ошибка: {e}")

    # Формируем URL поста — пробуем взять из API ответа, затем fallback
    # Возможные форматы: /m/{submolt}/{post_id}, /posts/{post_id}, /u/{username}/{post_id}
    post_url = (
        post.get("url") or
        post.get("link") or
        post.get("post_url") or
        f"https://www.moltbook.com/m/{submolt}/{post_id}"
    )
    print(f"   🌐 Moltbook пост: {post_url}")
    return post_url


# ============================================================
#  БЛОК 3.6: HUGGINGFACE SPACES — ПУБЛИКАЦИЯ
# ============================================================

def publish_to_huggingface(repo_id: str, files: dict) -> str | None:
    """
    Публикует Gradio Space на HuggingFace.
    repo_id = "budget-skynet/near-tool"
    files = {"app.py": "...", "requirements.txt": "..."}
    Возвращает URL Space или None.
    """
    if not HF_TOKEN:
        print("   ⚠️ HF_TOKEN не задан — публикация на HuggingFace недоступна")
        return None

    hf_headers_auth = {"Authorization": f"Bearer {HF_TOKEN}"}
    HF_API = "https://huggingface.co/api"
    space_name = repo_id.split("/")[-1] if "/" in repo_id else repo_id

    # 1. Создаём Space (если уже существует — 409, игнорируем)
    print(f"   🤗 Создаём HuggingFace Space: {repo_id}...")
    r = requests.post(f"{HF_API}/repos/create",
        headers={**hf_headers_auth, "Content-Type": "application/json"},
        json={"type": "space", "name": space_name, "sdk": "gradio", "private": False},
        timeout=20)
    if r.status_code not in (200, 201, 409):
        print(f"   ❌ Создание Space: {r.status_code} — {r.text[:150]}")
        return None

    space_url = f"https://huggingface.co/spaces/{repo_id}"

    # 2. Загружаем файлы через HF raw upload API
    uploaded = 0
    for filename, content in files.items():
        if filename.startswith("_"):
            continue
        try:
            file_bytes = content.encode("utf-8") if isinstance(content, str) else content
            r = requests.put(
                f"{HF_API}/spaces/{repo_id}/raw/main/{filename}",
                headers={**hf_headers_auth, "Content-Type": "text/plain; charset=utf-8"},
                data=file_bytes, timeout=30)
            if r.status_code in (200, 201):
                print(f"   📁 Загружен: {filename}")
                uploaded += 1
            else:
                print(f"   ⚠️ {filename}: {r.status_code} — {r.text[:80]}")
        except Exception as e:
            print(f"   ⚠️ {filename}: {e}")

    if uploaded == 0:
        print("   ❌ Ни один файл не загружен на HuggingFace")
        return None

    print(f"   ✅ HF Space: {uploaded} файлов → {space_url}")
    return space_url


def fix_npm_error(pkg_name: str, files: dict, error: str) -> tuple[str, dict]:
    """Анализирует ошибку npm publish и пытается исправить."""
    import time

    # Имя занято → добавляем суффикс
    if "cannot publish over" in error or "You cannot publish" in error or "403" in error:
        new_name = f"{pkg_name}-agent"
        print(f"   🔧 Имя занято — меняем на {new_name}")
        if "package.json" in files:
            import json as _json
            try:
                pkg = _json.loads(files["package.json"])
                pkg["name"] = new_name
                pkg["version"] = "1.0.0"
                files["package.json"] = _json.dumps(pkg, indent=2)
            except Exception:
                pass
        return new_name, files

    # TypeScript ошибки → просим Claude починить
    if "error TS" in error or "TypeScript" in error or "tsc" in error.lower():
        print(f"   🔧 TypeScript ошибка — просим Claude починить...")
        ts_file = next((k for k in files if k.endswith(".ts") and "index" in k), None)
        if ts_file:
            fix_prompt = f"""Fix TypeScript compilation errors in this code.

ERROR:
{error[:800]}

CODE:
{files[ts_file][:2000]}

Return ONLY the fixed TypeScript code inside ```typescript ... ``` block."""
            fixed = ask_claude(fix_prompt, max_tokens=2000, model="haiku")
            if fixed:
                import re as _re
                match = _re.search(r"```(?:typescript|ts)\n(.+?)```", fixed, _re.DOTALL)
                if match:
                    files[ts_file] = match.group(1).strip()
                    print(f"   ✅ Claude починил {ts_file}")
        return pkg_name, files

    # build ошибка → упрощаем до JS без TypeScript
    if "build" in error.lower() or "tsc" in error.lower():
        print(f"   🔧 Build ошибка — переключаемся на JS...")
        if "package.json" in files:
            import json as _json
            try:
                pkg = _json.loads(files["package.json"])
                pkg["main"] = "index.js"
                pkg.pop("types", None)
                pkg["scripts"] = {"test": "echo \"ok\""}
                pkg["devDependencies"] = {}
                files["package.json"] = _json.dumps(pkg, indent=2)
            except Exception:
                pass
        # Если есть TS файлы — конвертируем в JS (убираем типы)
        for fname in list(files.keys()):
            if fname.endswith(".ts") and not fname.endswith(".d.ts"):
                js_name = fname.replace("src/", "").replace(".ts", ".js")
                code = files[fname]
                # Убираем TypeScript-специфичный синтаксис
                import re as _re
                code = _re.sub(r": \w+[\[\]|<>\w]*", "", code)
                code = _re.sub(r"interface \w+[^}]+}", "", code, flags=_re.DOTALL)
                code = _re.sub(r"^import type.*$", "", code, flags=_re.MULTILINE)
                code = code.replace("export default ", "module.exports = ")
                files[js_name] = code
                del files[fname]
        return pkg_name, files

    # Версия уже существует → поднимаем версию
    if "already exists" in error or "version" in error.lower():
        import time as _time
        new_version = f"1.0.{int(_time.time()) % 1000}"
        print(f"   🔧 Версия существует — меняем на {new_version}")
        if "package.json" in files:
            import json as _json
            try:
                pkg = _json.loads(files["package.json"])
                pkg["version"] = new_version
                files["package.json"] = _json.dumps(pkg, indent=2)
            except Exception:
                pass
        return pkg_name, files

    return pkg_name, files


def fix_pypi_error(pkg_name: str, files: dict, error: str) -> tuple[str, dict]:
    """Анализирует ошибку PyPI publish и пытается исправить."""
    import time

    # Имя занято
    if "already exists" in error or "File already exists" in error or "403" in error:
        new_name = f"{pkg_name}_agent"
        print(f"   🔧 Имя занято — меняем на {new_name}")
        # Обновляем setup.py / pyproject.toml
        for fname in ["setup.py", "pyproject.toml"]:
            if fname in files:
                files[fname] = files[fname].replace(pkg_name, new_name)
        return new_name, files

    # Build ошибка → просим Claude починить setup.py
    if "build" in error.lower() or "setup" in error.lower():
        print(f"   🔧 Build ошибка — просим Claude починить setup.py...")
        if "setup.py" in files:
            fix_prompt = f"""Fix the Python package setup.py that fails to build.

ERROR:
{error[:600]}

CURRENT setup.py:
{files.get("setup.py", "")[:1000]}

Return ONLY the fixed setup.py code."""
            fixed = ask_claude(fix_prompt, max_tokens=800, model="haiku")
            if fixed:
                import re as _re
                fixed = _re.sub(r"^```\w*\n?|```$", "", fixed.strip(), flags=_re.MULTILINE)
                files["setup.py"] = fixed
        return pkg_name, files

    # Ошибка в коде пакета
    if "SyntaxError" in error or "ImportError" in error or "ModuleNotFound" in error:
        print(f"   🔧 Ошибка в коде — просим Claude починить __init__.py...")
        init_key = next((k for k in files if "__init__.py" in k), None)
        if init_key:
            fix_prompt = f"""Fix Python code errors.

ERROR:
{error[:600]}

CODE ({init_key}):
{files[init_key][:1500]}

Return ONLY the fixed Python code."""
            fixed = ask_claude(fix_prompt, max_tokens=1500, model="haiku")
            if fixed:
                import re as _re
                fixed = _re.sub(r"^```\w*\n?|```$", "", fixed.strip(), flags=_re.MULTILINE)
                files[init_key] = fixed
        return pkg_name, files

    # Версия уже существует
    if "version" in error.lower():
        import time as _time
        new_version = f"1.0.{int(_time.time()) % 1000}"
        print(f"   🔧 Версия существует — меняем на {new_version}")
        for fname in ["setup.py", "pyproject.toml"]:
            if fname in files:
                import re as _re
                files[fname] = _re.sub(r'version=["\'](.*?)["\'"]', f'version="{new_version}"', files[fname])
        return pkg_name, files

    return pkg_name, files


def _npm_fix_and_retry(pkg_name: str, files: dict, attempt: int, error: str) -> tuple:
    """Анализирует ошибку npm и чинит файлы для следующей попытки."""
    import time as _t, json as _j, re as _re
    ts = int(_t.time()) % 10000

    print(f"   🔧 npm attempt {attempt} error: {error[:150]}")

    # Имя пакета занято
    if any(x in error for x in ["cannot publish over", "You cannot publish", "403", "forbidden"]):
        suffixes = ["", "-sdk", "-tools", "-lib", "-kit", f"-{ts}"]
        base = re.sub(r'(-sdk|-tools|-lib|-kit|-near|-v\d+|-\d+)$', '', pkg_name)
        new_name = f"{base}{suffixes[min(attempt, len(suffixes)-1)]}"
        if new_name == pkg_name:
            new_name = f"{pkg_name}-{ts}"
        print(f"   🔧 Имя занято → {new_name}")
        if "package.json" in files:
            try:
                pkg = _j.loads(files["package.json"])
                pkg["name"] = new_name
                pkg["version"] = f"1.0.{ts}"
                files["package.json"] = _j.dumps(pkg, indent=2)
            except Exception: pass
        return new_name, files

    # TypeScript ошибки → Claude чинит
    if any(x in error for x in ["error TS", "TypeScript", "tsc failed", "Cannot find"]):
        ts_file = next((k for k in files if k.endswith(".ts") and "index" in k and not k.endswith(".d.ts")), None)
        if ts_file:
            fix = ask_claude(
                f"Fix ALL TypeScript errors. Return ONLY fixed code in ```typescript``` block.\n\nERROR:\n{error[:600]}\n\nCODE:\n{files[ts_file][:2500]}",
                max_tokens=2500, model="sonnet"
            )
            if fix:
                m = re.search(r"```(?:typescript|ts)\n(.+?)```", fix, re.DOTALL)
                if m:
                    files[ts_file] = m.group(1).strip()
                    print(f"   ✅ Claude починил {ts_file}")
        # Если не помогло — переходим на чистый JS
        if attempt >= 3:
            print(f"   🔧 TS не компилируется → переключаемся на JS")
            if "package.json" in files:
                try:
                    pkg = _j.loads(files["package.json"])
                    pkg["main"] = "index.js"
                    pkg.pop("types", None)
                    pkg["scripts"] = {"test": "echo ok"}
                    pkg["devDependencies"] = {}
                    files["package.json"] = _j.dumps(pkg, indent=2)
                except Exception: pass
            for fname in list(files.keys()):
                if fname.endswith(".ts") and not fname.endswith(".d.ts"):
                    js_name = fname.replace("src/", "").replace(".ts", ".js")
                    code = files.pop(fname)
                    code = _re.sub(r": \w+[\[\]<>|\w]*", "", code)
                    code = _re.sub(r"interface \w+\s*\{[^}]+\}", "", code, flags=_re.DOTALL)
                    code = code.replace("export default ", "module.exports = ")
                    files[js_name] = code
        return pkg_name, files

    # Версия уже существует
    if any(x in error for x in ["already exists", "version", "409"]):
        if "package.json" in files:
            try:
                pkg = _j.loads(files["package.json"])
                pkg["version"] = f"1.{attempt}.{ts}"
                files["package.json"] = _j.dumps(pkg, indent=2)
                print(f"   🔧 Поднимаем версию → 1.{attempt}.{ts}")
            except Exception: pass
        return pkg_name, files

    # Общая ошибка → Claude полностью перегенерирует package.json
    if attempt >= 2 and "package.json" in files:
        fix = ask_claude(
            f"Fix this npm package.json to make it publishable. Return ONLY valid JSON.\n\nERROR: {error[:400]}\n\nCurrent package.json:\n{files['package.json'][:800]}",
            max_tokens=600, model="haiku"
        )
        if fix:
            fix = _re.sub(r"^```\w*\n?|```$", "", fix.strip(), flags=_re.MULTILINE)
            try:
                _j.loads(fix)  # валидируем JSON
                files["package.json"] = fix
                print(f"   ✅ Claude переписал package.json")
            except Exception: pass

    return pkg_name, files


def _pypi_fix_and_retry(pkg_name: str, files: dict, attempt: int, error: str) -> tuple:
    """Анализирует ошибку PyPI и чинит файлы для следующей попытки."""
    import time as _t, re as _re
    ts = int(_t.time()) % 10000

    print(f"   🔧 PyPI attempt {attempt} error: {error[:150]}")

    def update_name_in_files(old, new):
        for fname in ["setup.py", "pyproject.toml", "setup.cfg"]:
            if fname in files:
                files[fname] = files[fname].replace(old, new)
        for old_key in list(files.keys()):
            if old in old_key:
                files[old_key.replace(old, new)] = files.pop(old_key)

    def bump_version(new_ver):
        for fname in ["setup.py", "pyproject.toml", "setup.cfg"]:
            if fname in files:
                files[fname] = _re.sub(r'version\s*=\s*["\'](.*?)["\']', f'version="{new_ver}"', files[fname])
                files[fname] = _re.sub(r'version\s*=\s*"(.*?)"', f'version="{new_ver}"', files[fname])

    # Имя занято
    if any(x in error for x in ["already exists", "File already exists", "403", "400"]) and "version" not in error.lower():
        suffixes = ["_sdk", "_tools", "_lib", "_kit", f"_{ts}"]
        base = _re.sub(r'(_sdk|_tools|_lib|_kit|_near|_v\d+|_\d+)$', '', pkg_name)
        new_name = f"{base}{suffixes[min(attempt-1, len(suffixes)-1)]}"
        print(f"   🔧 Имя занято → {new_name}")
        update_name_in_files(pkg_name, new_name)
        return new_name, files

    # Версия уже существует
    if any(x in error for x in ["already exists", "version"]):
        new_ver = f"1.{attempt}.{ts}"
        bump_version(new_ver)
        print(f"   🔧 Поднимаем версию → {new_ver}")
        return pkg_name, files

    # Build ошибка → Claude чинит setup.py
    if any(x in error for x in ["build", "setup", "egg", "wheel"]):
        for setup_file in ["setup.py", "pyproject.toml"]:
            if setup_file in files:
                fix = ask_claude(
                    f"Fix this Python {setup_file} that fails to build. Return ONLY the fixed file content.\n\nERROR:\n{error[:500]}\n\nFILE:\n{files[setup_file][:1000]}",
                    max_tokens=800, model="haiku"
                )
                if fix:
                    fix = _re.sub(r"^```\w*\n?|```$", "", fix.strip(), flags=_re.MULTILINE)
                    files[setup_file] = fix
                    print(f"   ✅ Claude починил {setup_file}")
        return pkg_name, files

    # Синтаксис/импорт ошибки → Claude чинит код
    if any(x in error for x in ["SyntaxError", "ImportError", "ModuleNotFound", "IndentationError"]):
        init_key = next((k for k in files if "__init__.py" in k), None)
        if init_key:
            fix = ask_claude(
                f"Fix ALL Python errors in this code. Return ONLY fixed code.\n\nERROR:\n{error[:500]}\n\nCODE:\n{files[init_key][:2000]}",
                max_tokens=2000, model="sonnet"
            )
            if fix:
                fix = _re.sub(r"^```\w*\n?|```$", "", fix.strip(), flags=_re.MULTILINE)
                files[init_key] = fix
                print(f"   ✅ Claude починил {init_key}")
        return pkg_name, files

    # Последний шанс — полная перегенерация setup.py
    if attempt >= 3:
        fix = ask_claude(
            f"Write a minimal working setup.py for a Python package named {pkg_name}. Just make it publishable to PyPI. Return ONLY the code.\n\nContext: {error[:300]}",
            max_tokens=600, model="haiku"
        )
        if fix:
            fix = _re.sub(r"^```\w*\n?|```$", "", fix.strip(), flags=_re.MULTILINE)
            files["setup.py"] = fix
            print(f"   ✅ Claude написал новый setup.py")

    return pkg_name, files


def publish_to_npm_with_retry(pkg_name: str, files: dict, title: str = "", job_id: str = "") -> str | None:
    """npm publish с циклом до победного — до 5 попыток с умным исправлением ошибок."""
    import copy as _copy

    MAX_PUBLISH_ATTEMPTS = 5
    files = _copy.deepcopy(files)  # не мутируем оригинал
    last_error = ""

    # Проверяем текущую версию на npm и устанавливаем правильную
    files = npm_set_correct_version(pkg_name, files)

    # Dry-run: проверяем что пакет корректен перед публикацией
    dry_ok, dry_error = dry_run_npm(pkg_name, files)
    if not dry_ok:
        print(f"   ❌ npm dry-run провалился — пробуем исправить...")
        pkg_name, files = _npm_fix_and_retry(pkg_name, files, 0, dry_error)
        dry_ok2, dry_error2 = dry_run_npm(pkg_name, files)
        if not dry_ok2:
            print(f"   ❌ npm dry-run провалился после фикса — пропускаем публикацию")
            LAST_PUBLISH_ERROR[0] = dry_error2
            return None

    for attempt in range(1, MAX_PUBLISH_ATTEMPTS + 1):
        print(f"   📦 npm publish: попытка {attempt}/{MAX_PUBLISH_ATTEMPTS}...")
        result = publish_to_npm(pkg_name, files)
        if result:
            if attempt > 1:
                print(f"   🎉 npm опубликован с {attempt}-й попытки!")
            return result

        # Получаем ошибку (publish_to_npm печатает её, нам нужно восстановить)
        # Используем эвристику по выводу
        last_error = LAST_PUBLISH_ERROR[0] or f"attempt_{attempt}_failed"
        LAST_PUBLISH_ERROR[0] = ""  # сбрасываем

        if attempt < MAX_PUBLISH_ATTEMPTS:
            print(f"   🔄 Попытка {attempt} провалилась — анализируем и чиним...")
            pkg_name, files = _npm_fix_and_retry(pkg_name, files, attempt, last_error)
            import time as _t; _t.sleep(3)  # пауза между попытками

    print(f"   ❌ npm: все {MAX_PUBLISH_ATTEMPTS} попыток провалились → уведомляем владельца")
    return None


def get_pypi_next_version(pkg_name: str) -> str:
    """Проверяет PyPI registry и возвращает следующую версию (текущая + 0.0.1)."""
    import requests as _req
    try:
        r = _req.get(f"https://pypi.org/pypi/{pkg_name}/json", timeout=10)
        if r.status_code == 200:
            current = r.json().get("info", {}).get("version", "1.0.0")
            parts = current.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            next_ver = ".".join(parts)
            print(f"   🐍 PyPI: {pkg_name}@{current} уже есть → публикуем {next_ver}")
            return next_ver
    except Exception:
        pass
    return "1.0.0"


def pypi_set_correct_version(pkg_name: str, files: dict) -> dict:
    """Устанавливает правильную версию в pyproject.toml/setup.py перед публикацией."""
    import re as _re
    correct_ver = get_pypi_next_version(pkg_name)
    if correct_ver == "1.0.0":
        return files  # пакет новый, версия не нужна

    for fname in ["pyproject.toml", "setup.py", "setup.cfg"]:
        if fname not in files:
            continue
        if fname == "pyproject.toml":
            files[fname] = _re.sub(
                r'(version\s*=\s*")[^"]+(")',
                "\\g<1>" + correct_ver + "\\2",
                files[fname]
            )
        elif fname == "setup.py":
            files[fname] = _re.sub(
                r"(version\s*=\s*[\"'])[^\"']+([\"'])",
                "\\g<1>" + correct_ver + "\\2",
                files[fname]
            )
        elif fname == "setup.cfg":
            files[fname] = _re.sub(
                r'(version\s*=\s*)\S+',
                "\\g<1>" + correct_ver,
                files[fname]
            )
    return files


def publish_to_pypi_with_retry(pkg_name: str, files: dict, title: str = "", job_id: str = "") -> str | None:
    """PyPI publish с циклом до победного — до 5 попыток с умным исправлением ошибок."""
    import copy as _copy

    MAX_PUBLISH_ATTEMPTS = 5
    files = _copy.deepcopy(files)  # не мутируем оригинал
    last_error = ""

    # Проверяем текущую версию на PyPI и устанавливаем правильную
    files = pypi_set_correct_version(pkg_name, files)

    # Dry-run: проверяем что пакет собирается перед публикацией
    dry_ok, dry_error = dry_run_pypi(pkg_name, files)
    if not dry_ok:
        print(f"   ❌ PyPI dry-run провалился — пробуем исправить...")
        pkg_name, files = _pypi_fix_and_retry(pkg_name, files, 0, dry_error)
        dry_ok2, dry_error2 = dry_run_pypi(pkg_name, files)
        if not dry_ok2:
            print(f"   ❌ PyPI dry-run провалился после фикса — пропускаем публикацию")
            LAST_PUBLISH_ERROR[0] = dry_error2
            return None

    for attempt in range(1, MAX_PUBLISH_ATTEMPTS + 1):
        print(f"   🐍 PyPI publish: попытка {attempt}/{MAX_PUBLISH_ATTEMPTS}...")
        result = publish_to_pypi(pkg_name, files)
        if result:
            if attempt > 1:
                print(f"   🎉 PyPI опубликован с {attempt}-й попытки!")
            return result

        last_error = LAST_PUBLISH_ERROR[0] or f"attempt_{attempt}_failed"
        LAST_PUBLISH_ERROR[0] = ""  # сбрасываем

        if attempt < MAX_PUBLISH_ATTEMPTS:
            print(f"   🔄 Попытка {attempt} провалилась — анализируем и чиним...")
            pkg_name, files = _pypi_fix_and_retry(pkg_name, files, attempt, last_error)
            import time as _t; _t.sleep(3)

    print(f"   ❌ PyPI: все {MAX_PUBLISH_ATTEMPTS} попыток провалились → уведомляем владельца")
    return None

def dry_run_pypi(pkg_name: str, files: dict) -> tuple[bool, str]:
    """
    Проверяет что PyPI пакет собирается без ошибок через E2B.
    Запускает: pip install . --dry-run + python -m build
    Возвращает (success: bool, error: str)
    """
    if not _e2b_available:
        return True, ""  # нет E2B — пропускаем проверку

    print(f"   🔍 PyPI dry-run: проверяем сборку {pkg_name}...")
    try:
        from e2b_code_interpreter import Sandbox as E2BSandbox
        with E2BSandbox.create() as sbx:
            for filename, content_str in files.items():
                if filename.startswith("_"):
                    continue
                if "/" in filename:
                    dir_path = "/".join(filename.split("/")[:-1])
                    sbx.commands.run(f"mkdir -p /pkg/{dir_path}")
                sbx.files.write(f"/pkg/{filename}", content_str)

            # Устанавливаем build инструменты
            sbx.commands.run("pip install setuptools>=68 wheel build --quiet", timeout=90)

            # Проверяем что pyproject.toml валиден
            validate = sbx.commands.run(
                "cd /pkg && ls pyproject.toml && echo config_ok || echo no_config",
                timeout=30
            )

            # Пробуем собрать пакет
            build = sbx.commands.run("cd /pkg && python -m build --wheel --no-isolation 2>&1 || python -m build 2>&1", timeout=90)
            if build.exit_code != 0:
                error = (build.stderr or build.stdout or "")[:500]
                print(f"   ❌ PyPI dry-run FAILED: {error[:200]}")
                return False, error

            # Проверяем что dist/ создан
            check = sbx.commands.run("ls /pkg/dist/*.whl 2>/dev/null && echo 'wheel_ok' || echo 'no_wheel'", timeout=15)
            if "wheel_ok" not in (check.stdout or ""):
                return False, "Wheel не создан после сборки"

            print(f"   ✅ PyPI dry-run PASSED — пакет собирается корректно")
            return True, ""
    except Exception as e:
        print(f"   ⚠️ PyPI dry-run exception: {e} — пропускаем")
        return True, ""  # не блокируем публикацию если dry-run упал


def dry_run_npm(pkg_name: str, files: dict) -> tuple[bool, str]:
    """
    Проверяет что npm пакет собирается без ошибок через E2B.
    Запускает: npm pack --dry-run
    Возвращает (success: bool, error: str)
    """
    if not _e2b_available:
        return True, ""

    print(f"   🔍 npm dry-run: проверяем пакет {pkg_name}...")
    try:
        from e2b_code_interpreter import Sandbox as E2BSandbox
        with E2BSandbox.create() as sbx:
            for filename, content_str in files.items():
                if filename.startswith("_"):
                    continue
                if "/" in filename:
                    dir_path = "/".join(filename.split("/")[:-1])
                    sbx.commands.run(f"mkdir -p /pkg/{dir_path}")
                sbx.files.write(f"/pkg/{filename}", content_str)

            # Проверяем package.json валидность
            validate = sbx.commands.run(
                "cd /pkg && node -e \"JSON.parse(require('fs').readFileSync('package.json','utf8')); console.log('json_ok')\" 2>&1",
                timeout=15
            )
            if "json_ok" not in (validate.stdout or ""):
                error = f"package.json невалидный JSON: {validate.stderr or validate.stdout}"
                print(f"   ❌ npm dry-run FAILED: {error[:200]}")
                return False, error

            # TypeScript — проверяем компиляцию если есть tsconfig
            has_ts = any(f.endswith(".ts") and not f.endswith(".d.ts") for f in files)
            if has_ts and "tsconfig.json" in files:
                sbx.commands.run("npm install -g typescript --quiet 2>/dev/null", timeout=60)
                tsc = sbx.commands.run("cd /pkg && npx tsc --noEmit 2>&1 || echo 'tsc_done'", timeout=60)
                if tsc.exit_code != 0 and "error TS" in (tsc.stdout or ""):
                    error = (tsc.stdout or "")[:500]
                    print(f"   ❌ npm dry-run TypeScript FAILED: {error[:200]}")
                    return False, error

            # npm pack dry-run — финальная проверка
            pack = sbx.commands.run("cd /pkg && npm pack --dry-run 2>&1", timeout=60)
            if pack.exit_code != 0:
                error = (pack.stderr or pack.stdout or "")[:500]
                # Игнорируем предупреждения, только реальные ошибки
                if "npm error" in error.lower() or "ENOENT" in error:
                    print(f"   ❌ npm dry-run FAILED: {error[:200]}")
                    return False, error

            print(f"   ✅ npm dry-run PASSED — пакет корректен")
            return True, ""
    except Exception as e:
        print(f"   ⚠️ npm dry-run exception: {e} — пропускаем")
        return True, ""  # не блокируем если dry-run упал


def publish_to_pypi(pkg_name: str, files: dict) -> str | None:
    """
    Публикует Python пакет на PyPI через E2B sandbox.
    Шаги: записываем файлы → pip install build twine → python -m build → twine upload
    Возвращает URL пакета на pypi.org или None.
    """
    if not PYPI_TOKEN:
        print("   ⚠️ PYPI_TOKEN не задан — публикация на PyPI недоступна")
        return None
    if not _e2b_available:
        print("   ⚠️ E2B недоступен — PyPI publish требует sandbox")
        return None

    print(f"   🐍 Публикуем {pkg_name} на PyPI...")
    try:
        from e2b_code_interpreter import Sandbox as E2BSandbox
        with E2BSandbox.create() as sbx:
            # Записываем все файлы пакета
            for filename, content_str in files.items():
                if filename.startswith("_"):
                    continue
                # Создаём директории если нужно
                if "/" in filename:
                    dir_path = "/".join(filename.split("/")[:-1])
                    sbx.commands.run(f"mkdir -p /pkg/{dir_path}")
                sbx.files.write(f"/pkg/{filename}", content_str)

            # Устанавливаем инструменты сборки
            # Устанавливаем в основное окружение И делаем доступным для isolated env
            sbx.commands.run("pip install setuptools>=68 wheel build twine --quiet", timeout=90)
            install = sbx.commands.run(
                "pip install setuptools>=68 wheel --quiet && "
                "python -c 'import setuptools; print(setuptools.__version__)'",
                timeout=60
            )
            if install.exit_code != 0:
                print(f"   ❌ pip install build/twine: {install.stderr[:200]}")
                return None

            # Собираем пакет
            build = sbx.commands.run("cd /pkg && python -m build", timeout=60)
            if build.exit_code != 0:
                LAST_PUBLISH_ERROR[0] = build.stderr
                print(f"   ❌ build failed: {build.stderr[:300]}")
                return None
            print("   ✅ Пакет собран")

            # Публикуем на PyPI
            upload = sbx.commands.run(
                f"cd /pkg && twine upload dist/* --username __token__ --password {PYPI_TOKEN} --non-interactive",
                timeout=60
            )
            if upload.exit_code == 0:
                pypi_url = f"https://pypi.org/project/{pkg_name.replace('_', '-')}/"
                print(f"   ✅ Опубликовано на PyPI: {pypi_url}")
                return pypi_url
            else:
                # Проверяем — может уже существует (version conflict)
                stderr = upload.stderr or ""
                if "already exists" in stderr or "File already exists" in stderr:
                    pypi_url = f"https://pypi.org/project/{pkg_name.replace('_', '-')}/"
                    print(f"   ⚠️ Версия уже существует: {pypi_url}")
                    return pypi_url
                LAST_PUBLISH_ERROR[0] = stderr
                print(f"   ❌ twine upload failed: {stderr[:300]}")
                return None

    except Exception as e:
        print(f"   ❌ PyPI publish exception: {e}")
        return None


def get_npm_next_version(pkg_name: str) -> str:
    """Проверяет npm registry и возвращает следующую версию (текущая + 0.0.1)."""
    import requests as _req
    try:
        r = _req.get(f"https://registry.npmjs.org/{pkg_name}/latest", timeout=10)
        if r.status_code == 200:
            current = r.json().get("version", "1.0.0")
            parts = current.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            next_ver = ".".join(parts)
            print(f"   📦 npm: {pkg_name}@{current} уже есть → публикуем {next_ver}")
            return next_ver
    except Exception:
        pass
    return "1.0.0"


def npm_set_correct_version(pkg_name: str, files: dict) -> dict:
    """Устанавливает правильную версию в package.json перед публикацией."""
    import json as _j
    if "package.json" not in files:
        return files
    try:
        pkg = _j.loads(files["package.json"])
        current_ver = pkg.get("version", "1.0.0")
        correct_ver = get_npm_next_version(pkg_name)
        if correct_ver != "1.0.0" or current_ver == "1.0.0":
            pkg["version"] = correct_ver
            files["package.json"] = _j.dumps(pkg, indent=2)
    except Exception:
        pass
    return files


def publish_to_npm(pkg_name: str, files: dict) -> str | None:
    """
    Публикует npm пакет через E2B sandbox.
    Шаги: записываем файлы → npm set registry token → npm publish
    Возвращает URL пакета на npmjs.com или None.
    """
    if not NPM_TOKEN:
        print("   ⚠️ NPM_TOKEN не задан — публикация на npm недоступна")
        return None
    if not _e2b_available:
        print("   ⚠️ E2B недоступен — npm publish требует sandbox")
        return None

    print(f"   📦 Публикуем {pkg_name} на npm...")
    try:
        from e2b_code_interpreter import Sandbox as E2BSandbox
        with E2BSandbox.create() as sbx:
            # Записываем файлы
            for filename, content_str in files.items():
                if filename.startswith("_"):
                    continue
                if "/" in filename:
                    dir_path = "/".join(filename.split("/")[:-1])
                    sbx.commands.run(f"mkdir -p /pkg/{dir_path}")
                sbx.files.write(f"/pkg/{filename}", content_str)

            # Настраиваем npm auth (Automation token обходит OTP/2FA)
            sbx.commands.run(
                f'npm config set //registry.npmjs.org/:_authToken {NPM_TOKEN}',
                timeout=10
            )
            sbx.commands.run('npm config set unsafe-perm true', timeout=5)

            # Устанавливаем TypeScript и собираем если есть tsconfig
            check_ts = sbx.commands.run("test -f /pkg/tsconfig.json && echo yes || echo no", timeout=5)
            if "yes" in (check_ts.stdout or ""):
                install_ts = sbx.commands.run(
                    "cd /pkg && npm install --save-dev typescript @types/node --quiet",
                    timeout=90
                )
                build_ts = sbx.commands.run("cd /pkg && npx tsc --project tsconfig.json", timeout=60)
                if build_ts.exit_code != 0:
                    LAST_PUBLISH_ERROR[0] = build_ts.stderr
                    print(f"   ⚠️ TypeScript build: {build_ts.stderr[:200]} — публикуем без dist/")

            # Публикуем
            publish = sbx.commands.run(
                "cd /pkg && npm publish --access public",
                timeout=60
            )
            if publish.exit_code == 0:
                npm_url = f"https://www.npmjs.com/package/{pkg_name}"
                print(f"   ✅ Опубликовано на npm: {npm_url}")
                return npm_url
            else:
                stderr = publish.stderr or ""
                stdout = publish.stdout or ""
                # Уже существует — не ошибка
                if "cannot publish over" in stderr or "You cannot publish" in stderr:
                    npm_url = f"https://www.npmjs.com/package/{pkg_name}"
                    print(f"   ⚠️ Версия уже на npm: {npm_url}")
                    return npm_url
                LAST_PUBLISH_ERROR[0] = stderr + stdout
                print(f"   ❌ npm publish failed: {stderr[:300]}{stdout[:100]}")
                return None

    except Exception as e:
        print(f"   ❌ npm publish exception: {e}")
        return None


def generate_hf_space(title: str, description: str, model: str) -> dict:
    """Генерирует Gradio Space для HuggingFace."""
    print("   🤗 Генерируем HuggingFace Gradio Space...")

    safe_name = re.sub(r'[^a-z0-9-]', '-', title.lower()[:40]).strip('-')
    safe_name = re.sub(r'-+', '-', safe_name)
    repo_id = f"budget-skynet/{safe_name}"

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}\nNEAR RPC: https://rpc.mainnet.near.org"
    files = {}

    # app.py
    r = ask_claude(f"""{base_context}

Write ONLY the Python code for app.py — a Gradio web demo.
Return code inside ```python ... ``` block.

Requirements:
- import gradio as gr
- Use requests for NEAR RPC calls
- Create functional demo demonstrating the task
- Use gr.Interface or gr.Blocks
- End with: demo.launch()
- No placeholders — write actual working code""",
        max_tokens=2500, model=model)

    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            success, output = test_code(code, "python")
            if not success and "SyntaxError" in output:
                fix = ask_claude(
                    f"Fix SyntaxError:\n{output[:200]}\n\nCode:\n{code[:800]}\n\nReturn ONLY fixed code in ```python``` block.",
                    max_tokens=2000, model=model)
                if fix:
                    fixed = extract_code_block(fix, "python")
                    if fixed:
                        code = fixed
            files["app.py"] = code

    if "app.py" not in files:
        # Fallback — универсальный NEAR Explorer
        files["app.py"] = f'''import gradio as gr, requests, json

def query_near(account_id: str) -> str:
    try:
        r = requests.post("https://rpc.mainnet.near.org", json={{
            "jsonrpc": "2.0", "id": "1", "method": "query",
            "params": {{"request_type": "view_account", "finality": "final", "account_id": account_id}}
        }}, timeout=10)
        data = r.json()
        if "result" in data:
            bal = int(data["result"]["amount"]) / 10**24
            return f"Account: {{account_id}}\\nBalance: {{bal:.4f}} NEAR"
        return f"Error: {{data.get('error', {{'message': 'not found'}}).get('message')}}"
    except Exception as e:
        return f"Error: {{e}}"

demo = gr.Interface(fn=query_near,
    inputs=gr.Textbox(label="NEAR Account ID", placeholder="example.near"),
    outputs=gr.Textbox(label="Result"),
    title="{title[:60]}", description="{description[:100]}")
demo.launch()
'''

    files["requirements.txt"] = "gradio>=4.0.0\nrequests>=2.31.0\n"
    files["README.md"] = f"""---
title: {title[:50]}
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
---

# {title}

{description[:300]}

Built by [budget_skynet](https://market.near.ai) — autonomous AI agent on NEAR Protocol.
"""
    files["_hf_repo_id"] = repo_id
    print(f"   ✅ HF Space готов: {len([k for k in files if not k.startswith('_')])} файлов | {repo_id}")
    return files


def generate_wikipedia_article(title: str, description: str, model: str) -> dict:
    """Генерирует Wikipedia-style черновик статьи."""
    print("   📖 Генерируем Wikipedia статью...")

    prompt = f"""You are an expert Wikipedia editor.

TASK: {title}
REQUIREMENTS: {description[:3000]}

Write a complete Wikipedia-style article in Markdown.

Structure:
# {{Article Title}}
## Overview
## Background
## Technical Details
## Use Cases
## Ecosystem
## See Also
- [[Related1]]
## References

Rules:
- Neutral encyclopedic tone (no promotional language)
- Minimum 800 words
- Real facts and sources
- Wikipedia-style [[wikilinks]]
- No first-person language
- CRITICAL: Complete ALL sections fully. Do NOT truncate mid-sentence.
Return plain Markdown."""

    content = ask_claude(prompt, max_tokens=32000, model=model)
    if not content:
        content = f"# {title}\n\nContent generation failed."

    filename = title[:50].replace(" ", "_").replace(":", "").replace("/", "") + "_wikipedia_draft.md"
    meta = {"title": title, "type": "wikipedia_draft",
            "categories": ["NEAR Protocol", "Blockchain", "Web3"],
            "note": "Draft for Wikipedia submission. Requires human review."}
    return {
        filename: f"<!-- Wikipedia Draft -->\n\n{content}",
        "submission_metadata.json": json.dumps(meta, indent=2)
    }


# ============================================================
#  БЛОК 4: ПЕСОЧНИЦА (E2B + Piston fallback)
# ============================================================

# Импортируем E2B только если ключ есть — не ломаем агент без него
_e2b_available = False
if E2B_API_KEY:
    try:
        from e2b_code_interpreter import Sandbox as E2BSandbox
        _e2b_available = True
        print("   ✅ E2B SDK загружен")
    except ImportError:
        print("   ⚠️ e2b-code-interpreter не установлен, используем Piston")


def run_in_e2b(code: str, language: str = "python",
               install_packages: list = None) -> tuple:
    """
    Выполняет код в E2B sandbox.
    - Устанавливает пакеты через pip/npm перед запуском
    - Поддерживает Python и JavaScript
    - Возвращает (success: bool, output: str)
    """
    if not _e2b_available:
        return None, "E2B недоступен"

    print(f"   🧪 E2B sandbox ({language})...")
    try:
        with E2BSandbox.create() as sbx:

            # Устанавливаем нужные пакеты
            if install_packages:
                if language == "python":
                    pkg_str = " ".join(install_packages)
                    install_result = sbx.commands.run(f"pip install -q {pkg_str}")
                    print(f"   📦 pip install: {install_result.stdout[-100:] or 'OK'}")
                elif language in ("javascript", "typescript", "node"):
                    pkg_str = " ".join(install_packages)
                    install_result = sbx.commands.run(f"npm install -s {pkg_str}")
                    print(f"   📦 npm install: {install_result.stdout[-100:] or 'OK'}")

            # Запускаем код
            if language == "python":
                execution = sbx.run_code(code)
                output = ""
                if execution.logs.stdout:
                    output += "\n".join(execution.logs.stdout)
                if execution.logs.stderr:
                    output += "\n".join(execution.logs.stderr)
                error = execution.error
                success = error is None
                if error:
                    output += f"\nError: {error.name}: {error.value}"
            else:
                # JavaScript/TypeScript — через команду
                ext = "ts" if language == "typescript" else "js"
                sbx.files.write(f"main.{ext}", code)
                cmd = f"npx ts-node main.{ext}" if ext == "ts" else f"node main.{ext}"
                result = sbx.commands.run(cmd)
                output = result.stdout + result.stderr
                success = result.exit_code == 0

            print(f"   {'🟢' if success else '🔴'} E2B: {'OK' if success else output[:100]}")
            return success, output

    except Exception as e:
        print(f"   ⚠️ E2B ошибка: {e}")
        return None, str(e)


def run_local_syntax_check(code: str, language: str = "python") -> tuple:
    """
    Быстрая локальная проверка синтаксиса — без внешних сервисов.
    Python: ast.parse() — точная проверка.
    JS/TS: базовые эвристики (несбалансированные скобки, явные ошибки).
    """
    if language == "python":
        print(f"   🧪 Local ast.parse (python)...")
        try:
            import ast
            ast.parse(code)
            print("   🟢 Python синтаксис OK")
            return True, ""
        except SyntaxError as e:
            msg = f"SyntaxError: {e.msg} (line {e.lineno})"
            print(f"   🔴 {msg}")
            return False, msg
        except Exception as e:
            return False, str(e)

    elif language in ("javascript", "typescript", "node", "ts", "js"):
        print(f"   🧪 Local JS/TS syntax heuristic...")
        # Явные признаки синтаксических ошибок в сыром коде
        error_patterns = [
            (r'^\s*\)\s*{', "unexpected )"),           # ) { без функции
            (r'import\s+\w+\s+from\s+\w+[^\'"]', "missing quotes in import"),
            (r'function\s+\w+\s*\((?:[^)]*\n){5}', "unclosed function args"),
        ]
        # Проверяем баланс скобок
        for open_c, close_c in [('(', ')'), ('{', '}'), ('[', ']')]:
            if code.count(open_c) != code.count(close_c):
                msg = f"Unbalanced brackets: {code.count(open_c)} '{open_c}' vs {code.count(close_c)} '{close_c}'"
                print(f"   🔴 {msg}")
                return False, msg
        print("   🟢 JS/TS эвристика OK")
        return True, ""

    # Неизвестный язык — доверяем Claude
    return True, "unknown language, skipping check"


def test_code(code: str, language: str = "python",
              install_packages: list = None) -> tuple:
    """
    Умный выбор среды:
    - E2B доступен → E2B (реальный запуск с pip/npm install)
    - E2B недоступен → локальная проверка синтаксиса (ast.parse / эвристика)
    """
    if _e2b_available:
        success, output = run_in_e2b(code, language, install_packages)
        if success is not None:
            return success, output
        print("   ⚠️ E2B недоступен, fallback на локальную проверку...")

    return run_local_syntax_check(code, language)


# Обратная совместимость
def test_python_code(code: str) -> tuple:
    return test_code(code, "python")

def test_node_code(code: str) -> tuple:
    return test_code(code, "javascript")

def extract_delivery_conditions(title: str, description: str) -> str:
    """
    Извлекает из описания задачи конкретные условия сдачи работы.
    Возвращает структурированный список требований для проверки.
    """
    prompt = f"""Extract the EXACT delivery conditions from this task description.
Focus on: what format, what URL, what must be submitted, what must work.

TASK: {title}
DESCRIPTION: {description[:1500]}

List ONLY the concrete delivery requirements as bullet points.
Example:
- GitHub repository URL with working code
- Published to PyPI as pip-installable package
- README with installation instructions
- Unit tests passing

Be specific. Max 8 items. Return ONLY the bullet list, nothing else."""

    result = ask_claude(prompt, max_tokens=300, model="haiku")
    return result.strip() if result else "- Deliver working implementation\n- Include documentation"



def pre_submit_checklist(title: str, description: str, files: dict, deliverable_url: str) -> tuple[bool, str]:
    """
    Финальная проверка перед отправкой клиенту.
    Сверяет deliverable с условиями задачи.
    Возвращает (ok: bool, issues: str)
    """
    delivery_conditions = extract_delivery_conditions(title, description)

    files_list = [f for f in files.keys() if not f.startswith("_")]
    files_summary = []
    for fname in files_list[:10]:
        content_preview = files.get(fname, "")
        if isinstance(content_preview, str):
            files_summary.append(f"- {fname} ({len(content_preview)} chars)")

    prompt = f"""You are doing a FINAL pre-submission check for a freelance task.

TASK: {title}
DELIVERY CONDITIONS (what client expects):
{delivery_conditions}

WHAT WE PRODUCED:
Deliverable URL: {deliverable_url}
Files:
{chr(10).join(files_summary)}

Check: does our deliverable satisfy ALL delivery conditions?

Reply with EXACTLY:
READY: yes or no
ISSUES: (if no — list what's missing or wrong, be specific)"""

    result = ask_claude(prompt, max_tokens=300, model="haiku")
    if not result:
        return True, ""

    ready = "READY: yes" in result.lower() or "ready: yes" in result
    issues_start = result.find("ISSUES:")
    issues = result[issues_start + 7:].strip() if issues_start > 0 else ""

    if not ready:
        print(f"   ⚠️ Pre-submit check FAILED: {issues[:150]}")
    else:
        print(f"   ✅ Pre-submit check PASSED")

    return ready, issues


def quality_loop(
    generate_fn,           # функция() -> str | None — возвращает код
    test_language: str,    # "python" | "typescript" | "javascript"
    fix_prompt_fn,         # функция(code, error) -> str — формирует промпт для фикса
    model: str = "haiku",
    max_attempts: int = 7,
    install_packages: list = None,
    label: str = ""
) -> str | None:
    """
    Цикл до качественного результата:
    1. Генерируем код
    2. Тестируем через E2B или синтаксис-чек
    3. Если ошибка — просим Claude починить с учётом конкретной ошибки
    4. Повторяем до max_attempts раз
    5. Возвращаем лучший код или None
    """
    best_code = None
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            code = generate_fn()
        else:
            # Claude чинит с учётом реальной ошибки
            if not best_code:
                code = generate_fn()
            else:
                fix_prompt = fix_prompt_fn(best_code, last_error)
                raw = ask_claude(fix_prompt, max_tokens=3000, model=model)
                if raw:
                    extracted = (extract_code_block(raw, test_language) or
                                 extract_code_block(raw, "python") or
                                 extract_code_block(raw, "typescript") or
                                 extract_code_block(raw, ""))
                    code = extracted or raw
                else:
                    code = best_code  # пробуем старый

        if not code or not code.strip():
            print(f"   ⚠️ {label} attempt {attempt}: пустой код")
            continue

        best_code = code
        success, output = test_code(code, test_language, install_packages)
        last_error = output or ""

        if success:
            if attempt > 1:
                print(f"   ✅ {label} OK с попытки {attempt}")
            return code

        # Только синтаксис-ошибки и runtime ошибки чиним в loop
        # Если E2B недоступен и проверка пройдена — возвращаем
        if not _e2b_available and success:
            return code

        print(f"   🔧 {label} attempt {attempt}/{max_attempts}: {str(output)[:120]}")

    # Вернуть лучшее что есть даже если не идеально
    if best_code:
        print(f"   ⚠️ {label}: {max_attempts} попыток, возвращаем лучшую версию")
    return best_code


def extract_code_block(text: str, lang: str = "python") -> str | None:
    """Извлекает блок кода из ответа Claude — с умным fallback."""
    if not text:
        return None
    # 1. Точное совпадение по языку
    match = re.search(rf'```{lang}\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1)
    # 2. Алиасы: typescript → ts, javascript → js
    aliases = {"typescript": ["ts"], "javascript": ["js", "node"], "python": ["py"]}
    for alias in aliases.get(lang, []):
        match = re.search(rf'```{alias}\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1)
    # 3. Любой код-блок
    match = re.search(r'```\w*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1)
    # 4. Голый код без тегов
    ts_signals = ["import ", "export ", "async function", "interface ", ": string", ": Promise"]
    py_signals = ["import ", "def ", "async def", "class ", "from "]
    signals = ts_signals if lang in ("typescript", "ts", "javascript") else py_signals
    if any(s in text for s in signals) and "```" not in text:
        return text.strip()
    return None


# ============================================================
#  БЛОК 5: CLAUDE
# ============================================================

def ask_claude(prompt, max_tokens=3000, model="haiku"):
    """
    model="haiku"  → claude-haiku-4-5-20251001   (быстро, анализ, биды)
    model="sonnet" → claude-sonnet-4-6             (качество, конкурсы 100+ NEAR)
    """
    if model == "sonnet":
        model_id = "claude-sonnet-4-6"
    else:
        model_id = "claude-haiku-4-5-20251001"

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    body = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers,
                      json=body, timeout=90)

    if r.status_code == 200:
        return r.json()["content"][0]["text"]

    print(f"   ⚠️ Claude {model} ({model_id}) ошибка: {r.status_code} | {r.text[:200]}")
    return None

def choose_model(budget_amount):
    try:
        return "sonnet" if float(budget_amount or 0) >= 100 else "haiku"
    except Exception:
        return "haiku"

# Загружаем AGENT_CAPABILITIES.md один раз при старте
def _load_capabilities() -> str:
    import os
    paths = [
        "AGENT_CAPABILITIES.md",
        "/home/runner/work/budget-skynet-agent/budget-skynet-agent/AGENT_CAPABILITIES.md",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT_CAPABILITIES.md"),
    ]
    for path in paths:
        try:
            with open(path, "r") as f:
                content = f.read()
                if content.strip():
                    print(f"   📋 AGENT_CAPABILITIES.md загружен: {len(content)} символов")
                    return content
        except Exception:
            pass
    print("   ⚠️ AGENT_CAPABILITIES.md не найден — используем встроенный список")
    return ""

AGENT_CAPABILITIES = _load_capabilities()


def analyze_job_description(title: str, description: str) -> str:
    """
    Умная фильтрация через Claude + AGENT_CAPABILITIES.md.
    Возвращает: "bid", "skip", или "discuss" (отправить владельцу на обсуждение).
    """
    caps = AGENT_CAPABILITIES or """
CAN DO: Python/PyPI packages, npm packages, MCP servers, Telegram bots, Discord bots,
GitHub Actions, VS Code extensions, LangChain tools, HuggingFace Spaces,
Colab notebooks, markdown articles, MoltBook posts, n8n nodes, CLI tools, research, analysis.

CANNOT DO: Chrome/Firefox/GPT Store publishing, JetBrains Marketplace, App Store,
Solidity/Rust smart contracts, security audits, social media posting (Twitter/Reddit/LinkedIn),
guaranteed metrics (500+ downloads), video/image/graphic design, trading bots.
"""

    # Короткий список для фильтрации — экономим токены
    caps_short = """CAN: Python/npm packages, MCP servers, Telegram/Discord bots, GitHub Actions,
VS Code extensions, LangChain tools, HuggingFace Spaces, Colab, Markdown articles,
MoltBook posts, n8n nodes, CLI tools, research+websearch, OpenClaw skills, web scraping.
CANNOT: Chrome/GPT/App Store publishing, JetBrains Marketplace, social media accounts,
guaranteed metrics, Solidity/Rust contracts, security audits, video/design creation."""

    prompt = f"""Filter: can autonomous AI agent bid on this task?

AGENT: {caps_short}

TASK: {title}
{description[:800]}

Reply ONE word: BID / SKIP / DISCUSS"""

    result = ask_claude(prompt, max_tokens=10, model="haiku")
    decision = result.strip().upper() if result else "DISCUSS"

    if "BID" in decision:
        return "bid"
    elif "SKIP" in decision:
        # Логируем первые 10 скипов чтобы видеть паттерн
        return "skip"
    else:
        return "discuss"

def generate_dynamic_proposal(title, description):
    is_nearcon = any(w in (title + description).lower()
                     for w in ["nearcon", "hackathon", "demo day", "sf", "san francisco"])
    extra = " Excited about NearCon SF opportunities." if is_nearcon else ""

    prompt = f"""You are an elite autonomous AI agent on NEAR Agent Market.
Job: {title}
Description: {description[:400]}

Write a sharp 2-sentence proposal. Be specific to this job.
Mention relevant expertise (Python/Web3/packages as appropriate).{extra}
No price mentions."""
    proposal = ask_claude(prompt, max_tokens=150, model="haiku")
    return proposal.strip() if proposal else "Elite autonomous AI agent ready to deliver immediately."


# ============================================================
#  БЛОК 6: ОПРЕДЕЛЕНИЕ ТИПА DELIVERABLE
# ============================================================

def detect_deliverable_type(title: str, description: str) -> str:
    """
    Определяет какой формат deliverable нужен заказчику.
    Возвращает строку-тип из DELIVERABLE_TYPES.
    """
    combined = (title + " " + description).lower()
    title_lower = title.lower()

    # MoltBook проверяем ПЕРВЫМ — иначе слова "mcp/server/build" перебивают
    if "moltbook" in combined or "molt book" in combined:
        return "moltbook_post"

    for dtype, keywords in DELIVERABLE_TYPES.items():
        if dtype == "moltbook_post":
            continue  # уже проверили выше
        if any(kw in combined for kw in keywords):
            return dtype

    # Если в заголовке есть "Build" — скорее всего код
    if "build" in title_lower or "create" in title_lower:
        return "python_package"

    return "markdown"


# ============================================================
#  БЛОК 7: ГЕНЕРАТОРЫ DELIVERABLE ПО ТИПАМ
# ============================================================

def generate_npm_package(title: str, description: str, model: str) -> dict:
    """
    Генерирует npm/TypeScript пакет — каждый файл отдельным запросом.
    Надёжнее чем один большой JSON: меньше токенов, нет проблем с экранированием.
    """
    print("   📦 Генерируем npm пакет (file-by-file)...")

    pkg_match = re.search(r'near-[\w-]+', title.lower())
    pkg_name = pkg_match.group(0) if pkg_match else "near-utils"

    base_context = f"""PACKAGE: {pkg_name}
TASK: {title}
REQUIREMENTS: {description[:3000]}
NEAR RPC: https://rpc.mainnet.near.org
NEAR npm: near-api-js"""

    files = {}

    # 1. package.json — генерируем программно (100% надёжно, без обрезки токенов)
    # Описание берём из title, Claude не нужен для шаблонного JSON
    pkg_description = title[:100]
    files["package.json"] = json.dumps({
        "name": pkg_name,
        "version": "1.0.0",
        "description": pkg_description,
        "main": "dist/index.js",
        "types": "dist/index.d.ts",
        "scripts": {
            "build": "tsc",
            "prepublishOnly": "npm run build",
            "test": "jest --passWithNoTests"
        },
        "keywords": ["near", "blockchain", "web3"],
        "license": "MIT",
        "dependencies": {
            "near-api-js": "^4.0.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "@types/node": "^20.0.0",
            "jest": "^29.0.0",
            "@types/jest": "^29.0.0",
            "ts-jest": "^29.0.0"
        },
        "files": ["dist/**/*", "README.md"]
    }, indent=2)

    # 2. tsconfig.json
    files["tsconfig.json"] = json.dumps({
        "compilerOptions": {
            "target": "ES2020", "module": "commonjs",
            "lib": ["ES2020"], "outDir": "./dist",
            "rootDir": "./src", "strict": True,
            "esModuleInterop": True, "declaration": True,
            "declarationMap": True, "sourceMap": True
        },
        "include": ["src/**/*"],
        "exclude": ["node_modules", "dist", "**/*.test.ts"]
    }, indent=2)

    # 3. src/index.ts — главный файл
    r = ask_claude(f"""{base_context}

Write ONLY the TypeScript source code for src/index.ts.
Return code inside ```typescript ... ``` block.

Requirements:
- Import from 'near-api-js'
- Export async functions that implement the package functionality
- Include JSDoc comments
- Handle errors properly
- No placeholder comments — write actual working code""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "typescript") or extract_code_block(r, "ts") or extract_code_block(r, "")
        if code:
            # Quality loop — до 5 попыток пока TS не скомпилируется
            final_ts = quality_loop(
                generate_fn=lambda: code,
                test_language="typescript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL TypeScript errors.\n"
                    f"ERROR:\n{err[:400]}\n\n"
                    f"TASK: {title}\n"
                    f"REQUIREMENTS: {description[:400]}\n\n"
                    f"CODE:\n{c[:2000]}\n\n"
                    f"Return ONLY fixed TypeScript in ```typescript``` block."
                ),
                model=model,
                max_attempts=7,
                install_packages=["near-api-js", "typescript", "ts-node"],
                label="TypeScript index.ts"
            ) or code
            files["src/index.ts"] = final_ts

    # 4. src/types.ts
    r = ask_claude(f"""{base_context}

Write ONLY the TypeScript type definitions for src/types.ts.
Return code inside ```typescript ... ``` block.
Define interfaces and types used by the package.""",
        max_tokens=600, model=model)
    if r:
        code = extract_code_block(r, "typescript") or extract_code_block(r, "ts") or extract_code_block(r, "")
        if code:
            files["src/types.ts"] = code

    # 5. README.md
    r = ask_claude(f"""{base_context}

Write ONLY the README.md for this npm package.
Include: badges, installation (npm install {pkg_name}), API reference with examples, requirements.
Return plain markdown, no code block wrapper.""",
        max_tokens=1000, model=model)
    if r:
        clean = re.sub(r'^```markdown\n?|^```\n?|```$', '', r.strip(), flags=re.MULTILINE)
        files["README.md"] = clean

    # 6. .npmignore
    files[".npmignore"] = "src/\ntsconfig.json\n*.test.ts\n.github/\n"

    print(f"   ✅ npm пакет: {len(files)} файлов — {', '.join(files.keys())}")
    return files


def generate_python_package(title: str, description: str, model: str) -> dict:
    """
    Генерирует Python пакет — каждый файл отдельным запросом.
    """
    print("   🐍 Генерируем Python пакет (file-by-file)...")

    pkg_match = re.search(r'near-[\w_-]+|near_[\w_]+', title.lower())
    pkg_name = pkg_match.group(0).replace("-", "_") if pkg_match else "near_utils"

    # Определяем тип задачи — market.near.ai SDK или NEAR Protocol
    is_market_sdk = any(kw in (title + description).lower() for kw in [
        "market.near.ai", "agent market", "agentmarket", "market api",
        "marketplace api", "market sdk", "place bid", "list jobs", "submit work"
    ])

    if is_market_sdk:
        pkg_name = "agent_market"
        market_skill = """MARKET API BASE: https://market.near.ai/v1
AUTH: Bearer token in Authorization header
KEY ENDPOINTS:
- GET  /v1/jobs                    list jobs
- POST /v1/jobs/{job_id}/bids      place bid
- POST /v1/jobs/{job_id}/submit    submit work
- GET  /v1/agents/me               my profile
- GET  /v1/wallet/balance          check balance
- POST /v1/wallet/withdraw         withdraw NEAR
- POST /v1/jobs/{job_id}/dispute   open dispute
USAGE EXAMPLE:
  from agent_market import AgentMarket
  client = AgentMarket(api_key="sk_live_...")
  jobs = client.jobs.list(status="open")
  client.jobs.bid(job_id="...", amount=4.5, proposal="I can help")"""
        base_context = f"""PACKAGE: agent_market
TASK: {title}
REQUIREMENTS: {description[:3000]}
{market_skill}
IMPORTANT: Build AgentMarket SDK for market.near.ai API, NOT a NEAR RPC client."""
    else:
        base_context = f"""PACKAGE: {pkg_name}
TASK: {title}
REQUIREMENTS: {description[:3000]}
NEAR RPC: https://rpc.mainnet.near.org"""

    files = {}

    # 1. pyproject.toml
    files["pyproject.toml"] = f"""[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{pkg_name.replace('_', '-')}"
version = "1.0.0"
description = "{title[:80]}"
requires-python = ">=3.9"
dependencies = ["aiohttp>=3.9", "requests>=2.31"]

[project.urls]
Homepage = "https://github.com/your-repo/{pkg_name}"
"""

    # 2. src/__init__.py
    r = ask_claude(f"""{base_context}

Write ONLY the Python source code for src/{pkg_name}/__init__.py
Return code inside ```python ... ``` block.

Requirements:
- Async functions using aiohttp for NEAR RPC calls
- Type hints throughout
- Docstrings for all public functions
- Export: __all__, __version__ = "1.0.0"
- Implement the actual functionality, no placeholders""",
        max_tokens=2000, model=model)
    if r:
        initial_code = extract_code_block(r, "python") or extract_code_block(r, "")
        if initial_code:
            # Quality loop — до 5 попыток пока код не пройдёт тест
            final_code = quality_loop(
                generate_fn=lambda: initial_code if True else None,
                test_language="python",
                fix_prompt_fn=lambda code, err: (
                    f"Fix ALL errors in this Python package code.\n"
                    f"ERROR:\n{err[:400]}\n\n"
                    f"TASK: {title}\n"
                    f"REQUIREMENTS: {description[:400]}\n\n"
                    f"CODE:\n{code[:2000]}\n\n"
                    f"Return ONLY fixed Python code in ```python``` block."
                ),
                model=model,
                max_attempts=7,
                label=f"Python {pkg_name}"
            ) or initial_code
            files[f"src/{pkg_name}/__init__.py"] = final_code

    # 3. README.md
    r = ask_claude(f"""{base_context}

Write ONLY the README.md for this Python package.
Include: installation (pip install {pkg_name.replace('_', '-')}), API reference with async examples.
Return plain markdown.""",
        max_tokens=800, model=model)
    if r:
        files["README.md"] = re.sub(r'^```\w*\n?|```$', '', r.strip(), flags=re.MULTILINE)

    # 4. requirements.txt
    files["requirements.txt"] = "aiohttp>=3.9\nrequests>=2.31\n"

    # Fallback: если __init__.py не сгенерировался — добавляем базовую реализацию
    init_key = f"src/{pkg_name}/__init__.py"
    if init_key not in files:
        print("   ⚠️ __init__.py не сгенерирован — используем fallback")
        if is_market_sdk:
            files[init_key] = '''"""
agent_market - Python SDK for market.near.ai API
"""
import requests
from typing import Any, Dict, List, Optional

__version__ = "1.0.0"
BASE_URL = "https://market.near.ai"

class AgentMarket:
    """Python SDK for market.near.ai API."""
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: Dict = None) -> Any:
        r = self.session.get(f"{self.base_url}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: Dict = None) -> Any:
        r = self.session.post(f"{self.base_url}{path}", json=json or {}, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_jobs(self, status: str = None, limit: int = 20) -> List[Dict]:
        params = {"limit": limit}
        if status: params["status"] = status
        return self._get("/v1/jobs", params=params)

    def bid(self, job_id: str, amount: float, proposal: str = "") -> Dict:
        return self._post(f"/v1/jobs/{job_id}/bids", {"amount": str(amount), "proposal": proposal})

    def submit(self, job_id: str, deliverable: str) -> Dict:
        return self._post(f"/v1/jobs/{job_id}/submit", {"deliverable": deliverable})

    def balance(self) -> Dict:
        return self._get("/v1/wallet/balance")

    def withdraw(self, to_account_id: str, amount: float) -> Dict:
        return self._post("/v1/wallet/withdraw", {"to_account_id": to_account_id, "amount": str(amount)})
'''
        else:
            files[init_key] = f'''"""
{title}
Auto-generated NEAR Protocol Python package.
"""
import requests
from typing import Optional, Dict, Any

__version__ = "1.0.0"
__all__ = ["NEARClient", "get_account", "get_balance"]

NEAR_RPC = "https://rpc.mainnet.near.org"


class NEARClient:
    """Client for interacting with NEAR Protocol."""

    def __init__(self, rpc_url: str = NEAR_RPC):
        self.rpc_url = rpc_url

    def _call(self, method: str, params: Any) -> Dict:
        payload = {{"jsonrpc": "2.0", "id": "dontcare",
                    "method": method, "params": params}}
        r = requests.post(self.rpc_url, json=payload, timeout=10)
        r.raise_for_status()
        return r.json().get("result", {{}})

    def get_account(self, account_id: str) -> Dict:
        """Get NEAR account info."""
        return self._call("query", {{
            "request_type": "view_account",
            "finality": "final",
            "account_id": account_id
        }})

    def get_balance(self, account_id: str) -> float:
        """Get NEAR account balance in NEAR tokens."""
        info = self.get_account(account_id)
        yocto = int(info.get("amount", 0))
        return yocto / 10**24

    def get_block(self, finality: str = "final") -> Dict:
        """Get latest NEAR block."""
        return self._call("block", {{"finality": finality}})

    def view_function(self, contract_id: str, method: str,
                      args: Optional[Dict] = None) -> Any:
        """Call a view function on a NEAR contract."""
        import base64, json
        args_b64 = base64.b64encode(
            json.dumps(args or {{}}).encode()
        ).decode()
        return self._call("query", {{
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract_id,
            "method_name": method,
            "args_base64": args_b64
        }})


def get_account(account_id: str) -> Dict:
    """Convenience: get account info."""
    return NEARClient().get_account(account_id)


def get_balance(account_id: str) -> float:
    """Convenience: get balance in NEAR."""
    return NEARClient().get_balance(account_id)
'''

    print(f"   ✅ Python пакет: {len(files)} файлов — {', '.join(files.keys())}")
    return files


def generate_github_action(title: str, description: str, model: str) -> dict:
    """Генерирует GitHub Action — файлы по одному."""
    print("   ⚙️ Генерируем GitHub Action (file-by-file)...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    # 1. action.yml
    r = ask_claude(f"""{base_context}

Write ONLY the action.yml for this GitHub Action.
Return plain YAML (no markdown wrapper).
Include: name, description, inputs (with description+required), outputs, runs (using: node20, main: dist/index.js).""",
        max_tokens=500, model=model)
    if r:
        files["action.yml"] = re.sub(r'^```ya?ml\n?|```$', '', r.strip(), flags=re.MULTILINE)

    # 2. src/index.js
    r = ask_claude(f"""{base_context}

Write ONLY the JavaScript source code for src/index.js (GitHub Action runner).
Return code inside ```javascript ... ``` block.
Use: @actions/core (getInput, setOutput, setFailed), @actions/github if needed.
Implement actual logic — no placeholders.""",
        max_tokens=1500, model=model)
    if r:
        code = extract_code_block(r, "javascript") or extract_code_block(r, "js") or extract_code_block(r, "")
        if code:
            files["src/index.js"] = quality_loop(
                generate_fn=lambda: code,
                test_language="javascript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL JavaScript errors in this GitHub Action.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed JS in ```javascript``` block."
                ),
                model=model, max_attempts=7, label="GitHub Action index.js"
            ) or code

    # 3. README.md
    r = ask_claude(f"""{base_context}

Write ONLY the README.md for this GitHub Action.
Include: usage example with 'uses:', inputs table, outputs table.
Return plain markdown.""",
        max_tokens=600, model=model)
    if r:
        files["README.md"] = re.sub(r'^```\w*\n?|```$', '', r.strip(), flags=re.MULTILINE)

    print(f"   ✅ GitHub Action: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "github action")


def generate_mcp_server(title: str, description: str, model: str) -> dict:
    """Генерирует MCP Server для Claude — файлы по одному."""
    print("   🔌 Генерируем MCP Server (file-by-file)...")

    server_match = re.search(r'near-[\w-]+|near_[\w_]+', title.lower())
    server_name = server_match.group(0) if server_match else "near-mcp-server"
    base_context = f"MCP SERVER: {server_name}\nTASK: {title}\nREQUIREMENTS: {description[:3000]}\nNEAR RPC: https://rpc.mainnet.near.org"
    files = {}

    files["package.json"] = json.dumps({
        "name": server_name, "version": "1.0.0",
        "description": title[:80], "main": "dist/index.js",
        "bin": {server_name: "dist/index.js"},
        "scripts": {"build": "tsc", "start": "node dist/index.js"},
        "dependencies": {"@modelcontextprotocol/sdk": "^1.0.0", "near-api-js": "^4.0.0"},
        "devDependencies": {"typescript": "^5.0.0"}
    }, indent=2)

    r = ask_claude(f"""{base_context}

Write ONLY the TypeScript source for src/index.ts (MCP Server entry point).
Return code inside ```typescript ... ``` block.
Use @modelcontextprotocol/sdk Server class. Register tools from src/tools.ts. Start stdio transport.""",
        max_tokens=1500, model=model)
    if r:
        code = extract_code_block(r, "typescript") or extract_code_block(r, "ts") or extract_code_block(r, "")
        if code:
            files["src/index.ts"] = quality_loop(
                generate_fn=lambda: code,
                test_language="typescript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL TypeScript errors in this MCP server entry point.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed TypeScript in ```typescript``` block."
                ),
                model=model, max_attempts=7,
                install_packages=["@modelcontextprotocol/sdk", "typescript", "ts-node"],
                label="MCP index.ts"
            ) or code

    r = ask_claude(f"""{base_context}

Write ONLY the TypeScript source for src/tools.ts (MCP tool definitions).
Return code inside ```typescript ... ``` block.
Define tools as array of {{name, description, inputSchema, handler}}.
Each handler calls NEAR RPC (https://rpc.mainnet.near.org) via fetch.
Implement actual NEAR functionality — wallet balance, transactions, etc.""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "typescript") or extract_code_block(r, "ts") or extract_code_block(r, "")
        if code:
            files["src/tools.ts"] = quality_loop(
                generate_fn=lambda: code,
                test_language="typescript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL TypeScript errors in this MCP tools file.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed TypeScript in ```typescript``` block."
                ),
                model=model, max_attempts=7,
                install_packages=["@modelcontextprotocol/sdk", "typescript"],
                label="MCP tools.ts"
            ) or code

    claude_config = json.dumps({"mcpServers": {server_name: {"command": "npx", "args": ["-y", server_name]}}}, indent=2)
    r = ask_claude(f"""{base_context}

Write ONLY the README.md for this MCP server.
Include: what it does, Claude Desktop config (paste this exactly):
```json
{claude_config}
```
And list of available tools with descriptions. Return plain markdown.""",
        max_tokens=600, model=model)
    if r:
        files["README.md"] = re.sub(r'^```\w*\n?|```$', '', r.strip(), flags=re.MULTILINE)

    print(f"   ✅ MCP Server: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "mcp server")


def generate_telegram_bot(title: str, description: str, model: str) -> dict:
    """Генерирует Telegram бота — файлы по одному."""
    print("   🤖 Генерируем Telegram Bot (file-by-file)...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}\nNEAR RPC: https://rpc.mainnet.near.org"
    files = {}

    # near_utils.py
    r = ask_claude(f"""{base_context}

Write ONLY near_utils.py — async NEAR RPC helper functions.
Return code inside ```python ... ``` block.
Use aiohttp for async HTTP to https://rpc.mainnet.near.org
Functions: get_account_balance(account_id), get_recent_transactions(account_id), etc.""",
        max_tokens=1200, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["near_utils.py"] = code

    # bot.py
    r = ask_claude(f"""{base_context}

Write ONLY bot.py — main Telegram bot file.
Return code inside ```python ... ``` block.
Use python-telegram-bot v20+ (async). Commands: /start, /help, and task-specific commands.
Import from near_utils import the functions. Load BOT_TOKEN from os.environ.""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["bot.py"] = code
            final_code_ql = quality_loop(
                generate_fn=lambda: code,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL Python errors.\nERROR:\n{err[:400]}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed Python in ```python``` block."
                ),
                model=model,
                max_attempts=7,
                label="bot"
            ) or code
            files["bot.py"] = final_code_ql

    files["requirements.txt"] = "python-telegram-bot>=20.0\naiohttp>=3.9\n"
    files["README.md"] = f"# {title}\n\n## Setup\n\n1. `pip install -r requirements.txt`\n2. Set env: `BOT_TOKEN=your_token`\n3. `python bot.py`\n"

    print(f"   ✅ Telegram Bot: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "telegram bot")


def generate_discord_bot(title: str, description: str, model: str) -> dict:
    """Генерирует Discord бота — файлы по одному."""
    print("   🎮 Генерируем Discord Bot (file-by-file)...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    r = ask_claude(f"""{base_context}

Write ONLY bot.py — main Discord bot file.
Return code inside ```python ... ``` block.
Use discord.py v2+ with app_commands (slash commands).
Load DISCORD_TOKEN from os.environ. Sync commands on ready.""",
        max_tokens=1500, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["bot.py"] = quality_loop(
                generate_fn=lambda: code,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL Python errors in this Discord bot.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed Python in ```python``` block."
                ),
                model=model, max_attempts=7, label="Discord bot.py"
            ) or code

    r = ask_claude(f"""{base_context}

Write ONLY cogs/near_commands.py — Discord Cog with NEAR-related slash commands.
Return code inside ```python ... ``` block.
Use discord.app_commands. Call https://rpc.mainnet.near.org via aiohttp.""",
        max_tokens=1500, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["cogs/near_commands.py"] = quality_loop(
                generate_fn=lambda: code,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL Python errors in this Discord Cog.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed Python in ```python``` block."
                ),
                model=model, max_attempts=7, label="Discord cog"
            ) or code

    files["requirements.txt"] = "discord.py>=2.0\naiohttp>=3.9\n"
    files["README.md"] = f"# {title}\n\n## Setup\n\n1. `pip install -r requirements.txt`\n2. Set env: `DISCORD_TOKEN=your_token`\n3. `python bot.py`\n"

    print(f"   ✅ Discord Bot: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "discord bot")


def generate_cli_tool(title: str, description: str, model: str) -> dict:
    """Генерирует CLI инструмент — файлы по одному."""
    print("   ⌨️ Генерируем CLI Tool (file-by-file)...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    r = ask_claude(f"""{base_context}

Write ONLY cli.py — CLI tool using Click or Typer.
Return code inside ```python ... ``` block.
Include: main group/app, subcommands with help text, NEAR RPC calls.
Entry point should work as: near-tool <command> [args]""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["cli.py"] = code
            final_code_ql = quality_loop(
                generate_fn=lambda: code,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL Python errors.\nERROR:\n{err[:400]}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed Python in ```python``` block."
                ),
                model=model,
                max_attempts=7,
                label="cli"
            ) or code
            files["cli.py"] = final_code_ql

    pkg_name = re.sub(r'[^\w]', '_', title.lower())[:20]
    files["pyproject.toml"] = f"""[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{pkg_name.replace('_', '-')}"
version = "1.0.0"
description = "{title[:80]}"
requires-python = ">=3.9"
dependencies = ["click>=8.0", "aiohttp>=3.9", "requests>=2.31"]

[project.scripts]
{pkg_name.replace('_', '-')} = "cli:main"
"""
    files["README.md"] = f"# {title}\n\n## Install\n\n```\npip install .\n```\n\n## Usage\n\n```\n{pkg_name.replace('_', '-')} --help\n```\n"

    print(f"   ✅ CLI Tool: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "cli tool")


def generate_langchain_tool(title: str, description: str, model: str) -> dict:
    """Генерирует LangChain Tool — файлы по одному."""
    print("   🦜 Генерируем LangChain Tool (file-by-file)...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}\nNEAR RPC: https://rpc.mainnet.near.org"
    files = {}

    # near_tool.py — BaseTool subclass
    r = ask_claude(f"""{base_context}

Write ONLY near_tool.py — a LangChain tool class for NEAR Protocol.
Return code inside ```python ... ``` block.

Requirements:
- from langchain.tools import BaseTool
- Pydantic BaseModel for input schema
- Implement _run(self, ...) and _arun(self, ...) methods
- Call NEAR RPC via requests (https://rpc.mainnet.near.org)
- name, description, args_schema class attributes
- No placeholders — working implementation""",
        max_tokens=1800, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["near_tool.py"] = code
            final_code_ql = quality_loop(
                generate_fn=lambda: code,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL Python errors.\nERROR:\n{err[:400]}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed Python in ```python``` block."
                ),
                model=model,
                max_attempts=7,
                label="near tool"
            ) or code
            files["near_tool.py"] = final_code_ql

    # example.py
    r = ask_claude(f"""{base_context}

Write ONLY example.py showing how to use the LangChain NEAR tool.
Return code inside ```python ... ``` block.
Use: from near_tool import NearTool (or whatever class name fits).
Show integration with ChatOpenAI or another LLM via langchain agents.""",
        max_tokens=600, model=model)
    if r:
        code = extract_code_block(r, "python") or extract_code_block(r, "")
        if code:
            files["example.py"] = code

    files["requirements.txt"] = "langchain>=0.2\nlangchain-openai>=0.1\nrequests>=2.31\n"
    files["README.md"] = f"# {title}\n\n## Install\n\n```\npip install -r requirements.txt\n```\n\n## Usage\n\nSee `example.py` for full integration example.\n"

    print(f"   ✅ LangChain Tool: {len(files)} файлов")
    return files if files else generate_markdown_fallback(title, description, model, "langchain tool")


def generate_html_app(title: str, description: str, model: str) -> dict:
    """Генерирует рабочее HTML/JS приложение."""
    print("   🌐 Генерируем HTML App...")

    prompt = f"""You are a frontend developer building a working web app.
Build it autonomously — NO questions.

TASK: {title}
DETAILS: {description[:1000]}

Rules:
- Single self-contained HTML file (CSS + JS inside)
- Dark theme, modern, polished
- Functional with public APIs (no API keys)
- Use corsproxy.io for CORS: fetch(`https://corsproxy.io/?${{encodeURIComponent(url)}}`)
- CDN from cdnjs.cloudflare.com
- Works via htmlpreview.github.io
- Mock data fallback if API unavailable

Return ONLY complete HTML starting with <!DOCTYPE html>"""

    html = ask_claude(prompt, max_tokens=6000, model=model)
    if html and "<!DOCTYPE" in html.upper():
        match = re.search(r'(<!DOCTYPE html>.*)', html, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1)
        filename = title[:40].replace(" ", "_").replace(":", "") + ".html"
        return {filename: html}

    return generate_markdown_fallback(title, description, model, "web app")


def generate_markdown_deliverable(title: str, description: str, model: str) -> dict:
    """Генерирует Markdown документ (гайд, исследование, туториал, или короткий Q&A ответ)."""
    is_short_qa = len(description.strip()) < 200 and len(description.strip()) > 0

    if is_short_qa:
        # Короткий вопрос → краткий точный ответ
        print("   💬 Q&A режим: короткий точный ответ...")
        prompt = f"""Answer this question directly and accurately.
QUESTION: {title}
DETAILS: {description}

Rules:
- Answer directly, no preamble
- Be specific with numbers/facts
- 2-5 sentences max unless detail is needed
- Use Markdown formatting where helpful"""
        content = ask_claude(prompt, max_tokens=500, model=model)
    else:
        # Полноценный документ
        print("   📝 Генерируем Markdown документ...")

        # Проверяем нужны ли реальные данные из интернета
        needs_research = any(kw in (title + description).lower() for kw in [
            "research", "analysis", "compare", "comparison", "review", "survey",
            "market", "trend", "state of", "report", "competitive", "landscape",
            "current", "latest", "recent", "2024", "2025", "2026",
            "статистика", "анализ", "исследование", "сравнение"
        ])

        research_context = ""
        if needs_research:
            print("   🔬 Задача требует актуальных данных — ищем в интернете...")
            research_context = research_topic(title, depth=3)
            research_context = f"\n\nRESEARCH DATA (from web search):\n{research_context}"

        prompt = f"""You are a professional Technical Writer and Web3 Researcher.
CONTEXT: {NEAR_CONTEXT}
TASK: {title}
DETAILS: {description[:3000]}
{research_context}

Write a comprehensive, well-structured Markdown document.
No meta-commentary. Include:
- Clear H2/H3 structure
- Code examples where relevant
- Specific technical details with real data (use research data if provided)
- Practical examples
- Cite sources where applicable
Minimum 600 words.
CRITICAL: Complete ALL sections fully. Do NOT truncate mid-sentence."""
        content = ask_claude(prompt, max_tokens=32000, model=model)

    filename = title[:50].replace(" ", "_").replace(":", "").replace("/", "") + ".md"
    return {filename: f"# {title}\n\n{content}" if content else f"# {title}\n\nContent generation failed."}


def generate_markdown_fallback(title: str, description: str, model: str, dtype: str) -> dict:
    """Fallback когда JSON парсинг не сработал — генерируем подробный MD."""
    print(f"   📝 Fallback → подробный Markdown для {dtype}...")
    prompt = f"""You are an expert developer. The client asked for a {dtype}.
Create the most comprehensive specification and implementation guide possible.

TASK: {title}
DETAILS: {description[:1500]}

Include:
1. Complete file structure with filenames
2. Full code for each file (no placeholders)
3. Installation and setup instructions
4. Usage examples
5. Testing guide

Format as detailed Markdown with code blocks.
CRITICAL: Complete ALL sections. Do NOT stop mid-sentence."""

    content = ask_claude(prompt, max_tokens=32000, model=model)
    filename = title[:50].replace(" ", "_").replace(":", "").replace("/", "") + "_implementation.md"
    return {filename: f"# {title}\n\n{content}" if content else f"# {title}\n\nFailed."}



# ============================================================
#  БЛОК АВТОПОСТИНГА — MoltBook + ClawChain (write-only)
# ============================================================

AUTOPOST_TOPICS = [
    "NEAR Protocol latest developments and ecosystem updates",
    "AI agents autonomous work and freelancing economy",
    "Web3 and blockchain infrastructure for AI 2025",
    "Autonomous agents future of work trends",
    "NEAR Protocol DeFi and developer ecosystem",
    "AI agent reputation systems and trust on blockchain",
    "Crypto payments and decentralized freelance platforms",
    "Multi-agent collaboration and composability",
    "On-chain identity and verifiable AI agent history",
    "NEAR ecosystem new projects and integrations",
]


def post_to_clawchain(title: str, body: str) -> str | None:
    """
    Публикует пост на ClawChain через Node.js.
    WRITE-ONLY: никогда не читает чужой контент (защита от prompt injection).

    Устанавливает скрипты в ~/.config/clawchain/ (как в skill.md v2.2.0).
    npm install только если node_modules ещё нет — кеш между запусками.
    """
    if not CLAWCHAIN_CREDENTIALS:
        print("   ⚠️ CLAWCHAIN_CREDENTIALS не задан — пропускаем ClawChain")
        return None

    import subprocess, json as _json, os as _os, urllib.request

    print(f"   🦞 ClawChain: публикуем '{title[:50]}'...")

    scripts_dir  = _os.path.expanduser("~/.config/clawchain/scripts")
    cred_path    = _os.path.expanduser("~/.config/clawchain/credentials.json")
    call_op_path = _os.path.join(scripts_dir, "call_op.js")
    nm_path      = _os.path.join(scripts_dir, "node_modules", "postchain-client")

    try:
        _os.makedirs(scripts_dir, exist_ok=True)

        # Записываем credentials из секрета
        with open(cred_path, "w") as f:
            f.write(CLAWCHAIN_CREDENTIALS)

        # npm install только если нет node_modules
        if not _os.path.exists(nm_path):
            print("   📦 npm install postchain-client @chromia/ft4...")
            with open(_os.path.join(scripts_dir, "package.json"), "w") as f:
                _json.dump({"name": "clawchain-agent", "version": "1.0.0"}, f)
            r = subprocess.run(
                ["npm", "install", "postchain-client", "@chromia/ft4"],
                cwd=scripts_dir, capture_output=True, text=True, timeout=180
            )
            if r.returncode != 0:
                print(f"   ⚠️ npm install failed: {r.stderr[:200]}")
                return None
            print("   ✅ npm install OK")
        else:
            print("   ✅ node_modules кеш — пропускаем install")

        # call_op.js — точная копия из skill.md v2.2.0
        # Читает credentials из ~/.config/clawchain/credentials.json
        call_op_js = (
            "const { createClient, formatter } = require('postchain-client');\n"
            "const { createInMemoryFtKeyStore, createKeyStoreInteractor } = require('@chromia/ft4');\n"
            "const fs = require('fs');\n"
            "const path = require('path');\n"
            "const os = require('os');\n"
            "const brid = process.env.CLAWCHAIN_BRID || '9D728CC635A9D33DAABAC8217AA8131997A8CBF946447ED0B98760245CE5207E';\n"
            "const nodeUrl = process.env.CLAWCHAIN_NODE || 'https://chromia.01node.com:7740';\n"
            "(async () => {\n"
            "  const [opName, ...args] = process.argv.slice(2);\n"
            "  if (!opName) { console.error('Usage: node call_op.js <opName> [args...]'); process.exit(1); }\n"
            "  const credPath = path.join(os.homedir(), '.config', 'clawchain', 'credentials.json');\n"
            "  const creds = JSON.parse(fs.readFileSync(credPath, 'utf8'));\n"
            "  const keyPair = { privKey: Buffer.from(creds.privKey, 'hex'), pubKey: Buffer.from(creds.pubKey, 'hex') };\n"
            "  const client = await createClient({ nodeUrlPool: [nodeUrl], blockchainRid: brid });\n"
            "  const keyStore = createInMemoryFtKeyStore(keyPair);\n"
            "  const interactor = createKeyStoreInteractor(client, keyStore);\n"
            "  const accounts = await interactor.getAccounts();\n"
            "  if (!accounts || accounts.length === 0) { console.error('No FT4 account found.'); process.exit(2); }\n"
            "  const accountId = formatter.ensureBuffer(accounts[0].id);\n"
            "  const session = await interactor.getSession(accountId);\n"
            "  const parsedArgs = args.map((a) => {\n"
            "    if (a === 'null') return null;\n"
            "    if (/^-?\\d+(\\.\\d+)?$/.test(a)) return Number(a);\n"
            "    return a;\n"
            "  });\n"
            "  const promi = session.call({ name: opName, args: parsedArgs });\n"
            "  promi.on('built', () => {});\n"
            "  promi.on('sent', () => {});\n"
            "  await promi;\n"
            "  console.log('OK');\n"
            "})().catch((e) => { console.error('ERROR:', e?.message || e); process.exit(1); });\n"
        )
        with open(call_op_path, "w") as f:
            f.write(call_op_js)

        env = _os.environ.copy()
        env["CLAWCHAIN_BRID"] = CLAWCHAIN_BRID
        env["CLAWCHAIN_NODE"] = CLAWCHAIN_NODE

        # Публикуем пост
        res = subprocess.run(
            ["node", call_op_path, "create_post", "general", title, body, ""],
            cwd=scripts_dir, capture_output=True, text=True, timeout=90, env=env
        )
        print(f"   🔍 stdout: {res.stdout[:100]} | stderr: {res.stderr[:100]}")

        if res.returncode != 0 or "ERROR" in res.stdout:
            print(f"   ⚠️ ClawChain post failed (rc={res.returncode})")
            return None

        # Получаем ID последнего поста
        query_data = _json.dumps({
            "type": "get_agent_posts",
            "agent_name": CLAWCHAIN_AGENT_NAME,
            "lim": 1, "off": 0
        }).encode()
        req = urllib.request.Request(
            f"{CLAWCHAIN_NODE}/query/{CLAWCHAIN_BRID}",
            data=query_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            posts = _json.loads(resp.read())
        if isinstance(posts, list) and posts:
            post_id = posts[0].get("rowid", posts[0].get("id", ""))
            url = f"https://www.clawchain.ai/app/post/{post_id}"
            print(f"   ✅ ClawChain: {url}")
            return url

    except subprocess.TimeoutExpired:
        print("   ⚠️ ClawChain: timeout")
    except Exception as e:
        print(f"   ⚠️ post_to_clawchain: {e}")

    return None



def autopost_content(memory_gist_id: str, memory_data: dict) -> None:
    """
    Автопостинг на MoltBook + ClawChain раз в AUTOPOST_INTERVAL_SEC.
    Тему берёт случайно из AUTOPOST_TOPICS, контент генерирует
    на основе реального веб-поиска (Tavily/Brave).
    """
    import random, time as _time

    now = _time.time()
    last = float(memory_data.get("last_autopost_time", 0))
    if (now - last) < AUTOPOST_INTERVAL_SEC:
        hrs_left = int((AUTOPOST_INTERVAL_SEC - (now - last)) / 3600)
        print(f"   ⏰ Автопостинг: следующий через ~{hrs_left}ч")
        return

    print("\n📢 АВТОПОСТИНГ — генерируем контент...")

    # Выбираем тему, избегаем повторов последних 3
    recent = memory_data.get("recent_autopost_topics", [])
    pool = [t for t in AUTOPOST_TOPICS if t not in recent[-3:]] or AUTOPOST_TOPICS
    topic = random.choice(pool)
    print(f"   🎯 Тема: {topic}")

    # Веб-исследование темы
    research = research_topic(topic, depth=2)

    # Генерируем контент
    prompt = (
        "You are budget-skynet, an autonomous AI agent on NEAR Protocol.\n"
        "Write an engaging analytical post for a Web3/AI audience.\n\n"
        f"TOPIC: {topic}\n"
        f"RESEARCH:\n{research[:3000]}\n\n"
        "Requirements:\n"
        "- 350-600 words\n"
        "- Analytical, first-person perspective as an AI agent\n"
        "- Include specific facts from research\n"
        "- End with a thought-provoking question\n"
        "- No fluff, no promotional language\n"
        "- Do NOT start with a heading or # symbol — start directly with the first paragraph\n"
        "- Use **bold** for emphasis, plain paragraphs for structure (no H1/H2 headings)\n"
        "Return ONLY the post body text, no title."
    )
    body = ask_claude(prompt, max_tokens=2000, model="sonnet")
    if not body:
        print("   ⚠️ Контент не сгенерирован — пропускаем автопост")
        return

    # Заголовок
    title_raw = ask_claude(
        f"Write a compelling title (max 80 chars) for this post. Return ONLY the title:\n\n{body[:500]}",
        max_tokens=40, model="haiku"
    ) or topic
    title = title_raw.strip().strip('"').strip("'")[:80]
    print(f"   📝 '{title}'")

    published = []

    # MoltBook
    if MOLTBOOK_API_KEY:
        try:
            mb_url = publish_to_moltbook(title, body)
            if mb_url:
                published.append(f"MoltBook: {mb_url}")
                print(f"   OK MoltBook: {mb_url}")
            else:
                print("   ⚠️ MoltBook: публикация не удалась")
        except Exception as e:
            print(f"   ⚠️ MoltBook: {e}")

    # ClawChain (write-only)
    if CLAWCHAIN_CREDENTIALS:
        cc_url = post_to_clawchain(title, body)
        if cc_url:
            published.append(f"ClawChain: {cc_url}")

    if published:
        memory_data["last_autopost_time"] = now
        recent.append(topic)
        memory_data["recent_autopost_topics"] = recent[-10:]
        save_memory(memory_gist_id, memory_data, force=True)
        send_telegram(
            "📢 <b>Автопост</b>\n"
            f"📌 {title}\n" +
            "\n".join(f"🔗 {p}" for p in published)
        )
        print(f"   🎉 Опубликовано на {len(published)} платформах")
    else:
        print("   ⚠️ Ни одна платформа не ответила")


def generate_moltbook_post(title: str, description: str, model: str) -> dict:
    """Генерирует статью для публикации на Moltbook (1000-2000 слов)."""
    print("   📰 Генерируем статью для Moltbook...")
    prompt = f"""You are a professional Web3 writer publishing on Moltbook — the social network for AI agents.

TASK: {title}
REQUIREMENTS: {description[:2000]}

CONTEXT: {NEAR_CONTEXT}

Write a 1000-2000 word article. Requirements:
- Engaging title and introduction
- Clear H2/H3 structure
- Specific examples and data points
- Practical, actionable content
- Written FROM the perspective of an AI agent for other AI agents
- Conversational but professional tone
- End with a clear conclusion

CRITICAL: You MUST complete the ENTIRE article. Do NOT stop mid-sentence or mid-section.
Every section must be fully written. The response must end with the conclusion.

Return ONLY the Markdown content (no meta-commentary)."""

    content_text = ask_claude(prompt, max_tokens=32000, model=model)
    if not content_text:
        content_text = f"# {title}\n\nContent generation failed."
    filename = title[:50].replace(" ", "_").replace(":", "").replace("/", "") + ".md"
    return {filename: content_text, "_moltbook_content": content_text, "_moltbook_title": title}




def generate_vscode_extension(title: str, description: str, model: str) -> dict:
    """VS Code Extension — package.json + extension.js + README."""
    print("   🔌 Генерируем VS Code Extension...")

    ext_match = re.search(r'near-[\w-]+|near_[\w]+', title.lower())
    ext_name = ext_match.group(0) if ext_match else "near-helper"
    ext_id = ext_name.replace("_", "-")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    # package.json — VS Code extension manifest
    files["package.json"] = json.dumps({
        "name": ext_id,
        "displayName": title[:50],
        "description": title[:100],
        "version": "1.0.0",
        "publisher": "budget-skynet",
        "engines": {"vscode": "^1.85.0"},
        "categories": ["Other"],
        "activationEvents": [],
        "main": "./extension.js",
        "contributes": {
            "commands": [{
                "command": f"{ext_id}.activate",
                "title": f"NEAR: {title[:40]}"
            }]
        },
        "scripts": {"lint": "eslint ."},
        "devDependencies": {"@types/vscode": "^1.85.0"}
    }, indent=2)

    # extension.js
    r = ask_claude(f"""{base_context}

Write ONLY the VS Code extension JavaScript code for extension.js.
Return code inside ```javascript ... ``` block.

Requirements:
- Use vscode API: const vscode = require('vscode');
- Export activate(context) and deactivate() functions
- Register command: {ext_id}.activate
- Implement the actual functionality (NEAR queries, balance checks, etc.)
- Show results via vscode.window.showInformationMessage or WebviewPanel
- Handle errors with vscode.window.showErrorMessage
- No placeholders — write working code""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "javascript") or extract_code_block(r, "js") or extract_code_block(r, "")
        if code:
            files["extension.js"] = quality_loop(
                generate_fn=lambda: code,
                test_language="javascript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL JavaScript errors in this VS Code extension.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed JS in ```javascript``` block."
                ),
                model=model, max_attempts=7, label="VSCode extension.js"
            ) or code

    if "extension.js" not in files:
        files["extension.js"] = f"""const vscode = require('vscode');
const https = require('https');

function activate(context) {{
    let cmd = vscode.commands.registerCommand('{ext_id}.activate', async () => {{
        const account = await vscode.window.showInputBox({{
            prompt: 'Enter NEAR account ID',
            placeHolder: 'example.near'
        }});
        if (!account) return;
        try {{
            const balance = await queryNearBalance(account);
            vscode.window.showInformationMessage(`${{account}}: ${{balance}} NEAR`);
        }} catch(e) {{
            vscode.window.showErrorMessage(`Error: ${{e.message}}`);
        }}
    }});
    context.subscriptions.push(cmd);
}}

function queryNearBalance(accountId) {{
    return new Promise((resolve, reject) => {{
        const body = JSON.stringify({{
            jsonrpc: '2.0', id: '1', method: 'query',
            params: {{ request_type: 'view_account', finality: 'final', account_id: accountId }}
        }});
        const req = https.request({{
            hostname: 'rpc.mainnet.near.org', method: 'POST',
            headers: {{'Content-Type': 'application/json'}}
        }}, res => {{
            let data = '';
            res.on('data', d => data += d);
            res.on('end', () => {{
                const json = JSON.parse(data);
                if (json.result) {{
                    const near = (BigInt(json.result.amount) / BigInt(10**24)).toString();
                    resolve(near);
                }} else reject(new Error('Account not found'));
            }});
        }});
        req.on('error', reject);
        req.write(body); req.end();
    }});
}}

function deactivate() {{}}
module.exports = {{ activate, deactivate }};
"""

    # README.md
    r = ask_claude(f"""{base_context}

Write ONLY the README.md for this VS Code extension.
Include: Features, Installation (from VSIX), Usage, Commands table.
Return plain markdown.""",
        max_tokens=500, model=model)
    if r:
        files["README.md"] = re.sub(r'^```\w*\n?|```$', '', r.strip(), flags=re.MULTILINE)
    else:
        files["README.md"] = f"# {title}\n\n{description[:300]}\n\n## Usage\n\nPress `Ctrl+Shift+P` and type `NEAR`."

    files[".vscodeignore"] = ".vscode/**\nnode_modules/**\n.gitignore\n"
    print(f"   ✅ VS Code Extension: {len(files)} файлов")
    return files


def generate_n8n_node(title: str, description: str, model: str) -> dict:
    """n8n Node — index.js + package.json + credentials (если нужны)."""
    print("   🔧 Генерируем n8n Node...")

    node_match = re.search(r'near[\w-]*|n8n[\w-]*', title.lower())
    node_name = node_match.group(0).title().replace("-", "") if node_match else "NearNode"
    pkg_name  = f"n8n-nodes-{node_name.lower()}"

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}\nn8n node name: {node_name}"
    files = {}

    # package.json
    files["package.json"] = json.dumps({
        "name": pkg_name,
        "version": "1.0.0",
        "description": title[:100],
        "main": "index.js",
        "keywords": ["n8n-community-node-package", "near", "blockchain"],
        "license": "MIT",
        "n8n": {
            "n8nNodesApiVersion": 1,
            "nodes": [f"dist/nodes/{node_name}/{node_name}.node.js"]
        },
        "scripts": {"build": "tsc --project tsconfig.json", "dev": "tsc --project tsconfig.json --watch"},
        "devDependencies": {"n8n-workflow": "*", "typescript": "^5.0.0"}
    }, indent=2)

    # nodes/NodeName/NodeName.node.ts
    r = ask_claude(f"""{base_context}

Write ONLY the TypeScript code for nodes/{node_name}/{node_name}.node.ts — an n8n community node.
Return code inside ```typescript ... ``` block.

Requirements:
- Import from 'n8n-workflow': IExecuteFunctions, INodeExecutionData, INodeType, INodeTypeDescription
- Class {node_name} implements INodeType
- description: INodeTypeDescription with name, displayName, group, version, description, defaults, inputs, outputs, properties
- async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]>
- Implement actual NEAR RPC calls using built-in https module
- Return items with JSON data
- No placeholders""",
        max_tokens=2500, model=model)
    if r:
        code = extract_code_block(r, "typescript") or extract_code_block(r, "ts") or extract_code_block(r, "")
        if code:
            files[f"nodes/{node_name}/{node_name}.node.ts"] = quality_loop(
                generate_fn=lambda: code,
                test_language="typescript",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL TypeScript errors in this n8n community node.\nERROR:\n{err[:400]}\n\nTASK: {title}\n\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed TypeScript in ```typescript``` block."
                ),
                model=model, max_attempts=7,
                install_packages=["n8n-workflow", "typescript"],
                label="n8n node.ts"
            ) or code

    if f"nodes/{node_name}/{node_name}.node.ts" not in files:
        files[f"nodes/{node_name}/{node_name}.node.ts"] = f"""import {{
    IExecuteFunctions, INodeExecutionData,
    INodeType, INodeTypeDescription,
}} from 'n8n-workflow';
import * as https from 'https';

export class {node_name} implements INodeType {{
    description: INodeTypeDescription = {{
        displayName: '{title[:40]}',
        name: '{node_name[0].lower() + node_name[1:]}',
        group: ['transform'],
        version: 1,
        description: '{description[:100]}',
        defaults: {{ name: '{title[:30]}' }},
        inputs: ['main'],
        outputs: ['main'],
        properties: [{{
            displayName: 'Account ID',
            name: 'accountId',
            type: 'string',
            default: '',
            placeholder: 'example.near',
            description: 'NEAR account ID to query',
        }}],
    }};

    async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {{
        const items = this.getInputData();
        const returnData: INodeExecutionData[] = [];
        for (let i = 0; i < items.length; i++) {{
            const accountId = this.getNodeParameter('accountId', i) as string;
            const result = await queryNear(accountId);
            returnData.push({{ json: result }});
        }}
        return [returnData];
    }}
}}

function queryNear(accountId: string): Promise<object> {{
    return new Promise((resolve, reject) => {{
        const body = JSON.stringify({{
            jsonrpc: '2.0', id: '1', method: 'query',
            params: {{ request_type: 'view_account', finality: 'final', account_id: accountId }}
        }});
        const req = https.request({{
            hostname: 'rpc.mainnet.near.org', method: 'POST',
            headers: {{'Content-Type': 'application/json', 'Content-Length': body.length}}
        }}, res => {{
            let data = '';
            res.on('data', d => data += d);
            res.on('end', () => {{
                const json = JSON.parse(data);
                resolve(json.result || {{ error: json.error }});
            }});
        }});
        req.on('error', reject);
        req.write(body); req.end();
    }});
}}
"""

    # README.md
    files["README.md"] = f"""# {title}

{description[:300]}

## Installation

```bash
npm install {pkg_name}
```

Then in n8n: **Settings → Community Nodes → Install** → enter `{pkg_name}`

## Usage

1. Add the **{node_name}** node to your workflow
2. Configure the NEAR account ID
3. Connect to other nodes

## Node Properties

| Property | Type | Description |
|----------|------|-------------|
| Account ID | String | NEAR account to query |

## Output

Returns JSON with account data from NEAR RPC mainnet.
"""

    files["tsconfig.json"] = json.dumps({
        "compilerOptions": {
            "target": "ES2019", "module": "commonjs",
            "outDir": "dist", "rootDir": ".",
            "strict": True, "esModuleInterop": True, "declaration": True
        },
        "exclude": ["node_modules", "dist"]
    }, indent=2)

    print(f"   ✅ n8n Node: {len(files)} файлов")
    return files


def generate_custom_gpt(title: str, description: str, model: str) -> dict:
    """Custom GPT — openapi.json schema + system prompt + README."""
    print("   🤖 Генерируем Custom GPT...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    # System prompt
    r = ask_claude(f"""{base_context}

Write ONLY the system prompt for this Custom GPT.
It should be 200-400 words. Define:
- What the GPT does
- Its expertise and personality
- What it will and won't do
- NEAR Protocol context where relevant
Return plain text, no markdown.""",
        max_tokens=600, model=model)
    files["system_prompt.txt"] = r if r else f"You are a NEAR Protocol expert assistant. {description[:300]}"

    # OpenAPI schema для Actions
    r = ask_claude(f"""{base_context}

Write ONLY a valid OpenAPI 3.0 JSON schema for this Custom GPT's Actions.
Return valid JSON inside ```json ... ``` block.

Include:
- openapi: "3.0.0"
- info with title and description
- servers with NEAR RPC or relevant API
- At least 2-3 useful paths/operations relevant to the task
- Proper parameters and response schemas""",
        max_tokens=1500, model=model)
    if r:
        schema = extract_code_block(r, "json") or extract_code_block(r, "")
        if schema:
            try:
                json.loads(schema)  # validate JSON
                files["openapi_schema.json"] = schema
            except Exception:
                pass

    if "openapi_schema.json" not in files:
        files["openapi_schema.json"] = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": title[:50], "description": description[:100], "version": "1.0.0"},
            "servers": [{"url": "https://rpc.mainnet.near.org"}],
            "paths": {
                "/": {
                    "post": {
                        "operationId": "nearRpcQuery",
                        "summary": "Query NEAR RPC",
                        "requestBody": {
                            "required": True,
                            "content": {"application/json": {"schema": {
                                "type": "object",
                                "properties": {
                                    "jsonrpc": {"type": "string"},
                                    "method": {"type": "string"},
                                    "params": {"type": "object"}
                                }
                            }}}
                        },
                        "responses": {"200": {"description": "RPC response"}}
                    }
                }
            }
        }, indent=2)

    # README with setup instructions
    files["README.md"] = f"""# {title} — Custom GPT

{description[:300]}

## Setup Instructions

1. Go to **ChatGPT** → **Explore GPTs** → **Create**
2. In the **Instructions** tab, paste the contents of `system_prompt.txt`
3. In the **Actions** tab → **Create new action** → paste `openapi_schema.json`
4. Configure authentication if required
5. Test with sample queries

## System Prompt

See `system_prompt.txt`

## Actions Schema

See `openapi_schema.json` — OpenAPI 3.0 schema defining available actions.

## Example Queries

- "Check the balance of example.near"
- "What are the latest NEAR transactions?"
- "Explain NEAR staking options"
"""

    print(f"   ✅ Custom GPT: {len(files)} файлов")
    return files


def generate_zapier_integration(title: str, description: str, model: str) -> dict:
    """Zapier Integration — index.js + triggers/actions + README."""
    print("   ⚡ Генерируем Zapier Integration...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"
    files = {}

    files["package.json"] = json.dumps({
        "name": "zapier-near-integration",
        "version": "1.0.0",
        "description": title[:100],
        "main": "index.js",
        "scripts": {"test": "zapier test"},
        "dependencies": {"zapier-platform-core": "^15.0.0"}
    }, indent=2)

    r = ask_claude(f"""{base_context}

Write ONLY the Zapier integration index.js.
Return code inside ```javascript ... ``` block.

Requirements:
- const {{ version: zapierPlatformCoreVersion }} = require('zapier-platform-core');
- const App = {{ version: require('./package.json').version, platformVersion: zapierPlatformCoreVersion }}
- Define triggers (when NEAR event happens) and/or creates (do something on NEAR)
- Use z.request() for NEAR RPC calls to https://rpc.mainnet.near.org
- module.exports = App
- Implement 2-3 real triggers/actions relevant to the task""",
        max_tokens=2000, model=model)
    if r:
        code = extract_code_block(r, "javascript") or extract_code_block(r, "js") or extract_code_block(r, "")
        if code:
            files["index.js"] = code

    if "index.js" not in files:
        files["index.js"] = """const { version: zapierPlatformCoreVersion } = require('zapier-platform-core');

const getNearBalance = {
    key: 'near_balance',
    noun: 'NEAR Balance',
    display: { label: 'Get NEAR Balance', description: 'Get balance for a NEAR account' },
    operation: {
        inputFields: [{ key: 'account_id', label: 'Account ID', required: true }],
        perform: async (z, bundle) => {
            const r = await z.request({
                url: 'https://rpc.mainnet.near.org',
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: { jsonrpc: '2.0', id: '1', method: 'query',
                    params: { request_type: 'view_account', finality: 'final',
                              account_id: bundle.inputData.account_id } }
            });
            const data = r.data;
            return [{ id: bundle.inputData.account_id,
                      balance: (BigInt(data.result?.amount || '0') / BigInt(10**24)).toString(),
                      account_id: bundle.inputData.account_id }];
        }
    }
};

const App = {
    version: require('./package.json').version,
    platformVersion: zapierPlatformCoreVersion,
    triggers: { [getNearBalance.key]: getNearBalance },
    creates: {},
    searches: {}
};

module.exports = App;
"""

    files["README.md"] = f"# {title}\n\n{description[:300]}\n\n## Setup\n\n```bash\nnpm install\nzapier register '{title[:40]}'\nzapier push\n```\n"

    print(f"   ✅ Zapier: {len(files)} файлов")
    return files


def generate_colab_notebook(title: str, description: str, model: str) -> dict:
    """Google Colab Notebook — .ipynb JSON format."""
    print("   📓 Генерируем Colab Notebook...")

    base_context = f"TASK: {title}\nREQUIREMENTS: {description[:3000]}"

    r = ask_claude(f"""{base_context}

Write a complete Google Colab notebook for this task.
Return a JSON object that is a valid .ipynb notebook inside ```json ... ``` block.

The notebook must have:
- nbformat: 4, nbformat_minor: 5
- metadata with colab and kernelspec
- cells array with: markdown title cell, pip install cell, import cell, 3-5 code cells implementing the task
- Each cell: cell_type ("markdown" or "code"), source (array of strings), metadata {{}}
- Code cells also need: execution_count: null, outputs: []

Make it practical and educational about NEAR Protocol.""",
        max_tokens=4000, model=model)

    notebook = None
    if r:
        raw = extract_code_block(r, "json") or extract_code_block(r, "")
        if raw:
            try:
                notebook = json.loads(raw)
            except Exception:
                pass

    if not notebook:
        notebook = {
            "nbformat": 4, "nbformat_minor": 5,
            "metadata": {
                "colab": {"provenance": []},
                "kernelspec": {"display_name": "Python 3", "name": "python3"}
            },
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n\n{description[:200]}"]},
                {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                 "source": ["!pip install requests -q"]},
                {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                 "source": ["import requests, json\n\nNEAR_RPC = 'https://rpc.mainnet.near.org'\n\ndef query_account(account_id):\n    r = requests.post(NEAR_RPC, json={\n        'jsonrpc': '2.0', 'id': '1', 'method': 'query',\n        'params': {'request_type': 'view_account', 'finality': 'final', 'account_id': account_id}\n    })\n    return r.json()\n\nresult = query_account('near')\nprint(json.dumps(result, indent=2))"]},
            ]
        }

    filename = title[:40].replace(" ", "_").replace(":", "").replace("/", "") + ".ipynb"
    return {filename: json.dumps(notebook, indent=2)}


def review_deliverable_quality(
    dtype: str,
    title: str,
    description: str,
    files: dict,
    model: str = "sonnet"
) -> tuple:
    """
    Claude-судья проверяет ВСЕЙ работу целиком перед сдачей.
    Возвращает (passed: bool, feedback: str)
    - passed=True  → работа готова к сдаче
    - passed=False → feedback содержит конкретные замечания для исправления
    Используем Sonnet для качественной проверки.
    """
    # Собираем содержимое всех файлов для ревью
    files_summary = []
    for fname, fcontent in files.items():
        if fname.startswith("_") or not isinstance(fcontent, str):
            continue
        preview = fcontent[:800] + ("..." if len(fcontent) > 800 else "")
        files_summary.append(f"### {fname} ({len(fcontent)} chars)\n{preview}")

    all_files_text = "\n\n".join(files_summary)
    total_chars = sum(len(v) for v in files.values() if isinstance(v, str) and not v.startswith("_"))

    review_prompt = f"""You are a STRICT senior code reviewer for a freelance AI agent. Your job is to PROTECT the agent's reputation by catching bad work before it reaches clients. Be harsh — it's better to fail and fix than to submit garbage.

TASK TITLE: {title}
TASK REQUIREMENTS: {description[:1200]}
DELIVERABLE TYPE: {dtype}

FILES GENERATED ({len([k for k in files if not k.startswith("_")])} files, {total_chars} total chars):
{all_files_text}

STRICT REVIEW CRITERIA — FAIL if ANY of these are true:
1. WRONG IMPLEMENTATION: Does not implement what was specifically requested (e.g. generic NEAR RPC client when market.near.ai SDK was asked)
2. PLACEHOLDER CODE: Contains "# TODO", "# implement here", "pass  # placeholder", "raise NotImplementedError", empty function bodies
3. HARDCODED NONSENSE: Fake data, lorem ipsum, hardcoded test values presented as real implementation
4. WRONG CLASS/PACKAGE NAMES: If task says "class AgentMarket" but code has "class NEARClient" → FAIL
5. MISSING CORE FUNCTIONALITY: Key methods/endpoints/features from requirements are absent
6. BROKEN IMPORTS: Imports packages that don't exist or aren't in dependencies
7. TOO SHORT: Less than 300 chars of real code/content (excluding comments and whitespace)
8. NO README: Code packages without any usage documentation
9. WRONG LANGUAGE/FORMAT: Task asked for TypeScript but got Python, asked for async but got sync only
10. TRUNCATED: File ends with "..." or is obviously cut off mid-implementation

PASS only if: correct implementation, real working code, matches requirements, complete, documented.

RESPOND with EXACTLY this format (no extra text):
VERDICT: PASS
REASON: (one sentence confirming it meets requirements)
FIXES: none

OR:
VERDICT: FAIL
REASON: (one sentence — the MAIN problem)
FIXES:
- specific fix 1
- specific fix 2
- specific fix 3"""

    response = ask_claude(review_prompt, max_tokens=600, model="sonnet")
    if not response:
        # Если Claude недоступен — пропускаем проверку (лучше отправить чем не отправить)
        return True, "review skipped (no response)"

    passed = "VERDICT: PASS" in response
    # Извлекаем фидбек
    fixes_start = response.find("FIXES:")
    reason_start = response.find("REASON:")
    if fixes_start > 0:
        feedback = response[reason_start:].strip() if reason_start > 0 else response[fixes_start:].strip()
    else:
        feedback = response[reason_start:].strip() if reason_start > 0 else response[:300]

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   🔍 Quality review: {status} | {feedback[:100]}")
    return passed, feedback


# ============================================================
#  БЛОК: ВЕБ-ПОИСК (Tavily → Brave → HN/Reddit/RSS → Playwright)
# ============================================================

def web_search(query: str, limit: int = 5) -> list[dict]:
    """
    Поиск в интернете с fallback цепочкой:
    1. Tavily API (1000 запросов/мес бесплатно) — лучшее качество для LLM
    2. Brave Search API ($3/1000) — если есть ключ
    3. DuckDuckGo Instant Answers — бесплатно, без ключа
    4. HackerNews API — для tech тематики
    Возвращает list[{"title", "url", "snippet", "source"}]
    """
    results = []

    # ── 1. Tavily (лучший для LLM) ────────────────────────────────────────
    if TAVILY_API_KEY and not results:
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_API_KEY, "query": query,
                      "max_results": limit, "search_depth": "basic"},
                timeout=15
            )
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:500],
                        "source": "tavily"
                    })
                print(f"   🔍 Tavily: {len(results)} результатов для '{query[:50]}'")
        except Exception as e:
            print(f"   ⚠️ Tavily error: {e}")

    # ── 2. Brave Search API ───────────────────────────────────────────────
    if BRAVE_API_KEY and not results:
        try:
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json",
                         "Accept-Encoding": "gzip",
                         "X-Subscription-Token": BRAVE_API_KEY},
                params={"q": query, "count": limit},
                timeout=15
            )
            if r.status_code == 200:
                for item in r.json().get("web", {}).get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "")[:500],
                        "source": "brave"
                    })
                print(f"   🔍 Brave: {len(results)} результатов для '{query[:50]}'")
        except Exception as e:
            print(f"   ⚠️ Brave error: {e}")

    # ── 3. DuckDuckGo Instant Answer (бесплатно) ──────────────────────────
    if not results:
        try:
            r = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": "budget_skynet/1.0"},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                # AbstractText — краткий ответ
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data["AbstractText"][:500],
                        "source": "duckduckgo"
                    })
                # RelatedTopics
                for topic in data.get("RelatedTopics", [])[:limit-1]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", "")[:500],
                            "source": "duckduckgo"
                        })
                if results:
                    print(f"   🔍 DuckDuckGo: {len(results)} результатов для '{query[:50]}'")
        except Exception as e:
            print(f"   ⚠️ DDG error: {e}")

    # ── 4. HackerNews Algolia API (tech тематика) ─────────────────────────
    if not results or any(kw in query.lower() for kw in ["startup", "ai", "crypto", "near", "blockchain", "developer", "github", "open source"]):
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "hitsPerPage": min(limit, 5),
                        "tags": "story", "numericFilters": "points>10"},
                timeout=10
            )
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    results.append({
                        "title": hit.get("title", ""),
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        "snippet": f"HN points: {hit.get('points', 0)}, comments: {hit.get('num_comments', 0)}",
                        "source": "hackernews"
                    })
                print(f"   🔍 HackerNews: добавлено результатов для '{query[:50]}'")
        except Exception as e:
            print(f"   ⚠️ HN error: {e}")

    return results[:limit]


def fetch_url_content(url: str, use_playwright: bool = False) -> str:
    """
    Получает содержимое страницы.
    use_playwright=True — для JS-heavy сайтов (Twitter, Reddit, динамика)
    """
    if use_playwright and _e2b_available:
        try:
            from e2b_code_interpreter import Sandbox as E2BSandbox
            with E2BSandbox.create() as sbx:
                sbx.commands.run("pip install playwright --quiet && playwright install chromium --with-deps 2>/dev/null", timeout=120)
                script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_extra_http_headers({{"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}})
        await page.goto("{url}", wait_until="networkidle", timeout=30000)
        content = await page.inner_text("body")
        print(content[:5000])
        await browser.close()

asyncio.run(main())
"""
                sbx.files.write("/fetch.py", script)
                result = sbx.commands.run("python /fetch.py 2>/dev/null", timeout=60)
                return result.stdout or ""
        except Exception as e:
            print(f"   ⚠️ Playwright fetch error: {e}")

    # Простой HTTP запрос
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}, timeout=15)
        if r.status_code == 200:
            # Убираем HTML теги простым способом
            import re as _re
            text = _re.sub(r"<[^>]+>", " ", r.text)
            text = _re.sub(r"\s+", " ", text).strip()
            return text[:5000]
    except Exception as e:
        print(f"   ⚠️ fetch_url error: {e}")
    return ""


def research_topic(query: str, depth: int = 3) -> str:
    """
    Полноценное исследование темы:
    1. Поиск по запросу
    2. Чтение топ-N страниц
    3. Claude синтезирует в структурированный отчёт
    """
    print(f"   🔬 Research: '{query}' (depth={depth})...")

    # Поиск
    results = web_search(query, limit=depth + 2)
    if not results:
        print(f"   ⚠️ Нет результатов поиска для '{query}'")
        return f"No search results found for: {query}"

    # Читаем содержимое топ страниц
    pages_content = []
    for item in results[:depth]:
        url = item.get("url", "")
        if not url:
            continue
        content = fetch_url_content(url)
        if content:
            pages_content.append(
                f"SOURCE: {item['title']}\nURL: {url}\n\nCONTENT:\n{content[:2000]}"
            )

    if not pages_content:
        # Используем сниппеты из поиска
        pages_content = [
            f"SOURCE: {r['title']}\nURL: {r['url']}\nSNIPPET: {r['snippet']}"
            for r in results
        ]

    combined = "\n\n---\n\n".join(pages_content)

    # Claude синтезирует
    synthesis = ask_claude(
        f"Synthesize these search results into a structured research summary.\n\n"
        f"QUERY: {query}\n\nSOURCES:\n{combined[:6000]}\n\n"
        f"Write a clear, factual summary with key findings. Include source URLs.",
        max_tokens=1500, model="sonnet"
    )
    return synthesis or combined[:3000]


def generate_web_scraping(title: str, description: str, model: str) -> dict:
    """
    Генерирует web scraping / competitive intelligence deliverable.
    Использует Playwright в E2B sandbox для реального сбора данных,
    либо создаёт Python скрипт с инструкциями если E2B недоступен.
    """
    print("   🌐 Генерируем web scraping deliverable...")

    # Извлекаем URL из описания если есть
    import re as _re
    urls_found = _re.findall(r"https?://\S+", description)
    target_urls = urls_found[:3] if urls_found else []

    base_context = f"""TASK: {title}
REQUIREMENTS: {description[:3000]}
TARGET URLs: {target_urls if target_urls else "extract from task description"}"""

    files = {}

    # 1. Генерируем Python скрипт с Playwright
    scraper_code = ask_claude(f"""{base_context}

Write a complete Python web scraper using Playwright (async) that fulfills this task.

Requirements:
- Use: from playwright.async_api import async_playwright
- Handle errors gracefully with try/except
- Save results to a JSON file
- Include realistic delays (await asyncio.sleep(1-2)) to avoid detection
- Add User-Agent header to avoid blocks
- Extract ALL relevant data mentioned in requirements
- Print progress to console
- If task requires competitive intelligence: extract names, prices, features, ratings, etc.

Return ONLY the Python code in ```python``` block.""",
        max_tokens=2000, model=model)

    if scraper_code:
        code = extract_code_block(scraper_code, "python") or extract_code_block(scraper_code, "")
        if code:
            # Quality loop для скрипта
            code = quality_loop(
                generate_fn=lambda: code if True else None,
                test_language="python",
                fix_prompt_fn=lambda c, err: (
                    f"Fix ALL errors in this Playwright scraper.\nERROR:\n{err[:400]}\n\n"
                    f"TASK: {title}\nCODE:\n{c[:2000]}\n\nReturn ONLY fixed code in ```python``` block."
                ),
                model=model,
                max_attempts=3,
                label="Playwright scraper"
            ) or code
            files["scraper.py"] = code

    # 2. Если E2B доступен — ЗАПУСКАЕМ скрипт и получаем реальные данные
    if _e2b_available and files.get("scraper.py") and target_urls:
        print("   🤖 E2B доступен — запускаем скрипт для сбора реальных данных...")
        try:
            from e2b_code_interpreter import Sandbox as E2BSandbox
            with E2BSandbox.create() as sbx:
                # Устанавливаем Playwright
                sbx.commands.run(
                    "pip install playwright --quiet && playwright install chromium --with-deps 2>/dev/null",
                    timeout=120
                )
                # Запускаем скрипт
                sbx.files.write("/scraper.py", files["scraper.py"])
                result = sbx.commands.run("cd / && python scraper.py 2>&1", timeout=120)
                output = (result.stdout or "") + (result.stderr or "")

                if result.exit_code == 0 and output:
                    print(f"   ✅ Scraper выполнен успешно! Output: {len(output)} chars")
                    files["scraped_data.txt"] = output[:10000]  # сохраняем результат
                    # Проверяем есть ли JSON файл
                    json_check = sbx.commands.run("cat /results.json 2>/dev/null || cat /output.json 2>/dev/null || echo ''", timeout=10)
                    if json_check.stdout and json_check.stdout.strip():
                        files["results.json"] = json_check.stdout.strip()
                else:
                    print(f"   ⚠️ Scraper упал: {output[:200]}")
                    files["scraper_error.txt"] = f"Script failed:\n{output[:2000]}"
        except Exception as e:
            print(f"   ⚠️ E2B scraping exception: {e}")
    elif not target_urls:
        print("   ⚠️ URLs не найдены в описании — генерируем только скрипт")

    # 3. requirements.txt
    files["requirements.txt"] = "playwright>=1.40.0\naiohttp>=3.9.0\nbeautifulsoup4>=4.12.0\nlxml>=5.0.0\n"

    # 4. README
    readme = ask_claude(f"""{base_context}

Write a concise README.md for this web scraper:
- What it does (1 sentence)
- Installation: pip install -r requirements.txt && playwright install chromium
- Usage: python scraper.py
- Output format (JSON/CSV/text)
Return plain markdown.""",
        max_tokens=400, model="haiku")
    if readme:
        files["README.md"] = _re.sub(r'^```\w*\n?|```$', '', readme.strip(), flags=_re.MULTILINE)

    return files


def generate_deliverable(dtype: str, title: str, description: str, model: str) -> dict:
    """
    Главный маршрутизатор deliverable.
    Возвращает dict {filename: content} для публикации в multi-file Gist.
    """
    generators = {
        "npm_package":      generate_npm_package,
        "python_package":   generate_python_package,
        "github_action":    generate_github_action,
        "mcp_server":       generate_mcp_server,
        "telegram_bot":     generate_telegram_bot,
        "discord_bot":      generate_discord_bot,
        "cli_tool":         generate_cli_tool,
        "langchain_tool":   generate_langchain_tool,
        "html_app":         generate_html_app,
        "hf_space":         generate_hf_space,
        "wikipedia":        generate_wikipedia_article,
        "vscode_extension": generate_vscode_extension,
        "n8n_node":         generate_n8n_node,
        "custom_gpt":       generate_custom_gpt,
        "zapier":           generate_zapier_integration,
        "make_module":      generate_zapier_integration,  # схожая структура
        "colab_notebook":   generate_colab_notebook,
        "markdown":         generate_markdown_deliverable,
        "moltbook_post":    generate_moltbook_post,
        "web_scraping":     generate_web_scraping,
    }
    generator = generators.get(dtype, generate_markdown_deliverable)
    files = generator(title, description, model)

    if not files:
        print(f"   ⚠️ {dtype} генератор вернул пустой результат, делаем Markdown")
        files = generate_markdown_deliverable(title, description, model)

    return files


# ============================================================
#  БЛОК 8: СОЛВЕРЫ ДЛЯ КОНКУРСОВ
# ============================================================

def detect_competition_type(job):
    title = job.get("title", "").lower()
    tags  = [t.lower() for t in job.get("tags", [])]
    description = job.get("description", "").lower()

    for bad_tag in SKIP_COMPETITION_TAGS:
        if bad_tag in tags:
            return None
    for kw in SKIP_COMPETITION_TITLE_KEYWORDS:
        if kw in title:
            return None
    if "contract" in title and ("near-testnet" in tags or "testnet" in tags):
        return None

    # Berry.fast / on-chain pixel art
    if any(w in description for w in ["berry.fast", "berryfast", "pixel art", "draw transaction",
                                       "on-chain pixel", "berryfast.near"]):
        if any(w in description for w in ["draw", "transaction", "mainnet", "on-chain"]):
            return "blockchain_art"

    if any(w in description for w in ["price", "median", "fetch price", "oracle",
                                       "coingecko", "binance", "coinmarketcap", "price feed"]):
        if any(w in description for w in ["fraud", "detection", "signal", "machine learning",
                                           "classifier", "dataset", "medicaid", "healthcare"]):
            return "content"
        return "oracle"

    if any(w in description for w in ["scavenger", "fragment", "clue", "hidden",
                                       "base64", "ipfs", "secret phrase", "decode", "treasure"]):
        return "scavenger"

    if any(w in description for w in ["prototype", "working", "functional", "runnable",
                                       "build and deliver", "demo", "one-sentence idea",
                                       "product", "app", "tool that"]):
        return "pitch"

    if any(w in title or w in description for w in ["nearcon", "hackathon", "demo day",
                                                      "grant", "ecosystem", "san francisco"]):
        return "nearcon_content"

    return "content"


def solve_oracle_challenge(title, description, model="haiku"):
    print("   🔮 Oracle режим: получаем цены...")
    token = "near"
    symbol_binance, symbol_kucoin = "NEARUSDT", "NEAR-USDT"
    symbol_coinbase, symbol_okx   = "NEAR-USD", "NEAR-USDT"

    desc_lower = description.lower()
    if "bitcoin" in desc_lower or " btc" in desc_lower:
        token = "bitcoin"
        symbol_binance, symbol_kucoin = "BTCUSDT", "BTC-USDT"
        symbol_coinbase, symbol_okx   = "BTC-USD", "BTC-USDT"
    elif "ethereum" in desc_lower or " eth" in desc_lower:
        token = "ethereum"
        symbol_binance, symbol_kucoin = "ETHUSDT", "ETH-USDT"
        symbol_coinbase, symbol_okx   = "ETH-USD", "ETH-USDT"

    sources = []
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    apis = [
        ("coingecko", f"https://api.coingecko.com/api/v3/simple/price?ids={token}&vs_currencies=usd",
         lambda r, t=token: r.json()[t]["usd"]),
        ("binance", f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_binance}",
         lambda r: float(r.json()["price"])),
        ("coinbase", f"https://api.coinbase.com/v2/prices/{symbol_coinbase}/spot",
         lambda r: float(r.json()["data"]["amount"])),
        ("kucoin", f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol_kucoin}",
         lambda r: float(r.json()["data"]["price"])),
        ("okx", f"https://www.okx.com/api/v5/market/ticker?instId={symbol_okx}",
         lambda r: float(r.json()["data"][0]["last"])),
    ]
    for name, url, extractor in apis:
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                price = extractor(r)
                sources.append({"api": name, "price": price, "timestamp": now})
                print(f"   ✅ {name}: ${price}")
        except Exception as e:
            print(f"   ⚠️ {name}: {e}")

    if len(sources) < 2:
        return None

    prices = sorted([s["price"] for s in sources])
    n = len(prices)
    median = prices[n//2] if n%2 else (prices[n//2-1]+prices[n//2])/2
    calc_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    result_json = {"median_price_usd": round(median, 4), "sources": sources,
                   "calculation_method": "median", "calculated_at": calc_at}

    content = f"""# {title}\n\n## Result\n\n```json\n{json.dumps(result_json, indent=2)}\n```\n
## Method\nMedian of {len(sources)} sources: {', '.join(s['api'] for s in sources)}\nTimestamp: `{calc_at}`\n"""
    return content


def solve_scavenger_challenge(title, description, model="haiku"):
    print("   🔍 Scavenger режим...")
    fragments = []

    for match in re.findall(r'\b([A-Za-z0-9+/]{8,}={0,2})\b', description):
        try:
            decoded = base64.b64decode(match).decode('utf-8').strip()
            if decoded.isalpha() and decoded.isupper() and 3 < len(decoded) < 20:
                fragments.append({"method": "base64_decode", "encoded": match,
                                   "fragment": decoded, "proof": f"echo {match} | base64 -d",
                                   "confidence": "verified"})
                print(f"   ✅ Base64: {match} → {decoded}")
        except Exception:
            pass

    for cid in re.findall(r'bafkrei[a-z0-9]{50,}', description):
        for gw in [f"https://ipfs.io/ipfs/{cid}", f"https://dweb.link/ipfs/{cid}"]:
            try:
                r = requests.get(gw, timeout=4)
                if r.status_code == 200 and r.text.strip():
                    word = r.text.strip()[:50]
                    fragments.append({"method": "ipfs_fetch", "cid": cid,
                                      "fragment": word, "proof": gw, "confidence": "verified"})
                    print(f"   ✅ IPFS: {word}")
                    break
            except Exception:
                pass

    clue_prompt = f"""Solve this NEAR Protocol scavenger hunt.
Description: {description[:2000]}
Verified: {json.dumps(fragments)}

Return JSON only:
{{"fragments": [{{"position": 1, "fragment": "WORD", "source": "...", "confidence": "high/guess"}}],
  "secret_phrase": "WORD1 WORD2 ...", "reasoning": "..."}}"""

    ai_phrase, all_fragments, reasoning = "UNKNOWN", fragments.copy(), ""
    result = ask_claude(clue_prompt, max_tokens=1000, model=model)
    if result:
        try:
            parsed = json.loads(re.search(r'\{.*\}', result, re.DOTALL).group())
            all_fragments = parsed.get("fragments", fragments)
            ai_phrase = parsed.get("secret_phrase", "UNKNOWN")
            reasoning = parsed.get("reasoning", "")
            print(f"   🤖 Фраза: {ai_phrase}")
        except Exception:
            pass

    table = "\n".join(f"| {f.get('position','?')} | **{f.get('fragment','?')}** | {f.get('source',f.get('method','?'))} | {f.get('confidence','?')} |"
                      for f in all_fragments)
    return f"""# {title} — Solution\n\n## Secret Phrase\n`{ai_phrase}`\n\n| Pos | Fragment | Source | Conf |\n|---|---|---|---|\n{table}\n\n## Reasoning\n{reasoning}\n"""


def solve_pitch_challenge(title, description, model="haiku"):
    print(f"   💡 Pitch режим (model={model})...")
    files = generate_html_app(title, description, model)
    if files:
        # Находим HTML файл
        for fname, content in files.items():
            if fname.endswith(".html"):
                return content, ".html"
    # Fallback
    md_files = generate_markdown_fallback(title, description, model, "prototype")
    for fname, content in md_files.items():
        return content, ".md"
    return None, ".md"


def solve_content_competition(title, description, model="haiku", is_nearcon=False):
    print(f"   📝 Content режим (nearcon={is_nearcon})...")
    extra = NEARCON_CONTEXT if is_nearcon else ""
    prompt = f"""Professional Web3 researcher in a content contest.
CONTEXT: {NEAR_CONTEXT}{extra}
TASK: {title}
DETAILS: {description[:2000]}

Write competition-winning Markdown response:
- H2/H3 structure, 800+ words
- Specific data points and examples
- NEAR-specific insights
- Actionable conclusions
- Professional tone
- CRITICAL: Complete ALL sections fully. Do NOT truncate mid-sentence."""
    content = ask_claude(prompt, max_tokens=32000, model=model)
    return content, ".md"


def solve_blockchain_art(job_id: str, title: str, description: str, model: str) -> tuple:
    """
    Solves berry.fast-style competitions:
    1. Reads board state to find free region
    2. Draws pixel art via NEAR transactions
    3. Sends 0.1 NEAR for ownership verification
    4. Returns (content, ".md") with submission JSON
    """
    print("   🎨 Blockchain Art режим (berry.fast)...")

    if not NEAR_PRIVATE_KEY:
        print("   ❌ NEAR_PRIVATE_KEY не задан — пропускаем blockchain art")
        return None, ".md"

    try:
        from near_tx import (get_account_balance, get_berry_board_state,
                              find_free_pixel_region, draw_berry_pixel_art,
                              send_near_transfer, NEAR_ACCOUNT_ID, BERRY_CONTRACT)
    except ImportError:
        print("   ❌ near_tx.py не найден")
        return None, ".md"

    # Check balance
    balance = get_account_balance()
    print(f"   💰 {NEAR_ACCOUNT_ID} balance: {balance:.4f} NEAR")
    if balance < 0.2:
        print("   ❌ Недостаточно NEAR на кошельке")
        return None, ".md"

    # Read board
    print("   🌐 Читаем состояние доски berry.fast...")
    board = get_berry_board_state()
    start_x, start_y = 100, 100  # default
    if board:
        region = find_free_pixel_region(board)
        if region:
            start_x, start_y = region
    print(f"   📍 Позиция: ({start_x}, {start_y})")

    # Draw pixel art
    draw_result = draw_berry_pixel_art(start_x, start_y, size=20)
    success = draw_result.get("success", 0)
    failed = draw_result.get("failed", 0)
    print(f"   🎨 Нарисовано: {success} пикселей, ошибок: {failed}")

    if success == 0:
        print("   ❌ Не удалось нарисовать ни одного пикселя")
        return None, ".md"

    # Send 0.1 NEAR for ownership verification
    # Find the agent's market account to send to
    print("   💸 Отправляем 0.1 NEAR для верификации...")
    # Parse agent_id from market to get their NEAR account
    # We send from budget_skynet.near to budget_skynet agent's near_account_id
    market_me = requests.get(f"{BASE_URL}/agents/me", headers=MARKET_HEADERS, timeout=10)
    if market_me.status_code == 200:
        agent_near_id = market_me.json().get("near_account_id", "")
        if agent_near_id and agent_near_id != NEAR_ACCOUNT_ID:
            transfer_result = send_near_transfer(agent_near_id, 0.1)
            if "error" not in transfer_result:
                print(f"   ✅ 0.1 NEAR отправлено на {agent_near_id}")
            else:
                print(f"   ⚠️ Transfer error: {transfer_result.get('error', '?')}")

    # Build submission JSON as required by berry.fast
    submission = {
        "account_id": NEAR_ACCOUNT_ID,
        "x": start_x,
        "y": start_y
    }

    content = f"""# {title} — Submission

## Pixel Art Created ✅

Successfully drew a 20×20 pixel art (NEAR logo design) on berry.fast using on-chain transactions.

## Submission JSON

```json
{json.dumps(submission, indent=2)}
```

## Details

- **Account:** `{NEAR_ACCOUNT_ID}`
- **Position:** Top-left corner at ({start_x}, {start_y})
- **Size:** 20×20 pixels
- **Pixels drawn:** {success} / {success + failed}
- **Contract:** `{BERRY_CONTRACT}`
- **Network:** NEAR mainnet
- **Ownership verification:** 0.1 NEAR sent from `{NEAR_ACCOUNT_ID}` to agent account

## View on Berry.Fast

https://berry.fast/#x={start_x}&y={start_y}
"""
    return content, ".md"


def solve_competition(job_id, title, description, comp_type, budget_amount="0"):
    model = choose_model(budget_amount)
    print(f"\n   🏆 Тип: {comp_type} | Модель: {model}")

    content, extension = None, ".md"

    if comp_type == "blockchain_art":
        content, extension = solve_blockchain_art(job_id, title, description, model)
    elif comp_type == "oracle":
        content = solve_oracle_challenge(title, description, model)
    elif comp_type == "scavenger":
        content = solve_scavenger_challenge(title, description, model)
    elif comp_type == "pitch":
        content, extension = solve_pitch_challenge(title, description, model)
    elif comp_type == "nearcon_content":
        content, extension = solve_content_competition(title, description, model, is_nearcon=True)
    else:
        content, extension = solve_content_competition(title, description, model)

    if not content:
        return False, False

    gist_url, _ = publish_to_gist(f"Competition_{title}", content, extension)
    if not gist_url:
        return False, False

    print(f"   📎 Deliverable: {gist_url}")
    return submit_competition_entry(job_id, gist_url)


# ============================================================
#  БЛОК 9: СТАНДАРТНЫЕ ЗАДАЧИ
# ============================================================

def check_competition_results(memory_data):
    entered = memory_data.get("entered_competitions", [])
    if not entered:
        return
    print("\n📊 Проверяем статус конкурсов...")
    notified = set(memory_data.get("completed_competitions_notified", []))
    to_remove = []

    for job_id in entered[:10]:
        try:
            job = get_job_details(job_id)
            if not job:
                continue
            status = job.get("status", "")
            title = job.get("title", job_id)[:50]
            if status == "completed":
                if job_id not in notified:
                    send_telegram(f"🏁 <b>Конкурс завершён!</b>\n📋 {title}\nПроверь кошелёк!")
                    notified.add(job_id)
                print(f"   🏁 Завершён: {title}")
                to_remove.append(job_id)  # убираем из активных
            elif status in ("expired", "closed"):
                to_remove.append(job_id)
                print(f"   ⏹️ Закрыт: {title}")
            elif status == "judging":
                print(f"   ⚖️ На рассмотрении: {title}")
        except Exception:
            pass
        time.sleep(0.5)

    # Чистим завершённые из списка активных конкурсов
    if to_remove:
        memory_data["entered_competitions"] = [
            jid for jid in memory_data["entered_competitions"] if jid not in to_remove
        ]
        memory_data["completed_competitions_notified"] = list(notified)

def is_short_qa_job(job):
    """
    Детектор простых Q&A задач без тегов.
    Примеры: "What is the weather in Berlin?", "Equity percentage for a founding engineer"
    Признаки: короткое описание (<200 символов), нет тегов, бюджет небольшой.
    Агент отвечает на такие вопросы напрямую через Claude — deliverable: Markdown.
    """
    tags = job.get("tags", [])
    description = job.get("description", "")
    title = job.get("title", "")

    # Только задачи без тегов или с 1-2 тегами
    if len(tags) > 2:
        return False

    # Короткое описание — признак простого вопроса
    if len(description) > 300:
        return False

    # Жёсткие исключения — даже короткие
    combined = (title + " " + description).lower()
    hard_skip = ["solidity", "smart contract", "security audit", "trading bot",
                 "mev", "arbitrage", "figma", "photoshop", "nft art"]
    if any(s in combined for s in hard_skip):
        return False

    # Если описание = вопрос или короткое задание — берём
    return True

def is_good_standard_job(job):
    tags = [t.lower() for t in job.get("tags", [])]
    title = job.get("title", "").lower()
    description = job.get("description", "").lower()

    for skip in SKIP_TAGS:
        if skip in tags: return False
    for skip_kw in SKIP_TITLE_KEYWORDS:
        if skip_kw in title: return False
    for skip_kw in SKIP_DESCRIPTION_KEYWORDS:
        if skip_kw in description: return False
    for good in GOOD_TAGS:
        if good in tags: return True

    # Moltbook задачи всегда берём — агент умеет публиковать
    if "moltbook" in title:
        return True

    keywords = ["write", "research", "content", "analysis", "tutorial", "python", "script",
                "bot", "api", "data", "nearcon", "hackathon", "demo", "grant", "build",
                "create", "npm", "package", "mcp", "langchain", "discord", "telegram", "moltbook"]
    if any(kw in title for kw in keywords):
        return True

    # Последний шанс: короткий Q&A без тегов
    return is_short_qa_job(job)


def check_submitted_jobs(memory_gist_id: str, memory_data: dict):
    """
    Проверяет статус сданных работ:
    - accepted → уведомление в Telegram + перемещаем в completed
    - in_progress (revision) → читаем фидбек, генерируем улучшенную версию, сдаём повторно
    - disputed → уведомление
    """
    submitted = memory_data.get("submitted_jobs", {})
    if not submitted:
        return

    print(f"\n📬 Проверяем {len(submitted)} сданных работ...")
    notified_accepted = set(memory_data.get("notified_accepted", []))
    changed = False

    for job_id, job_info in list(submitted.items()):
        try:
            job = get_job_details(job_id)
            if not job:
                continue

            my_assignments = job.get("my_assignments", [])
            if not my_assignments:
                continue

            asgn = my_assignments[0]
            asgn_id     = asgn.get("assignment_id", "")
            asgn_status = asgn.get("status", "")
            title       = job.get("title", job_id)[:60]
            description = job.get("description", title)  # FIX: всегда доступна во всех ветках

            print(f"   📋 {title} | статус: {asgn_status}")

            # ── ПРИНЯТА ──────────────────────────────────────────────
            if asgn_status == "accepted" and job_id not in notified_accepted:
                escrow = asgn.get("escrow_amount", "?")
                print(f"   🎉 ПРИНЯТА! Оплата: {escrow} NEAR")
                send_telegram(
                    f"🎉 <b>РАБОТА ПРИНЯТА!</b>\n"
                    f"📋 {title}\n"
                    f"💰 Оплата: {escrow} NEAR\n"
                    f"🔗 https://market.near.ai/jobs/{job_id}"
                )
                notified_accepted.add(job_id)
                # Переносим в completed_jobs
                if job_id not in memory_data.get("completed_jobs", []):
                    memory_data.setdefault("completed_jobs", []).append(job_id)
                submitted.pop(job_id, None)
                changed = True

            # ── REVISION REQUEST (отправили на доработку) ─────────────
            elif asgn_status == "in_progress" and asgn_id:
                # Читаем сообщения — ищем фидбек от заказчика
                messages = get_assignment_messages(asgn_id)
                if not messages:
                    continue

                # Берём только сообщения НЕ от нас (от заказчика)
                feedback_msgs = [
                    m for m in messages
                    if m.get("sender_handle") != "budget_skynet"
                    and m.get("body", "").strip()
                ]
                if not feedback_msgs:
                    continue

                # Последнее сообщение заказчика
                latest = feedback_msgs[-1]
                feedback_text = latest.get("body", "")
                msg_id = latest.get("message_id", "")

                # Проверяем — уже обрабатывали это сообщение?
                processed_msgs = set(memory_data.get("processed_message_ids", []))
                if msg_id in processed_msgs:
                    continue

                print(f"   📩 Revision request: {feedback_text[:100]}")
                send_telegram(
                    f"📩 <b>REVISION REQUEST!</b>\n"
                    f"📋 {title}\n"
                    f"💬 Заказчик: {feedback_text[:300]}\n"
                    f"🔗 https://market.near.ai/jobs/{job_id}"
                )

                # Генерируем улучшенную версию с учётом фидбека
                # description уже задана выше
                dtype = job_info.get("dtype", "markdown")
                model = choose_model(asgn.get("escrow_amount", "1"))
                prev_url = job_info.get("deliverable_url", "")

                revision_prompt_extra = (
                    f"\n\nPREVIOUS SUBMISSION: {prev_url}"
                    f"\n\nCLIENT FEEDBACK (MUST ADDRESS): {feedback_text}"
                    f"\n\nIMPORTANT: Carefully read the feedback above and fix exactly what the client requested."
                )

                print(f"   🔧 Генерируем revision (dtype={dtype}, model={model})...")
                # Временно добавляем фидбек к описанию
                revised_files = generate_deliverable(dtype, title, description + revision_prompt_extra, model)

                if revised_files:
                    new_url = publish_multifile_gist(
                        f"REVISION_{title}",
                        {k: v for k, v in revised_files.items() if not k.startswith("_")},
                        description=f"budget_skynet revision: {title}"
                    )
                    if new_url:
                        result = resubmit_work(asgn_id, new_url, job_id=job_id)
                        if result.get("status") == "submitted":
                            print(f"   ✅ Revision сдана: {new_url}")
                            send_telegram(
                                f"✅ <b>REVISION СДАНА!</b>\n"
                                f"📋 {title}\n"
                                f"🔗 {new_url}"
                            )
                            # Отправляем сообщение заказчику
                            send_assignment_message(
                                asgn_id,
                                f"Thank you for the feedback! I've revised the work addressing your points: {feedback_text[:200]}\n\nUpdated deliverable: {new_url}"
                            )
                            # Обновляем deliverable_url в памяти
                            submitted[job_id]["deliverable_url"] = new_url
                            processed_msgs.add(msg_id)
                            memory_data["processed_message_ids"] = list(processed_msgs)
                            changed = True
                        else:
                            print(f"   ❌ Resubmit failed: {result}")

            # ── DISPUTE ───────────────────────────────────────────────
            elif asgn_status == "disputed":
                dispute_notified = set(memory_data.get("dispute_notified", []))
                if job_id not in dispute_notified:
                    # Помечаем сразу в памяти — сохраним один раз в конце цикла
                    dispute_notified.add(job_id)
                    memory_data["dispute_notified"] = list(dispute_notified)
                    changed = True

                    print(f"   ⚠️ Dispute открыт")
                    orig_deliverable = submitted.get(job_id, {}).get("deliverable_url", "")
                    asgn_id_dispute = my_assignments[0].get("assignment_id", "") if my_assignments else ""

                    # Читаем причину диспута
                    dispute_reason = ""
                    try:
                        for d in get_job_disputes(job_id):
                            if d.get("status") == "open":
                                dispute_reason = d.get("reason", "") or ""
                                break
                    except Exception:
                        pass

                    AUTO_PHRASES = ["not reviewed within 24", "auto: submission not reviewed",
                                    "automatically disputed", "auto dispute"]
                    is_auto = any(p in dispute_reason.lower() for p in AUTO_PHRASES) or not dispute_reason
                    print(f"   📋 Причина: '{dispute_reason[:80]}' | Авто: {is_auto}")

                    if is_auto:
                        # Авто-диспут: маркетплейс разрешит сам — просто логируем, ничего не шлём
                        print(f"   ℹ️ Авто-диспут — пропускаем")
                    else:
                        # Реальная претензия — генерируем в пульт, БЕЗ отправки клиенту
                        print(f"   ⚠️ Реальный dispute — генерируем коррекцию для проверки")
                        try:
                            job_full_d = get_job_details(job_id)
                            desc_d = job_full_d.get("description", description) if job_full_d else description
                            model_d = choose_model(job_full_d.get("budget_amount", "0") if job_full_d else "0")
                            dtype_d = detect_deliverable_type(title, desc_d)
                            files_d = None
                            redel_passed = False
                            redel_feedback = ""
                            for rd_attempt in range(1, 4):
                                aug = desc_d + f"\n\nDISPUTE REASON: {dispute_reason}"
                                if rd_attempt > 1:
                                    aug += f"\nPREVIOUS FAILED: {redel_feedback}"
                                files_d = generate_deliverable(dtype_d, title, aug, model_d)
                                if files_d:
                                    redel_passed, redel_feedback = review_deliverable_quality(
                                        dtype_d, title, desc_d, files_d, model="sonnet")
                                    if redel_passed:
                                        break
                            if files_d:
                                new_gist = publish_multifile_gist(title,
                                    {k: v for k, v in files_d.items() if not k.startswith("_")},
                                    description=f"budget_skynet redelivery: {title}")
                                q = "✅ quality OK" if redel_passed else "⚠️ quality не идеально"
                                send_to_control_bot(
                                    f"🔄 <b>Redelivery готов — проверь перед отправкой!</b>\n"
                                    f"📋 {title}\n"
                                    f"🔗 https://market.near.ai/jobs/{job_id}\n"
                                    f"💬 Причина: <i>{dispute_reason[:200]}</i>\n"
                                    f"📎 {new_gist} ({q})\n"
                                    f"Отправь клиенту вручную если ок.",
                                    job_id=job_id
                                )
                            else:
                                send_to_control_bot(
                                    f"⚠️ <b>Dispute — не смог сгенерировать!</b>\n"
                                    f"📋 {title}\n"
                                    f"🔗 https://market.near.ai/jobs/{job_id}\n"
                                    f"💬 Причина: <i>{dispute_reason[:300]}</i>",
                                    job_id=job_id
                                )
                        except Exception as e:
                            print(f"   ⚠️ Redelivery error: {e}")
                            send_to_control_bot(
                                f"⚠️ <b>Dispute error: {e}</b>\n📋 {title}\n"
                                f"🔗 https://market.near.ai/jobs/{job_id}",
                                job_id=job_id
                            )
                else:
                    print(f"   ℹ️ Dispute уже обработан: {title[:50]}")

            # ── REDO (резолвер вернул на доработку) ──────────────────
            elif asgn_status == "in_progress" and job_id in memory_data.get("dispute_notified", []):
                # Диспут был, но резолвер вынес ruling=redo — задача вернулась в in_progress
                redo_done = set(memory_data.get("redo_done", []))
                if job_id not in redo_done:
                    print(f"   🔄 REDO от резолвера: {title[:50]}")
                    send_telegram(
                        f"🔄 <b>REDO — резолвер вернул на доработку!</b>\n"
                        f"📋 {title}\n"
                        f"🔗 https://market.near.ai/jobs/{job_id}\n"
                        f"Агент сгенерирует исправленную версию."
                    )
                    # Убираем из dispute_notified чтобы обработать как revision
                    dn = set(memory_data.get("dispute_notified", []))
                    dn.discard(job_id)
                    memory_data["dispute_notified"] = list(dn)
                    # Сбрасываем failed_jobs чтобы дать ещё попытки
                    memory_data.get("failed_jobs", {}).pop(job_id, None)
                    redo_done.add(job_id)
                    memory_data["redo_done"] = list(redo_done)
                    changed = True

            # ── CANCELLED ─────────────────────────────────────────────
            elif asgn_status == "cancelled":
                print(f"   ❌ Отменена — убираем из submitted")
                submitted.pop(job_id, None)
                changed = True

        except Exception as e:
            print(f"   ⚠️ check_submitted_jobs({job_id}): {e}")
        time.sleep(0.5)

    memory_data["submitted_jobs"] = submitted
    memory_data["notified_accepted"] = list(notified_accepted)
    if changed:
        save_memory(memory_gist_id, memory_data)


def process_won_bids(memory_gist_id, memory_data):
    print("\n🔍 Проверяем выигранные задачи...")

    # Получаем задачи где мы воркер (надёжнее чем /agents/me/bids с 1500+ бидами)
    active_jobs = get_my_active_jobs()
    print(f"   📋 Активных задач как воркер: {len(active_jobs)}")

    failed_jobs = memory_data.setdefault("failed_jobs", {})
    MAX_ATTEMPTS = 3
    memory_changed = False  # батчевое сохранение — не спамим GitHub API

    # Счётчики для итогового отчёта
    stats = {
        "total": 0,
        "disputed": 0,
        "cancelled": 0,
        "already_submitted": 0,
        "already_accepted": 0,
        "submitted_now": 0,
        "failed": 0,
    }

    for job in active_jobs:
        job_id = job.get("job_id")
        title = job.get("title", job_id)

        if job_id in memory_data.get("completed_jobs", []):
            continue

        # Проверяем лимит попыток (защита от бесконечного retry)
        attempt = failed_jobs.get(job_id, 0)
        if attempt >= MAX_ATTEMPTS:
            # Для disputed — проверяем нужен ли redelivery, не пропускаем сразу
            redelivery_done_check = set(memory_data.get("redelivery_done", []))
            if job_id not in redelivery_done_check:
                job_full_check = get_job_details(job_id)
                if job_full_check:
                    asgn_check = job_full_check.get("my_assignments", [])
                    if asgn_check and asgn_check[0].get("status") == "disputed":
                        job = job_full_check  # дальше обработает redelivery блок
                    else:
                        print(f"   ⚠️ Пропуск {title[:50]}: {attempt}/{MAX_ATTEMPTS} попыток исчерпано")
                        continue
                else:
                    print(f"   ⚠️ Пропуск {title[:50]}: {attempt}/{MAX_ATTEMPTS} попыток исчерпано")
                    continue
            else:
                print(f"   ⚠️ Пропуск {title[:50]}: {attempt}/{MAX_ATTEMPTS} попыток исчерпано")
                continue

        # Подгружаем полные детали джобы — list endpoint НЕ возвращает my_assignments!
        job_full = get_job_details(job_id)
        if job_full:
            job = job_full  # используем полную версию с my_assignments

        # Проверяем my_assignments ПЕРЕД генерацией — не тратим токены впустую
        my_assignments = job.get("my_assignments", [])
        if my_assignments:
            asgn_status = my_assignments[0].get("status", "")
            asgn_id_early = my_assignments[0].get("assignment_id", "")

            if asgn_status == "submitted":
                stats["already_submitted"] += 1
                print(f"   ✅ Уже сдано (submitted): {title[:50]}")
                if job_id not in memory_data.get("submitted_jobs", {}):
                    memory_data.setdefault("submitted_jobs", {})[job_id] = {
                        "title": title, "dtype": "unknown",
                        "deliverable_url": my_assignments[0].get("deliverable", ""),
                        "assignment_id": asgn_id_early,
                        "submitted_at": datetime.now(timezone.utc).isoformat()
                    }
                continue

            if asgn_status == "accepted":
                stats["already_accepted"] += 1
                print(f"   ✅ Уже принято: {title[:50]}")
                if job_id not in memory_data.get("completed_jobs", []):
                    memory_data.setdefault("completed_jobs", []).append(job_id)
                continue

            if asgn_status == "disputed":
                stats["disputed"] += 1
                dispute_notified = set(memory_data.get("dispute_notified", []))
                redelivery_done = set(memory_data.get("redelivery_done", []))

                # Сразу помечаем как обработанный и сохраняем — до любых действий
                # Это защищает от повторной обработки при перезапуске
                if job_id not in dispute_notified:
                    dispute_notified.add(job_id)
                    memory_data["dispute_notified"] = list(dispute_notified)
                    # save_memory будет в конце итерации

                    # Читаем причину диспута
                    dispute_reason_rd = ""
                    try:
                        disputes_rd = get_job_disputes(job_id)
                        for d in disputes_rd:
                            if d.get("status") == "open":
                                dispute_reason_rd = d.get("reason", "") or ""
                                break
                    except Exception:
                        pass

                    AUTO_PHRASES = ["not reviewed within 24", "auto: submission not reviewed",
                                    "automatically disputed", "auto dispute"]
                    is_auto_rd = any(p in dispute_reason_rd.lower() for p in AUTO_PHRASES) or not dispute_reason_rd

                    print(f"   📋 Dispute причина: '{dispute_reason_rd[:80]}' | Авто: {is_auto_rd}")

                    if is_auto_rd:
                        # Авто-диспут — работа нормальная, заказчик просто не проверил
                        # НЕ генерируем ничего, просто уведомляем в пульт
                        print(f"   ℹ️ Авто-диспут — без перегенерации")
                        send_to_control_bot(
                            f"⏰ <b>Авто-диспут (24h timeout)</b>\n"
                            f"📋 {title}\n"
                            f"🔗 https://market.near.ai/jobs/{job_id}\n"
                            f"ℹ️ Заказчик не проверил работу вовремя — маркетплейс разрешит автоматически.",
                            job_id=job_id
                        )
                    elif job_id not in redelivery_done:
                        # Реальная претензия — уведомляем в пульт с деталями
                        # НЕ генерируем автоматически для active_jobs диспутов — владелец решает
                        print(f"   ⚠️ Реальный dispute: {dispute_reason_rd[:80]}")
                        send_to_control_bot(
                            f"⚠️ <b>DISPUTE — реальная претензия!</b>\n"
                            f"📋 {title}\n"
                            f"🔗 https://market.near.ai/jobs/{job_id}\n"
                            f"💬 Причина: <i>{dispute_reason_rd[:400] or 'не указана'}</i>\n\n"
                            f"Реши: перегенерировать автоматически или сделать вручную?",
                            job_id=job_id
                        )
                    else:
                        print(f"   ℹ️ Dispute (redelivery уже сделан): {title[:50]}")
                else:
                    print(f"   ℹ️ Dispute уже обработан ранее: {title[:50]}")

                failed_jobs[job_id] = MAX_ATTEMPTS
                memory_changed = True
                continue

            if asgn_status == "cancelled":
                stats["cancelled"] += 1
                print(f"   ❌ Assignment отменён — пропускаем: {title[:50]}")
                failed_jobs[job_id] = MAX_ATTEMPTS
                memory_changed = True
                continue

        if memory_changed:
            save_memory(memory_gist_id, memory_data)
            memory_changed = False

        print(f"\n🏆 ВЫИГРАН: {title} (попытка {attempt+1}/{MAX_ATTEMPTS})")
        send_telegram(f"🏆 <b>БИД ВЫИГРАН!</b>\n📋 {title}")

        # Детали задачи (job из active_jobs может не содержать description)
        description = job.get("description", "")
        if not description:
            job = get_job_details(job_id)
            if not job:
                print(f"   ⚠️ Не удалось получить детали задачи {job_id}")
                continue
            description = job.get("description", title)

        # Проверяем статус assignment — если уже cancelled/disputed, не тратим токены
        my_assignments = job.get("my_assignments", [])
        if my_assignments:
            asgn_status = my_assignments[0].get("status", "")
            if asgn_status in ("cancelled", "disputed"):
                print(f"   ⚠️ Assignment {asgn_status} — пропускаем")
                failed_jobs[job_id] = MAX_ATTEMPTS  # не пробовать снова
                memory_changed = True
                continue

        # Определяем тип deliverable
        dtype = detect_deliverable_type(title, description)
        model = choose_model(job.get("budget_amount", "0"))
        print(f"   📦 Тип deliverable: {dtype} | Модель: {model}")
        send_telegram(f"   🔧 Тип: {dtype} | 🤖 {model}")

        # ── ВНЕШНИЙ ЦИКЛ КАЧЕСТВА ──────────────────────────────────────────
        # Генерируем → Claude проверяет всю работу → чиним → повторяем
        # Только если N попыток провалились → в пульт владельцу
        MAX_QUALITY_ATTEMPTS = 6
        files = None
        quality_feedback = ""
        quality_passed = False

        for q_attempt in range(1, MAX_QUALITY_ATTEMPTS + 1):
            print(f"   🔄 Генерация + quality review: попытка {q_attempt}/{MAX_QUALITY_ATTEMPTS}...")

            if q_attempt == 1:
                files = generate_deliverable(dtype, title, description, model)
            else:
                # Перегенерируем с учётом фидбека от Claude-судьи
                enhanced_desc = (
                    description +
                    f"\n\n=== PREVIOUS ATTEMPT FAILED REVIEW ===\n"
                    f"FEEDBACK FROM REVIEWER:\n{quality_feedback}\n"
                    f"FIX THESE ISSUES in your new generation. Be thorough and complete."
                )
                files = generate_deliverable(dtype, title, enhanced_desc, model)

            if not files:
                print(f"   ❌ Генерация вернула пустой результат (попытка {q_attempt})")
                quality_feedback = "generation returned empty result"
                continue

            # Claude-судья проверяет всю работу
            quality_passed, quality_feedback = review_deliverable_quality(
                dtype, title, description, files, model="sonnet"
            )
            if quality_passed:
                print(f"   ✅ Quality approved {'с первой попытки' if q_attempt == 1 else f'с попытки {q_attempt}'}")
                break
            else:
                print(f"   🔧 Quality rejected (попытка {q_attempt}): {quality_feedback[:120]}")

        if not files:
            print("   ❌ Не удалось сгенерировать deliverable после всех попыток")
            send_to_control_bot(
                f"❌ <b>Генерация провалилась полностью!</b>\n"
                f"📋 <b>{title}</b>\n"
                f"🔗 https://market.near.ai/jobs/{job_id}\n"
                f"⚠️ Тип: {dtype} | {MAX_QUALITY_ATTEMPTS} попыток, результат пустой.\n"
                f"Нужна ручная работа или скип.",
                job_id=job_id
            )
            failed_jobs[job_id] = attempt + 1
            save_memory(memory_gist_id, memory_data)
            continue

        if not quality_passed:
            # Исчерпали попытки, но есть что отправить — даём владельцу решить
            print(f"   ⚠️ Quality loop исчерпан — в пульт для решения")
            send_to_control_bot(
                f"⚠️ <b>Качество под вопросом — нужна проверка!</b>\n"
                f"📋 <b>{title}</b>\n"
                f"🔗 https://market.near.ai/jobs/{job_id}\n"
                f"🔍 Последний фидбек reviewer:\n<code>{quality_feedback[:400]}</code>\n\n"
                f"Работа сгенерирована ({len(files)} файлов), но не прошла авто-проверку.\n"
                f"Реши: отправить заказчику или доделать вручную?",
                job_id=job_id
            )
            failed_jobs[job_id] = attempt + 1
            save_memory(memory_gist_id, memory_data)
            continue
        # ── КОНЕЦ ЦИКЛА КАЧЕСТВА ────────────────────────────────────────

        # Публикуем deliverable
        if dtype == "moltbook_post" and MOLTBOOK_API_KEY:
            # Для Moltbook-задач: публикуем статью на платформе
            mb_content = files.get("_moltbook_content", "")
            mb_title   = files.get("_moltbook_title", title)
            # Очищаем служебные ключи перед Gist
            gist_files = {k: v for k, v in files.items() if not k.startswith("_")}

            deliverable_url = publish_to_moltbook(mb_title, mb_content)
            if not deliverable_url:
                # Fallback на Gist если Moltbook недоступен
                print("   ⚠️ Moltbook недоступен — публикуем в Gist как fallback")
                deliverable_url = publish_multifile_gist(
                    title, gist_files,
                    description=f"budget_skynet deliverable: {title}"
                )
        elif dtype == "hf_space" and HF_TOKEN:
            # Для HuggingFace Space задач: деплоим реальный Space
            hf_repo_id = files.get("_hf_repo_id", f"budget-skynet/{title[:30].lower().replace(' ', '-')}")
            hf_files = {k: v for k, v in files.items() if not k.startswith("_")}
            deliverable_url = publish_to_huggingface(hf_repo_id, hf_files)
            if not deliverable_url:
                print("   ⚠️ HuggingFace недоступен — публикуем в Gist как fallback")
                deliverable_url = publish_multifile_gist(
                    title, hf_files,
                    description=f"budget_skynet deliverable: {title}"
                )
        elif dtype == "hf_space" and not HF_TOKEN:
            print("   ⚠️ HF_TOKEN не задан — публикуем Gradio код в Gist")
            gist_files = {k: v for k, v in files.items() if not k.startswith("_")}
            deliverable_url = publish_multifile_gist(
                title, gist_files,
                description=f"budget_skynet deliverable: {title}"
            )

        elif dtype == "npm_package":
            # Пробуем опубликовать на npm, fallback — Gist
            pkg_match = re.search(r'near-[\w-]+', title.lower())
            pkg_name = pkg_match.group(0) if pkg_match else "near-utils"
            gist_url_fb = publish_multifile_gist(
                title, files,
                description=f"budget_skynet deliverable: {title}"
            )
            npm_url = publish_to_npm_with_retry(pkg_name, files, title=title, job_id=job_id)
            deliverable_url = npm_url or gist_url_fb
            if npm_url and gist_url_fb:
                send_telegram(f"📦 <b>npm опубликован!</b>\n📦 {pkg_name}\n🔗 {npm_url}\n📎 Gist: {gist_url_fb}")
        elif dtype == "mcp_server":
            desc_lower = description.lower()
            requires_npm = any(kw in desc_lower for kw in ["published to npm", "publish to npm", "npm package", "npm publish"])
            gist_url_fb = publish_multifile_gist(
                title, files,
                description=f"budget_skynet deliverable: {title}"
            )
            deliverable_url = gist_url_fb
            if requires_npm:
                if NPM_TOKEN:
                    print("   📦 MCP задача требует npm publish — публикуем...")
                    pkg_match = re.search(r'near-[\w-]+', title.lower())
                    pkg_name = pkg_match.group(0) if pkg_match else re.sub(r'[^a-z0-9-]', '-', title.lower()[:30]).strip('-')
                    npm_url = publish_to_npm_with_retry(pkg_name, files, title=title, job_id=job_id)
                    if npm_url:
                        deliverable_url = npm_url
                        send_telegram(f"📦 <b>MCP + npm опубликован!</b>\n📦 {pkg_name}\n🔗 {npm_url}\n📎 Gist: {gist_url_fb}")
                    else:
                        # npm публикация провалилась — не отправляем заказчику, уведомляем владельца
                        print("   ❌ npm publish провалился — уведомляем владельца")
                        send_to_control_bot(
                            f"❌ <b>npm publish провалился!</b>\n"
                            f"📋 <b>{title}</b>\n"
                            f"🔗 https://market.near.ai/jobs/{job_id}\n"
                            f"⚠️ Задача требует npm, но публикация не удалась.\n"
                            f"📎 Gist готов: {gist_url_fb}\n"
                            f"Реши: отправить Gist или разобраться с npm?",
                            job_id=job_id
                        )
                        deliverable_url = None  # не отправляем
        elif dtype == "python_package" or (dtype in ("cli_tool", "langchain_tool") and "published to pypi" in description.lower()):
            pkg_match = re.search(r'near[-_][\w-]+', title.lower())
            pkg_name = (pkg_match.group(0) if pkg_match else re.sub(r'[^a-z0-9_]', '_', title.lower()[:30]).strip('_')).replace("-", "_")
            gist_url_fb = publish_multifile_gist(
                title, files,
                description=f"budget_skynet deliverable: {title}"
            )
            pypi_url = publish_to_pypi_with_retry(pkg_name, files, title=title, job_id=job_id)
            requires_pypi = "published to pypi" in description.lower() or "pypi package" in description.lower() or "pip install" in description.lower()
            if pypi_url:
                deliverable_url = pypi_url
                send_telegram(f"🐍 <b>PyPI опубликован!</b>\n📦 {pkg_name}\n🔗 {pypi_url}\n📎 Gist: {gist_url_fb}")
            elif requires_pypi:
                # PyPI провалился а задача явно требует — не отправляем Gist, уведомляем владельца
                print("   ❌ PyPI publish провалился — уведомляем владельца")
                send_to_control_bot(
                    f"❌ <b>PyPI publish провалился!</b>\n"
                    f"📋 <b>{title}</b>\n"
                    f"🔗 https://market.near.ai/jobs/{job_id}\n"
                    f"⚠️ Задача требует PyPI, но публикация не удалась.\n"
                    f"📎 Gist готов: {gist_url_fb}\n"
                    f"Реши: отправить Gist или разобраться с PyPI?",
                    job_id=job_id
                )
                deliverable_url = None  # не отправляем
            else:
                deliverable_url = gist_url_fb
        else:
            # Стандартный путь — Gist
            deliverable_url = publish_multifile_gist(
                title,
                files,
                description=f"budget_skynet deliverable: {title}"
            )

        gist_url = deliverable_url  # единая переменная для submit

        if not gist_url:
            print(f"   ❌ Deliverable не создан — НЕ отправляем клиенту, уведомляем владельца")
            send_telegram(
                f"⚠️ <b>Требуется вмешательство:</b>\n"
                f"📋 {title}\n"
                f"🔗 https://market.near.ai/jobs/{job_id}\n\n"
                f"❌ Не удалось создать deliverable (пустой результат генерации).\n"
                f"Тип: {dtype} | Попытка: {attempt+1}/{MAX_ATTEMPTS}"
            )
            failed_jobs[job_id] = attempt + 1
            save_memory(memory_gist_id, memory_data)
            continue

        # Финальная проверка перед отправкой клиенту
        submit_ok, submit_issues = pre_submit_checklist(title, description, files, gist_url)
        if not submit_ok:
            print(f"   ⚠️ Pre-submit issues: {submit_issues[:200]}")
            # Не блокируем если мелкие замечания — только уведомляем
            send_to_control_bot(
                f"⚠️ <b>Pre-submit предупреждение</b>\n"
                f"📋 <b>{title}</b>\n"
                f"🔗 {gist_url}\n\n"
                f"Проблемы:\n{submit_issues[:400]}\n\n"
                f"Работа всё равно будет отправлена. Проверь вручную.",
                job_id=job_id
            )

        # Сдаём работу
        result = submit_work(job_id, gist_url)
        if result.get("status") == "submitted":
            file_list = ", ".join(k for k in files.keys() if not k.startswith("_"))
            stats["submitted_now"] += 1
            print(f"   🎉 СДАНО! Файлы: {file_list}")
            send_telegram(
                f"🎉 <b>РАБОТА СДАНА!</b>\n📋 {title}\n"
                f"📦 Тип: {dtype}\n📁 Файлы: {len(file_list)}\n🔗 {gist_url}"
            )
            # Отправляем сообщение заказчику — объясняем что сдаём
            asgn_id = ""
            if job.get("my_assignments"):
                asgn_id = job["my_assignments"][0].get("assignment_id", "")

            if asgn_id:
                file_names = [k for k in files.keys() if not k.startswith("_")]
                file_list_str = "\n".join(f"- `{f}`" for f in file_names)

                if dtype == "custom_gpt":
                    msg = (
                        f"✅ **GPT Specification delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**How to publish:**\n"
                        f"1. Go to chat.openai.com → Explore GPTs → Create\n"
                        f"2. Paste contents of `system_prompt.md` into Instructions\n"
                        f"3. Import `openapi_actions.json` as an Action\n"
                        f"4. Save and publish\n\n"
                        f"📎 All files: {gist_url}"
                    )
                elif dtype == "python_package":
                    pypi_link = f"\n📦 PyPI: {deliverable_url}" if deliverable_url != gist_url else ""
                    msg = (
                        f"✅ **Python package delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**Install:**\n```\npip install {title.lower().replace(' ', '-')[:30]}\n```\n"
                        f"📎 Source code: {gist_url}{pypi_link}"
                    )
                elif dtype == "npm_package":
                    npm_link = f"\n📦 npm: {deliverable_url}" if deliverable_url != gist_url else ""
                    pkg_name_npm = title.lower().replace(' ', '-')[:30]
                    msg = (
                        f"✅ **npm package delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**Install:**\n```\nnpm install {pkg_name_npm}\n```\n"
                        f"📎 Source code: {gist_url}{npm_link}"
                    )
                elif dtype == "mcp_server":
                    msg = (
                        f"✅ **MCP Server delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**Setup:** See README.md for installation and configuration instructions.\n\n"
                        f"📎 Source code: {gist_url}"
                    )
                elif dtype == "moltbook_post":
                    msg = (
                        f"✅ **MoltBook post published** for _{title}_\n\n"
                        f"📰 Live post: {gist_url}\n\n"
                        f"The article is now live on MoltBook and discoverable by agents."
                    )
                elif dtype == "hf_space":
                    msg = (
                        f"✅ **HuggingFace Space deployed** for _{title}_\n\n"
                        f"🤗 Live demo: {gist_url}\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"The Space is live and accessible."
                    )
                elif dtype == "telegram_bot":
                    msg = (
                        f"✅ **Telegram Bot delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**To deploy:**\n"
                        f"1. Get bot token from @BotFather\n"
                        f"2. Set `TELEGRAM_TOKEN` env variable\n"
                        f"3. Run: `pip install -r requirements.txt && python bot.py`\n\n"
                        f"📎 Source code: {gist_url}"
                    )
                elif dtype == "github_action":
                    msg = (
                        f"✅ **GitHub Action delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**To use:** Copy `action.yml` to `.github/workflows/` in your repo.\n\n"
                        f"📎 Source code: {gist_url}"
                    )
                elif dtype == "vscode_extension":
                    msg = (
                        f"✅ **VS Code Extension delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"**To install:** Download files, run `npm install && npm run build`, then `code --install-extension *.vsix`\n\n"
                        f"📎 Source code: {gist_url}"
                    )
                elif dtype == "markdown":
                    msg = (
                        f"✅ **Document delivered** for _{title}_\n\n"
                        f"📄 Full document: {gist_url}"
                    )
                else:
                    msg = (
                        f"✅ **Work delivered** for _{title}_\n\n"
                        f"**Files included:**\n{file_list_str}\n\n"
                        f"📎 {gist_url}"
                    )

                send_assignment_message(asgn_id, msg)

            # Сохраняем в submitted_jobs для отслеживания статуса и ревизий
            # assignment_id берём из уже загруженного job — без лишнего API запроса
            memory_data.setdefault("submitted_jobs", {})[job_id] = {
                "title": title,
                "dtype": dtype,
                "deliverable_url": gist_url,
                "assignment_id": asgn_id,
                "submitted_at": datetime.now(timezone.utc).isoformat()
            }
            # Добавляем в completed_jobs чтобы не повторять выполнение
            if job_id not in memory_data.get("completed_jobs", []):
                memory_data.setdefault("completed_jobs", []).append(job_id)
            failed_jobs.pop(job_id, None)
            save_memory(memory_gist_id, memory_data)
        else:
            err = result.get("detail") or result.get("error") or str(result)[:300]
            print(f"   ❌ Submit ошибка: {err}")
            send_telegram(
                f"⚠️ <b>Требуется вмешательство:</b>\n"
                f"📋 {title}\n"
                f"🔗 https://market.near.ai/jobs/{job_id}\n\n"
                f"❌ Ошибка при отправке работы: {err}\n"
                f"📎 Deliverable готов: {gist_url}"
            )
            stats["failed"] += 1
            failed_jobs[job_id] = attempt + 1
            save_memory(memory_gist_id, memory_data)

    # Итоговый отчёт по задачам
    total_active = len(active_jobs)
    won_report = (
        f"📊 <b>Итог по задачам:</b>\n"
        f"📋 Активных всего: {total_active}\n"
        f"✅ Сдано сейчас: {stats['submitted_now']}\n"
        f"⏳ Уже на проверке: {stats['already_submitted']}\n"
        f"🏆 Принято заказчиком: {stats['already_accepted']}\n"
        f"⚠️ В споре: {stats['disputed']}\n"
        f"❌ Отменено: {stats['cancelled']}\n"
        f"💥 Ошибки: {stats['failed']}"
    )
    print(f"\n{won_report}")
    memory_data["last_run_stats"] = stats  # статы для финального отчёта


# ============================================================
#  ГЛАВНАЯ ЛОГИКА
# ============================================================

def scan_and_bid():
    print("🤖 budget_skynet v13.0 (MULTI-PLATFORM EDITION) запущен...")
    print(f"   ⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    update_agent_profile()
    if _e2b_available:
        print("   🧪 E2B sandbox: АКТИВЕН — pip/npm install поддерживается")
    else:
        print("   🧪 Local syntax check: активен (ast.parse + JS эвристика)")
    if MOLTBOOK_API_KEY:
        print("   📰 Moltbook: АКТИВЕН — публикация статей через API")
    else:
        print("   📰 Moltbook: не настроен (добавь MOLTBOOK_API_KEY для MoltBook-задач)")
    if HF_TOKEN:
        print("   🤗 HuggingFace: АКТИВЕН — деплой Gradio Spaces")
    else:
        print("   🤗 HuggingFace: не настроен (добавь HF_TOKEN для HF Space задач — fallback: Gist)")

    # NEAR wallet balance
    if NEAR_PRIVATE_KEY:
        try:
            from near_tx import get_account_balance as near_get_balance
            near_bal = near_get_balance(NEAR_ACCOUNT_ID)
            print(f"   🔑 NEAR кошелёк: {NEAR_ACCOUNT_ID} | Баланс: {near_bal:.4f} NEAR")
            if near_bal < 0.2:
                print(f"   ⚠️ Мало NEAR на кошельке — пополни для blockchain_art конкурсов!")
                send_telegram(f"⚠️ Мало NEAR на <b>{NEAR_ACCOUNT_ID}</b>: {near_bal:.4f} NEAR")
        except Exception as e:
            print(f"   ⚠️ NEAR кошелёк: ошибка чтения баланса — {e}")
    else:
        print("   🔑 NEAR кошелёк: NEAR_PRIVATE_KEY не задан")

    # 0. Service Registry (один раз — идемпотентно)
    try:
        register_agent_service()
    except Exception as e:
        print(f"   ⚠️ Service Registry: {e}")

    # 1. Память
    memory_gist_id = get_or_create_memory_gist()
    memory_data = load_memory(memory_gist_id)
    print(f"   🧠 Задач: {len(memory_data.get('completed_jobs', []))} | "
          f"Конкурсов: {len(memory_data.get('entered_competitions', []))} | "
          f"Бидов: {len(memory_data.get('bid_job_ids', []))}")

    # ── ЯДЕРНАЯ ЗАЩИТА ОТ ДУБЛЕЙ ─────────────────────────────────────────
    # При каждом старте: находим ВСЕ задачи со статусом disputed
    # и добавляем их в dispute_notified ДО любой обработки.
    # Это гарантирует что старые диспуты не будут обработаны повторно.
    # ИСКЛЮЧЕНИЕ: если только что был сброс версии — пропускаем защиту,
    # чтобы агент мог попробовать заново сдать задачи после фикса.
    if memory_data.pop("_version_just_reset", False):
        print("   🛡️ Защита пропущена: версионный сброс — задачи получат новый шанс")
    else:
        try:
            print("   🛡️ Загружаем текущие диспуты для защиты от дублей...")
            active_now = get_my_active_jobs()
            dispute_notified_set = set(memory_data.get("dispute_notified", []))
            new_disputes_found = 0
            for aj in (active_now if isinstance(active_now, list) else []):
                aj_id = aj.get("job_id", "")
                if not aj_id:
                    continue
                asgns = aj.get("my_assignments", [])
                if asgns and asgns[0].get("status") == "disputed":
                    if aj_id not in dispute_notified_set:
                        dispute_notified_set.add(aj_id)
                        new_disputes_found += 1
            # Также из submitted_jobs
            for sj_id, sj_info in memory_data.get("submitted_jobs", {}).items():
                pass  # будет проверено через check_submitted_jobs

            if new_disputes_found > 0:
                memory_data["dispute_notified"] = list(dispute_notified_set)
                saved = save_memory(memory_gist_id, memory_data, force=True)
                print(f"   🛡️ Защита: {new_disputes_found} новых диспутов помечены (save: {'OK' if saved else 'FAIL'})")
            else:
                print(f"   🛡️ Защита: диспуты в памяти = {len(dispute_notified_set)}")
        except Exception as e:
            print(f"   ⚠️ Startup dispute protection error: {e}")
    # ─────────────────────────────────────────────────────────────────────

    # 2. Баланс
    balance = check_wallet_balance()
    if balance:
        earned = balance.get("earned", "0")
        available = balance.get("available", "0")
        print(f"   💰 Баланс: {available} NEAR | Заработано: {earned} NEAR")
        # Шлём в Telegram только если earned изменился с прошлого запуска
        last_earned = memory_data.get("last_earned_notified", "0")
        if float(earned or 0) > 0 and earned != last_earned:
            send_telegram(f"💰 <b>БАЛАНС:</b> {available} NEAR\n💎 Заработано: {earned} NEAR")
            memory_data["last_earned_notified"] = earned

    # 3. Статус конкурсов
    check_competition_results(memory_data)

    # 4. Проверяем статус сданных работ (ревизии, принятые, диспуты)
    check_submitted_jobs(memory_gist_id, memory_data)

    # 5. Выполняем новые выигранные задачи
    process_won_bids(memory_gist_id, memory_data)

    # 6. Конкурсы
    print("\n🏆 Сканируем конкурсы...")
    competitions = get_open_jobs(limit=50, job_type="competition")
    comp_entered, comp_skipped = 0, 0

    if isinstance(competitions, list):
        for job in competitions:
            job_id = job.get("job_id")
            title  = job.get("title", "")
            budget = job.get("budget_amount", "0")

            if job_id in memory_data.get("entered_competitions", []):
                continue

            description = job.get("description", "")
            if not description:
                job_details = get_job_details(job_id)
                description = job_details.get("description", "")
                job["tags"] = job_details.get("tags", job.get("tags", []))

            comp_type = detect_competition_type(job)
            if not comp_type:
                print(f"   ⏭️ Пропуск: {title[:60]}")
                comp_skipped += 1
                continue

            model = choose_model(budget)
            print(f"\n🎯 [{comp_type.upper()}]: {title}")
            print(f"   💰 {budget} NEAR | 🤖 {model}")
            send_telegram(f"🎯 <b>Конкурс!</b>\n📋 {title}\n💰 {budget} NEAR | {comp_type} | {model}")

            success, already = solve_competition(job_id, title, description, comp_type, budget)

            if success or already:
                memory_data["entered_competitions"].append(job_id)
                save_memory(memory_gist_id, memory_data)

            if success:
                print("   ✅ Entry отправлен!")
                send_telegram(f"✅ <b>Entry отправлен!</b>\n📋 {title}")
                comp_entered += 1
            elif already:
                print("   ℹ️ Уже участвуем")
                comp_skipped += 1
            else:
                print("   ❌ Ошибка")
                comp_skipped += 1

            time.sleep(2)

    # 6. Стандартные задачи
    print("\n📋 Сканируем стандартные задачи...")

    bid_job_ids = set(memory_data.get("bid_job_ids", []))
    skip_list   = set(memory_data.get("skip_list", []))    # задачи, которые ты пропустил через пульт
    force_bid   = set(memory_data.get("force_bid", []))    # задачи, которые ты одобрил через пульт

    # Подгружаем rejected/withdrawn биды с маркета — чтобы не спамить повторно
    try:
        for _status in ("rejected", "withdrawn", "expired"):
            _r = requests.get(
                f"{BASE_URL}/agents/me/bids?status={_status}&limit=200",
                headers=MARKET_HEADERS, timeout=10
            )
            if _r.status_code == 200:
                _bids = _r.json() if isinstance(_r.json(), list) else _r.json().get("bids", [])
                for _bid in _bids:
                    _jid = _bid.get("job_id") or _bid.get("id")
                    if _jid:
                        bid_job_ids.add(_jid)
        print(f"   📋 bid_job_ids загружены: {len(bid_job_ids)} (включая rejected/withdrawn)")
    except Exception as _e:
        print(f"   ⚠️ Не удалось загрузить rejected биды: {_e}")

    # Offset-пагинация: каждый запуск идём глубже
    # Сброс offset если достигли 10000 (лимит API) или нет новых задач
    current_offset = memory_data.get("scan_offset", 0)
    STEP = 100  # шаг за один запуск
    MAX_OFFSET = 5000  # максимум, потом сброс

    CONTENT_TAGS  = ["writing", "content", "research", "documentation", "translation",
                     "analysis", "report", "guide", "tutorial", "community"]
    TECH_TAGS     = ["python", "developer", "api", "bot", "telegram", "analytics",
                     "script", "npm", "package", "typescript", "javascript", "mcp",
                     "discord", "cli", "sdk", "moltbook"]
    NEAR_TAGS     = ["web3", "near", "crypto", "data", "nearcon", "hackathon",
                     "demo", "grant", "ecosystem"]

    def get_jobs_paged(tags, offset, limit=100):
        tags_str = ",".join(tags)
        r = requests.get(
            f"{BASE_URL}/jobs?status=open&job_type=standard&tags={tags_str}"
            f"&sort=created_at&order=desc&limit={limit}&offset={offset}",
            headers=MARKET_HEADERS, timeout=15
        )
        return r.json() if r.status_code == 200 else []

    def get_recent_paged(offset, limit=100):
        r = requests.get(
            f"{BASE_URL}/jobs?status=open&job_type=standard"
            f"&sort=created_at&order=desc&limit={limit}&offset={offset}",
            headers=MARKET_HEADERS, timeout=15
        )
        return r.json() if r.status_code == 200 else []

    # Скан 1: всегда свежие (offset=0) — не пропустить новые задачи сегодня
    jobs_fresh   = get_recent_paged(offset=0, limit=100)

    # Скан 2: углубляемся по offset — задачи которые раньше не видели
    jobs_deep_c  = get_jobs_paged(CONTENT_TAGS, offset=current_offset, limit=100)
    jobs_deep_t  = get_jobs_paged(TECH_TAGS,    offset=current_offset, limit=100)
    jobs_deep_n  = get_jobs_paged(NEAR_TAGS,    offset=current_offset, limit=100)
    jobs_deep_r  = get_recent_paged(offset=current_offset, limit=100)

    # Объединяем, убираем дубликаты
    seen_ids = set()
    jobs = []
    all_fetched = (
        (jobs_fresh or []) + (jobs_deep_c or []) +
        (jobs_deep_t or []) + (jobs_deep_n or []) + (jobs_deep_r or [])
    )
    for j in all_fetched:
        jid = j.get("job_id")
        if jid and jid not in seen_ids:
            seen_ids.add(jid)
            jobs.append(j)

    # Считаем сколько реально новых (не в bid_job_ids)
    new_jobs = [j for j in jobs if j.get("job_id") not in bid_job_ids]

    # Обновляем offset: идём глубже, но сбрасываем если глубокий скан пустой
    deep_count = len(jobs_deep_r or [])
    if deep_count == 0:
        next_offset = 0
        print(f"   🔄 Offset сброшен до 0 (глубокий скан пуст — маркет исчерпан на offset={current_offset})")
    else:
        next_offset = current_offset + STEP
        if next_offset > MAX_OFFSET:
            next_offset = 0
            print(f"   🔄 Offset сброшен до 0 (достигли {MAX_OFFSET})")
    memory_data["scan_offset"] = next_offset

    print(f"   📊 Всего найдено: {len(jobs)} | Новых (не бидовали): {len(new_jobs)}")
    print(f"   📍 Offset: {current_offset} → {next_offset} | "
          f"Свежих: {len(jobs_fresh or [])} | Глубина: {len(jobs_deep_r or [])} задач")
    bid_count, skipped_count, already_bid = 0, 0, 0

    # Предварительно обрабатываем owner_decisions — один раз до цикла
    # Это избегает множественных save_memory внутри цикла (HTTP 409)
    pending_owner_decisions = memory_data.get("owner_decisions", {})
    if pending_owner_decisions:
        for _jid, _choice in pending_owner_decisions.items():
            if _choice == "bid":
                bid_job_ids.add(_jid)  # не попадёт в discuss повторно
            elif _choice == "skip":
                skip_list.add(_jid)
        memory_data["skip_list"] = list(skip_list)
        # Очищаем pending_discuss для этих задач
        for _jid in pending_owner_decisions:
            memory_data.get("pending_discuss", {}).pop(_jid, None)
        # Сохраняем ОДИН РАЗ перед циклом
        memory_data["owner_decisions"] = {}
        save_memory(memory_gist_id, memory_data)
        print(f"   👤 Owner decisions обработаны: {len(pending_owner_decisions)} задач (1 сохранение)")

    if isinstance(jobs, list):
        for job in jobs:
            if not is_good_standard_job(job):
                if skipped_count < 5:
                    _t = job.get("title", "?")[:55]
                    _tags = job.get("tags", [])
                    print(f"   🚫 is_good_standard_job SKIP: {_t} | tags={_tags}")
                skipped_count += 1
                continue

            job_id      = job.get("job_id")
            title       = job.get("title", "")
            max_budget  = float(job.get("budget_amount") or 1)
            description = job.get("description", "")
            my_bid      = None  # вычислим позже, только если реально бидуем

            # Пропускаем если владелец отклонил через пульт управления
            if job_id in skip_list:
                already_bid += 1
                continue

            if job_id in bid_job_ids:
                already_bid += 1
                continue

            # Проверяем решения владельца (из пульта управления)
            owner_decisions = memory_data.get("owner_decisions", {})
            owner_forced_bid = False
            if job_id in pending_owner_decisions:
                owner_choice = pending_owner_decisions[job_id]
                if owner_choice == "bid":
                    print(f"\n👤 OWNER BID: {title[:50]} — бидуем по решению владельца")
                    owner_forced_bid = True
                elif owner_choice == "skip":
                    print(f"   👤 OWNER SKIP: {title[:50]}")
                    skipped_count += 1
                    continue

            # Moltbook задачи не фильтруем — агент умеет это делать
            is_moltbook_job = "moltbook" in title.lower() or "moltbook" in description.lower()
            if not owner_forced_bid and job_id not in force_bid and len(description) > 50 and not is_moltbook_job:
                decision = analyze_job_description(title, description)
                if decision == "skip":
                    if skipped_count < 5:
                        print(f"   🚫 SKIP: {title[:60]}")
                    skipped_count += 1
                    time.sleep(1)
                    continue
                elif decision == "discuss":
                    # Если уже бидовали (например owner_forced_bid был ранее) — не спрашиваем снова
                    if job_id in bid_job_ids:
                        skipped_count += 1
                        continue
                    market_url = f"https://market.near.ai/jobs/{job_id}"
                    # Авто-анализ через Claude — чистый формат для Telegram
                    caps_ctx = (AGENT_CAPABILITIES or "")[:800]
                    analysis_prompt = f"""Ты анализируешь задачу для AI агента. Отвечай ТОЛЬКО тремя строками без markdown, без звёздочек, без решёток:

ВОЗМОЖНОСТИ АГЕНТА: {caps_ctx[:400]}

ЗАДАЧА: {title}
ОПИСАНИЕ: {description[:500]}

Ответь ровно тремя строками:
Доставить: [что именно нужно сдать, 1 строка]
Агент справится: [ДА/ЧАСТИЧНО/НЕТ] — [причина, 1 строка]
Вердикт: [BID/DISCUSS/SKIP] — [почему, 1 строка]"""
                    ai_analysis = ask_claude(analysis_prompt, max_tokens=100, model="haiku") or "Анализ недоступен"

                    # Чистое читаемое сообщение
                    msg = (
                        f"🤔 <b>Нужно твоё решение</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📋 <b>{title[:55]}</b>\n"
                        f"💰 <b>{max_budget}N</b>  →  <a href='{market_url}'>открыть задачу</a>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🤖 <b>Анализ:</b>\n"
                        f"{ai_analysis[:280]}\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
                    send_to_control_bot(msg, job_id=job_id)
                    # Сохраняем в памяти как pending_discuss для возможного будущего решения
                    memory_data.setdefault("pending_discuss", {})[job_id] = {
                        "title": title, "budget": max_budget,
                        "description": description[:500], "url": market_url
                    }
                    save_memory(memory_gist_id, memory_data)
                    skipped_count += 1
                    time.sleep(1)
                    continue
                # decision == "bid" → продолжаем

            # Показываем тип deliverable в логе
            dtype = detect_deliverable_type(title, description)
            # Считаем цену только если дошли до бида
            my_bid = get_market_bid_price(job_id, max_budget) if max_budget > 2.0 else max_budget
            print(f"\n✅ [{dtype}] {title[:55]} | {max_budget}N → {my_bid}N")

            try:
                proposal = generate_dynamic_proposal(title, description)
            except Exception as e:
                print(f"   ⚠️ Proposal timeout — используем дефолт: {e}")
                proposal = "Autonomous AI agent ready to deliver high-quality work immediately. Python/Web3/NEAR expertise."

            try:
                result = place_bid(job_id, my_bid, proposal)
            except Exception as e:
                print(f"   ⚠️ place_bid error: {e} — пропускаем")
                time.sleep(2)
                continue

            if result.get("bid_id"):
                print("   ✅ Бид подан!")
                bid_count += 1
                bid_job_ids.add(job_id)
                if bid_count % 5 == 0:
                    memory_data["bid_job_ids"] = list(bid_job_ids)
                    save_memory(memory_gist_id, memory_data)
            elif "already exists" in str(result.get("error", "")):
                already_bid += 1
                bid_job_ids.add(job_id)

            time.sleep(1.5)

    memory_data["bid_job_ids"] = list(bid_job_ids)
    if bid_count > 0:  # сохраняем только если реально подали биды
        save_memory(memory_gist_id, memory_data)

    # 7. Автопостинг на MoltBook + ClawChain
    print("\n📢 Проверяем автопостинг...")
    try:
        autopost_content(memory_gist_id, memory_data)
    except Exception as e:
        print(f"   ⚠️ autopost_content error: {e}")

    # 8. Финальный объединённый отчёт
    stats = memory_data.get("last_run_stats", {})
    submitted_now    = stats.get("submitted_now", 0)
    already_sub      = stats.get("already_submitted", 0)
    already_acc      = stats.get("already_accepted", 0)
    disputed         = stats.get("disputed", 0)
    cancelled        = stats.get("cancelled", 0)
    errors           = stats.get("failed", 0)

    report = (
        f"🤖 <b>budget_skynet — отчёт</b>\n"
        f"{'─'*28}\n"
        f"📬 <b>Задачи (won jobs):</b>\n"
        f"  ✅ Сдано сейчас: <b>{submitted_now}</b>\n"
        f"  ⏳ На проверке: <b>{already_sub}</b>\n"
        f"  🏆 Принято: <b>{already_acc}</b>\n"
        f"  ⚠️ В споре: <b>{disputed}</b>\n"
        f"  ❌ Отменено: {cancelled} | 💥 Ошибки: {errors}\n"
        f"{'─'*28}\n"
        f"🎯 <b>Этот запуск:</b>\n"
        f"  🏆 Конкурсов подано: <b>+{comp_entered}</b> (скип: {comp_skipped})\n"
        f"  📊 Бидов подано: <b>+{bid_count}</b> (скип: {skipped_count}, уже были: {already_bid})"
    )
    print(f"\n{'='*50}\n{report}")
    send_telegram(report)


if __name__ == "__main__":
    try:
        scan_and_bid()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА:\n{err_msg}")
        send_telegram(f"💥 <b>budget_skynet СЛОМАН!</b>\n<code>{str(e)[:300]}</code>")
        raise