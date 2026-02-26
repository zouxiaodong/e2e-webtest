# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-Driven E2E Testing Platform: users describe tests in natural language, the platform generates and executes Playwright browser tests via Qwen LLM (Aliyun Bailian).

**Stack:** FastAPI + SQLAlchemy (async) · Vue 3 + Element Plus · Qwen LLM (qwen-plus / qwen-vl-plus) · Playwright

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env          # fill in BAILIAN_API_KEY and DATABASE_URL
python start_server.py        # OR: python -m app.main
```
Runs on `http://localhost:8000`. Swagger docs at `/docs`.

### Frontend
```bash
cd frontend
npm install
npm run dev                   # runs on http://localhost:5174
```
Vite proxies `/api` → `http://127.0.0.1:8000`.

### Database
Default: **SQLite** (`sqlite+aiosqlite:///./e2etest.db`) — no setup needed.
For MySQL: `CREATE DATABASE e2etest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
Special characters in DB password must be URL-encoded (`@` → `%40`).

### Tests
```bash
cd backend && pytest
```

## Environment Variables (`backend/.env`)

```
BAILIAN_API_KEY=your_key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_VL_MODEL=qwen-vl-plus
DATABASE_URL=sqlite+aiosqlite:///./e2etest.db   # or mysql+aiomysql://...
BROWSER_HEADLESS=True
BROWSER_TIMEOUT=30000
SESSION_STORAGE_PATH=./session_storage          # optional; defaults to {cwd}/session_storage
```

Dynamic settings (editable via UI at `/api/configs`) override `.env` for: `TARGET_URL`, `DEFAULT_USERNAME`, `DEFAULT_PASSWORD`, `CAPTCHA_SELECTOR`, `CAPTCHA_INPUT_SELECTOR`, `BROWSER_HEADLESS`, `BROWSER_TIMEOUT`, `USE_COMPUTER_USE`.

## Architecture

### Data Model

```
TestScenario (1) ──→ (N) TestCase ──→ (N) TestReport ──→ (N) TestStepResult
TestSession (login sessions, 24h TTL)
GlobalConfig (key-value singleton settings)
```

**TestScenario** key fields: `generation_strategy` (happy_path/basic/comprehensive), `login_config` (no_login/perform_login/use_global_session/use_session), `use_captcha`, `save_session`, `session_id` FK.

**TestCase** key fields: `priority` (P0–P3), `case_type` (positive/negative/boundary/exception/security/performance/compatibility), `actions` (JSON array), `script` (Playwright Python script).

**TestStepResult** `step_type`: navigation|click|fill|verify|wait|screenshot.

### Test Generation Flow (`app/services/generator/test_generator.py`)

1. **Fetch page content**: Spawns a subprocess running Playwright to screenshot the page and extract cleaned HTML (uses `lxml.html.clean.Cleaner` to strip CSS/JS before sending to LLM).
2. **Session loading** (if applicable): Injects cookies before navigation; injects localStorage/sessionStorage after load + refreshes page to activate login state; 5-second wait for SSE to settle.
3. **Page analysis**: Calls qwen-vl-plus on screenshot; falls back to regex HTML parsing if VL fails.
4. **Case generation by strategy**:
   - `happy_path` → 1 case (positive, P0)
   - `basic` → 3 cases (positive P0, exception P1, boundary P2)
   - `comprehensive` → 5 cases (positive P0, negative P1, boundary P2, exception P2, security P3)
5. **Playwright code generation**: Calls qwen-plus with DOM state + previous actions context → returns atomic async Python code. Selector priority: `data-testid` > `name` attribute > other strategies. Includes 2-second waits after each action.

All LLM calls are logged (request + response + timing) to `backend/logs/llm_interactions.log` via `app/core/llm_logger.py`.

### Test Execution Flow (`app/services/executor/test_executor.py`)

- `generate_script_only()`: generates script without executing (main path for UI).
- Actual Playwright work runs via `_run_playwright_in_thread()` in a `ThreadPoolExecutor` — see Windows event loop section below.
- `playwright_processor.py`: subprocess handler that runs synchronous Playwright API, loads session storage, iterates actions, optionally detects CAPTCHA, optionally uses Computer Use for element location.

### Windows Event Loop (Critical — Do Not Change)

Two different policies are needed:

| Location | Policy | Reason |
|---|---|---|
| `start_server.py` + `app/main.py` (main thread) | `WindowsSelectorEventLoopPolicy` | uvicorn/FastAPI compatibility |
| `test_executor.py` thread worker | `WindowsProactorEventLoopPolicy` | subprocess support required by Playwright |

The thread worker explicitly creates a new event loop (`asyncio.new_event_loop()`) and sets Proactor policy before running Playwright.

### Session Management

Session data (cookies, localStorage, sessionStorage) stored as JSON in `SESSION_STORAGE_PATH`.
- `no_login`: skip session entirely
- `perform_login`: run login flow, optionally call `session_manager.save_session()`
- `use_global_session` / `use_session`: call `session_manager.restore_session()` before page load

`session_manager.py` methods: `save_session`, `restore_session`, `clear_session`, `is_session_expired` (24h TTL), `get_session_summary`.

### CAPTCHA Handling

`captcha_handler.py` uses qwen-vl-plus to recognize CAPTCHA images. When `auto_detect_captcha=True`, verification-type actions (keywords: 验证, 断言, assert…) are skipped during processing and `browser_util.detect_and_solve_captcha(page)` is called before login button clicks.

### SQLAlchemy Async Patterns

- All DB operations use `AsyncSession` with `async/await`.
- Always use `selectinload` for relationships (e.g., `TestReport.step_results`) to avoid `MissingGreenlet` errors. Do **not** use lazy loading.
- `database.py` auto-detects SQLite vs MySQL via `is_sqlite = settings.DATABASE_URL.startswith("sqlite")` and adjusts engine kwargs (e.g., `check_same_thread=False` for SQLite).

## Key Files

| File | Purpose |
|---|---|
| `backend/app/services/generator/test_generator.py` | LLM-based test case + Playwright code generation |
| `backend/app/services/executor/test_executor.py` | Script generation, thread management, execution |
| `backend/app/services/executor/playwright_processor.py` | Subprocess Playwright runner |
| `backend/app/services/session/session_manager.py` | Login session persistence |
| `backend/app/services/tools/captcha_handler.py` | CAPTCHA recognition via VL model |
| `backend/app/core/config.py` | Settings (env vars + defaults) |
| `backend/app/core/database.py` | Async DB engine + session factory |
| `backend/app/models/test_case.py` | TestScenario, TestCase, TestReport, TestStepResult models |
| `backend/app/models/test_session.py` | TestSession model + LoginConfig enum |

## API Endpoints

**Scenarios** (`/api/scenarios`): CRUD + `POST /{id}/generate`, `POST /{id}/execute`, `GET /{id}/cases`, `GET /{id}/reports`, `GET /{id}/reports/{report_id}/steps`, `POST /quick-generate`

**Test Cases** (`/api/test-cases`): CRUD + `POST /{id}/generate`, `POST /{id}/execute`, `GET /{id}/reports`

**Configs** (`/api/configs`): `GET|PUT /settings` (bulk), `GET|PUT /{config_key}` (single)

## Documentation Files

- **IMPROVEMENTS.md** — scenario-based testing evolution, multi-strategy generation details
- **SESSION_MANAGEMENT.md** — session persistence architecture
- **backend/LLM_LOGS.md** — LLM interaction logging format
