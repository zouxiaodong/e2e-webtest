import asyncio
import sys
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径，确保测试脚本可以导入app模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.config import settings
from app.core.database import init_db
from app.api import test_cases, scenarios, configs

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 配置 uvicorn 的日志
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)

# 抑制数据库驱动的 DEBUG 噪音
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# OpenAI 相关库日志（需要排查LLM问题时改为 DEBUG）
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Windows 特定：使用 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程
if sys.platform == 'win32':
    print("[INFO] Setting WindowsSelectorEventLoopPolicy for Playwright support")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(f"[INFO] Current event loop policy: {asyncio.get_event_loop_policy().__class__.__name__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时输出当前配置
    print("=" * 60)
    print("[CONFIG] Current Settings")
    print("=" * 60)
    print(f"App Name: {settings.APP_NAME}")
    print(f"App Version: {settings.APP_VERSION}")
    print(f"Debug: {settings.DEBUG}")
    print(f"LLM Model: {settings.BAILIAN_LLM_MODEL}")
    print(f"VL Model: {settings.BAILIAN_VL_MODEL}")
    print(f"Database: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"Database: {settings.DATABASE_URL}")
    print(f"CORS: {settings.CORS_ORIGINS}")
    print(f"Browser Headless: {settings.BROWSER_HEADLESS}")
    print(f"Browser Timeout: {settings.BROWSER_TIMEOUT}ms")
    print("=" * 60)

    # Initialize database
    print("Initializing database...")
    await init_db()
    print("Database initialization complete")

    # Output actual config from database
    from .models.global_config import GlobalConfig, ConfigKeys
    from sqlalchemy import select
    from .core.database import get_db
    async for db in get_db():
        result = await db.execute(select(GlobalConfig))
        configs = result.scalars().all()
        config_dict = {c.config_key: c.config_value for c in configs}

        print("=" * 60)
        print("[CONFIG] Database Settings")
        print("=" * 60)
        print(f"Target URL: {config_dict.get(ConfigKeys.TARGET_URL, 'Not set')}")
        print(f"Default Username: {config_dict.get(ConfigKeys.DEFAULT_USERNAME, 'Not set')}")
        print(f"Browser Headless: {config_dict.get(ConfigKeys.BROWSER_HEADLESS, 'true')}")
        print(f"Browser Timeout: {config_dict.get(ConfigKeys.BROWSER_TIMEOUT, '30000')}ms")
        print("=" * 60)
        break

    yield
    # Cleanup on shutdown
    print("Application shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI E2E Testing Platform - Scenario and Test Case Management",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    print(f"[REQUEST] {request.method} {request.url.path} - Client: {request.client.host}")
    logger.info(f"[REQUEST] {request.method} {request.url.path} - Client: {request.client.host}")
    
    try:
        response = await call_next(request)
        print(f"[RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
        logger.info(f"[RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
        return response
    except Exception as e:
        print(f"[ERROR] {request.method} {request.url.path} - {type(e).__name__}: {str(e)}")
        logger.error(f"[ERROR] {request.method} {request.url.path} - {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

# 注册路由
app.include_router(test_cases.router)
app.include_router(scenarios.router)
app.include_router(configs.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI驱动的端到端测试平台",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理，记录所有未捕获的异常"""
    error_msg = f"❌ Unhandled exception: {request.method} {request.url.path} - {type(exc).__name__}: {str(exc)}"
    print(error_msg)
    logger.error(error_msg)
    import traceback
    traceback_str = traceback.format_exc()
    print(traceback_str)
    logger.error(traceback_str)
    return JSONResponse(
        status_code=500,
        content={"error": f"Internal Server Error: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("[STARTING] FastAPI server...")
    print("=" * 60)
    print("=" * 60)
    print("[CONFIG] Current Settings")
    print("=" * 60)
    print(f"App Name: {settings.APP_NAME}")
    print(f"App Version: {settings.APP_VERSION}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"LLM Model: {settings.BAILIAN_LLM_MODEL}")
    print(f"VL Model: {settings.BAILIAN_VL_MODEL}")
    print(f"Database: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"Database: {settings.DATABASE_URL}")
    print(f"CORS Origins: {settings.CORS_ORIGINS}")
    print(f"Browser Headless: {settings.BROWSER_HEADLESS}")
    print(f"Browser Timeout: {settings.BROWSER_TIMEOUT}ms")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 禁用 reload 以避免日志问题
        access_log=True,
        log_level="info",
        use_colors=True
    )