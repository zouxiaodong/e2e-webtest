"""
Script to optimize browser reuse in test generation
"""
import re

# Read the file
with open('D:/researches/e2etest/backend/app/services/executor/test_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modify _generate_computer_use_script function signature to add page_content parameter
old_sig = '''    async def _generate_computer_use_script(
        self,
        target_url: str,
        actions: list,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True
    ) -> str:
        """
        使用 Computer-Use 方案生成测试脚本
        Args:
            target_url: 目标URL
            actions: 操作列表
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
        Returns:
            完整的测试脚本
        """
        print(f"\\n   使用 Computer-Use 方案生成脚本...")
        print(f"   目标URL: {target_url}")
        print(f"   操作数量: {len(actions)}")'''

new_sig = '''    async def _generate_computer_use_script(
        self,
        target_url: str,
        actions: list,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True,
        page_content: dict = None
    ) -> str:
        """
        使用 Computer-Use 方案生成测试脚本
        Args:
            target_url: 目标URL
            actions: 操作列表
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
            page_content: 可选的页面内容（包含screenshot），如果有则复用避免重新打开浏览器
        Returns:
            完整的测试脚本
        """
        print(f"\\n   使用 Computer-Use 方案生成脚本...")
        print(f"   目标URL: {target_url}")
        print(f"   操作数量: {len(actions)}")
        print(f"   已有页面内容: {'是' if page_content and page_content.get('screenshot') else '否'}")'''

content = content.replace(old_sig, new_sig)

# 2. Modify the call to _generate_computer_use_script to pass page_content
old_call = '''final_script = await self._generate_computer_use_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage
            )'''

new_call = '''final_script = await self._generate_computer_use_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage,
                page_content=page_content
            )'''

content = content.replace(old_call, new_call)

# Write the file back
with open('D:/researches/e2etest/backend/app/services/executor/test_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Modified test_executor.py")
