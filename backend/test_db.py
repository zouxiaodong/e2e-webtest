import asyncio
from app.core.database import engine
from sqlalchemy import text

async def test_db():
    async with engine.begin() as conn:
        # 检查连接
        result = await conn.execute(text("SELECT 1"))
        print(f"数据库连接成功: {result.scalar()}")

        # 检查表是否存在
        result = await conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        print(f"数据库中的表: {tables}")

asyncio.run(test_db())