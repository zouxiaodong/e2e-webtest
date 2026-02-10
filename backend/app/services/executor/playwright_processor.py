"""
Playwright 处理器 - 在单独进程中处理 Playwright 任务
"""

import os
import json
import time
from typing import List, Dict, Any

from app.core.config import settings
from app.services.computer_use.computer_use_service import SyncComputerUseService


def detect_and_handle_captcha(page, api_key, base_url, vl_model):
    """
    检测并处理验证码 - 使用BrowserUtil工具类

    Args:
        page: Playwright page对象（同步）
        api_key: 百练API密钥
        base_url: 百练API基础URL
        vl_model: VL模型名称

    Returns:
        是否成功处理验证码
    """
    try:
        from app.utils.browser_util import get_browser_util
        browser_util = get_browser_util()

        # 使用browser_util的验证码检测和处理方法
        success = browser_util.detect_and_solve_captcha(page)
        return success
    except Exception as e:
        print(f"   [子进程] 验证码处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_playwright_task(task_data):
    """
    在单独进程中处理 Playwright 任务

    Args:
        task_data: 包含任务数据的字典

    Returns:
        生成的代码列表
    """
    try:
        target_url = task_data.get('target_url')
        actions = task_data.get('actions', [])
        browser_headless = task_data.get('browser_headless', True)
        auto_detect_captcha = task_data.get('auto_detect_captcha', False)
        load_saved_storage = task_data.get('load_saved_storage', True)

        # 获取 VL 模型配置
        api_key = settings.BAILIAN_API_KEY
        base_url = settings.BAILIAN_BASE_URL
        vl_model = settings.BAILIAN_VL_MODEL

        print(f"\n   [子进程] 开始处理 Playwright 任务...")
        print(f"   [子进程] 目标URL: {target_url}")
        print(f"   [子进程] 操作数量: {len(actions)}")
        print(f"   [子进程] 自动验证码检测: {auto_detect_captcha}")
        print(f"   [子进程] 加载保存的storage: {load_saved_storage}")

        collected_codes = []

        with SyncComputerUseService() as sync_computer_use_service:
            browser = sync_computer_use_service.p.chromium.launch(headless=browser_headless)
            page = browser.new_page()

            # 先导航到目标页面
            print(f"   [子进程] 正在导航到: {target_url}")
            page.goto(target_url)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 如果需要加载保存的storage
            if load_saved_storage:
                print("   [子进程] 正在加载保存的 cookies 和 storage...")
                from app.utils.browser_util import get_browser_util
                browser_util = get_browser_util()

                # 获取会话存储路径
                session_storage_path = os.getenv('SESSION_STORAGE_PATH', os.getcwd())

                # 使用browser_util加载storage
                browser_util.load_storage(
                    page,
                    cookies_path=os.path.join(session_storage_path, 'saved_cookies.json'),
                    localstorage_path=os.path.join(session_storage_path, 'saved_localstorage.json'),
                    sessionstorage_path=os.path.join(session_storage_path, 'saved_sessionstorage.json')
                )

                # 刷新页面使storage生效
                print("   [子进程] 正在刷新页面使登录状态生效...")
                page.reload(wait_until="domcontentloaded")
                time.sleep(5)
                print("   [子进程] ✅ 页面刷新完成")

            for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
                is_last = i == len(actions) - 1

                # 如果启用了自动验证码检测，跳过验证码相关的操作
                if auto_detect_captcha and any(keyword in action.lower() for keyword in ['验证码', 'captcha', '截图', 'screenshot']):
                    print(f"   [子进程] 跳过操作 {i}: {action} (自动验证码检测已启用)")
                    continue

                # 判断是否是验证/断言类型的操作
                is_verification = any(keyword in action.lower() for keyword in [
                    '验证', '断言', 'assert', '检查', '确认', '存在', '显示', '展示',
                    'verify', 'check', 'validate', 'confirm', 'visible', 'exist'
                ])

                # 收集操作代码 - 使用结构化日志
                code_lines = []
                step_type = "verify" if is_verification else "action"

                if is_verification:
                    print(f"   [子进程] 操作 {i} 是验证类型，使用VLLM进行截图分析: {action}")

                    # 生成验证代码（使用BrowserUtil工具类）
                    code_lines.append(f"                # Action {i}: {action}")
                    code_lines.append(f"                log_step_start({i}, '{action}', 'verify')")
                    code_lines.append(f"                try:")
                    code_lines.append(f"                    from app.utils.browser_util import get_browser_util")
                    code_lines.append(f"                    browser_util = get_browser_util()")
                    code_lines.append(f"                    await browser_util.assert_by_screenshot(")
                    code_lines.append(f"                        page,")
                    code_lines.append(f"                        verification_description='{action}',")
                    code_lines.append(f"                        action_name='Action {i}'")
                    code_lines.append(f"                    )")
                    code_lines.append(f"                    log_step_end({i}, 'passed')")
                    code_lines.append(f"                except Exception as e:")
                    code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                    code_lines.append(f"                    raise")
                else:
                    # 如果启用了自动验证码检测，在执行操作前检查验证码
                    if auto_detect_captcha:
                        detect_and_handle_captcha(page, api_key, base_url, vl_model)
                        time.sleep(1)  # 等待验证码填写完成

                    print(f"   [子进程] 正在使用 Computer-Use 方案生成操作 {i}/{len(actions) - 1}: {action}")

                    # 使用同步版本的 Computer-Use 服务分析页面并生成操作
                    action_result = sync_computer_use_service.analyze_page_and_generate_action(
                        page=page,
                        action_description=action
                    )

                    if not action_result.get("element_found"):
                        print(f"   [子进程] ⚠️ 操作 {i} 未找到元素: {action_result.get('reasoning', '未知原因')}")
                        # 生成一个注释说明未找到元素
                        code_lines.append(f"                # Action {i}: {action}")
                        code_lines.append(f"                log_step_start({i}, '{action}', 'action')")
                        code_lines.append(f"                try:")
                        code_lines.append(f"                    await page.wait_for_timeout(2000)")
                        code_lines.append(f"                    await page.screenshot(path=f'action_{i}_screenshot.png')")
                        code_lines.append(f"                    print(json.dumps({{'event': 'screenshot_saved', 'step': {i}, 'path': f'action_{i}_screenshot.png'}}, ensure_ascii=False))")
                        code_lines.append(f"                    log_step_end({i}, 'skipped')")
                    else:
                        # 生成代码，使用 action_result 中的 text_to_fill
                        action_code = sync_computer_use_service.generate_playwright_code_from_coordinates(
                            action=action_result.get("action", "click"),
                            coordinates=action_result.get("coordinates", {}),
                            text_to_fill=action_result.get("text_to_fill"),
                            is_last=is_last
                        )

                        print(f"   [子进程] 生成的代码:\n{action_code}")

                        code_lines.append(f"                # Action {i}: {action}")
                        code_lines.append(f"                log_step_start({i}, '{action}', 'action')")
                        code_lines.append(f"                try:")
                        for line in action_code.strip().split('\n'):
                            code_lines.append(f"                    {line}")
                        code_lines.append(f"                    log_step_end({i}, 'passed')")
                        code_lines.append(f"                except Exception as e:")
                        code_lines.append(f"                    log_step_end({i}, 'failed', error_message=str(e))")
                        code_lines.append(f"                    raise")

                        # 执行操作以便进行下一步截图分析
                        sync_computer_use_service.execute_action_with_coordinates(page, action_result)

                collected_codes.extend(code_lines)

            browser.close()
            print(f"   [子进程] Playwright 任务处理完成")
            return collected_codes

    except Exception as e:
        print(f"   [子进程] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise
