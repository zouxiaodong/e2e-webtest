from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, text, event
from datetime import datetime
import logging
from .config import settings

# SQLAlchemy engine 日志：仅输出 WARNING 及以上（屏蔽大量 SQL INFO 日志）
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# 从 models 导入基类（避免循环导入）
from ..models.test_case import Base as BaseModel
from ..models.global_config import GlobalConfig
from ..models.test_session import TestSession

# 使用导入的基类
Base = BaseModel

# 导入所有模型以确保它们被注册到 Base.metadata
from ..models.test_case import TestScenario, TestCase, TestReport, TestStepResult

# 检测数据库类型
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# 创建异步数据库引擎
# echo="debug" 会输出所有SQL，echo=True 输出SQL语句，echo=False 关闭
# 使用 echo=False + logging WARNING 级别，避免日志中大量 SQL INFO 输出
engine_kwargs = {
    "echo": False,
    "future": True
}

# SQLite 需要特殊处理
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)




async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库（创建数据表）"""
    print("=" * 50)
    print("Initializing database tables...")
    print("=" * 50)

    try:
        # 创建数据表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("[OK] Database tables created")

        print("=" * 50)
        print("[OK] Database initialization complete!")
        print("=" * 50)
    except Exception as e:
        print("=" * 50)
        print(f"[ERROR] Database initialization failed: {e}")
        print("=" * 50)
        raise