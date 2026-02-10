"""
浏览器测试工具类
提供截图验证、元素查找等常用功能
"""

import base64
import os
from typing import Optional
from openai import OpenAI


class BrowserUtil:
    """浏览器测试工具类"""

    def __init__(self):
        """初始化，从环境变量读取配置"""
        self.api_key = os.getenv('BAILIAN_API_KEY', '')
        self.base_url = os.getenv('BAILIAN_BASE_URL', '')
        self.vl_model = os.getenv('BAILIAN_VL_MODEL', 'qwen-vl-plus')

    async def verify_by_screenshot(
        self,
        page,
        verification_description: str,
        screenshot_path: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        通过截图使用VLLM验证页面内容

        Args:
            page: Playwright page对象
            verification_description: 验证描述（如"验证页面中存在近期预警趋势图"）
            screenshot_path: 可选，保存截图的路径

        Returns:
            (是否验证通过, VLLM返回的详细结果)
        """
        try:
            # 截图
            screenshot_bytes = await page.screenshot()
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            # 保存截图（如果指定了路径）
            if screenshot_path:
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_bytes)

            # 调用VLLM验证
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            response = client.chat.completions.create(
                model=self.vl_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个网页验证专家。分析截图，判断用户要求的验证内容是否满足。只回答'是'或'否'，并简要说明原因。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"请验证以下内容是否存在或正确显示：{verification_description}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.0,
                max_tokens=200
            )

            verification_result = response.choices[0].message.content.strip()

            # 判断是否通过
            is_passed = '是' in verification_result or 'yes' in verification_result.lower()

            return is_passed, verification_result

        except Exception as e:
            return False, f"验证过程出错: {str(e)}"

    async def assert_by_screenshot(
        self,
        page,
        verification_description: str,
        action_name: str = "验证",
        save_failed_screenshot: bool = True
    ):
        """
        通过截图使用VLLM验证页面内容，并断言结果

        Args:
            page: Playwright page对象
            verification_description: 验证描述
            action_name: 操作名称（用于日志和截图文件名）
            save_failed_screenshot: 验证失败时是否保存截图

        Raises:
            AssertionError: 验证失败时抛出
        """
        print(f"[BrowserUtil] 开始{action_name}: {verification_description}")

        is_passed, result = await self.verify_by_screenshot(
            page,
            verification_description,
            screenshot_path=None
        )

        print(f"[BrowserUtil] {action_name}结果: {result}")

        if not is_passed:
            # 验证失败，保存截图
            if save_failed_screenshot:
                failed_screenshot_path = f"{action_name}_failed.png"
                try:
                    await page.screenshot(path=failed_screenshot_path)
                    print(f"[BrowserUtil] 失败截图已保存: {failed_screenshot_path}")
                except Exception as e:
                    print(f"[BrowserUtil] 保存失败截图出错: {e}")

            raise AssertionError(f"{action_name}失败: {result}")

        print(f"[BrowserUtil] {action_name}通过")

    async def find_element_by_description(
        self,
        page,
        element_description: str
    ) -> tuple[bool, Optional[dict]]:
        """
        通过描述使用VLLM在页面中查找元素

        Args:
            page: Playwright page对象
            element_description: 元素描述（如"登录按钮"）

        Returns:
            (是否找到, 元素信息字典包含x, y坐标等)
        """
        try:
            # 截图
            screenshot_bytes = await page.screenshot()
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            # 调用VLLM查找元素
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            response = client.chat.completions.create(
                model=self.vl_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个网页元素定位专家。分析截图，找到用户描述的元素。返回JSON格式：{'found': true/false, 'x': 123, 'y': 456, 'reasoning': '原因说明'}。坐标是相对于截图的像素坐标。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"请在页面中找到以下元素：{element_description}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.0,
                max_tokens=300
            )

            result_text = response.choices[0].message.content.strip()

            # 解析JSON结果
            import json
            try:
                # 尝试从文本中提取JSON
                if '{' in result_text and '}' in result_text:
                    json_start = result_text.find('{')
                    json_end = result_text.rfind('}') + 1
                    result_json = json.loads(result_text[json_start:json_end])
                else:
                    result_json = json.loads(result_text)

                found = result_json.get('found', False)
                if found:
                    return True, {
                        'x': result_json.get('x', 0),
                        'y': result_json.get('y', 0),
                        'reasoning': result_json.get('reasoning', '')
                    }
                else:
                    return False, None

            except json.JSONDecodeError:
                # JSON解析失败，根据文本内容判断
                found = 'found' in result_text.lower() and 'true' in result_text.lower()
                return found, None

        except Exception as e:
            print(f"[BrowserUtil] 查找元素出错: {e}")
            return False, None

    async def detect_and_solve_captcha(self, page, captcha_selector: str = None) -> bool:
        """
        检测并自动识别填写验证码

        Args:
            page: Playwright page对象
            captcha_selector: 验证码图片的选择器（可选）

        Returns:
            是否成功处理验证码
        """
        try:
            # 如果没有指定选择器，尝试常见选择器
            selectors = [
                captcha_selector,
                'img[id*="captcha"]',
                'img[class*="captcha"]',
                'img[src*="captcha"]',
                '.captcha img',
                '#captcha img',
                'img[alt*="验证码"]'
            ]

            captcha_img = None
            for selector in selectors:
                if not selector:
                    continue
                try:
                    img = page.locator(selector).first
                    if await img.is_visible(timeout=1000):
                        captcha_img = img
                        print(f'[BrowserUtil] 找到验证码图片: {selector}')
                        break
                except:
                    continue

            if not captcha_img:
                return False

            # 截图验证码
            captcha_bytes = await captcha_img.screenshot()
            captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')

            # 调用VLLM识别验证码
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            response = client.chat.completions.create(
                model=self.vl_model,
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
            print(f'[BrowserUtil] 识别到验证码: {captcha_text}')

            # 查找验证码输入框
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

            captcha_input = None
            for selector in input_selectors:
                try:
                    elements = page.locator(selector)
                    if await elements.count() > 0:
                        captcha_input = elements.first
                        if await captcha_input.is_visible(timeout=1000):
                            print(f'[BrowserUtil] 找到验证码输入框: {selector}')
                            break
                except:
                    continue

            if captcha_input and await captcha_input.is_visible(timeout=1000):
                await captcha_input.fill(captcha_text)
                print('[BrowserUtil] 验证码已填写')
                return True

            return False

        except Exception as e:
            print(f'[BrowserUtil] 验证码处理失败: {e}')
            return False

    async def load_storage(self, page, cookies_path: str = 'saved_cookies.json',
                          localstorage_path: str = 'saved_localstorage.json',
                          sessionstorage_path: str = 'saved_sessionstorage.json'):
        """
        加载保存的cookies和storage

        Args:
            page: Playwright page对象
            cookies_path: cookies文件路径
            localstorage_path: localStorage文件路径
            sessionstorage_path: sessionStorage文件路径
        """
        import os

        # 加载cookies
        if os.path.exists(cookies_path):
            try:
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                await page.context.add_cookies(cookies)
                print(f'[BrowserUtil] Cookies已加载: {len(cookies)}个')
            except Exception as e:
                print(f'[BrowserUtil] 加载Cookies失败: {e}')

        # 加载localStorage
        if os.path.exists(localstorage_path):
            try:
                with open(localstorage_path, 'r', encoding='utf-8') as f:
                    ls_data = f.read()
                try:
                    ls_data_obj = json.loads(ls_data)
                    await page.evaluate("""data => {
                        localStorage.clear();
                        for (const key in data) {
                            localStorage.setItem(key, data[key]);
                        }
                    }""", ls_data_obj)
                except json.JSONDecodeError:
                    await page.evaluate("""data => {
                        localStorage.clear();
                        for (const key in data) {
                            localStorage.setItem(key, data[key]);
                        }
                    }""", ls_data)
                print('[BrowserUtil] LocalStorage已加载')
            except Exception as e:
                print(f'[BrowserUtil] 加载LocalStorage失败: {e}')

        # 加载sessionStorage
        if os.path.exists(sessionstorage_path):
            try:
                with open(sessionstorage_path, 'r', encoding='utf-8') as f:
                    ss_data = f.read()
                try:
                    ss_data_obj = json.loads(ss_data)
                    await page.evaluate("""data => {
                        sessionStorage.clear();
                        for (const key in data) {
                            sessionStorage.setItem(key, data[key]);
                        }
                    }""", ss_data_obj)
                except json.JSONDecodeError:
                    await page.evaluate("""data => {
                        sessionStorage.clear();
                        for (const key in data) {
                            sessionStorage.setItem(key, data[key]);
                        }
                    }""", ss_data)
                print('[BrowserUtil] SessionStorage已加载')
            except Exception as e:
                print(f'[BrowserUtil] 加载SessionStorage失败: {e}')

    async def save_storage(self, page, cookies_path: str = 'saved_cookies.json',
                          localstorage_path: str = 'saved_localstorage.json',
                          sessionstorage_path: str = 'saved_sessionstorage.json'):
        """
        保存cookies和storage到文件

        Args:
            page: Playwright page对象
            cookies_path: cookies文件路径
            localstorage_path: localStorage文件路径
            sessionstorage_path: sessionStorage文件路径
        """
        # 保存cookies
        try:
            cookies = await page.context.cookies()
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f'[BrowserUtil] Cookies已保存: {len(cookies)}个')
        except Exception as e:
            print(f'[BrowserUtil] 保存Cookies失败: {e}')

        # 保存localStorage
        try:
            ls_data = await page.evaluate('() => JSON.stringify(localStorage)')
            with open(localstorage_path, 'w', encoding='utf-8') as f:
                f.write(ls_data)
            print('[BrowserUtil] LocalStorage已保存')
        except Exception as e:
            print(f'[BrowserUtil] 保存LocalStorage失败: {e}')

        # 保存sessionStorage
        try:
            ss_data = await page.evaluate('() => JSON.stringify(sessionStorage)')
            with open(sessionstorage_path, 'w', encoding='utf-8') as f:
                f.write(ss_data)
            print('[BrowserUtil] SessionStorage已保存')
        except Exception as e:
            print(f'[BrowserUtil] 保存SessionStorage失败: {e}')


# 全局实例（单例模式）
_browser_util_instance = None


def get_browser_util() -> BrowserUtil:
    """获取BrowserUtil单例实例"""
    global _browser_util_instance
    if _browser_util_instance is None:
        _browser_util_instance = BrowserUtil()
    return _browser_util_instance
