"""
Playwright 处理器 - 在单独进程中运行 Playwright
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.sync_api import sync_playwright
from app.services.computer_use.computer_use_service import sync_computer_use_service


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

        print(f"\n   [子进程] 开始处理 Playwright 任务...")
        print(f"   [子进程] 目标URL: {target_url}")
        print(f"   [子进程] 操作数量: {len(actions)}")

        collected_codes = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=browser_headless)
            page = browser.new_page()
            page.goto(target_url)
            page.wait_for_load_state("networkidle")
            import time
            time.sleep(2)

            for i, action in enumerate(actions[1:], 1):  # 跳过第一个导航操作
                is_last = i == len(actions) - 1

                # 如果启用了自动验证码检测，跳过验证码相关的操作
                if auto_detect_captcha and any(keyword in action.lower() for keyword in ['验证码', 'captcha', '截图', 'screenshot']):
                    print(f"   [子进程] 跳过操作 {i}: {action} (自动验证码检测已启用)")
                    continue

                print(f"   [子进程] 正在使用 Computer-Use 方案生成操作 {i}/{len(actions) - 1}: {action}")

                # 使用同步版本的 Computer-Use 服务分析页面并生成操作
                action_result = sync_computer_use_service.analyze_page_and_generate_action(
                    page=page,
                    action_description=action
                )

                if not action_result.get("element_found"):
                    print(f"   [子进程] ⚠️ 操作 {i} 未找到元素: {action_result.get('reasoning', '未知原因')}")
                    continue

                # 生成代码，使用 action_result 中的 text_to_fill
                action_code = sync_computer_use_service.generate_playwright_code_from_coordinates(
                    action=action_result.get("action", "click"),
                    coordinates=action_result.get("coordinates", {}),
                    text_to_fill=action_result.get("text_to_fill"),
                    is_last=is_last
                )

                print(f"   [子进程] 生成的代码:\n{action_code}")

                # 收集操作代码
                code_lines = []
                code_lines.append(f"                # Action {i}: {action}")
                code_lines.append(f"                print('[TEST] Action {i} started')")
                for line in action_code.strip().split('\n'):
                    code_lines.append(f"                {line}")
                code_lines.append("                await asyncio.sleep(3)")
                code_lines.append(f"                print('[TEST] Action {i} completed')")

                collected_codes.extend(code_lines)

                # 执行操作以便进行下一步截图分析
                sync_computer_use_service.execute_action_with_coordinates(page, action_result)

            browser.close()
            print(f"   [子进程] Playwright 任务处理完成")
            return collected_codes

    except Exception as e:
        print(f"   [子进程] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise