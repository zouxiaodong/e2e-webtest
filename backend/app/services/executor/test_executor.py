import asyncio
import io
import re
import sys
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from contextlib import redirect_stdout
from datetime import datetime
import pytest
import ipytest
import nest_asyncio

# Windows 特定：使用 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(f"✅ 设置 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程")

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
            print("\n===== 开始执行测试工作流 =====")
            print(f"用户查询: {user_query}")
            print(f"目标URL: {target_url}")
            
            # Windows 特定：使用 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                print("✅ 设置 WindowsSelectorEventLoopPolicy 以支持 Playwright 子进程")

            # 步骤1: 生成操作步骤
            print("\n步骤1: 生成操作步骤...")
            actions = await test_generator.generate_actions(user_query, target_url)
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")
            for i, action in enumerate(actions):
                print(f"   {i+1}. {action}")

            # 步骤2: 初始化脚本
            print("\n步骤2: 初始化Playwright脚本...")
            script = await test_generator.generate_initial_script(target_url)
            print("✅ 初始化Playwright脚本完成")

            # 步骤3: 启动浏览器并获取初始DOM
            print("\n步骤3: 启动浏览器并获取初始DOM...")
            print("   正在启动浏览器...")
            self.dom_state = await self._get_dom_state(script)
            print(f"✅ 获取到DOM，长度: {len(self.dom_state)}")

            # 步骤4: 为每个操作生成代码
            print("\n步骤4: 为每个操作生成代码...")
            current_action = 1  # Action 0 是导航

            while current_action < len(actions):
                action = actions[current_action]
                is_last = current_action == len(actions) - 1

                print(f"\n   正在生成操作 {current_action}/{len(actions) - 1}: {action}")

                # 生成代码
                action_code = await test_generator.generate_playwright_code(
                    action,
                    self.dom_state,
                    self.aggregated_actions,
                    is_last
                )
                print(f"   ✅ 生成代码完成")

                # 验证代码
                is_valid, error = await test_generator.validate_generated_code(action_code)
                if not is_valid:
                    result["status"] = "error"
                    result["error"] = f"操作 {current_action} 代码验证失败: {error}"
                    result["script"] = script
                    print(f"   ❌ 操作 {current_action} 代码验证失败: {error}")
                    return result
                print(f"   ✅ 代码验证通过")

                # 插入代码到脚本
                script = test_generator.insert_code_into_script(script, action_code, current_action)
                self.aggregated_actions += "\n " + action_code
                print(f"   ✅ 代码插入完成")

                # 执行脚本获取新DOM
                print("   正在执行脚本获取新DOM...")
                self.dom_state = await self._get_dom_state(script)
                print(f"   ✅ 获取到新DOM，长度: {len(self.dom_state)}")
                current_action += 1

            # 步骤5: 生成测试名称
            print("\n步骤5: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, actions)
            result["test_name"] = test_name
            print(f"✅ 生成测试名称: {test_name}")

            # 步骤6: 完成脚本
            print("\n步骤6: 完成脚本...")
            final_script = await test_generator.finalize_script(script, test_name)
            result["script"] = final_script
            print("✅ 完成脚本")

            # 步骤7: 执行测试
            print("\n步骤7: 执行测试...")
            print("   正在执行测试...")
            execution_output = await self._execute_test(final_script)
            result["execution_output"] = execution_output
            print("✅ 测试执行完成")

            # 步骤8: 生成报告
            print("\n步骤8: 生成报告...")
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

    def _clean_dom_state(self, html: str) -> str:
        """
        清理 DOM 状态，移除 SVG、CSS、JavaScript 等无关内容
        Args:
            html: 原始 HTML
        Returns:
            清理后的 HTML
        """
        from lxml.html.clean import Cleaner
        import lxml.html

        # 使用 lxml 的 Cleaner 来清理 HTML
        cleaner = Cleaner(
            javascript=True,  # Remove script tags and js attributes
            style=True,       # Remove style tags
            inline_style=True, # Remove inline style attributes
            comments=True,    # Remove comments
            safe_attrs_only=True,  # Only keep safe attributes
            forms=False,      # Keep form tags (needed for testing)
            page_structure=False,  # Keep basic page structure
        )

        # 清理 HTML
        cleaned_html = cleaner.clean_html(html)

        # 转换为字符串
        if isinstance(cleaned_html, bytes):
            cleaned_html = cleaned_html.decode('utf-8')

        # 移除 SVG 内容
        import re
        # 移除 <svg>...</svg> 标签及其内容
        cleaned_html = re.sub(r'<svg[^>]*>.*?</svg>', '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        # 移除 <symbol>...</symbol> 标签及其内容
        cleaned_html = re.sub(r'<symbol[^>]*>.*?</symbol>', '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        # 移除 <path>...</path> 标签
        cleaned_html = re.sub(r'<path[^/]*/?>', '', cleaned_html, flags=re.IGNORECASE)
        # 移除 <use>...</use> 标签
        cleaned_html = re.sub(r'<use[^/]*/?>', '', cleaned_html, flags=re.IGNORECASE)

        # 移除多余空格
        cleaned_html = re.sub(r'\s+', ' ', cleaned_html)

        return cleaned_html.strip()

    async def _get_dom_state(self, script: str) -> str:
        """
        执行脚本并获取DOM状态
        Args:
            script: Playwright脚本
        Returns:
            DOM状态
        """
        import tempfile
        import os
        import subprocess
        import json

        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            temp_script_path = f.name

        try:
            # 打印脚本的最后几行，查看print语句
            with open(temp_script_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 10:
                    print("   脚本末尾10行:")
                    for line in lines[-10:]:
                        print(f"   {line.rstrip()}")

            # 使用subprocess运行脚本，这样可以在一个新的进程中执行，避免事件循环的问题
            print("   正在在新进程中执行Playwright脚本...")
            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode != 0:
                print(f"   ❌ 脚本执行失败: {result.stderr}")
                raise Exception(f"脚本执行失败: {result.stderr}")

            # 解析结果
            output = result.stdout.strip()
            print(f"   ✅ 脚本执行成功，输出长度: {len(output)}")

            # 解析JSON格式的输出，提取dom_state
            try:
                output_dict = json.loads(output)
                dom_state = output_dict.get("dom_state", "")
                print(f"   ✅ 解析DOM状态成功，原始长度: {len(dom_state)}")

                # 清理 DOM 状态，移除 SVG 等内容
                dom_state = self._clean_dom_state(dom_state)
                print(f"   ✅ 清理DOM状态完成，清理后长度: {len(dom_state)}")

                return dom_state
            except json.JSONDecodeError:
                print("   ⚠️  无法解析JSON输出，返回原始输出")
                return output
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_script_path)
            except:
                pass

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
