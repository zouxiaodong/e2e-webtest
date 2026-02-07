import asyncio
from app.core.database import get_db
from app.models.global_config import GlobalConfig
from sqlalchemy import select

async def test():
    async for db in get_db():
        result = await db.execute(select(GlobalConfig))
        configs = result.scalars().all()
        print('Configs:', configs)
        break

asyncio.run(test())