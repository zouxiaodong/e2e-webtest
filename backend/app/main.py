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
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 配置 uvicorn 的日志
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)

# 配置 OpenAI 和相关库的日志级别为 DEBUG，查看详细请求和响应
logging.getLogger("openai").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

# Windows 特定：使用 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程
if sys.platform == 'win32':
    print("🔄 设置 WindowsSelectorEventLoopPolicy 以支持 Playwright")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(f"✅ 当前事件循环策略: {asyncio.get_event_loop_policy().__class__.__name__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时输出当前配置
    print("=" * 60)
    print("📋 当前配置 (Settings)")
    print("=" * 60)
    print(f"应用名称: {settings.APP_NAME}")
    print(f"应用版本: {settings.APP_VERSION}")
    print(f"调试模式: {settings.DEBUG}")
    print(f"百练 LLM 模型: {settings.BAILIAN_LLM_MODEL}")
    print(f"百练 VL 模型: {settings.BAILIAN_VL_MODEL}")
    print(f"数据库: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"数据库: {settings.DATABASE_URL}")
    print(f"CORS 允许源: {settings.CORS_ORIGINS}")
    print(f"浏览器无头模式（默认）: {settings.BROWSER_HEADLESS}")
    print(f"浏览器超时（默认）: {settings.BROWSER_TIMEOUT}ms")
    print("=" * 60)

    # 初始化数据库
    print("正在初始化数据库...")
    await init_db()
    print("数据库初始化完成")

    # 输出数据库中的实际配置
    from .models.global_config import GlobalConfig, ConfigKeys
    from sqlalchemy import select
    from .core.database import get_db
    async for db in get_db():
        result = await db.execute(select(GlobalConfig))
        configs = result.scalars().all()
        config_dict = {c.config_key: c.config_value for c in configs}

        print("=" * 60)
        print("📋 数据库中的实际配置")
        print("=" * 60)
        print(f"目标URL: {config_dict.get(ConfigKeys.TARGET_URL, '未设置')}")
        print(f"默认用户名: {config_dict.get(ConfigKeys.DEFAULT_USERNAME, '未设置')}")
        print(f"浏览器无头模式: {config_dict.get(ConfigKeys.BROWSER_HEADLESS, 'true')} ({'关闭' if config_dict.get(ConfigKeys.BROWSER_HEADLESS) == 'false' else '开启'})")
        print(f"浏览器超时: {config_dict.get(ConfigKeys.BROWSER_TIMEOUT, '30000')}ms")
        print("=" * 60)
        break

    yield
    # 关闭时的清理工作
    print("应用关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI驱动的端到端测试平台 - 支持场景与用例管理",
    lifespan=lifespan
)

# 配置CORS（开发环境：允许所有）
# 注意：由于前端使用 vite 代理，理论上不需要 CORS 配置
# 但为了保险起见，保留简单的允许所有配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求"""
    print(f"📥 [REQUEST] {request.method} {request.url.path} - Client: {request.client.host}")
    logger.info(f"📥 [REQUEST] {request.method} {request.url.path} - Client: {request.client.host}")
    
    try:
        response = await call_next(request)
        print(f"📤 [RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
        logger.info(f"📤 [RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
        return response
    except Exception as e:
        print(f"❌ [ERROR] {request.method} {request.url.path} - {type(e).__name__}: {str(e)}")
        logger.error(f"❌ [ERROR] {request.method} {request.url.path} - {type(e).__name__}: {str(e)}")
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
    print("🚀 Starting FastAPI server...")
    print("=" * 60)
    print("=" * 60)
    print("📋 当前配置 (Settings)")
    print("=" * 60)
    print(f"应用名称: {settings.APP_NAME}")
    print(f"应用版本: {settings.APP_VERSION}")
    print(f"调试模式: {settings.DEBUG}")
    print(f"百练 LLM 模型: {settings.BAILIAN_LLM_MODEL}")
    print(f"百练 VL 模型: {settings.BAILIAN_VL_MODEL}")
    print(f"数据库: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"数据库: {settings.DATABASE_URL}")
    print(f"CORS 允许源: {settings.CORS_ORIGINS}")
    print(f"浏览器无头模式: {settings.BROWSER_HEADLESS}")
    print(f"浏览器超时: {settings.BROWSER_TIMEOUT}ms")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 禁用 reload 以避免日志问题
        access_log=True,
        log_level="debug",
        use_colors=True
    )