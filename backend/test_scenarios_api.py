import asyncio
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.test_case import TestScenario

async def test_scenarios_query():
    async with async_session_maker() as session:
        try:
            # 测试查询
            query = select(TestScenario)
            result = await session.execute(query)
            scenarios = result.scalars().all()
            print(f"查询成功，找到 {len(scenarios)} 个场景")
            for s in scenarios:
                print(f"  - ID: {s.id}, Name: {s.name}")
        except Exception as e:
            print(f"查询失败: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test_scenarios_query())