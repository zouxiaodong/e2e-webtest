import asyncio
import io
import re
import sys
from typing import Dict, Any, Optional, List
from contextlib import redirect_stdout
from datetime import datetime
import pytest
import ipytest
import nest_asyncio

from ..generator.test_generator import test_generator
from ..captcha.captcha_service import captcha_service
from ..llm.bailian_client import bailian_client
from ..computer_use.computer_use_service import computer_use_service


class TestExecutor:
    """测试执行引擎 - 使用持久化浏览器会话"""

    def __init__(self):
        self.dom_state: str = ""
        self.aggregated_actions: str = ""

    async def generate_script_only(
        self,
        user_query: str,
        target_url: str,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True
    ) -> Dict[str, Any]:
        """
        只生成测试脚本，不执行测试 - 用于批量生成用例
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect_captcha: 是否自动检测验证码
        Returns:
            包含脚本的字典
        """
        result = {
            "status": "success",
            "actions": [],
            "script": "",
            "test_name": "",
            "error": None
        }

        try:
            print("\n===== 开始生成测试脚本 =====")
            print(f"用户查询: {user_query}")
            print(f"目标URL: {target_url}")

            # 步骤1: 获取页面内容（截图和HTML）
            print("\n步骤1: 获取页面内容...")
            page_content = await test_generator.get_page_content(target_url)
            print(f"✅ 页面标题: {page_content.get('title', 'N/A')}")

            # 步骤2: 分析页面内容
            print("\n步骤2: 分析页面内容...")
            page_analysis = await test_generator.analyze_page_content(page_content, user_query)
            print(f"✅ 页面类型: {page_analysis.get('page_type', 'N/A')}")

            # 步骤3: 基于页面分析生成操作步骤
            print("\n步骤3: 生成操作步骤...")
            actions = await self._generate_actions_with_context(
                user_query, target_url, page_analysis
            )
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")

            # 步骤4: 生成完整脚本（使用页面HTML作为上下文）
            print("\n步骤4: 生成完整测试脚本...")
            final_script = await self._generate_complete_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, page_content.get('html', '')
            )
            result["script"] = final_script
            print("✅ 脚本生成完成")

            # 步骤5: 生成测试名称
            print("\n步骤5: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, actions)
            result["test_name"] = test_name
            print(f"✅ 生成测试名称: {test_name}")

            print("\n===== 测试脚本生成完成 =====")
            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ 生成脚本时出现错误: {str(e)}")
            print(f"\n错误详情:\n{error_detail}")
            return result

    async def execute_workflow(
        self,
        user_query: str,
        target_url: str,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True
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

            # 步骤1: 获取页面内容（截图和HTML）
            print("\n步骤1: 获取页面内容...")
            page_content = await test_generator.get_page_content(target_url)
            print(f"✅ 页面标题: {page_content.get('title', 'N/A')}")
            print(f"✅ HTML长度: {len(page_content.get('html', ''))}")
            print(f"✅ 截图长度: {len(page_content.get('screenshot', ''))}")

            # 步骤2: 分析页面内容
            print("\n步骤2: 分析页面内容...")
            page_analysis = await test_generator.analyze_page_content(page_content, user_query)
            print(f"✅ 页面类型: {page_analysis.get('page_type', 'N/A')}")
            print(f"✅ 发现 {len(page_analysis.get('forms', []))} 个表单")
            print(f"✅ 发现 {len(page_analysis.get('buttons', []))} 个按钮")

            # 步骤3: 基于页面分析生成操作步骤
            print("\n步骤3: 生成操作步骤...")
            actions = await self._generate_actions_with_context(
                user_query, target_url, page_analysis
            )
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")
            for i, action in enumerate(actions):
                print(f"   {i+1}. {action}")

            # 步骤4: 生成完整脚本（使用页面HTML作为上下文）
            print("\n步骤4: 生成完整测试脚本...")
            final_script = await self._generate_complete_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, page_content.get('html', '')
            )
            result["script"] = final_script
            print("✅ 脚本生成完成")
            print(f"\n生成的脚本预览:\n{final_script[:1000]}..." if len(final_script) > 1000 else f"\n生成的脚本:\n{final_script}")

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

    async def _generate_actions_with_context(
        self,
        user_query: str,
        target_url: str,
        page_analysis: Dict[str, Any]
    ) -> List[str]:
        """
        基于页面分析结果生成操作步骤
        Args:
            user_query: 用户查询
            target_url: 目标URL
            page_analysis: 页面分析结果
        Returns:
            操作步骤列表
        """
        # 构建包含页面信息的prompt
        forms_info = page_analysis.get('forms', [])
        buttons_info = page_analysis.get('buttons', [])
        page_type = page_analysis.get('page_type', 'unknown')

        system_prompt = """你是一个端到端测试专家。你的目标是将通用的业务端到端测试任务分解为更小的、明确定义的操作。"""

        # 检查是否有验证码输入框
        has_captcha = False
        for form in forms_info:
            for field in form.get('fields', []):
                field_name = field.get('name', '').lower()
                field_type = field.get('type', '').lower()
                if 'captcha' in field_name or '验证码' in field_name:
                    has_captcha = True
                    break

        captcha_hint = ""
        if has_captcha:
            captcha_hint = """
重要提示：页面包含验证码输入框，请按以下步骤处理：
1. 在填写用户名和密码之后，添加步骤："截取验证码图片并调用VL模型识别"
2. 然后添加步骤："在验证码输入框中填写识别结果"
3. 最后点击登录按钮"""

        prompt = f"""将以下输入转换为包含"actions"键和原子步骤列表作为值的JSON字典。
这些步骤将用于生成端到端测试脚本。
每个操作都应该是一个清晰的、原子步骤，可以转换为代码。
尽量生成完成用户测试意图所需的最少操作数量。
第一个操作必须始终是导航到目标URL。
最后一个操作应该始终是断言测试的预期结果。
不要在这个JSON结构之外添加任何额外的字符、注释或解释。只输出JSON结果。

重要提示：
1. 基于页面实际元素生成操作步骤
2. 使用页面中实际存在的表单字段名称
{captcha_hint}

页面信息：
- 页面类型: {page_type}
- 表单: {forms_info}
- 按钮: {buttons_info}

示例:
输入: "测试网站的登录流程"
输出: {{
    "actions": [
        "通过URL导航到登录页面。",
        "定位并在'username'输入框中输入有效的用户名",
        "定位并在'password'输入框中输入有效的密码",
        "点击'登录'按钮提交凭据",
        "通过期望页面跳转到首页来验证用户已登录"
    ]
}}

目标URL: {target_url}
用户查询: {user_query}
输出:"""

        response = await bailian_client.generate_text(prompt, system_prompt)

        # 解析JSON响应
        import json
        try:
            result = json.loads(response)
            return result.get("actions", [])
        except json.JSONDecodeError:
            # 如果解析失败，返回默认操作
            return [
                f"通过URL导航到 {target_url}",
                user_query,
                "验证测试已成功完成"
            ]

    async def _generate_complete_script(
        self,
        target_url: str,
        actions: list,
        auto_detect_captcha: bool,
        auto_cookie_localstorage: bool = True,
        html_content: str = ""
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

        # 添加导航后的延迟（使用16空格缩进）
        action_codes.append("                # 等待页面加载")
        action_codes.append("                await page.wait_for_timeout(2000)")

        # 如果需要自动加载 Cookie/LocalStorage，添加加载代码
        if auto_cookie_localstorage:
            action_codes.append("                # 加载保存的 cookies 和 localStorage")
            action_codes.append("                import os, json")
            action_codes.append("                if os.path.exists('saved_cookies.json'):")
            action_codes.append("                    with open('saved_cookies.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        cookies = json.load(f)")
            action_codes.append("                    await page.context.add_cookies(cookies)")
            action_codes.append("                    print('Cookies 已加载')")
            action_codes.append("                if os.path.exists('saved_localstorage.json'):")
            action_codes.append("                    with open('saved_localstorage.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        ls_data = f.read()")
            action_codes.append("                    await page.evaluate(f\"() => {{ localStorage.clear(); const data = {ls_data}; for (const key in data) {{ localStorage.setItem(key, data[key]); }} }}\")")
            action_codes.append("                    print('LocalStorage 已加载')")

        # 如果需要自动检测验证码，添加验证码处理代码
        captcha_handler_code = ""
        if auto_detect_captcha:
            # 获取LLM配置
            from ...core.config import settings
            api_key = settings.BAILIAN_API_KEY
            base_url = settings.BAILIAN_BASE_URL
            vl_model = settings.BAILIAN_VL_MODEL

            # 添加验证码处理代码（使用16空格缩进）
            action_codes.append(f"                # 自动检测并处理验证码")
            action_codes.append(f"                try:")
            action_codes.append(f"                    # 检查是否存在验证码图片")
            action_codes.append(f"                    captcha_img = page.locator('img[src*=\"captcha\"], img[id*=\"captcha\"], .captcha img').first")
            action_codes.append(f"                    if await captcha_img.is_visible(timeout=3000):")
            action_codes.append(f"                        print('检测到验证码')")
            action_codes.append(f"                        # 截取验证码图片")
            action_codes.append(f"                        captcha_bytes = await captcha_img.screenshot()")
            action_codes.append(f"                        import base64")
            action_codes.append(f"                        captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')")
            action_codes.append(f"")
            action_codes.append(f"                        # 调用LLM识别验证码")
            action_codes.append(f"                        import openai")
            action_codes.append(f"                        client = openai.OpenAI(api_key='{api_key}', base_url='{base_url}')")
            action_codes.append(f"")
            action_codes.append(f"                        response = client.chat.completions.create(")
            action_codes.append(f"                            model='{vl_model}',")
            action_codes.append(f"                            messages=[")
            action_codes.append(f"                                {{")
            action_codes.append(f"                                    \"role\": \"system\",")
            action_codes.append(f"                                    \"content\": \"你是一个验证码识别专家。识别图片中的验证码内容。如果是数学运算（如2+3=?），请计算并返回结果。只返回验证码值或计算结果，不要添加任何解释。\"")
            action_codes.append(f"                                }},")
            action_codes.append(f"                                {{")
            action_codes.append(f"                                    \"role\": \"user\",")
            action_codes.append(f"                                    \"content\": [")
            action_codes.append(f"                                        {{\"type\": \"text\", \"text\": \"请识别这张图片中的验证码内容。如果是数学运算题，请计算并返回结果。只返回最终结果。\"}},")
            action_codes.append(f"                                        {{\"type\": \"image_url\", \"image_url\": {{\"url\": f\"data:image/png;base64,{{captcha_base64}}\"}}}}")
            action_codes.append(f"                                    ]")
            action_codes.append(f"                                }}")
            action_codes.append(f"                            ],")
            action_codes.append(f"                            temperature=0.0,")
            action_codes.append(f"                            max_tokens=50")
            action_codes.append(f"                        )")
            action_codes.append(f"")
            action_codes.append(f"                        captcha_text = response.choices[0].message.content.strip()")
            action_codes.append(f"                        print(f'识别到验证码: {{captcha_text}}')")
            action_codes.append(f"")
            action_codes.append(f"                        # 查找验证码输入框并填写")
            action_codes.append(f"                        captcha_input = page.locator('input[name*=\"captcha\"], input[id*=\"captcha\"], input[placeholder*=\"验证码\"]').first")
            action_codes.append(f"                        if await captcha_input.is_visible(timeout=3000):")
            action_codes.append(f"                            await captcha_input.fill(captcha_text)")
            action_codes.append(f"                            print('验证码已填写')")
            action_codes.append(f"                except Exception as e:")
            action_codes.append(f"                    print(f'验证码处理失败: {{e}}')")
            action_codes.append(f"                    pass  # 没有验证码或处理失败")

        # 为每个操作生成代码
        # 使用获取到的HTML内容作为DOM状态
        dom_state = html_content[:5000] if html_content else ""  # 限制长度避免超出token限制
        aggregated_actions = ""

        for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
            is_last = i == len(actions) - 1

            # 如果启用了自动验证码检测，跳过验证码相关的操作（避免重复处理）
            if auto_detect_captcha and any(keyword in action.lower() for keyword in ['验证码', 'captcha', '截图', 'screenshot']):
                print(f"   跳过操作 {i}: {action} (自动验证码检测已启用)")
                continue

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
                print(f"   生成的代码:\n{action_code}")
                continue

            # 添加操作注释和代码（使用16空格缩进）
            action_codes.append(f"                # Action {i}: {action}")
            action_codes.append(f"                print('[TEST] Action {i} started')")
            print(f"   生成的代码预览:\n{action_code[:200]}..." if len(action_code) > 200 else f"   生成的代码:\n{action_code}")

            # 添加操作代码（缩进处理 - 16空格）
            for line in action_code.strip().split('\n'):
                action_codes.append(f"                {line}")

            # 添加3秒延迟（使用 asyncio.sleep 更明显）
            action_codes.append("                await asyncio.sleep(3)")
            action_codes.append(f"                print('[TEST] Action {i} completed')")

            aggregated_actions += "\n" + action_code

            # DOM状态保持不变（使用初始HTML）
            # 因为我们在生成代码时无法获取执行后的实际DOM

        # 构建完整脚本
        actions_str = '\n'.join(action_codes)

        script = f'''import pytest
from playwright.async_api import async_playwright, expect
import asyncio
import traceback

@pytest.mark.asyncio
async def test_generated():
    print("[TEST] Test started")
    browser = None
    try:
        async with async_playwright() as p:
            print("[TEST] Launching browser")
            # Launch browser
            browser = await p.chromium.launch(headless={browser_headless})
            page = await browser.new_page()
            print("[TEST] Browser launched")

            # Action 0: Navigate to target page
            print("[TEST] Navigating to: {target_url}")
            await page.goto("{target_url}")
            print("[TEST] Page loaded")
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state("networkidle")
            print("[TEST] Page network idle")
            
            # Additional wait to ensure page is visible
            await asyncio.sleep(3)
            print("[TEST] Initial wait completed")
            
            try:
                # Execute all actions
{actions_str}
            except Exception as e:
                print(f"[TEST] ERROR during actions: {{e}}")
                print(f"[TEST] Traceback: {{traceback.format_exc()}}")
                # Take screenshot on error
                try:
                    await page.screenshot(path="error_screenshot.png")
                    print("[TEST] Screenshot saved to error_screenshot.png")
                except:
                    pass
                raise

            # Final wait before closing
            print("[TEST] Final wait before closing")
            await asyncio.sleep(5)
            
            # Save cookies and localStorage if enabled
            if {auto_cookie_localstorage}:
                cookies = await page.context.cookies()
                with open('saved_cookies.json', 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print('[TEST] Cookies saved')
                ls_data = await page.evaluate('() => JSON.stringify(localStorage)')
                with open('saved_localstorage.json', 'w', encoding='utf-8') as f:
                    f.write(ls_data)
                print('[TEST] LocalStorage saved')
            
            # Close browser
            print("[TEST] Closing browser")
            await browser.close()
            print("[TEST] Test completed")
    except Exception as e:
        print(f"[TEST] FATAL ERROR: {{e}}")
        print(f"[TEST] Traceback: {{traceback.format_exc()}}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
'''
        return script

    async def generate_script_with_computer_use(
        self,
        user_query: str,
        target_url: str,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True
    ) -> Dict[str, Any]:
        """
        使用 Computer-Use 方案生成测试脚本（基于截图 + 坐标定位）
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect_captcha: 是否自动检测验证码
        Returns:
            包含脚本的字典
        """
        result = {
            "status": "success",
            "actions": [],
            "script": "",
            "test_name": "",
            "error": None
        }

        try:
            print("\n===== 开始使用 Computer-Use 方案生成测试脚本 =====")
            print(f"用户查询: {user_query}")
            print(f"目标URL: {target_url}")

            # 步骤1: 获取页面内容（截图和HTML）
            print("\n步骤1: 获取页面内容...")
            page_content = await test_generator.get_page_content(target_url)
            print(f"✅ 页面标题: {page_content.get('title', 'N/A')}")

            # 步骤2: 分析页面内容
            print("\n步骤2: 分析页面内容...")
            page_analysis = await test_generator.analyze_page_content(page_content, user_query)
            print(f"✅ 页面类型: {page_analysis.get('page_type', 'N/A')}")

            # 步骤3: 基于页面分析生成操作步骤
            print("\n步骤3: 生成操作步骤...")
            actions = await self._generate_actions_with_context(
                user_query, target_url, page_analysis
            )
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")

            # 步骤4: 使用 Computer-Use 方案生成脚本
            print("\n步骤4: 使用 Computer-Use 方案生成完整测试脚本...")
            final_script = await self._generate_computer_use_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage
            )
            result["script"] = final_script
            print("✅ 脚本生成完成")

            # 步骤5: 生成测试名称
            print("\n步骤5: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, actions)
            result["test_name"] = test_name
            print(f"✅ 生成测试名称: {test_name}")

            print("\n===== Computer-Use 测试脚本生成完成 =====")
            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ 生成脚本时出现错误: {str(e)}")
            print(f"\n错误详情:\n{error_detail}")
            return result

    async def _generate_computer_use_script(
        self,
        target_url: str,
        actions: list,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True
    ) -> str:
        """
        使用 Computer-Use 方案生成测试脚本
        Args:
            target_url: 目标URL
            actions: 操作列表
            auto_detect_captcha: 是否自动检测验证码
        Returns:
            完整的测试脚本
        """
        print(f"\n   使用 Computer-Use 方案生成脚本...")
        print(f"   目标URL: {target_url}")
        print(f"   操作数量: {len(actions)}")

        # 获取浏览器无头模式配置
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
        action_codes.append("                # 等待页面加载")
        action_codes.append("                await page.wait_for_timeout(2000)")

        # 如果需要自动加载 Cookie/LocalStorage，添加加载代码
        if auto_cookie_localstorage:
            action_codes.append("                # 加载保存的 cookies 和 localStorage")
            action_codes.append("                import os, json")
            action_codes.append("                if os.path.exists('saved_cookies.json'):")
            action_codes.append("                    with open('saved_cookies.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        cookies = json.load(f)")
            action_codes.append("                    await page.context.add_cookies(cookies)")
            action_codes.append("                    print('Cookies 已加载')")
            action_codes.append("                if os.path.exists('saved_localstorage.json'):")
            action_codes.append("                    with open('saved_localstorage.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        ls_data = f.read()")
            action_codes.append("                    await page.evaluate(f\"() => {{ localStorage.clear(); const data = {ls_data}; for (const key in data) {{ localStorage.setItem(key, data[key]); }} }}\")")
            action_codes.append("                    print('LocalStorage 已加载')")

        # 如果需要自动检测验证码，添加验证码处理代码
        if auto_detect_captcha:
            from ...core.config import settings
            api_key = settings.BAILIAN_API_KEY
            base_url = settings.BAILIAN_BASE_URL
            vl_model = settings.BAILIAN_VL_MODEL

            action_codes.append(f"                # 自动检测并处理验证码")
            action_codes.append(f"                try:")
            action_codes.append(f"                    captcha_img = page.locator('img[src*=\"captcha\"], img[id*=\"captcha\"], .captcha img').first")
            action_codes.append(f"                    if await captcha_img.is_visible(timeout=3000):")
            action_codes.append(f"                        print('检测到验证码')")
            action_codes.append(f"                        captcha_bytes = await captcha_img.screenshot()")
            action_codes.append(f"                        import base64")
            action_codes.append(f"                        captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')")
            action_codes.append(f"")
            action_codes.append(f"                        import openai")
            action_codes.append(f"                        client = openai.OpenAI(api_key='{api_key}', base_url='{base_url}')")
            action_codes.append(f"")
            action_codes.append(f"                        response = client.chat.completions.create(")
            action_codes.append(f"                            model='{vl_model}',")
            action_codes.append(f"                            messages=[")
            action_codes.append(f"                                {{")
            action_codes.append(f"                                    \"role\": \"system\",")
            action_codes.append(f"                                    \"content\": \"你是一个验证码识别专家。识别图片中的验证码内容。如果是数学运算（如2+3=?），请计算并返回结果。只返回验证码值或计算结果，不要添加任何解释。\"")
            action_codes.append(f"                                }},")
            action_codes.append(f"                                {{")
            action_codes.append(f"                                    \"role\": \"user\",")
            action_codes.append(f"                                    \"content\": [")
            action_codes.append(f"                                        {{\"type\": \"text\", \"text\": \"请识别这张图片中的验证码内容。如果是数学运算题，请计算并返回结果。只返回最终结果。\"}},")
            action_codes.append(f"                                        {{\"type\": \"image_url\", \"image_url\": {{\"url\": f\"data:image/png;base64,{{captcha_base64}}\"}}}}")
            action_codes.append(f"                                    ]")
            action_codes.append(f"                                }}")
            action_codes.append(f"                            ],")
            action_codes.append(f"                            temperature=0.0,")
            action_codes.append(f"                            max_tokens=50")
            action_codes.append(f"                        )")
            action_codes.append(f"")
            action_codes.append(f"                        captcha_text = response.choices[0].message.content.strip()")
            action_codes.append(f"                        print(f'识别到验证码: {{captcha_text}}')")
            action_codes.append(f"")
            action_codes.append(f"                        captcha_input = page.locator('input[name*=\"captcha\"], input[id*=\"captcha\"], input[placeholder*=\"验证码\"]').first")
            action_codes.append(f"                        if await captcha_input.is_visible(timeout=3000):")
            action_codes.append(f"                            await captcha_input.fill(captcha_text)")
            action_codes.append(f"                            print('验证码已填写')")
            action_codes.append(f"                except Exception as e:")
            action_codes.append(f"                    print(f'验证码处理失败: {{e}}')")
            action_codes.append(f"                    pass")

        # 使用单独的进程运行 Playwright，完全隔离 asyncio 循环
        print(f"\n   开始使用 Computer-Use 方案生成操作代码...")

        import concurrent.futures

        # 在单独的进程中运行
        from .playwright_processor import process_playwright_task
        task_data = {
            'target_url': target_url,
            'actions': actions,
            'browser_headless': browser_headless,
            'auto_detect_captcha': auto_detect_captcha
        }
        with concurrent.futures.ProcessPoolExecutor() as executor:
            future = executor.submit(process_playwright_task, task_data)
            collected_codes = future.result()

        # 将收集的代码添加到 action_codes
        action_codes.extend(collected_codes)

        actions_str = "\n".join(action_codes)

        # 生成完整脚本
        script = f'''import pytest
from playwright.async_api import async_playwright, expect
import asyncio
import traceback

@pytest.mark.asyncio
async def test_generated():
    print("[TEST] Test started")
    browser = None
    try:
        async with async_playwright() as p:
            print("[TEST] Launching browser")
            browser = await p.chromium.launch(headless={browser_headless})
            page = await browser.new_page()
            print("[TEST] Browser launched")

            # Action 0: Navigate to target page
            print("[TEST] Navigating to: {target_url}")
            await page.goto("{target_url}")
            print("[TEST] Page loaded")
            
            await page.wait_for_load_state("networkidle")
            print("[TEST] Page network idle")
            
            await asyncio.sleep(3)
            print("[TEST] Initial wait completed")
            
            try:
                # Execute all actions
{actions_str}
            except Exception as e:
                print(f"[TEST] ERROR during actions: {{e}}")
                print(f"[TEST] Traceback: {{traceback.format_exc()}}")
                try:
                    await page.screenshot(path="error_screenshot.png")
                    print("[TEST] Screenshot saved to error_screenshot.png")
                except:
                    pass
                raise

            print("[TEST] Final wait before closing")
            await asyncio.sleep(5)
            
            # Save cookies and localStorage if enabled
            if {auto_cookie_localstorage}:
                cookies = await page.context.cookies()
                with open('saved_cookies.json', 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print('[TEST] Cookies saved')
                ls_data = await page.evaluate('() => JSON.stringify(localStorage)')
                with open('saved_localstorage.json', 'w', encoding='utf-8') as f:
                    f.write(ls_data)
                print('[TEST] LocalStorage saved')
            
            print("[TEST] Closing browser")
            await browser.close()
            print("[TEST] Test completed")
    except Exception as e:
        print(f"[TEST] FATAL ERROR: {{e}}")
        print(f"[TEST] Traceback: {{traceback.format_exc()}}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
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
        # 使用 utf-8-sig 编码（带 BOM）以确保 Windows 正确识别
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8-sig') as f:
            f.write(script)
            temp_script_path = f.name

        try:
            print("   正在执行测试脚本...")
            print(f"   临时脚本路径: {temp_script_path}")

            # 使用 run_in_executor 在后台线程中执行 subprocess
            import concurrent.futures
            
            def run_subprocess():
                return subprocess.run(
                    [sys.executable, temp_script_path],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                    encoding='utf-8',
                    errors='replace'
                )
            
            print("   等待测试执行完成（最多5分钟）...")
            
            # 在线程池中执行 subprocess
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, run_subprocess)

            output = result.stdout + "\n" + result.stderr

            print(f"   测试执行完成，返回码: {result.returncode}")
            print(f"   标准输出:\n{result.stdout[:1000]}")
            if result.stderr:
                print(f"   标准错误:\n{result.stderr[:500]}")

            return output
        except subprocess.TimeoutExpired:
            print("   ⚠️ 测试执行超时（5分钟）")
            return "测试执行超时"
        except Exception as e:
            print(f"   ⚠️ 测试执行异常: {e}")
            import traceback
            print(f"   错误详情:\n{traceback.format_exc()}")
            return f"测试执行异常: {e}"
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_script_path)
            except:
                pass

    async def execute_saved_script(self, script: str) -> Dict[str, Any]:
        """
        执行已保存的测试脚本（不重新生成）
        Args:
            script: 已保存的测试脚本
        Returns:
            执行结果
        """
        result = {
            "status": "success",
            "script": script,
            "execution_output": "",
            "error": None
        }
        
        try:
            print("\n===== 开始执行已保存的测试脚本 =====")
            print("   直接执行已保存的脚本...")
            
            execution_output = await self._execute_test(script)
            result["execution_output"] = execution_output
            
            # 检查执行结果
            if "FAILED" in execution_output or "Error" in execution_output:
                result["status"] = "failed"
                result["error"] = "Test execution failed"
            
            print("✅ 测试执行完成")
            print("\n===== 测试执行完成 =====")
            return result
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ 执行过程中出现错误: {str(e)}")
            print(f"\n错误详情:\n{error_detail}")
            return result

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
