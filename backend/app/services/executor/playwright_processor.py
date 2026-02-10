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
        # 检测验证码图片 - 使用更通用的选择器
        captcha_img = None
        
        # 尝试多种选择器
        selectors = [
            'img[src*="captcha"]',
            'img[id*="captcha"]',
            'img[alt*="captcha"]',
            'img[alt*="验证码"]',
            '.captcha img',
            '#captcha img',
            '[class*="captcha"] img',
            'img[src*="code"]',
            'img[src*="verify"]'
        ]
        
        for selector in selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    captcha_img = elements.first
                    if captcha_img.is_visible(timeout=1000):
                        print(f"   [子进程] 使用选择器找到验证码: {selector}")
                        break
            except:
                continue
        
        # 如果没找到，尝试查找所有图片并检查 src 属性
        if not captcha_img:
            all_images = page.locator('img')
            for i in range(all_images.count()):
                img = all_images.nth(i)
                try:
                    src = img.get_attribute('src') or ''
                    alt = img.get_attribute('alt') or ''
                    if any(keyword in src.lower() or keyword in alt.lower() for keyword in ['captcha', '验证码', 'code', 'verify', 'check']):
                        captcha_img = img
                        if captcha_img.is_visible(timeout=1000):
                            print(f"   [子进程] 通过属性查找找到验证码: src={src[:50]}...")
                            break
                except:
                    continue
        
        if not captcha_img or not captcha_img.is_visible(timeout=1000):
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

        # 填写验证码 - 使用更通用的选择器
        captcha_input = None
        input_selectors = [
            'input[name*="captcha"]',
            'input[id*="captcha"]',
            'input[placeholder*="captcha"]',
            'input[placeholder*="验证码"]',
            'input[name*="code"]',
            'input[name*="verify"]',
            'input[type="text"][maxlength*="4"]',
            'input[type="text"][maxlength*="5"]',
            'input[type="text"][maxlength*="6"]'
        ]
        
        for selector in input_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    captcha_input = elements.first
                    if captcha_input.is_visible(timeout=1000):
                        print(f"   [子进程] 使用选择器找到验证码输入框: {selector}")
                        break
            except:
                continue
        
        if captcha_input and captcha_input.is_visible(timeout=1000):
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
        load_saved_storage = task_data.get('load_saved_storage', True)

        # 获取 VL 模型配置
        from app.core.config import settings
        api_key = settings.BAILIAN_API_KEY
        base_url = settings.BAILIAN_BASE_URL
        vl_model = settings.BAILIAN_VL_MODEL

        print(f"\n   [子进程] 开始处理 Playwright 任务...")
        print(f"   [子进程] 目标URL: {target_url}")
        print(f"   [子进程] 操作数量: {len(actions)}")
        print(f"   [子进程] 自动验证码检测: {auto_detect_captcha}")
        print(f"   [子进程] 加载保存的storage: {load_saved_storage}")

        collected_codes = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=browser_headless)
            page = browser.new_page()
            
            # 如果需要加载保存的storage
            if load_saved_storage:
                print("   [子进程] 正在加载保存的 cookies 和 storage...")
                import os, json
                
                # 获取会话存储路径
                session_storage_path = os.getenv('SESSION_STORAGE_PATH', os.getcwd())
                
                # 加载cookies
                cookie_file = os.path.join(session_storage_path, 'saved_cookies.json')
                if os.path.exists(cookie_file):
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                    if cookies:
                        page.context.add_cookies(cookies)
                        print(f"   [子进程] ✅ Cookies 已加载: {len(cookies)}个")
                    else:
                        print("   [子进程] ⚠️ Cookies 文件为空")
                else:
                    print(f"   [子进程] ⚠️ Cookies 文件不存在: {cookie_file}")
                
                # 加载localStorage和sessionStorage（在页面加载后）
                page.goto(target_url)
                page.wait_for_load_state("domcontentloaded")
                
                ls_file = os.path.join(session_storage_path, 'saved_localstorage.json')
                if os.path.exists(ls_file):
                    with open(ls_file, 'r', encoding='utf-8') as f:
                        ls_data = f.read()
                    try:
                        ls_data_obj = json.loads(ls_data)
                        page.evaluate("data => { localStorage.clear(); for (const key in data) { localStorage.setItem(key, data[key]); } }", ls_data_obj)
                        print("   [子进程] ✅ LocalStorage 已加载")
                    except json.JSONDecodeError:
                        print("   [子进程] ⚠️ LocalStorage 解析失败")
                else:
                    print(f"   [子进程] ⚠️ LocalStorage 文件不存在")
                
                ss_file = os.path.join(session_storage_path, 'saved_sessionstorage.json')
                if os.path.exists(ss_file):
                    with open(ss_file, 'r', encoding='utf-8') as f:
                        ss_data = f.read()
                    try:
                        ss_data_obj = json.loads(ss_data)
                        page.evaluate("data => { sessionStorage.clear(); for (const key in data) { sessionStorage.setItem(key, data[key]); } }", ss_data_obj)
                        print("   [子进程] ✅ SessionStorage 已加载")
                    except json.JSONDecodeError:
                        print("   [子进程] ⚠️ SessionStorage 解析失败")
                else:
                    print(f"   [子进程] ⚠️ SessionStorage 文件不存在")
                
                # 刷新页面使storage生效
                print("   [子进程] 正在刷新页面使登录状态生效...")
                page.reload(wait_until="domcontentloaded")
                import time
                time.sleep(5)
                print("   [子进程] ✅ 页面刷新完成")
            else:
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

                # 收集操作代码
                code_lines = []
                code_lines.append(f"                # Action {i}: {action}")
                code_lines.append(f"                print('[TEST] Action {i} started')")

                # 判断是否是验证/断言类型的操作
                is_verification = any(keyword in action.lower() for keyword in [
                    '验证', '断言', 'assert', '检查', '确认', '存在', '显示', '展示',
                    'verify', 'check', 'validate', 'confirm', 'visible', 'exist'
                ])

                if is_verification:
                    print(f"   [子进程] 操作 {i} 是验证类型，使用VLLM进行截图分析: {action}")
                    
                    # 截图并使用VLLM分析
                    screenshot_bytes = page.screenshot()
                    import base64
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    
                    # 调用VLLM分析页面
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key, base_url=base_url)
                    
                    response = client.chat.completions.create(
                        model=vl_model,
                        messages=[
                            {
                                "role": "system",
                                "content": "你是一个网页验证专家。分析截图，判断用户要求的验证内容是否满足。只回答'是'或'否'，并简要说明原因。"
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"请验证以下内容是否存在或正确显示：{action}"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                                ]
                            }
                        ],
                        temperature=0.0,
                        max_tokens=200
                    )
                    
                    verification_result = response.choices[0].message.content.strip()
                    print(f"   [子进程] VLLM验证结果: {verification_result}")

                    # 生成验证代码（使用BrowserUtil工具类）
                    code_lines.append(f"                # 使用BrowserUtil验证: {action}")
                    code_lines.append(f"                from app.utils.browser_util import get_browser_util")
                    code_lines.append(f"                browser_util = get_browser_util()")
                    code_lines.append(f"                await browser_util.assert_by_screenshot(")
                    code_lines.append(f"                    page,")
                    code_lines.append(f"                    verification_description='{action}',")
                    code_lines.append(f"                    action_name='Action {i}'")
                    code_lines.append(f"                )")
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
                        code_lines.append(f"                # ⚠️ 未找到元素: {action_result.get('reasoning', '未知原因')}")
                        code_lines.append(f"                # 尝试通过文本内容查找并验证")
                        code_lines.append(f"                try:")
                        code_lines.append(f"                    # 等待页面稳定")
                        code_lines.append(f"                    await page.wait_for_timeout(2000)")
                        code_lines.append(f"                    # 截图用于调试")
                        code_lines.append(f"                    await page.screenshot(path=f'action_{i}_screenshot.png')")
                        code_lines.append(f"                    print('[TEST] Action {i}: 截图已保存到 action_{i}_screenshot.png')")
                        code_lines.append(f"                except Exception as e:")
                        code_lines.append(f"                    print(f'[TEST] Action {i}: 截图失败 - {{e}}')")
                    else:
                        # 生成代码，使用 action_result 中的 text_to_fill
                        action_code = sync_computer_use_service.generate_playwright_code_from_coordinates(
                            action=action_result.get("action", "click"),
                            coordinates=action_result.get("coordinates", {}),
                            text_to_fill=action_result.get("text_to_fill"),
                            is_last=is_last
                        )

                        print(f"   [子进程] 生成的代码:\n{action_code}")

                        for line in action_code.strip().split('\n'):
                            code_lines.append(f"                {line}")

                        # 执行操作以便进行下一步截图分析
                        sync_computer_use_service.execute_action_with_coordinates(page, action_result)

                    # 如果启用了自动验证码检测，在执行操作后也检查验证码
                    if auto_detect_captcha:
                        time.sleep(1)  # 等待页面更新
                        detect_and_handle_captcha(page, api_key, base_url, vl_model)

                code_lines.append("                await asyncio.sleep(3)")
                code_lines.append(f"                print('[TEST] Action {i} completed')")

                collected_codes.extend(code_lines)

            browser.close()
            print(f"   [子进程] Playwright 任务处理完成")
            return collected_codes

    except Exception as e:
        print(f"   [子进程] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise