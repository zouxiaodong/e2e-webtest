import asyncio
import io
import re
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from contextlib import redirect_stdout
from datetime import datetime
import pytest
import ipytest
import nest_asyncio

from ..generator.test_generator import test_generator
from ..captcha.captcha_service import captcha_service
from ..llm.bailian_client import bailian_client


class TestExecutor:
    """测试执行引擎"""

    def __init__(self):
        self.current_page: Optional[Page] = None
        self.current_browser: Optional[Browser] = None
        self.dom_state: str = ""
        self.aggregated_actions: str = ""

    async def execute_workflow(
        self,
        user_query: str,
        target_url: str
    ) -> Dict[str, Any]:
        """
        执行完整的工作流
        Args:
            user_query: 用户查询
            target_url: 目标URL
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
            # Windows 特定：使用 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

            # 步骤1: 生成操作步骤
            print("步骤1: 生成操作步骤...")
            actions = await test_generator.generate_actions(user_query, target_url)
            result["actions"] = actions
            print(f"生成了 {len(actions)} 个操作步骤")

            # 步骤2: 初始化脚本
            print("步骤2: 初始化Playwright脚本...")
            script = await test_generator.generate_initial_script(target_url)

            # 步骤3: 启动浏览器并获取初始DOM
            print("步骤3: 启动浏览器并获取初始DOM...")
            self.dom_state = await self._get_dom_state(script)
            print(f"获取到DOM，长度: {len(self.dom_state)}")

            # 步骤4: 为每个操作生成代码
            print("步骤4: 为每个操作生成代码...")
            current_action = 1  # Action 0 是导航

            while current_action < len(actions):
                action = actions[current_action]
                is_last = current_action == len(actions) - 1

                print(f"正在生成操作 {current_action}/{len(actions) - 1}: {action}")

                # 生成代码
                action_code = await test_generator.generate_playwright_code(
                    action,
                    self.dom_state,
                    self.aggregated_actions,
                    is_last
                )

                # 验证代码
                is_valid, error = await test_generator.validate_generated_code(action_code)
                if not is_valid:
                    result["status"] = "error"
                    result["error"] = f"操作 {current_action} 代码验证失败: {error}"
                    result["script"] = script
                    return result

                # 插入代码到脚本
                script = test_generator.insert_code_into_script(script, action_code, current_action)
                self.aggregated_actions += "\n " + action_code

                # 执行脚本获取新DOM
                self.dom_state = await self._get_dom_state(script)
                current_action += 1

            # 步骤5: 生成测试名称
            print("步骤5: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, actions)
            result["test_name"] = test_name

            # 步骤6: 完成脚本
            print("步骤6: 完成脚本...")
            final_script = await test_generator.finalize_script(script, test_name)
            result["script"] = final_script

            # 步骤7: 执行测试
            print("步骤7: 执行测试...")
            execution_output = await self._execute_test(final_script)
            result["execution_output"] = execution_output

            # 步骤8: 生成报告
            print("步骤8: 生成报告...")
            report = await self._generate_report(result)
            result["report"] = report

            return result

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            return result

    async def _get_dom_state(self, script: str) -> str:
        """
        执行脚本并获取DOM状态
        Args:
            script: Playwright脚本
        Returns:
            DOM状态
        """
        # 直接在当前事件循环中执行脚本
        exec_namespace = {}
        exec(script, exec_namespace)
        dom_content = await exec_namespace["generated_script_run"]()
        return dom_content

    async def _execute_test(self, script: str) -> str:
        """
        执行测试脚本
        Args:
            script: 测试脚本
        Returns:
            执行输出
        """
        nest_asyncio.apply()

        exec(script, globals())

        output = io.StringIO()
        with redirect_stdout(output):
            ipytest.run()

        return output.getvalue()

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
        result = await self.execute_workflow(user_query, target_url)

        # 如果需要处理验证码
        if auto_detect or (captcha_selector and captcha_input_selector):
            # 在脚本中添加验证码处理代码
            if auto_detect:
                # 自动检测验证码
                captcha_code = f"""
        # 自动检测并处理验证码
        dom_content = await page.content()
        from app.services.captcha.captcha_service import captcha_service
        captcha_found, captcha_text = await captcha_service.auto_detect_and_handle_captcha(page)
        if captcha_found:
            print(f"自动处理验证码成功: {{captcha_text}}")
"""
            else:
                # 使用指定的选择器
                captcha_code = f"""
        # 处理验证码
        captcha_image = await page.locator("{captcha_selector}").screenshot()
        import base64
        captcha_base64 = base64.b64encode(captcha_image).decode('utf-8')
        from app.services.captcha.captcha_service import captcha_service
        captcha_text = await captcha_service.recognize_captcha(captcha_base64)
        await page.fill("{captcha_input_selector}", captcha_text)
        print(f"识别到验证码: {{captcha_text}}")
"""
            # 在适当的时机插入验证码处理代码
            result["script"] = result["script"].replace(
                "# Action 1",
                f"{captcha_code}\n        # Action 1"
            )

        return result


# 创建全局实例
test_executor = TestExecutor()