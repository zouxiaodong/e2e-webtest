"""
Playwright 处理器 - 在单独进程中运行 Playwright
"""

import sys
import os
import base64

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.sync_api import sync_playwright
from app.services.computer_use.computer_use_service import sync_computer_use_service


def detect_and_handle_captcha(page, api_key, base_url, vl_model):
    """
    检测并处理验证码
    Args:
        page: Playwright page 对象（同步）
        api_key: VL 模型 API 密钥
        base_url: VL 模型基础 URL
        vl_model: VL 模型名称
    Returns:
        是否成功处理验证码
    """
    try:
        # 检测验证码图片
        captcha_img = page.locator('img[src*="captcha"], img[id*="captcha"], .captcha img').first
        if not captcha_img.is_visible(timeout=3000):
            print("   [子进程] 未检测到验证码")
            return False

        print("   [子进程] 检测到验证码")
        
        # 截取验证码图片
        captcha_bytes = captcha_img.screenshot()
        captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')

        # 调用 VL 模型识别验证码
        import openai
        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        response = client.chat.completions.create(
            model=vl_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个验证码识别专家。识别图片中的验证码内容。如果是数学运算（如2+3=?），请计算并返回结果。只返回验证码值或计算结果，不要添加任何解释。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这张图片中的验证码内容。如果是数学运算题，请计算并返回结果。只返回最终结果。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{captcha_base64}"}}
                    ]
                }
            ],
            temperature=0.0,
            max_tokens=50
        )

        captcha_text = response.choices[0].message.content.strip()
        print(f"   [子进程] 识别到验证码: {captcha_text}")

        # 填写验证码
        captcha_input = page.locator('input[name*="captcha"], input[id*="captcha"], input[placeholder*="验证码"]').first
        if captcha_input.is_visible(timeout=3000):
            captcha_input.fill(captcha_text)
            print("   [子进程] 验证码已填写")
            return True
        else:
            print("   [子进程] 未找到验证码输入框")
            return False

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

        # 获取 VL 模型配置
        from app.core.config import settings
        api_key = settings.BAILIAN_API_KEY
        base_url = settings.BAILIAN_BASE_URL
        vl_model = settings.BAILIAN_VL_MODEL

        print(f"\n   [子进程] 开始处理 Playwright 任务...")
        print(f"   [子进程] 目标URL: {target_url}")
        print(f"   [子进程] 操作数量: {len(actions)}")
        print(f"   [子进程] 自动验证码检测: {auto_detect_captcha}")

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

                # 如果启用了自动验证码检测，在执行操作前检查验证码
                if auto_detect_captcha:
                    detect_and_handle_captcha(page, api_key, base_url, vl_model)
                    time.sleep(1)  # 等待验证码填写完成

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

                # 如果启用了自动验证码检测，在执行操作后也检查验证码
                if auto_detect_captcha:
                    time.sleep(1)  # 等待页面更新
                    detect_and_handle_captcha(page, api_key, base_url, vl_model)

            browser.close()
            print(f"   [子进程] Playwright 任务处理完成")
            return collected_codes

    except Exception as e:
        print(f"   [子进程] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise