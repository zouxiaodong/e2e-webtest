"""
MySQL 数据表初始化脚本
注意：数据库 'e2etest' 需要先手动创建
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.test_case import Base


async def create_tables():
    """创建数据表"""
    print("=" * 50)
    print("开始创建数据表...")
    print("=" * 50)
    
    print(f"数据库地址: {settings.DATABASE_URL}")
    
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True
    )

    try:
        async with engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            print("✅ 数据表创建成功")
        
        print("=" * 50)
        print("✅ 数据表初始化完成！")
        print("=" * 50)
    except Exception as e:
        print("=" * 50)
        print(f"❌ 创建数据表失败: {e}")
        print("=" * 50)
        raise
    finally:
        await engine.dispose()


async def init_database():
    """初始化数据表"""
    await create_tables()


if __name__ == "__main__":
    print("注意：请确保数据库 'e2etest' 已存在")
    print("如果数据库不存在，请联系管理员创建数据库")
    print()
    
    try:
        asyncio.run(init_database())
    except Exception as e:
        print(f"\n初始化失败: {e}")
        print("\n可能的解决方案：")
        print("1. 确保数据库 'e2etest' 已存在")
        print("2. 检查数据库连接配置（.env 文件）")
        print("3. 确认用户 'e2e' 有访问数据库 'e2etest' 的权限")