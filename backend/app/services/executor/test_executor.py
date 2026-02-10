import asyncio
import io
import re
import sys
import os
from typing import Dict, Any, Optional, List
from contextlib import redirect_stdout
from datetime import datetime
import pytest
import ipytest
import nest_asyncio
from dotenv import load_dotenv

from ..generator.test_generator import test_generator
from ..captcha.captcha_service import captcha_service
from ..llm.bailian_client import bailian_client
from ..computer_use.computer_use_service import computer_use_service

load_dotenv()


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
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True,
        page_content: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        只生成测试脚本，不执行测试 - 用于批量生成用例
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
            page_content: 页面内容（如果提供，则不重新获取）
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

            # 步骤1: 获取页面内容（截图和HTML）- 如果未提供则获取
            print("\n步骤1: 获取页面内容...")
            if page_content is None:
                page_content = await test_generator.get_page_content(target_url)
                print(f"✅ 页面标题: {page_content.get('title', 'N/A')}")
            else:
                print(f"✅ 使用已获取的页面内容: {page_content.get('title', 'N/A')}")

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
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage, page_content.get('html', '')
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
        load_saved_storage: bool = True,
        html_content: str = ""
    ) -> str:
        """
        生成完整的测试脚本（一次性生成所有操作）
        Args:
            target_url: 目标URL
            actions: 操作步骤列表
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
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

        # 如果需要自动加载 Cookie/LocalStorage/SessionStorage，添加加载代码
        if auto_cookie_localstorage and load_saved_storage:
            action_codes.append("                # 加载保存的 cookies、localStorage 和 sessionStorage")
            action_codes.append("                import os, json")
            
            # 获取会话存储路径
            session_storage_path = os.getenv('SESSION_STORAGE_PATH', '')
            if session_storage_path:
                action_codes.append(f"                session_storage_path = '{session_storage_path}'")
                action_codes.append("                cookie_file = os.path.join(session_storage_path, 'saved_cookies.json')")
                action_codes.append("                ls_file = os.path.join(session_storage_path, 'saved_localstorage.json')")
                action_codes.append("                ss_file = os.path.join(session_storage_path, 'saved_sessionstorage.json')")
            else:
                action_codes.append("                cookie_file = 'saved_cookies.json'")
                action_codes.append("                ls_file = 'saved_localstorage.json'")
                action_codes.append("                ss_file = 'saved_sessionstorage.json'")
            
            action_codes.append("                print(f'当前工作目录: {os.getcwd()}')")
            action_codes.append("                print(f'Cookie文件路径: {cookie_file}')")
            action_codes.append("                print(f'Cookie文件存在: {os.path.exists(cookie_file)}')")
            action_codes.append("                print(f'LocalStorage文件存在: {os.path.exists(ls_file)}')")
            action_codes.append("                print(f'SessionStorage文件存在: {os.path.exists(ss_file)}')")
            action_codes.append("                if os.path.exists(cookie_file):")
            action_codes.append("                    with open(cookie_file, 'r', encoding='utf-8') as f:")
            action_codes.append("                        cookies = json.load(f)")
            action_codes.append(f"                    print(f'加载了 {{len(cookies)}} 个cookies')")
            action_codes.append("                    await page.context.add_cookies(cookies)")
            action_codes.append("                    print('Cookies 已加载')")
            action_codes.append("                if os.path.exists(ls_file):")
            action_codes.append("                    with open(ls_file, 'r', encoding='utf-8') as f:")
            action_codes.append("                        ls_data = f.read()")
            action_codes.append("                    try:")
            action_codes.append("                        ls_data_obj = json.loads(ls_data)")
            action_codes.append(f"                        print(f'LocalStorage数据: {{ls_data_obj}}')")
            action_codes.append("                        await page.evaluate(\"data => { localStorage.clear(); for (const key in data) { localStorage.setItem(key, data[key]); } }\", ls_data_obj)")
            action_codes.append("                    except json.JSONDecodeError:")
            action_codes.append("                        print(f'LocalStorage解析失败，使用原始字符串: {{ls_data[:100]}}')")
            action_codes.append("                        await page.evaluate(\"data => { localStorage.clear(); for (const key in data) { localStorage.setItem(key, data[key]); } }\", ls_data)")
            action_codes.append("                    print('LocalStorage 已加载')")
            action_codes.append("                if os.path.exists(ss_file):")
            action_codes.append("                    with open(ss_file, 'r', encoding='utf-8') as f:")
            action_codes.append("                        ss_data = f.read()")
            action_codes.append("                    try:")
            action_codes.append("                        ss_data_obj = json.loads(ss_data)")
            action_codes.append(f"                        print(f'SessionStorage数据: {{ss_data_obj}}')")
            action_codes.append("                        await page.evaluate(\"data => { sessionStorage.clear(); for (const key in data) { sessionStorage.setItem(key, data[key]); } }\", ss_data_obj)")
            action_codes.append("                    except json.JSONDecodeError:")
            action_codes.append("                        print(f'SessionStorage解析失败，使用原始字符串: {{ss_data[:100]}}')")
            action_codes.append("                        await page.evaluate(\"data => { sessionStorage.clear(); for (const key in data) { sessionStorage.setItem(key, data[key]); } }\", ss_data)")
            action_codes.append("                    print('SessionStorage 已加载')")

        # 如果需要自动检测验证码，添加验证码处理代码
        captcha_handler_code = ""
        if auto_detect_captcha:
            # 获取LLM配置
            from ...core.config import settings
            api_key = settings.BAILIAN_API_KEY
            base_url = settings.BAILIAN_BASE_URL
            vl_model = settings.BAILIAN_VL_MODEL

            # 添加验证码处理代码（使用16空格缩进）
            action_codes.append(f"                # 使用VL模型一次性识别页面所有元素")
            action_codes.append(f"                try:")
            action_codes.append(f"                    # 截取整个页面截图")
            action_codes.append(f"                    import base64")
            action_codes.append(f"                    page_bytes = await page.screenshot()")
            action_codes.append(f"                    page_base64 = base64.b64encode(page_bytes).decode('utf-8')")
            action_codes.append(f"")
            action_codes.append(f"                    # 调用VL模型识别所有元素")
            action_codes.append(f"                    import openai")
            action_codes.append(f"                    client = openai.OpenAI(api_key='{api_key}', base_url='{base_url}')")
            action_codes.append(f"")
            action_codes.append(f"                    response = client.chat.completions.create(")
            action_codes.append(f"                        model='{vl_model}',")
            action_codes.append(f"                        messages=[")
            action_codes.append(f"                            {{")
            action_codes.append(f"                                \"role\": \"system\",")
            action_codes.append(f"                                \"content\": \"你是一个网页元素识别专家。请分析页面截图，识别以下元素：1. 用户名输入框的坐标和类型 2. 密码输入框的坐标和类型 3. 验证码输入框的坐标和类型（如果存在） 4. 登录按钮的坐标 5. 验证码的计算结果（如果存在验证码）。返回JSON格式：{{\\\"has_captcha\\\": true/false, \\\"captcha_result\\\": \\\"验证码结果\\\", \\\"username_input\\\": {{\\\"x\\\": 123, \\\"y\\\": 456}}, \\\"password_input\\\": {{\\\"x\\\": 123, \\\"y\\\": 456}}, \\\"captcha_input\\\": {{\\\"x\\\": 123, \\\"y\\\": 456}} 或 null, \\\"login_button\\\": {{\\\"x\\\": 123, \\\"y\\\": 456}}}}\"")
            action_codes.append(f"                            }},")
            action_codes.append(f"                            {{")
            action_codes.append(f"                                \"role\": \"user\",")
            action_codes.append(f"                                \"content\": [")
            action_codes.append(f"                                    {{\"type\": \"text\", \"text\": \"请分析这个登录页面，识别用户名输入框、密码输入框、验证码输入框（如果有）、登录按钮的坐标，以及验证码的计算结果（如果有验证码）。返回JSON格式。\"}},")
            action_codes.append(f"                                    {{\"type\": \"image_url\", \"image_url\": {{\"url\": f\"data:image/png;base64,{{page_base64}}\"}}}}")
            action_codes.append(f"                                ]")
            action_codes.append(f"                            }}")
            action_codes.append(f"                        ],")
            action_codes.append(f"                        temperature=0.0,")
            action_codes.append(f"                        max_tokens=500")
            action_codes.append(f"                    )")
            action_codes.append(f"")
            action_codes.append(f"                    # 解析VL模型的响应")
            action_codes.append(f"                    import json")
            action_codes.append(f"                    result_text = response.choices[0].message.content.strip()")
            action_codes.append(f"                    result = json.loads(result_text)")
            action_codes.append(f"                    print(f'VL模型识别结果: {{result}}')")
            action_codes.append(f"")
            action_codes.append(f"                    # 根据识别结果填写表单")
            action_codes.append(f"                    if result.get('has_captcha', False):")
            action_codes.append(f"                        captcha_result = result.get('captcha_result', '')")
            action_codes.append(f"                        print(f'识别到验证码: {{captcha_result}}')")
            action_codes.append(f"")
            action_codes.append(f"                    # 填写用户名")
            action_codes.append(f"                    if 'username_input' in result:")
            action_codes.append(f"                        username_coords = result['username_input']")
            action_codes.append(f"                        await page.mouse.click(username_coords['x'], username_coords['y'])")
            action_codes.append(f"                        await page.keyboard.type('admin')")
            action_codes.append(f"                        print('用户名已填写')")
            action_codes.append(f"")
            action_codes.append(f"                    # 填写密码")
            action_codes.append(f"                    if 'password_input' in result:")
            action_codes.append(f"                        password_coords = result['password_input']")
            action_codes.append(f"                        await page.mouse.click(password_coords['x'], password_coords['y'])")
            action_codes.append(f"                        await page.keyboard.type('PGzVdj8WnN')")
            action_codes.append(f"                        print('密码已填写')")
            action_codes.append(f"")
            action_codes.append(f"                    # 填写验证码")
            action_codes.append(f"                    if result.get('has_captcha', False) and 'captcha_input' in result:")
            action_codes.append(f"                        captcha_coords = result['captcha_input']")
            action_codes.append(f"                        await page.mouse.click(captcha_coords['x'], captcha_coords['y'])")
            action_codes.append(f"                        await page.keyboard.type(captcha_result)")
            action_codes.append(f"                        print('验证码已填写')")
            action_codes.append(f"")
            action_codes.append(f"                    # 点击登录按钮")
            action_codes.append(f"                    if 'login_button' in result:")
            action_codes.append(f"                        login_coords = result['login_button']")
            action_codes.append(f"                        await page.mouse.click(login_coords['x'], login_coords['y'])")
            action_codes.append(f"                        print('登录按钮已点击')")
            action_codes.append(f"                except Exception as e:")
            action_codes.append(f"                    print(f'VL模型识别失败: {{e}}')")
            action_codes.append(f"                    pass  # VL模型识别失败，继续执行后续操作")

        # 为每个操作生成代码
        # 使用获取到的HTML内容作为DOM状态
        dom_state = html_content[:5000] if html_content else ""  # 限制长度避免超出token限制
        aggregated_actions = ""

        # 如果启用了自动验证码检测，跳过所有表单操作（因为VL模型会一次性处理）
        if auto_detect_captcha:
            print(f"   自动验证码检测已启用，跳过所有表单操作")
        else:
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
            await asyncio.sleep(30)  # Wait 30 seconds for debugging
            
            # Save cookies, localStorage and sessionStorage if enabled
            if {auto_cookie_localstorage}:
                import os
                session_storage_path = os.getenv('SESSION_STORAGE_PATH', '')
                if session_storage_path:
                    cookie_file = os.path.join(session_storage_path, 'saved_cookies.json')
                    ls_file = os.path.join(session_storage_path, 'saved_localstorage.json')
                    ss_file = os.path.join(session_storage_path, 'saved_sessionstorage.json')
                else:
                    cookie_file = 'saved_cookies.json'
                    ls_file = 'saved_localstorage.json'
                    ss_file = 'saved_sessionstorage.json'
                
                cookies = await page.context.cookies()
                with open(cookie_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print(f'[TEST] Cookies saved to {{cookie_file}}')
                ls_data = await page.evaluate('() => JSON.stringify(localStorage)')
                with open(ls_file, 'w', encoding='utf-8') as f:
                    f.write(ls_data)
                print(f'[TEST] LocalStorage saved to {{ls_file}}')
                ss_data = await page.evaluate('() => JSON.stringify(sessionStorage)')
                with open(ss_file, 'w', encoding='utf-8') as f:
                    f.write(ss_data)
                print(f'[TEST] SessionStorage saved to {{ss_file}}')
            
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
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True,
        page_content: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        使用 Computer-Use 方案生成测试脚本（基于截图 + 坐标定位）
        Args:
            user_query: 用户查询
            target_url: 目标URL
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
            page_content: 页面内容（如果提供，则不重新获取）
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

            # 步骤1: 获取页面内容（截图和HTML）- 如果未提供则获取
            print("\n步骤1: 获取页面内容...")
            if page_content is None:
                page_content = await test_generator.get_page_content(target_url)
                print(f"✅ 页面标题: {page_content.get('title', 'N/A')}")
            else:
                print(f"✅ 使用已获取的页面内容: {page_content.get('title', 'N/A')}")

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
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage
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
        if auto_cookie_localstorage and load_saved_storage:
            action_codes.append("                # 加载保存的 cookies 和 localStorage")
            action_codes.append("                import os")
            action_codes.append("                if os.path.exists('saved_cookies.json'):")
            action_codes.append("                    with open('saved_cookies.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        cookies = json.load(f)")
            action_codes.append("                    await page.context.add_cookies(cookies)")
            action_codes.append("                    print('Cookies 已加载')")
            action_codes.append("                if os.path.exists('saved_localstorage.json'):")
            action_codes.append("                    with open('saved_localstorage.json', 'r', encoding='utf-8') as f:")
            action_codes.append("                        ls_data = f.read()")
            action_codes.append("                    try:")
            action_codes.append("                        ls_data_obj = json.loads(ls_data)")
            action_codes.append("                        await page.evaluate(\"data => { localStorage.clear(); for (const key in data) { localStorage.setItem(key, data[key]); } }\", ls_data_obj)")
            action_codes.append("                    except json.JSONDecodeError:")
            action_codes.append("                        await page.evaluate(\"data => { localStorage.clear(); for (const key in data) { localStorage.setItem(key, data[key]); } }\", ls_data)")
            action_codes.append("                    print('LocalStorage 已加载')")

        # 如果需要自动检测验证码，添加验证码处理代码
        if auto_detect_captcha:
            action_codes.append(f"                # 自动检测并处理验证码（使用 browser_util）")
            action_codes.append(f"                try:")
            action_codes.append(f"                    from app.utils.browser_util import get_browser_util")
            action_codes.append(f"                    browser_util = get_browser_util()")
            action_codes.append(f"                    await browser_util.detect_and_solve_captcha(page)")
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
            'auto_detect_captcha': auto_detect_captcha,
            'load_saved_storage': load_saved_storage
        }
        with concurrent.futures.ProcessPoolExecutor() as executor:
            future = executor.submit(process_playwright_task, task_data)
            collected_codes = future.result()

        # 将收集的代码添加到 action_codes
        action_codes.extend(collected_codes)

        actions_str = "\n".join(action_codes)

        # 读取环境变量配置
        python_path = os.getenv('PYTHON_PATH', '')
        session_storage_path = os.getenv('SESSION_STORAGE_PATH', '.')

        # 生成完整脚本
        script = f'''import sys
import os

# 配置常量（从环境变量读取）
PYTHON_PATH = r'{python_path}'
SESSION_STORAGE_PATH = r'{session_storage_path}'

# 必须在最开头处理PYTHON_PATH，否则后续import可能找不到模块
if PYTHON_PATH and PYTHON_PATH not in sys.path:
    sys.path.insert(0, PYTHON_PATH)

import pytest
from playwright.async_api import async_playwright, expect
import asyncio
import traceback
import json
import time
from datetime import datetime

# 全局步骤结果列表
step_results = []

def log_step_start(step_number, step_name, step_type="action"):
    """记录步骤开始"""
    log_entry = {{
        "event": "step_start",
        "step_number": step_number,
        "step_name": step_name,
        "step_type": step_type,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "timestamp": time.time()
    }}
    step_results.append(log_entry)
    print(json.dumps(log_entry, ensure_ascii=False))

def log_step_end(step_number, status="passed", output_data=None, error_message=None):
    """记录步骤结束"""
    end_time = datetime.now().isoformat()
    # 找到对应的开始记录计算耗时
    start_timestamp = None
    for step in reversed(step_results):
        if step.get("step_number") == step_number and step.get("event") == "step_start":
            start_timestamp = step.get("timestamp")
            break
    
    duration_ms = None
    if start_timestamp:
        duration_ms = int((time.time() - start_timestamp) * 1000)
    
    log_entry = {{
        "event": "step_end",
        "step_number": step_number,
        "status": status,
        "end_time": end_time,
        "execution_duration_ms": duration_ms,
        "output_data": output_data,
        "error_message": error_message
    }}
    print(json.dumps(log_entry, ensure_ascii=False))

@pytest.mark.asyncio
async def test_generated():
    print(json.dumps({{"event": "test_start", "message": "Test started"}}, ensure_ascii=False))
    browser = None
    test_start_time = time.time()
    
    try:
        async with async_playwright() as p:
            print(json.dumps({{"event": "browser_launch_start"}}, ensure_ascii=False))
            browser = await p.chromium.launch(headless={browser_headless})
            page = await browser.new_page()
            print(json.dumps({{"event": "browser_launch_end", "status": "success"}}, ensure_ascii=False))

            # Action 0: Navigate to target page
            log_step_start(0, "Navigate to {target_url}", "navigation")
            try:
                await page.goto("{target_url}")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)
                log_step_end(0, "passed", {{"url": "{target_url}"}})
            except Exception as e:
                log_step_end(0, "failed", error_message=str(e))
                raise
            
            try:
                # Execute all actions
{actions_str}
            except Exception as e:
                print(json.dumps({{
                    "event": "action_error",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }}, ensure_ascii=False))
                try:
                    await page.screenshot(path="error_screenshot.png")
                    print(json.dumps({{"event": "screenshot_saved", "path": "error_screenshot.png"}}, ensure_ascii=False))
                except:
                    pass
                raise

            print(json.dumps({{"event": "test_completed", "total_duration_ms": int((time.time() - test_start_time) * 1000)}}, ensure_ascii=False))
            
            # Save cookies, localStorage and sessionStorage if enabled
            if {auto_cookie_localstorage}:
                cookies = await page.context.cookies()
                cookies_path = os.path.join(SESSION_STORAGE_PATH, 'saved_cookies.json')
                with open(cookies_path, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                
                ls_data = await page.evaluate('() => JSON.stringify(localStorage)')
                ls_path = os.path.join(SESSION_STORAGE_PATH, 'saved_localstorage.json')
                with open(ls_path, 'w', encoding='utf-8') as f:
                    f.write(ls_data)
                
                ss_data = await page.evaluate('() => JSON.stringify(sessionStorage)')
                ss_path = os.path.join(SESSION_STORAGE_PATH, 'saved_sessionstorage.json')
                with open(ss_path, 'w', encoding='utf-8') as f:
                    f.write(ss_data)
            
            await browser.close()
            
    except Exception as e:
        print(json.dumps({{
            "event": "test_failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }}, ensure_ascii=False))
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
                    errors='replace',
                    cwd=os.getcwd()  # 使用当前工作目录
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

    def _parse_step_results(self, execution_output: str) -> List[Dict[str, Any]]:
        """
        解析测试脚本输出的步骤结果
        Args:
            execution_output: 测试脚本执行输出
        Returns:
            步骤结果列表
        """
        import json
        import re
        
        step_results = []
        lines = execution_output.split('\n')
        
        for line in lines:
            try:
                if line.strip().startswith('{'):
                    step_data = json.loads(line.strip())
                    
                    # 只处理步骤开始和结束事件
                    if step_data.get("event") in ["step_start", "step_end"]:
                        step_results.append(step_data)
            except json.JSONDecodeError:
                continue
            except Exception:
                continue
        
        return step_results

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
            
            # 解析步骤结果
            step_results = self._parse_step_results(execution_output)
            result["step_results"] = step_results
            
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
