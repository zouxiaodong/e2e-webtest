# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-Driven End-to-End (E2E) Testing Platform** that allows users to generate and execute automated browser tests using natural language descriptions. It combines Qwen LLM models from Aliyun's Bailian platform with Playwright for web automation.

**Stack:**
- Backend: FastAPI + SQLAlchemy (async MySQL)
- Frontend: Vue 3 + Element Plus
- LLM: Aliyun Bailian (Qwen models)
- Browser Automation: Playwright
- Architecture: Scenario-based test management with session reuse

## Quick Start Commands

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Edit .env with your Bailian API key and database credentials
python start_server.py
# OR: python -m app.main
```

Backend runs on `http://localhost:8000` with auto-reload enabled. API docs available at `/docs`.

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5174`.

### Database Setup
```bash
# Create database
mysql -u root -p
CREATE DATABASE e2etest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Note: If using special characters in DB password, URL-encode them (e.g., `@` → `%40`).

### Running Tests
```bash
cd backend
pytest
```

## Key Architecture Notes

### Backend Structure
- **app/api/** - API routes (test_cases, scenarios, configs)
- **app/models/** - SQLAlchemy models (TestScenario, TestCase, TestSession, GlobalConfig)
- **app/schemas/** - Pydantic schemas for request/response validation
- **app/services/**
  - **llm/** - Bailian API client for test generation
  - **generator/** - Test generation engine (analyzes scenarios → generates test cases)
  - **executor/** - Test execution engine (Playwright automation)
  - **captcha/** - CAPTCHA recognition using qwen-vl-plus
  - **session/** - Session persistence for login reuse
  - **computer_use/** - Computer Use API subprocess handler

### Frontend Structure
- **src/api/** - API client functions
- **src/views/** - Page components (QuickGenerate, Scenarios, Configs, etc.)
- **src/router/** - Route definitions
- **src/components/** - Reusable UI components

### Critical Design Patterns

**1. Scenario-Based Testing**
The platform operates at the scenario level, not individual test cases. Each scenario can generate multiple test cases based on strategy:
- **Happy Path** (仅正向测试) - 1 test case (positive flow)
- **Basic** (基础覆盖) - 3 test cases (positive, exception, boundary)
- **Comprehensive** (全面测试) - 5 test cases (positive, negative, boundary, exception, security)

Models: `TestScenario` (1) → (N) `TestCase` with priority (P0-P3) and type (positive, negative, boundary, exception, security, etc.).

**2. Session Management**
Avoid repeated login/LLM calls via session reuse:
- **no_login** - Public pages, no session needed
- **perform_login** - Execute login, optionally save session
- **use_global_session** - Reuse global login session
- **use_session** - Reuse specific saved session

Sessions store cookies, localStorage, and sessionStorage. TTL: 24 hours by default.

**3. LLM Integration**
Tests are generated via Qwen LLM:
- `TestGenerator` parses scenario → generates test code
- Qwen-vl-plus used for CAPTCHA detection
- All LLM interactions logged to `backend/logs/llm_interactions.log`

**4. Windows Event Loop Issue**
The code explicitly handles Windows Playwright compatibility:
```python
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```
This is set in both `start_server.py` and `app/main.py`. **Do not remove this.**

### Important Implementation Notes

- **Async/await everywhere**: All database calls and service methods are async
- **Playwright subprocess**: Computer Use service spawns subprocess with event loop policy
- **SQLAlchemy relationships**: Models use async session + selectinload/raiseload to avoid lazy loading issues (see recent commits)
- **API endpoint organization**: New endpoints should follow RESTful conventions
- **Test data**: Use `/api/global-config` for centralized username/password/URL configuration

## Environment Variables

Required in `backend/.env`:
```
BAILIAN_API_KEY=your_key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_VL_MODEL=qwen-vl-plus
DATABASE_URL=mysql+aiomysql://user:password@host/e2etest
BROWSER_HEADLESS=True
BROWSER_TIMEOUT=30000
```

## Common Development Tasks

**Adding a new API endpoint:**
1. Create schema in `app/schemas/`
2. Create/update model in `app/models/`
3. Create route in `app/api/`
4. Integrate service logic from `app/services/`
5. Update CORS settings in `app/main.py` if needed

**Modifying test generation logic:**
- Edit `app/services/generator/test_generator.py`
- Understand scenario analysis flow before generating test cases
- Refer to `IMPROVEMENTS.md` for multi-strategy generation

**Debugging LLM issues:**
- Check `backend/logs/llm_interactions.log` for full API requests/responses
- Verify Bailian API key in `.env`
- Check token limits for qwen-plus model

**Fixing Playwright execution issues:**
- Ensure `playwright install chromium` was run
- On Windows, verify event loop policy is set
- Check `BROWSER_HEADLESS` setting in `.env`

## Documentation Files

- **README.md** - User guide, setup instructions, feature overview
- **IMPROVEMENTS.md** - Detailed explanation of scenario-based testing and generation strategies
- **SESSION_MANAGEMENT.md** - Session persistence and reuse architecture
- **AGENTS.md** - Original LangGraph-based agent architecture (reference only)

## Database Schema Highlights

Key relationships:
- `TestScenario` (1) → (N) `TestCase` (scenario_id foreign key)
- `TestCase` → `TestReport` (test_case_id foreign key)
- `TestSession` → usage tracked via `last_used_at`
- `GlobalConfig` - singleton pattern for system-wide settings

Fields to note:
- `TestCase.priority` - P0/P1/P2/P3
- `TestCase.case_type` - positive/negative/boundary/exception/security/performance/compatibility
- `TestSession.expires_at` - automatic expiration logic needed in cleanup
- `TestScenario.generation_strategy` - happy_path/basic/comprehensive

## Git Notes

Recent commits focus on:
- Event loop policy fixes for Windows + Playwright
- SQLAlchemy async/await pattern consistency
- selectinload/raiseload for relationship optimization
- Computer Use subprocess integration

Current working state: `backend/start_server.py` has uncommitted changes (likely debug output or settings).
