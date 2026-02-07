import asyncio
import io
import re
import sys
from typing import Dict, Any, Optional
from contextlib import redirect_stdout
from datetime import datetime
import pytest
import ipytest
import nest_asyncio

from ..generator.test_generator import test_generator
from ..captcha.captcha_service import captcha_service
from ..llm.bailian_client import bailian_client


class TestExecutor:
    """测试执行引擎 - 使用持久化浏览器会话"""

    def __init__(self):
        self.dom_state: str = ""
        self.aggregated_actions: str = ""

    async def execute_workflow(
        self,
        user_query: str,
        target_url: str,
        auto_detect_captcha: bool = False
    ) -> Dict[str, Any]:
        """
        执行完整的工作流 - 只打开一次浏览器
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect_captcha: 是否自动检测验证码
        Returns:
            执行结果
        """
        result = {
            "status": "success",
            "actions": [],
            "script": "",
            "test_name": "",
            "error": None,
            "execution_output": "",
            "report": ""
        }

        try:
            print("\n===== 开始执行测试工作流 =====")
            print(f"用户查询: {user_query}")
            print(f"目标URL: {target_url}")
            print(f"自动检测验证码: {auto_detect_captcha}")

            # 步骤1: 生成操作步骤
            print("\n步骤1: 生成操作步骤...")
            actions = await test_generator.generate_actions(user_query, target_url)
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")
            for i, action in enumerate(actions):
                print(f"   {i+1}. {action}")

            # 步骤2: 生成完整脚本（一次性生成所有操作）
            print("\n步骤2: 生成完整测试脚本...")
            final_script = await self._generate_complete_script(
                target_url, actions, auto_detect_captcha
            )
            result["script"] = final_script
            print("✅ 脚本生成完成")

            # 步骤3: 生成测试名称
            print("\n步骤3: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, actions)
            result["test_name"] = test_name
            print(f"✅ 生成测试名称: {test_name}")

            # 步骤4: 执行测试（只打开一次浏览器）
            print("\n步骤4: 执行测试...")
            print("   正在执行测试（只打开一次浏览器）...")
            execution_output = await self._execute_test(final_script)
            result["execution_output"] = execution_output
            print("✅ 测试执行完成")

            # 步骤5: 生成报告
            print("\n步骤5: 生成报告...")
            report = await self._generate_report(result)
            result["report"] = report
            print("✅ 生成报告完成")

            print("\n===== 测试工作流执行完成 =====")
            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ 执行过程中出现错误: {str(e)}")
            print(f"\n错误详情:\n{error_detail}")
            return result

    async def _generate_complete_script(
        self,
        target_url: str,
        actions: list,
        auto_detect_captcha: bool
    ) -> str:
        """
        生成完整的测试脚本（一次性生成所有操作）
        Args:
            target_url: 目标URL
            actions: 操作步骤列表
            auto_detect_captcha: 是否自动检测验证码
        Returns:
            完整的测试脚本
        """
        # 获取浏览器配置
        browser_headless = False
        from ...core.database import get_db
        from ...models.global_config import GlobalConfig, ConfigKeys
        from sqlalchemy import select

        async for db in get_db():
            result = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.BROWSER_HEADLESS)
            )
            config = result.scalar_one_or_none()
            if config:
                browser_headless = config.config_value.lower() == "true"
            break

        # 构建操作代码
        action_codes = []

        # 添加导航后的延迟
        action_codes.append("        # 等待页面加载")
        action_codes.append("        await page.wait_for_timeout(2000)")

        # 如果需要自动检测验证码，添加验证码处理代码
        if auto_detect_captcha:
            action_codes.append("")
            action_codes.append("        # 自动检测并处理验证码")
            action_codes.append("        try:")
            action_codes.append("            # 检查是否存在验证码图片")
            action_codes.append("            captcha_img = page.locator('img[src*=\"captcha\"], img[id*=\"captcha\"], .captcha img').first")
            action_codes.append("            if await captcha_img.is_visible(timeout=3000):")
            action_codes.append("                print('检测到验证码')")
            action_codes.append("                # 截取验证码图片")
            action_codes.append("                captcha_bytes = await captcha_img.screenshot()")
            action_codes.append("                import base64")
            action_codes.append("                captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')")
            action_codes.append("                # 这里需要调用验证码识别服务")
            action_codes.append("                # 暂时跳过验证码填写")
            action_codes.append("                print('验证码识别功能需要在主进程中实现')")
            action_codes.append("        except:")
            action_codes.append("            pass  # 没有验证码")
            action_codes.append("")

        # 为每个操作生成代码
        dom_state = ""  # 初始DOM为空
        aggregated_actions = ""

        for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
            is_last = i == len(actions) - 1

            print(f"   正在生成操作 {i}/{len(actions) - 1}: {action}")

            # 生成代码
            action_code = await test_generator.generate_playwright_code(
                action,
                dom_state,
                aggregated_actions,
                is_last
            )

            # 验证代码
            is_valid, error = await test_generator.validate_generated_code(action_code)
            if not is_valid:
                print(f"   ⚠️ 操作 {i} 代码验证失败: {error}")
                continue

            # 添加操作注释和代码
            action_codes.append("")
            action_codes.append(f"        # Action {i}: {action}")

            # 添加操作代码（缩进处理）
            for line in action_code.strip().split('\n'):
                action_codes.append(f"        {line}")

            # 添加2秒延迟
            action_codes.append("        await page.wait_for_timeout(2000)")

            aggregated_actions += "\n" + action_code

            # 更新DOM状态（用于下一个操作的生成）
            # 注意：这里我们无法获取实际DOM，所以使用空字符串
            # 在实际执行时，代码会在浏览器中运行
            dom_state = ""

        # 构建完整脚本
        actions_str = '\n'.join(action_codes)

        script = f'''import pytest
from playwright.async_api import async_playwright, expect
import asyncio

@pytest.mark.asyncio
async def test_generated():
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless={browser_headless})
        page = await browser.new_page()

        # Action 0: 导航到目标页面
        await page.goto("{target_url}")
{actions_str}

        # 关闭浏览器
        await browser.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return script

    async def _execute_test(self, script: str) -> str:
        """
        执行测试脚本
        Args:
            script: 测试脚本
        Returns:
            执行输出
        """
        import tempfile
        import os
        import subprocess

        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            temp_script_path = f.name

        try:
            print("   正在执行测试脚本...")
            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode != 0:
                print(f"   ⚠️ 测试执行有警告或错误: {result.stderr[:500]}")

            output = result.stdout + "\n" + result.stderr
            return output
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_script_path)
            except:
                pass

    async def _generate_report(self, result: Dict[str, Any]) -> str:
        """
        生成测试报告
        Args:
            result: 执行结果
        Returns:
            Markdown格式的报告
        """
        # 提取pytest结果
        pattern = r"(?:\x1b\[[0-9;]*m)?=+\s?.*?\s?=+(?:\x1b\[[0-9;]*m)?"
        matches = re.findall(pattern, result.get("execution_output", ""))
        pytest_extracted_results = "\n".join(matches)

        # 格式化操作步骤
        actions_taken = "\n".join(
            f"{i + 1}. {item}"
            for i, item in enumerate(result.get("actions", []))
        )

        report = f"""
# 测试生成报告

为端点 {result.get('test_name', 'N/A')} 生成了一个测试。

## 测试评估结果
{pytest_extracted_results}

## 测试期间执行的操作
{actions_taken}

## 生成的脚本
```python
{result.get('script', 'N/A')}
```
"""
        return report

    async def execute_with_captcha(
        self,
        user_query: str,
        target_url: str,
        auto_detect: bool = False,
        captcha_selector: Optional[str] = None,
        captcha_input_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行带验证码的测试
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect: 是否自动检测验证码
            captcha_selector: 验证码选择器
            captcha_input_selector: 验证码输入框选择器
        Returns:
            执行结果
        """
        return await self.execute_workflow(user_query, target_url, auto_detect_captcha=auto_detect)


# 创建全局实例
test_executor = TestExecutor()
