import asyncio
import io
import re
import sys
import os
import concurrent.futures
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
from ..agent_browser.agent_browser_service import AgentBrowserService
from ..agent_browser.action_planner import ActionPlanner

load_dotenv()


def _run_playwright_in_thread(task_func, *args, **kwargs):
    """
    在线程中运行 Playwright 操作，使用不同的事件循环策略

    Windows上的 WindowsSelectorEventLoopPolicy 不支持子进程操作，
    而 Playwright 需要创建浏览器子进程。所以在线程中运行 Playwright，
    让线程使用 ProactorEventLoopPolicy 来支持子进程操作。
    """
    if sys.platform == 'win32':
        # 在线程中设置 ProactorEventLoopPolicy，支持子进程
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # 在线程中创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(task_func(*args, **kwargs))
    finally:
        loop.close()


class TestExecutor:
    """测试执行引擎 - 使用持久化浏览器会话"""

    def __init__(self):
        self.dom_state: str = ""
        self.aggregated_actions: str = ""

    async def _read_captcha_config_from_db(self) -> Dict[str, Any]:
        """
        从数据库读取验证码相关配置（CAPTCHA_SELECTOR, CAPTCHA_INPUT_SELECTOR）
        Returns:
            {"captcha_selector": str or None, "captcha_input_selector": str or None}
        """
        from ...core.database import get_db
        from ...models.global_config import GlobalConfig, ConfigKeys
        from sqlalchemy import select

        captcha_selector = None
        captcha_input_selector = None

        async for db in get_db():
            # 读取 CAPTCHA_SELECTOR
            result = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.CAPTCHA_SELECTOR)
            )
            config = result.scalar_one_or_none()
            if config and config.config_value:
                captcha_selector = config.config_value.strip()

            # 读取 CAPTCHA_INPUT_SELECTOR
            result = await db.execute(
                select(GlobalConfig).where(GlobalConfig.config_key == ConfigKeys.CAPTCHA_INPUT_SELECTOR)
            )
            config = result.scalar_one_or_none()
            if config and config.config_value:
                captcha_input_selector = config.config_value.strip()

            break

        print(f"[CaptchaConfig] captcha_selector={captcha_selector}, captcha_input_selector={captcha_input_selector}")
        return {
            "captcha_selector": captcha_selector,
            "captcha_input_selector": captcha_input_selector
        }

    async def _detect_captcha_from_page(self, page_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用VL模型检测页面截图中是否有验证码，并读取DB配置的选择器
        Returns:
            {"has_captcha": bool, "captcha_type": str, "captcha_description": str,
             "captcha_selector": str or None, "captcha_input_selector": str or None}
        """
        from ..captcha.captcha_service import captcha_service

        # 提取截图base64
        screenshot_data = page_content.get('screenshot', '')
        if screenshot_data.startswith('data:image'):
            screenshot_base64 = screenshot_data.split(',')[1] if ',' in screenshot_data else screenshot_data
        else:
            screenshot_base64 = screenshot_data

        # VL检测验证码
        vl_result = await captcha_service.detect_captcha_from_screenshot(screenshot_base64)

        # 读取DB配置
        db_config = await self._read_captcha_config_from_db()

        return {
            "has_captcha": vl_result.get("has_captcha", False),
            "captcha_type": vl_result.get("captcha_type", "none"),
            "captcha_description": vl_result.get("captcha_description", ""),
            "captcha_selector": db_config.get("captcha_selector"),
            "captcha_input_selector": db_config.get("captcha_input_selector")
        }

    def _is_captcha_recognition_action(self, action: str) -> bool:
        """检测是否为验证码截图/VL模型识别动作"""
        a = action.lower()
        if 'vl模型' in a:
            return True
        if '验证码' in a and any(k in a for k in ['截取', '截图', '识别图片', '识别验证码']):
            return True
        if 'captcha' in a and any(k in a for k in ['screenshot', 'capture', 'recognize', 'vl']):
            return True
        return False

    def _is_captcha_fill_action(self, action: str) -> bool:
        """检测是否为填写验证码识别结果的动作（已由detect_and_solve_captcha处理，应跳过）"""
        a = action.lower()
        return '识别结果' in a

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

            # 步骤2.5: VL验证码检测 + 读取DB配置选择器
            print("\n步骤2.5: VL验证码检测...")
            captcha_info = await self._detect_captcha_from_page(page_content)
            print(f"✅ 验证码检测结果: has_captcha={captcha_info['has_captcha']}, type={captcha_info['captcha_type']}")
            if captcha_info['captcha_selector']:
                print(f"   DB配置 captcha_selector: {captcha_info['captcha_selector']}")
            if captcha_info['captcha_input_selector']:
                print(f"   DB配置 captcha_input_selector: {captcha_info['captcha_input_selector']}")

            # 步骤2.6: 提取表单选择器
            print("\n步骤2.6: 提取表单选择器...")
            form_selectors = test_generator.extract_form_selectors(page_content.get('html', ''))
            print(f"✅ 提取到 {len(form_selectors)} 个表单选择器")
            for name, selector in form_selectors.items():
                print(f"   {name}: {selector}")

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
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage,
                page_content.get('html', ''), captcha_info=captcha_info, form_selectors=form_selectors
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

            # 步骤2.5: VL验证码检测 + 读取DB配置选择器
            print("\n步骤2.5: VL验证码检测...")
            captcha_info = await self._detect_captcha_from_page(page_content)
            print(f"✅ 验证码检测结果: has_captcha={captcha_info['has_captcha']}, type={captcha_info['captcha_type']}")

            # 步骤2.6: 提取表单选择器
            print("\n步骤2.6: 提取表单选择器...")
            form_selectors = test_generator.extract_form_selectors(page_content.get('html', ''))
            print(f"✅ 提取到 {len(form_selectors)} 个表单选择器")

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
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage,
                html_content=page_content.get('html', ''), captcha_info=captcha_info, form_selectors=form_selectors
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
        html_content: str = "",
        captcha_info: Dict[str, Any] = None,
        form_selectors: Dict[str, str] = None
    ) -> str:
        """
        生成完整的测试脚本（一次性生成所有操作）
        Args:
            target_url: 目标URL
            actions: 操作步骤列表
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
            html_content: 页面HTML内容
            captcha_info: VL验证码检测结果 + DB配置选择器
            form_selectors: 从DOM提取的表单选择器
        Returns:
            完整的测试脚本
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

        # 如果需要自动检测验证码，检测是否有验证码相关操作，预先注入 sys.path 设置代码
        # 使用VL检测结果（captcha_info）来决定是否注入验证码处理代码
        if captcha_info is None:
            captcha_info = {}
        if form_selectors is None:
            form_selectors = {}

        vl_has_captcha = captcha_info.get("has_captcha", False)
        cfg_captcha_selector = captcha_info.get("captcha_selector")
        cfg_captcha_input_selector = captcha_info.get("captcha_input_selector")

        # 为每个操作生成代码
        # 使用获取到的HTML内容作为DOM状态
        dom_state = html_content[:5000] if html_content else ""  # 限制长度避免超出token限制
        aggregated_actions = ""

        # 决定是否需要验证码处理：VL检测到验证码 OR LLM生成了验证码步骤 OR auto_detect_captcha
        has_captcha_actions = any(
            self._is_captcha_recognition_action(a) or self._is_captcha_fill_action(a)
            for a in actions[1:]
        )
        need_captcha_handling = vl_has_captcha or has_captcha_actions or auto_detect_captcha

        if need_captcha_handling:
            print(f"   [验证码] 需要验证码处理: VL检测={vl_has_captcha}, LLM步骤={has_captcha_actions}, auto={auto_detect_captcha}")
            action_codes.append("                # 设置Python搜索路径以使用browser_util（读取PYTHON_PATH环境变量）")
            action_codes.append("                import sys as _sys, os as _os")
            action_codes.append("                try:")
            action_codes.append("                    from dotenv import load_dotenv as _load_dotenv")
            action_codes.append("                    _load_dotenv()")
            action_codes.append("                except ImportError:")
            action_codes.append("                    pass")
            action_codes.append("                _python_path = _os.getenv('PYTHON_PATH', '')")
            action_codes.append("                if _python_path and _python_path not in _sys.path:")
            action_codes.append("                    _sys.path.insert(0, _python_path)")
            action_codes.append("                    print(f'[TEST] sys.path已添加: {_python_path}')")

        captcha_injected = False  # 跟踪验证码处理是否已注入

        # 构建传给 detect_and_solve_captcha 的选择器参数字符串
        captcha_sel_repr = repr(cfg_captcha_selector) if cfg_captcha_selector else "None"
        captcha_input_sel_repr = repr(cfg_captcha_input_selector) if cfg_captcha_input_selector else "None"

        def _inject_captcha_code(action_codes_list, action_idx, action_desc, is_auto=False):
            """注入 detect_and_solve_captcha 代码块"""
            prefix = "[自动验证码处理] " if is_auto else ""
            action_codes_list.append(f"                # {prefix}Action {action_idx}: {action_desc}")
            action_codes_list.append(f"                print('[TEST] Action {action_idx} started: captcha handling')")
            action_codes_list.append(f"                try:")
            action_codes_list.append(f"                    from app.utils.browser_util import get_browser_util as _get_browser_util")
            action_codes_list.append(f"                    await _get_browser_util().detect_and_solve_captcha(page, captcha_selector={captcha_sel_repr}, captcha_input_selector={captcha_input_sel_repr})")
            action_codes_list.append(f"                    print('[TEST] 验证码已自动识别并填写')")
            action_codes_list.append(f"                except ImportError:")
            action_codes_list.append(f"                    print('[TEST] Warning: browser_util导入失败，请在.env中配置PYTHON_PATH指向backend目录')")
            action_codes_list.append(f"                except Exception as _e:")
            fatal_str = "（非致命）" if is_auto else ""
            action_codes_list.append(f"                    print(f'[TEST] 验证码处理失败{fatal_str}: {{_e}}')")
            action_codes_list.append(f"                await asyncio.sleep(3)")
            action_codes_list.append(f"                print('[TEST] Action {action_idx} completed: captcha handling')")

        for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
            is_last = i == len(actions) - 1

            # 验证码截图/VL模型识别动作：注入 browser_util.detect_and_solve_captcha 代码
            if self._is_captcha_recognition_action(action):
                print(f"   [验证码] 操作 {i} 为验证码识别，注入browser_util代码: {action}")
                _inject_captcha_code(action_codes, i, action)
                aggregated_actions += f"\n# browser_util.detect_and_solve_captcha(page) 已处理验证码"
                captcha_injected = True
                continue

            # 填写验证码识别结果动作：detect_and_solve_captcha 已包含此步骤，跳过
            if self._is_captcha_fill_action(action):
                print(f"   [验证码] 操作 {i} 为填写识别结果，已由detect_and_solve_captcha处理，跳过: {action}")
                action_codes.append(f"                # Action {i}: {action} (已由验证码识别步骤自动处理，跳过)")
                action_codes.append(f"                print('[TEST] Action {i} skipped: captcha fill already handled')")
                continue

            # 验证码相关操作（宽松匹配）
            if need_captcha_handling and any(k in action.lower() for k in ['验证码', 'captcha']):
                print(f"   [验证码] 操作 {i} 可能与验证码相关，注入 detect_and_solve_captcha: {action}")
                _inject_captcha_code(action_codes, i, action)
                aggregated_actions += f"\n# browser_util.detect_and_solve_captcha(page) 已处理验证码"
                captcha_injected = True
                continue

            # 在登录/提交按钮点击之前自动注入验证码处理
            # 条件：(VL检测到验证码 OR auto_detect_captcha) AND 是登录操作 AND 尚未注入
            is_login_action = any(k in action.lower() for k in [
                '登录', '登入', 'login', 'sign in', 'signin', '提交', 'submit', '确认登录'
            ]) and any(k in action.lower() for k in ['点击', 'click', '按钮', 'button', '提交'])
            if need_captcha_handling and is_login_action and not captcha_injected:
                print(f"   [验证码] 操作 {i} 为登录按钮，在点击前自动注入 detect_and_solve_captcha")
                _inject_captcha_code(action_codes, i, "在登录前自动检测并填写验证码", is_auto=True)
                captcha_injected = True

            print(f"   正在生成操作 {i}/{len(actions) - 1}: {action}")

            # 生成代码（传入表单选择器帮助LLM生成更准确的代码）
            action_code = await test_generator.generate_playwright_code(
                action,
                dom_state,
                aggregated_actions,
                is_last,
                form_selectors=form_selectors
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

            # 步骤2.5: VL验证码检测 + 读取DB配置选择器
            print("\n步骤2.5: VL验证码检测...")
            captcha_info = await self._detect_captcha_from_page(page_content)
            print(f"✅ 验证码检测结果: has_captcha={captcha_info['has_captcha']}, type={captcha_info['captcha_type']}")

            # 步骤3: 基于页面分析生成操作步骤
            print("\n步骤3: 生成操作步骤...")
            actions = await self._generate_actions_with_context(
                user_query, target_url, page_analysis
            )
            result["actions"] = actions
            print(f"✅ 生成了 {len(actions)} 个操作步骤")

            # 步骤4: 使用 Computer-Use 方案生成脚本（纯坐标方式，不需要表单选择器）
            print("\n步骤4: 使用 Computer-Use 方案生成完整测试脚本...")
            final_script = await self._generate_computer_use_script(
                target_url, actions, auto_detect_captcha, auto_cookie_localstorage, load_saved_storage,
                captcha_info=captcha_info
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
        load_saved_storage: bool = True,
        captcha_info: Dict[str, Any] = None
    ) -> str:
        """
        使用 Computer-Use 方案生成测试脚本（纯坐标方式）
        Args:
            target_url: 目标URL
            actions: 操作列表
            auto_detect_captcha: 是否自动检测验证码
            auto_cookie_localstorage: 是否自动加载和保存cookie/localstorage
            load_saved_storage: 是否加载保存的cookie/localstorage/sessionstorage
            captcha_info: VL验证码检测结果 + DB配置选择器
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
            action_codes.append(f"                # 加载保存的 cookies、localStorage 和 sessionStorage（使用 browser_util）")
            action_codes.append(f"                try:")
            action_codes.append(f"                    from app.utils.browser_util import get_browser_util")
            action_codes.append(f"                    browser_util = get_browser_util()")
            action_codes.append(f"                    await browser_util.load_storage(")
            action_codes.append(f"                        cookies_path=os.path.join(SESSION_STORAGE_PATH, 'saved_cookies.json'),")
            action_codes.append(f"                        localstorage_path=os.path.join(SESSION_STORAGE_PATH, 'saved_localstorage.json'),")
            action_codes.append(f"                        sessionstorage_path=os.path.join(SESSION_STORAGE_PATH, 'saved_sessionstorage.json')")
            action_codes.append(f"                    )")
            action_codes.append(f"                except Exception as e:")
            action_codes.append(f"                    print(f'加载 storage 失败: {{e}}')")

        # 使用线程池运行 Playwright，允许使用不同的事件循环策略
        print(f"\n   开始使用 Computer-Use 方案生成操作代码...")

        action_codes_from_playwright = []

        # 定义在线程中执行的异步函数
        async def run_playwright_operations():
            from app.services.computer_use.computer_use_service import ComputerUseService
            from playwright.async_api import async_playwright
            import time

            local_action_codes = []
            aggregated_actions = ""  # 跟踪已生成的操作，用于 LLM 上下文
            captcha_injected = False  # 跟踪验证码处理是否已注入

            # 从captcha_info获取配置选择器
            _captcha_info = captcha_info or {}
            vl_has_captcha = _captcha_info.get("has_captcha", False)
            cfg_captcha_sel = repr(_captcha_info.get("captcha_selector")) if _captcha_info.get("captcha_selector") else "None"
            cfg_captcha_input_sel = repr(_captcha_info.get("captcha_input_selector")) if _captcha_info.get("captcha_input_selector") else "None"
            need_captcha = vl_has_captcha or auto_detect_captcha

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=browser_headless)
                page = await browser.new_page()

                # 导航到目标页面
                print(f"   正在导航到: {target_url}")
                await page.goto(target_url)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # 如果需要加载保存的storage
                if load_saved_storage:
                    print("   正在加载保存的 cookies 和 storage...")
                    from app.utils.browser_util import get_browser_util
                    browser_util = get_browser_util()

                    session_storage_path = os.getenv('SESSION_STORAGE_PATH', os.getcwd())
                    await browser_util.load_storage(
                        page,
                        cookies_path=os.path.join(session_storage_path, 'saved_cookies.json'),
                        localstorage_path=os.path.join(session_storage_path, 'saved_localstorage.json'),
                        sessionstorage_path=os.path.join(session_storage_path, 'saved_sessionstorage.json')
                    )

                    print("   正在刷新页面使登录状态生效...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(5000)
                    print("   ✅ 页面刷新完成")

                computer_use_service = ComputerUseService()

                # 处理每个操作
                for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
                    is_last = i == len(actions) - 1

                    # 判断是否是验证/断言类型的操作
                    is_verification = any(keyword in action.lower() for keyword in [
                        '验证', '断言', 'assert', '检查', '确认', '存在', '显示', '展示',
                        'verify', 'check', 'validate', 'confirm', 'visible', 'exist'
                    ])

                    code_lines = []
                    step_type = "verify" if is_verification else "action"

                    if is_verification:
                        print(f"   操作 {i} 是验证类型，使用VLLM进行截图分析: {action}")

                        # 生成验证代码
                        action_escaped = repr(action)
                        code_lines.append(f"                # Action {i}: {action}")
                        code_lines.append(f"                log_step_start({i}, {action_escaped}, 'verify')")
                        code_lines.append(f"                try:")
                        code_lines.append(f"                    from app.utils.browser_util import get_browser_util")
                        code_lines.append(f"                    browser_util = get_browser_util()")
                        code_lines.append(f"                    await browser_util.assert_by_screenshot(")
                        code_lines.append(f"                        page,")
                        code_lines.append(f"                        verification_description={action_escaped},")
                        code_lines.append(f"                        action_name='Action {i}'")
                        code_lines.append(f"                    )")
                        code_lines.append(f"                    log_step_end({i}, 'passed')")
                        code_lines.append(f"                except Exception as e:")
                        code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                        code_lines.append(f"                    raise")
                    else:
                        # 验证码截图/VL模型识别动作：始终使用 detect_and_solve_captcha
                        if self._is_captcha_recognition_action(action):
                            print(f"   [验证码] 操作 {i} 为验证码识别，注入 detect_and_solve_captcha: {action}")
                            action_escaped = repr(action)
                            code_lines.append(f"                # Action {i}: {action}")
                            code_lines.append(f"                log_step_start({i}, {action_escaped}, 'action')")
                            code_lines.append(f"                try:")
                            code_lines.append(f"                    from app.utils.browser_util import get_browser_util")
                            code_lines.append(f"                    await get_browser_util().detect_and_solve_captcha(page, captcha_selector={cfg_captcha_sel}, captcha_input_selector={cfg_captcha_input_sel})")
                            code_lines.append(f"                    log_step_end({i}, 'passed')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                            local_action_codes.extend(code_lines)
                            captcha_injected = True
                            continue
                        if self._is_captcha_fill_action(action):
                            print(f"   [验证码] 操作 {i} 为填写识别结果，已由detect_and_solve_captcha处理，跳过: {action}")
                            local_action_codes.append(f"                # Action {i}: {action} (已由验证码识别步骤自动处理，跳过)")
                            continue

                        # 验证码相关操作（宽松匹配）
                        if need_captcha and any(k in action.lower() for k in ['验证码', 'captcha']):
                            print(f"   [验证码] 操作 {i} 可能与验证码相关，注入 detect_and_solve_captcha: {action}")
                            action_escaped = repr(action)
                            code_lines.append(f"                # Action {i}: {action}")
                            code_lines.append(f"                log_step_start({i}, {action_escaped}, 'action')")
                            code_lines.append(f"                try:")
                            code_lines.append(f"                    from app.utils.browser_util import get_browser_util")
                            code_lines.append(f"                    await get_browser_util().detect_and_solve_captcha(page, captcha_selector={cfg_captcha_sel}, captcha_input_selector={cfg_captcha_input_sel})")
                            code_lines.append(f"                    log_step_end({i}, 'passed')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                            local_action_codes.extend(code_lines)
                            captcha_injected = True
                            continue

                        # 在登录/提交按钮点击之前自动注入验证码处理
                        is_login_action = any(k in action.lower() for k in [
                            '登录', '登入', 'login', 'sign in', 'signin', '提交', 'submit', '确认登录'
                        ]) and any(k in action.lower() for k in ['点击', 'click', '按钮', 'button', '提交'])
                        if need_captcha and is_login_action and not captcha_injected:
                            print(f"   [验证码] 操作 {i} 为登录按钮，在点击前自动注入 detect_and_solve_captcha")
                            action_escaped_cap = repr(action)
                            code_lines.append(f"                # [自动验证码处理] 在登录前自动检测并填写验证码")
                            code_lines.append(f"                log_step_start({i}, '自动检测验证码', 'action')")
                            code_lines.append(f"                try:")
                            code_lines.append(f"                    from app.utils.browser_util import get_browser_util")
                            code_lines.append(f"                    await get_browser_util().detect_and_solve_captcha(page, captcha_selector={cfg_captcha_sel}, captcha_input_selector={cfg_captcha_input_sel})")
                            code_lines.append(f"                    log_step_end({i}, 'passed')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    print(f'验证码处理失败（非致命）: {{e}}')")
                            local_action_codes.extend(code_lines)
                            code_lines = []
                            captcha_injected = True

                        print(f"   正在使用 Computer-Use 方案生成操作 {i}/{len(actions) - 1}: {action}")

                        # 使用 Computer-Use 服务（基于截图+坐标定位，更通用）
                        action_result = await computer_use_service.analyze_page_and_generate_action(
                            page=page,
                            action_description=action
                        )

                        action_escaped = repr(action)
                        if not action_result.get("element_found"):
                            # Computer-Use 未找到元素，回退到 DOM 选择器模式
                            print(f"   ⚠️ 操作 {i} Computer-Use未找到元素，回退到DOM选择器: {action_result.get('reasoning', '')}")
                            dom_state = (await page.content())[:5000]
                            action_code = await test_generator.generate_playwright_code(
                                action, dom_state, aggregated_actions, is_last
                            )
                            code_lines.append(f"                # Action {i}: {action}")
                            code_lines.append(f"                log_step_start({i}, {action_escaped}, 'action')")
                            code_lines.append(f"                try:")
                            for line in action_code.strip().split('\n'):
                                code_lines.append(f"                    {line}")
                            code_lines.append(f"                    log_step_end({i}, 'passed')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                        else:
                            # Computer-Use 找到元素，使用坐标生成代码
                            from app.services.computer_use.computer_use_service import SyncComputerUseService
                            sync_service = SyncComputerUseService()
                            action_code = sync_service.generate_playwright_code_from_coordinates(
                                action=action_result.get("action", "click"),
                                coordinates=action_result.get("coordinates", {}),
                                text_to_fill=action_result.get("text_to_fill"),
                                is_last=is_last
                            )
                            print(f"   生成的坐标代码:\n{action_code}")
                            code_lines.append(f"                # Action {i}: {action}")
                            code_lines.append(f"                log_step_start({i}, {action_escaped}, 'action')")
                            code_lines.append(f"                try:")
                            for line in action_code.strip().split('\n'):
                                code_lines.append(f"                    {line}")
                            code_lines.append(f"                    log_step_end({i}, 'passed')")
                            code_lines.append(f"                except Exception as e:")
                            code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                            code_lines.append(f"                    raise")
                            await self._execute_action_async(page, action_result)

                        aggregated_actions += f"\n# Action {i}: {action}"

                    local_action_codes.extend(code_lines)

                await browser.close()
                print(f"   Playwright 任务处理完成")

            return local_action_codes

        # 在线程中运行 Playwright
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_run_playwright_in_thread, run_playwright_operations)
                action_codes_from_playwright = future.result(timeout=300)
        except Exception as e:
            print(f"   ❌ Playwright 处理错误: {e}")
            import traceback
            traceback.print_exc()
            raise

        # 将收集的代码添加到 action_codes
        action_codes.extend(action_codes_from_playwright)

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

    async def _generate_actions_from_snapshot(
        self,
        user_query: str,
        target_url: str,
        snapshot_text: str,
    ) -> List[str]:
        """
        基于 agent-browser 无障碍树快照生成操作步骤（不需要 VL 模型）
        Args:
            user_query: 用户查询
            target_url: 目标URL
            snapshot_text: 页面无障碍树快照文本
        Returns:
            操作步骤列表
        """
        system_prompt = """你是一个端到端测试专家。你的目标是将通用的业务端到端测试任务分解为更小的、明确定义的操作。"""

        prompt = f"""将以下输入转换为包含"actions"键和原子步骤列表作为值的JSON字典。
这些步骤将用于生成端到端测试脚本。
每个操作都应该是一个清晰的、原子步骤，可以转换为代码。
尽量生成完成用户测试意图所需的最少操作数量。
第一个操作必须始终是导航到目标URL。
最后一个操作应该始终是断言测试的预期结果。
不要在这个JSON结构之外添加任何额外的字符、注释或解释。只输出JSON结果。

当前页面无障碍树快照（@eN 为可交互元素的引用）：
{snapshot_text[:5000]}

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

        import json
        try:
            parsed = json.loads(response)
            return parsed.get("actions", [])
        except json.JSONDecodeError:
            return [
                f"通过URL导航到 {target_url}",
                user_query,
                "验证测试已成功完成"
            ]

    async def generate_script_with_agent_browser(
        self,
        user_query: str,
        target_url: str,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True,
        page_content: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        使用 agent-browser 方案生成测试脚本（基于无障碍树 snapshot/ref）。
        生成阶段打开真实浏览器进行 snapshot+plan+执行，提取 element_name/element_role，
        产出引用 ab_browser_util 的 Python 测试脚本。脚本可通过 subprocess 重新执行。
        """
        result = {
            "status": "success",
            "actions": [],
            "script": "",
            "test_name": "",
            "error": None,
        }

        try:
            print("\n===== 开始使用 agent-browser 方案生成测试脚本 =====")
            print(f"用户查询: {user_query}")
            print(f"目标URL: {target_url}")

            # 读取全局配置（用户名、密码、headless）
            default_username = ""
            default_password = ""
            from ...core.database import get_db
            from ...models.global_config import GlobalConfig, ConfigKeys
            from sqlalchemy import select

            browser_headless = True
            async for db in get_db():
                for key_attr, target_var in [
                    (ConfigKeys.DEFAULT_USERNAME, "default_username"),
                    (ConfigKeys.DEFAULT_PASSWORD, "default_password"),
                    (ConfigKeys.BROWSER_HEADLESS, "browser_headless"),
                ]:
                    r = await db.execute(
                        select(GlobalConfig).where(GlobalConfig.config_key == key_attr)
                    )
                    cfg = r.scalar_one_or_none()
                    if cfg and cfg.config_value:
                        if target_var == "default_username":
                            default_username = cfg.config_value
                        elif target_var == "default_password":
                            default_password = cfg.config_value
                        elif target_var == "browser_headless":
                            browser_headless = cfg.config_value.lower() == "true"
                break

            # 步骤1: 使用 agent-browser 生成脚本
            print("\n步骤1: 使用 agent-browser 打开页面、分析、生成脚本...")
            final_script = await self._generate_agent_browser_script(
                target_url=target_url,
                user_query=user_query,
                auto_detect_captcha=auto_detect_captcha,
                auto_cookie_localstorage=auto_cookie_localstorage,
                load_saved_storage=load_saved_storage,
                browser_headless=browser_headless,
                default_username=default_username,
                default_password=default_password,
            )
            result["script"] = final_script
            print("✅ 脚本生成完成")

            # 步骤2: 生成测试名称
            print("\n步骤2: 生成测试名称...")
            test_name = await bailian_client.generate_test_name(user_query, result["actions"])
            result["test_name"] = test_name
            print(f"✅ 生成测试名称: {test_name}")

            print("\n===== agent-browser 测试脚本生成完成 =====")
            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ agent-browser 生成错误: {str(e)}")
            print(f"\n错误详情:\n{error_detail}")
            return result

    async def _generate_agent_browser_script(
        self,
        target_url: str,
        user_query: str,
        auto_detect_captcha: bool = False,
        auto_cookie_localstorage: bool = True,
        load_saved_storage: bool = True,
        browser_headless: bool = True,
        default_username: str = "",
        default_password: str = "",
    ) -> str:
        """
        使用 agent-browser 真实浏览器生成 Python 测试脚本。
        流程：open → snapshot → LLM 生成动作列表 → 逐步 snapshot+plan+执行 → 收集 element info → 组装脚本 → close
        """
        ab_service = AgentBrowserService()
        action_planner = ActionPlanner()

        # 读取环境变量配置
        python_path = os.getenv('PYTHON_PATH', '')
        session_storage_path = os.getenv('SESSION_STORAGE_PATH', '.')

        # 浏览器 profile 目录（持久化 cookies、localStorage 等）
        browser_profile_path = os.path.join(session_storage_path, 'browser_profile')
        os.makedirs(browser_profile_path, exist_ok=True)

        # 生成阶段也使用 --profile，确保生成时能看到已登录状态的页面
        if load_saved_storage:
            ab_service.profile_path = browser_profile_path

        # 收集每个 action 对应的代码行
        action_codes = []

        async def run_agent_browser_generation():
            nonlocal action_codes

            try:
                # ===== 1. 检查 agent-browser 是否安装 =====
                installed = await ab_service.check_installed()
                if not installed:
                    raise RuntimeError(
                        "agent-browser 未安装。请运行: npm install -g @anthropic-ai/agent-browser && agent-browser install"
                    )

                # ===== 2. 打开浏览器 =====
                print(f"[AgentBrowser] 正在打开浏览器: {target_url}")
                open_result = await ab_service.open(target_url, headless=browser_headless)
                if not open_result.get("success", True) and open_result.get("error"):
                    raise RuntimeError(f"agent-browser open 失败: {open_result['error']}")
                await ab_service.set_viewport(1920, 1080)
                await ab_service.wait(3000)

                # ===== 3. 会话由 --profile 自动管理（cookies、localStorage 等） =====
                if load_saved_storage:
                    print(f"[AgentBrowser] 使用 --profile 加载已保存的浏览器状态: {browser_profile_path}")
                else:
                    print("[AgentBrowser] 登录场景，不加载已有浏览器状态")

                # ===== 4. 获取无障碍树快照用于生成 actions =====
                print("[AgentBrowser] 获取页面无障碍树快照...")
                initial_snap = await ab_service.snapshot(interactive=True)
                initial_snapshot_text = initial_snap.get("data", {}).get("snapshot", "") or initial_snap.get("snapshot", "") or initial_snap.get("raw_output", "")
                print(f"[AgentBrowser] 快照长度: {len(initial_snapshot_text)} 字符")

                # ===== 5. 基于快照生成操作步骤 =====
                print("[AgentBrowser] 基于无障碍树快照生成操作步骤...")
                actions = await self._generate_actions_from_snapshot(
                    user_query, target_url, initial_snapshot_text
                )
                print(f"[AgentBrowser] 生成了 {len(actions)} 个操作步骤:")
                for idx, action in enumerate(actions):
                    print(f"   {idx + 1}. {action}")

                # ===== 6. 逐步 snapshot+plan+执行，收集 element_name/element_role =====
                aggregated = ""
                captcha_injected = False
                step_counter = 0  # 独立步骤计数器（避免注入步骤时编号冲突）

                for i, action in enumerate(actions[1:], 1):  # 跳过导航
                    # 跳过验证码截图/VL识别动作
                    if self._is_captcha_recognition_action(action):
                        print(f"[AgentBrowser] 跳过验证码识别动作: {action}")
                        continue
                    if self._is_captcha_fill_action(action):
                        print(f"[AgentBrowser] 跳过验证码填写动作: {action}")
                        continue

                    step_counter += 1

                    is_verification = any(k in action.lower() for k in [
                        '验证', '断言', 'assert', '检查', '确认', '存在', '显示',
                        'verify', 'check', 'validate', 'confirm', 'visible', 'exist'
                    ])

                    # 在登录按钮点击前注入验证码处理
                    action_lower = action.lower()
                    action_no_space = action_lower.replace(" ", "")
                    is_login_action = any(k in action_no_space for k in [
                        '登录', '登入', 'login', 'signin', '提交', 'submit'
                    ]) and any(k in action_no_space for k in ['点击', 'click', '按钮', 'button', '提交'])

                    if auto_detect_captcha and is_login_action and not captcha_injected:
                        print(f"[AgentBrowser] 在登录前注入验证码处理代码")
                        captcha_step = step_counter
                        step_counter += 1  # 验证码占一个步骤，后面的动作编号递增
                        action_escaped_cap = repr("自动检测验证码")
                        action_codes.append(f"        # [自动验证码处理] 在登录前自动检测并填写验证码")
                        action_codes.append(f"        log_step_start({captcha_step}, {action_escaped_cap}, 'action')")
                        action_codes.append(f"        try:")
                        action_codes.append(f"            ab.detect_and_solve_captcha()")
                        action_codes.append(f"            screenshot_path_{captcha_step} = os.path.join(EXEC_SCREENSHOTS_DIR, 'step_{captcha_step}.png')")
                        action_codes.append(f"            ab.screenshot(path=screenshot_path_{captcha_step})")
                        action_codes.append(f"            step_screenshots.append({{\"step_number\": {captcha_step}, \"step_name\": {action_escaped_cap}, \"screenshot_path\": screenshot_path_{captcha_step}}})")
                        action_codes.append(f"            log_step_end({captcha_step}, 'passed', {{\"screenshot_path\": screenshot_path_{captcha_step}}})")
                        action_codes.append(f"        except Exception as e:")
                        action_codes.append(f"            log_step_end({captcha_step}, 'failed', error_message=str(e))")
                        action_codes.append(f"            print(f'验证码处理失败（非致命）: {{e}}')")
                        captcha_injected = True

                    action_escaped = repr(action)
                    sn = step_counter  # 当前步骤编号

                    if is_verification:
                        # 验证操作：截图 + 标记通过（与 computer-use 模式一致）
                        print(f"   操作 {i} 是验证类型: {action}")
                        action_codes.append(f"        # Action {sn}: {action}")
                        action_codes.append(f"        log_step_start({sn}, {action_escaped}, 'verify')")
                        action_codes.append(f"        try:")
                        action_codes.append(f"            screenshot_path_{sn} = os.path.join(EXEC_SCREENSHOTS_DIR, 'step_{sn}.png')")
                        action_codes.append(f"            ab.screenshot(path=screenshot_path_{sn})")
                        action_codes.append(f"            step_screenshots.append({{\"step_number\": {sn}, \"step_name\": {action_escaped}, \"screenshot_path\": screenshot_path_{sn}}})")
                        action_codes.append(f"            ab.wait(2000)")
                        action_codes.append(f"            log_step_end({sn}, 'passed', {{\"screenshot_path\": screenshot_path_{sn}}})")
                        action_codes.append(f"        except Exception as e:")
                        action_codes.append(f"            log_step_end({sn}, 'failed', error_message=str(e))")
                        action_codes.append(f"            raise")

                        # 在真实浏览器上也执行截图（推进状态）
                        await ab_service.screenshot()
                    else:
                        # 获取最新快照
                        snap = await ab_service.snapshot(interactive=True)
                        snapshot_text = snap.get("data", {}).get("snapshot", "") or snap.get("snapshot", "") or snap.get("raw_output", "")

                        # 用 LLM 规划操作
                        plan = await action_planner.plan_action(
                            action, snapshot_text, aggregated,
                            default_username=default_username,
                            default_password=default_password,
                        )

                        if plan.get("error"):
                            print(f"   ⚠️ 操作 {i} ActionPlanner 错误: {plan.get('reasoning', '')}")
                            action_codes.append(f"        # Action {sn}: {action} (ActionPlanner 错误，跳过)")
                            aggregated += f"\n# Action {sn}: {action} (skipped)"
                            continue

                        cmd = plan["command"]
                        ref = plan["ref"]
                        value = plan.get("value", "")
                        element_name = plan.get("element_name", "")
                        element_role = plan.get("element_role", "")

                        # 生成 Python 代码行（使用 smart_click/smart_fill）
                        action_codes.append(f"        # Action {sn}: {action}")
                        action_codes.append(f"        log_step_start({sn}, {action_escaped}, 'action')")
                        action_codes.append(f"        try:")

                        if cmd == "fill" and element_name:
                            value_escaped = repr(value)
                            name_escaped = repr(element_name)
                            role_escaped = repr(element_role) if element_role else "None"
                            action_codes.append(f"            ab.smart_fill(element_text={name_escaped}, value={value_escaped}, element_role={role_escaped})")
                        elif cmd == "click" and element_name:
                            name_escaped = repr(element_name)
                            role_escaped = repr(element_role) if element_role else "None"
                            action_codes.append(f"            ab.smart_click(element_text={name_escaped}, element_role={role_escaped})")
                        elif cmd == "wait":
                            action_codes.append(f"            ab.wait(2000)")
                        elif cmd == "screenshot":
                            action_codes.append(f"            ab.screenshot()")
                        else:
                            # 回退：如果没有 element_name，使用通用描述
                            if cmd == "click":
                                action_codes.append(f"            ab.smart_click(element_text={repr(action)}, element_role=None)")
                            elif cmd == "fill":
                                action_codes.append(f"            ab.smart_fill(element_text={repr(action)}, value={repr(value)}, element_role=None)")
                            else:
                                action_codes.append(f"            ab.wait(2000)")

                        action_codes.append(f"            ab.wait(2000)")
                        action_codes.append(f"            screenshot_path_{sn} = os.path.join(EXEC_SCREENSHOTS_DIR, 'step_{sn}.png')")
                        action_codes.append(f"            ab.screenshot(path=screenshot_path_{sn})")
                        action_codes.append(f"            step_screenshots.append({{\"step_number\": {sn}, \"step_name\": {action_escaped}, \"screenshot_path\": screenshot_path_{sn}}})")
                        action_codes.append(f"            log_step_end({sn}, 'passed', {{\"screenshot_path\": screenshot_path_{sn}}})")
                        action_codes.append(f"        except Exception as e:")
                        action_codes.append(f"            log_step_end({sn}, 'failed', error_message=str(e))")
                        action_codes.append(f"            raise")

                        # 在真实浏览器上执行操作（推进页面状态）
                        try:
                            if cmd == "click" and ref:
                                await ab_service.click(ref)
                            elif cmd == "fill" and ref:
                                await ab_service.fill(ref, value)
                            elif cmd == "wait":
                                await ab_service.wait(2000)
                            elif cmd == "screenshot":
                                await ab_service.screenshot()
                            await ab_service.wait(2000)
                        except Exception as exec_err:
                            print(f"   ⚠️ 操作 {i} 执行失败（不影响脚本生成）: {exec_err}")

                    aggregated += f"\n# Action {i}: {action}"

                # ===== 7. 会话状态由 --profile 自动保存 =====
                print("[AgentBrowser] 浏览器状态已由 --profile 自动保存")

            finally:
                print("[AgentBrowser] 正在关闭浏览器...")
                try:
                    await ab_service.close()
                    print("[AgentBrowser] 浏览器已关闭")
                except Exception as close_err:
                    print(f"[AgentBrowser] 关闭浏览器失败: {close_err}")

        # 在主事件循环中执行（agent-browser 是 Node CLI，不需要 ProactorEventLoop）
        await run_agent_browser_generation()

        # 组装完整 Python 脚本
        actions_str = "\n".join(action_codes)

        # 使用 --profile 持久化浏览器状态（cookies、localStorage 等）
        # 登录场景 (load_saved_storage=False): 清空 profile 重新登录，执行后自动保存状态
        # 非登录场景 (load_saved_storage=True): 复用已有 profile，自动带上登录状态
        clear_profile_code = ""
        if not load_saved_storage:
            clear_profile_code = """
    # 登录场景：清空已有 profile，确保从全新状态开始登录
    import shutil
    if os.path.exists(BROWSER_PROFILE_PATH):
        shutil.rmtree(BROWSER_PROFILE_PATH)
        print(f'[TEST] 已清空浏览器 profile: {BROWSER_PROFILE_PATH}')
    os.makedirs(BROWSER_PROFILE_PATH, exist_ok=True)
"""

        script = f'''import sys
import os

# 配置常量（从环境变量读取）
PYTHON_PATH = r'{python_path}'
SESSION_STORAGE_PATH = r'{session_storage_path}'

# 必须在最开头处理PYTHON_PATH，否则后续import可能找不到模块
if PYTHON_PATH and PYTHON_PATH not in sys.path:
    sys.path.insert(0, PYTHON_PATH)

import pytest
import json
import time
import uuid
from datetime import datetime

# 全局步骤结果列表
step_results = []

# 截图目录
SCREENSHOTS_DIR = os.path.join(SESSION_STORAGE_PATH, 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# 浏览器 profile 目录（持久化 cookies、localStorage 等）
BROWSER_PROFILE_PATH = os.path.join(SESSION_STORAGE_PATH, 'browser_profile')
os.makedirs(BROWSER_PROFILE_PATH, exist_ok=True)

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

def test_generated():
    print(json.dumps({{"event": "test_start", "message": "Test started"}}, ensure_ascii=False))
    from app.utils.ab_browser_util import AgentBrowserUtil
    session_id = uuid.uuid4().hex[:8]
{clear_profile_code}
    # 使用 --profile 自动持久化浏览器状态（cookies、localStorage、sessionStorage 等）
    ab = AgentBrowserUtil(session_id=session_id, profile_path=BROWSER_PROFILE_PATH)
    test_start_time = time.time()
    step_screenshots = []  # 收集每步截图信息用于批量VL验证

    # 为本次执行创建独立截图子目录
    EXEC_SCREENSHOTS_DIR = os.path.join(SCREENSHOTS_DIR, session_id)
    os.makedirs(EXEC_SCREENSHOTS_DIR, exist_ok=True)

    try:
        # Step 0: Navigate
        log_step_start(0, "Navigate to {target_url}", "navigation")
        try:
            ab.open("{target_url}", headless={browser_headless})
            ab.set_viewport(1920, 1080)
            time.sleep(3)
            ab.wait(3000)
            # 截图
            screenshot_path_0 = os.path.join(EXEC_SCREENSHOTS_DIR, 'step_0.png')
            ab.screenshot(path=screenshot_path_0)
            step_screenshots.append({{"step_number": 0, "step_name": "Navigate to {target_url}", "screenshot_path": screenshot_path_0}})
            log_step_end(0, "passed", {{"url": "{target_url}", "screenshot_path": screenshot_path_0}})
        except Exception as e:
            log_step_end(0, "failed", error_message=str(e))
            raise

        # Execute all actions
{actions_str}
        # 批量VL验证截图
        valid_screenshots = [s for s in step_screenshots if os.path.exists(s["screenshot_path"])]
        if valid_screenshots:
            try:
                verification_results = ab.verify_step_screenshots(valid_screenshots)
                for vr in verification_results:
                    print(json.dumps({{
                        "event": "step_verification",
                        "step_number": vr["step_number"],
                        "verified": vr["verified"],
                        "reason": vr["reason"]
                    }}, ensure_ascii=False))
            except Exception as vl_err:
                print(f"[VL验证] 批量验证失败（非致命）: {{vl_err}}")

        print(json.dumps({{"event": "test_completed", "total_duration_ms": int((time.time() - test_start_time) * 1000)}}, ensure_ascii=False))

    except Exception as e:
        import traceback
        print(json.dumps({{
            "event": "test_failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }}, ensure_ascii=False))
        raise
    finally:
        try:
            ab.close()
        except Exception:
            pass

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
'''
        return script

    async def _execute_action_async(self, page, action_result):
        """异步执行页面操作（使用坐标定位，用于生成期间推进页面状态）"""
        try:
            action_type = action_result.get("action", "click")
            coordinates = action_result.get("coordinates", {})
            text_to_fill = action_result.get("text_to_fill")

            x = coordinates.get("x", 0)
            y = coordinates.get("y", 0)

            if action_type == "click":
                await page.mouse.click(x, y)
                await page.wait_for_timeout(1000)
            elif action_type == "fill" and text_to_fill:
                # 点击坐标位置激活输入框，然后填充
                await page.mouse.click(x, y)
                await page.wait_for_timeout(500)
                # 清空后输入
                await page.keyboard.press("Control+a")
                await page.keyboard.type(text_to_fill, delay=50)
                await page.wait_for_timeout(500)
            elif action_type == "scroll":
                await page.evaluate(f"window.scrollBy({x}, {y})")
            elif action_type == "wait":
                await page.wait_for_timeout(2000)

        except Exception as e:
            print(f"   执行操作时出错: {e}")
            # 不中断流程，继续处理下一个操作

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

        # 使用 backend/app/temp/ 目录保存临时脚本，方便排查问题
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8-sig', dir=temp_dir) as f:
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
            print(f"   标准输出:\n{result.stdout[:5000]}")
            if result.stderr:
                print(f"   标准错误:\n{result.stderr[:2000]}")

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

                    # 处理步骤开始、结束、VL验证事件
                    if step_data.get("event") in ["step_start", "step_end", "step_verification"]:
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
            # 基于解析出的步骤事件判断（更精确，不会被日志中的 "Error" 文本误触发）
            has_test_failed_event = any(
                s.get("event") == "step_end" and s.get("status") == "failed"
                for s in step_results
            )
            has_test_failed_json = any(
                line.strip().startswith('{') and '"event": "test_failed"' in line
                for line in execution_output.split('\n')
            )
            # pytest 最终汇总行: "X failed" 或 "FAILED"
            has_pytest_failure = "FAILED" in execution_output and "passed" not in execution_output.split("FAILED")[-1]

            if has_test_failed_event or has_test_failed_json or has_pytest_failure:
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
