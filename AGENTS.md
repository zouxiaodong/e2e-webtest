# AGENTS.md - AI E2E Testing Platform

AI-driven E2E testing platform using LLM (Bailian/Qwen) to generate Playwright test cases from natural language.

## Tech Stack

- **Backend**: FastAPI 0.115, SQLAlchemy 2.0 (async), MySQL, Python 3.11+
- **Frontend**: Vue 3, Element Plus, Vite
- **Testing**: Playwright, pytest
- **LLM**: Bailian (Qwen-plus for text, Qwen-vl-plus for vision)

## Build, Run & Test Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
# Create database: CREATE DATABASE e2etest CHARACTER SET utf8mb4;
python -m app.main          # API: http://localhost:8000/docs
# OR python start_server.py
```

### Frontend
```bash
cd frontend && npm install
npm run dev     # http://localhost:5174
npm run build   # Production build
```

### Running Tests
```bash
cd backend
pytest                          # Run all tests
pytest test_api.py              # Run specific file
pytest -k "test_name"           # Run by keyword
pytest test_api.py::test_name -v # Run single test function
pytest -v                       # Verbose output
pytest --playwright             # Playwright tests
python test_api.py              # Run standalone async scripts
```

## Code Style Guidelines

### Python (Backend)

**Imports**: stdlib → third-party → local
```python
import asyncio, sys, os, logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import get_db
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseResponse
```

**Naming**: Classes=PascalCase, Functions/vars=snake_case, Constants=UPPER_SNAKE_CASE, Tables=snake_case plural

**Types**: Use `Optional[X]` (not `X | None`) and `List[X]` (not `list[X]`) for compatibility

**Async/Await**: All DB/I/O must be async. Use `AsyncSession`. Windows requires:
```python
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

**Error Handling**: Use HTTPException, proper status codes, log errors before raising

```python
try:
    result = await db.execute(select(TestCase).where(TestCase.id == test_case_id))
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
except Exception as e:
    logger.error(f"Error: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
```

**SQLAlchemy Models**:
```python
class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="用例名称")
    status = Column(String(50), default="draft", comment="状态")
```

**FastAPI Routes**:
```python
router = APIRouter(prefix="/api/test-cases", tags=["测试用例"])

@router.get("/", response_model=List[TestCaseResponse])
async def list_test_cases(db: AsyncSession = Depends(get_db)):
    ...
```

### Frontend (Vue 3)
- Use Composition API with `<script setup>`
- Use Element Plus components
- Use Pinia for state management

## Project Structure
```
backend/
├── app/
│   ├── api/           # FastAPI routes
│   ├── core/          # config.py, database.py
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   └── services/      # llm/, generator/, executor/, captcha/
├── requirements.txt
└── .env               # Local config (not committed)

frontend/
├── src/
│   ├── api/, views/, components/, router/
├── package.json
└── vite.config.js
```

## Key Files
- `backend/app/main.py` - FastAPI entry point
- `backend/app/core/config.py` - Settings
- `backend/app/core/database.py` - Database connection
- `backend/app/services/executor/test_executor.py` - Test execution
- `backend/app/services/generator/test_generator.py` - Test generation
- `backend/app/services/llm/bailian_client.py` - LLM client

## Environment Variables
Copy `backend/.env.example` to `backend/.env`:
```env
BAILIAN_API_KEY=your_key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_LLM_MODEL=qwen-plus
BAILIAN_VL_MODEL=qwen-vl-plus
DATABASE_URL=mysql+aiomysql://user:pass@host:port/db
DEBUG=True
BROWSER_HEADLESS=True
BROWSER_TIMEOUT=30000
```

## Important Notes
- **Windows**: Use `asyncio.WindowsSelectorEventLoopPolicy()` for Playwright
- **Database**: Use `selectinload`/`raiseload` for SQLAlchemy relationships to avoid lazy loading
- **Tests**: Most test files are standalone async scripts run with `python test_file.py`
