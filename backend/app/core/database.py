from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, text
from datetime import datetime
from .config import settings

# 从 models 导入基类（避免循环导入）
from ..models.test_case import Base as BaseModel
from ..models.global_config import GlobalConfig
from ..models.test_session import TestSession

# 使用导入的基类
Base = BaseModel

# 导入所有模型以确保它们被注册到 Base.metadata
from ..models.test_case import TestScenario, TestCase, TestReport, TestStepResult

# 创建异步数据库引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
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
    print("正在初始化数据表...")
    print("=" * 50)

    try:
        # 创建数据表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("✅ 数据表创建完成")

        print("=" * 50)
        print("✅ 数据表初始化完成！")
        print("=" * 50)
    except Exception as e:
        print("=" * 50)
        print(f"❌ 数据表初始化失败: {e}")
        print("=" * 50)
        raise