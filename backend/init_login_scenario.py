"""
初始化SQLite数据库并创建登录测试场景的脚本
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.database import init_db, async_session_maker
from app.models.test_case import TestScenario
from sqlalchemy import select


async def create_login_scenario():
    """创建登录测试场景"""
    async with async_session_maker() as db:
        # 检查是否已存在同名场景
        result = await db.execute(
            select(TestScenario).where(TestScenario.name == "登录测试场景")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"场景已存在，ID: {existing.id}")
            return existing
        
        # 创建新场景
        scenario = TestScenario(
            name="登录测试场景",
            description="测试登录功能，输入正确的用户名和密码，验证登录成功",
            target_url="https://xas.stelguard.com/login?redirect=/index",
            user_query="测试登录功能，输入正确的用户名和密码，验证登录成功",
            generation_strategy="happy_path",
            status="draft"
        )
        db.add(scenario)
        await db.commit()
        await db.refresh(scenario)
        print(f"场景创建成功，ID: {scenario.id}")
        return scenario


async def main():
    print("=" * 50)
    print("1. 初始化数据库...")
    print("=" * 50)
    await init_db()
    
    print("=" * 50)
    print("2. 创建登录测试场景...")
    print("=" * 50)
    scenario = await create_login_scenario()
    
    print("=" * 50)
    print("3. 场景信息:")
    print("=" * 50)
    print(f"  场景ID: {scenario.id}")
    print(f"  场景名称: {scenario.name}")
    print(f"  目标URL: {scenario.target_url}")
    print(f"  用户查询: {scenario.user_query}")
    print(f"  生成策略: {scenario.generation_strategy}")
    print("=" * 50)
    print("请在界面上进行以下操作:")
    print(f"  1. 生成测试用例: POST /api/scenarios/{scenario.id}/generate")
    print(f"  2. 执行测试用例: POST /api/scenarios/{scenario.id}/execute")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
