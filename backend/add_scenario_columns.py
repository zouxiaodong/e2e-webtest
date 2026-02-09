"""数据库迁移脚本：为 test_scenarios 表添加验证码和 Cookie/LocalStorage 配置字段"""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def add_scenario_columns():
    """为 test_scenarios 表添加新字段"""
    async with engine.begin() as conn:
        print("正在为 test_scenarios 表添加新字段...")
        
        # 检查字段是否已存在
        check_sql = text("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'test_scenarios' 
            AND COLUMN_NAME = 'use_captcha'
        """)
        result = await conn.execute(check_sql)
        count = result.fetchone()[0]
        
        if count == 0:
            # 添加 use_captcha 字段
            await conn.execute(text("""
                ALTER TABLE test_scenarios 
                ADD COLUMN use_captcha BOOLEAN DEFAULT FALSE COMMENT '是否使用验证码'
            """))
            print("✅ 已添加 use_captcha 字段")
        else:
            print("⚠️ use_captcha 字段已存在，跳过")
        
        # 检查 auto_cookie_localstorage 字段
        check_sql = text("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'test_scenarios' 
            AND COLUMN_NAME = 'auto_cookie_localstorage'
        """)
        result = await conn.execute(check_sql)
        count = result.fetchone()[0]
        
        if count == 0:
            # 添加 auto_cookie_localstorage 字段
            await conn.execute(text("""
                ALTER TABLE test_scenarios 
                ADD COLUMN auto_cookie_localstorage BOOLEAN DEFAULT TRUE COMMENT '自动加载和保存 cookie/localstorage'
            """))
            print("✅ 已添加 auto_cookie_localstorage 字段")
        else:
            print("⚠️ auto_cookie_localstorage 字段已存在，跳过")
        
        print("\n✅ 数据库迁移完成！")


if __name__ == "__main__":
    asyncio.run(add_scenario_columns())
