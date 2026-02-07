import asyncio
from sqlalchemy import text
from app.core.database import engine

async def add_missing_columns():
    async with engine.begin() as conn:
        # 检查字段是否存在
        result = await conn.execute(text("DESCRIBE test_scenarios"))
        columns = [row[0] for row in result.fetchall()]
        print(f"当前表的字段: {columns}")

        # 添加 login_config 字段
        if 'login_config' not in columns:
            print("添加 login_config 字段...")
            await conn.execute(text("ALTER TABLE test_scenarios ADD COLUMN login_config VARCHAR(50) DEFAULT 'no_login' COMMENT '登录配置'"))
        else:
            print("login_config 字段已存在")

        # 添加 session_id 字段
        if 'session_id' not in columns:
            print("添加 session_id 字段...")
            await conn.execute(text("ALTER TABLE test_scenarios ADD COLUMN session_id INT COMMENT '关联的会话ID'"))
        else:
            print("session_id 字段已存在")

        # 添加 save_session 字段
        if 'save_session' not in columns:
            print("添加 save_session 字段...")
            await conn.execute(text("ALTER TABLE test_scenarios ADD COLUMN save_session BOOLEAN DEFAULT FALSE COMMENT '是否保存会话'"))
        else:
            print("save_session 字段已存在")

        # 再次检查
        result = await conn.execute(text("DESCRIBE test_scenarios"))
        columns = [row[0] for row in result.fetchall()]
        print(f"更新后的字段: {columns}")
        print("✅ 字段添加完成！")

asyncio.run(add_missing_columns())