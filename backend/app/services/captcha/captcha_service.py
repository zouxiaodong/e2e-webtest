from typing import Optional, Tuple
from playwright.async_api import Page, Locator
import base64
import re
from ..llm.bailian_client import bailian_client
from ...core.config import settings


class CaptchaService:
    """验证码识别服务 - 自动识别验证码位置"""

    @staticmethod
    async def analyze_page_for_captcha(dom_content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        使用 LLM 分析页面 DOM，自动识别验证码元素和输入框
        Args:
            dom_content: 页面 DOM 内容
        Returns:
            (验证码选择器, 输入框选择器)
        """
        system_prompt = """你是一个前端测试专家。你的任务是分析 HTML 页面内容，找出验证码相关的元素。"""

        prompt = f"""分析以下 HTML 页面，找出验证码图片元素和验证码输入框。

HTML 内容:
{dom_content[:5000]}

请以 JSON 格式返回分析结果，包含以下字段：
- "captcha_selector": 验证码图片元素的 CSS 选择器（例如：#captcha-img, img.captcha）
- "input_selector": 验证码输入框的 CSS 选择器（例如：#captcha-code, input[name="captcha"]）
- "found": 是否找到验证码（true/false）

如果没有找到验证码，将 "found" 设为 false，其他字段设为 null。

只输出 JSON 结果，不要添加任何解释。"""

        try:
            response = await bailian_client.generate_text(prompt, system_prompt)
            
            # 解析 JSON 响应
            import json
            result = json.loads(response)
            
            if result.get("found", False):
                return result.get("captcha_selector"), result.get("input_selector")
            return None, None
            
        except Exception as e:
            print(f"LLM 分析验证码失败: {e}")
            # 如果 LLM 失败，使用传统方法查找
            return CaptchaService._find_captcha_traditional(dom_content)

    @staticmethod
    def _find_captcha_traditional(dom_content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        使用传统方法查找验证码元素（备选方案）
        Args:
            dom_content: 页面 DOM 内容
        Returns:
            (验证码选择器, 输入框选择器)
        """
        captcha_patterns = [
            r'<img[^>]*(?:captcha|验证码|yzm)[^>]*(?:id=["\']([^"\']+)["\']|class=["\']([^"\']+)["\'])',
            r'<img[^>]*src=["\'][^"\']*(?:captcha|验证码|yzm)[^"\']*["\']',
        ]
        
        input_patterns = [
            r'<input[^>]*(?:captcha|验证码|code)[^>]*(?:id=["\']([^"\']+)["\']|name=["\']([^"\']+)["\'])',
        ]
        
        captcha_selector = None
        input_selector = None
        
        # 查找验证码图片
        for pattern in captcha_patterns:
            match = re.search(pattern, dom_content, re.IGNORECASE)
            if match:
                id_attr = match.group(1) if len(match.groups()) > 0 and match.group(1) else None
                class_attr = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                
                if id_attr:
                    captcha_selector = f"#{id_attr}"
                elif class_attr:
                    captcha_selector = f".{class_attr.split()[0]}"
                else:
                    captcha_selector = 'img[src*="captcha"], img[src*="验证码"]'
                break
        
        # 查找验证码输入框
        for pattern in input_patterns:
            match = re.search(pattern, dom_content, re.IGNORECASE)
            if match:
                id_attr = match.group(1) if len(match.groups()) > 0 and match.group(1) else None
                name_attr = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                
                if id_attr:
                    input_selector = f"#{id_attr}"
                elif name_attr:
                    input_selector = f'input[name="{name_attr}"]'
                else:
                    input_selector = 'input[name*="captcha"], input[id*="captcha"]'
                break
        
        return captcha_selector, input_selector

    @staticmethod
    async def screenshot_captcha(
        page: Page,
        selector: str,
        timeout: int = 5000
    ) -> Optional[str]:
        """
        截取验证码图片
        Args:
            page: Playwright页面对象
            selector: 验证码元素选择器
            timeout: 超时时间
        Returns:
            base64编码的图片
        """
        try:
            # 等待验证码元素出现
            captcha_element = page.locator(selector)
            await captcha_element.wait_for(state="visible", timeout=timeout)

            # 截取验证码元素
            screenshot_bytes = await captcha_element.screenshot()

            # 转换为base64
            base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
            return base64_image
        except Exception as e:
            print(f"截取验证码失败: {e}")
            return None

    @staticmethod
    async def recognize_captcha(image_base64: str) -> str:
        """
        识别验证码
        Args:
            image_base64: base64编码的验证码图片
        Returns:
            识别的验证码内容
        """
        if not image_base64:
            return ""

        captcha_text = await bailian_client.recognize_captcha(image_base64)
        return captcha_text

    @staticmethod
    async def auto_detect_and_handle_captcha(
        page: Page,
        max_retries: int = 3
    ) -> Tuple[bool, str]:
        """
        自动检测页面中的验证码并处理
        Args:
            page: Playwright页面对象
            max_retries: 最大重试次数
        Returns:
            (是否成功, 验证码内容)
        """
        print("正在分析页面，自动检测验证码...")
        
        # 获取页面 DOM
        dom_content = await page.content()
        
        # 使用 LLM 分析页面，自动识别验证码位置
        captcha_selector, input_selector = await CaptchaService.analyze_page_for_captcha(dom_content)
        
        if not captcha_selector:
            print("未检测到验证码")
            return True, ""
        
        print(f"自动检测到验证码: 图片选择器={captcha_selector}, 输入框选择器={input_selector}")
        
        # 处理验证码
        for attempt in range(max_retries):
            # 截取验证码
            captcha_image = await CaptchaService.screenshot_captcha(page, captcha_selector)
            if not captcha_image:
                print(f"尝试 {attempt + 1}: 无法截取验证码")
                continue

            # 识别验证码
            captcha_text = await CaptchaService.recognize_captcha(captcha_image)
            if not captcha_text or captcha_text == "CAPTCHA_NOT_FOUND":
                print(f"尝试 {attempt + 1}: 无法识别验证码")
                continue

            print(f"尝试 {attempt + 1}: 识别到验证码: {captcha_text}")

            # 填入验证码
            try:
                if input_selector:
                    await page.fill(input_selector, captcha_text)
                else:
                    # 如果没有找到输入框选择器，尝试找到第一个可见的输入框
                    await page.locator('input:visible').first.fill(captcha_text)
                return True, captcha_text
            except Exception as e:
                print(f"尝试 {attempt + 1}: 填入验证码失败: {e}")
                continue

        print(f"验证码处理失败，已重试 {max_retries} 次")
        return False, ""

    @staticmethod
    async def handle_captcha(
        page: Page,
        captcha_selector: str,
        input_selector: str,
        max_retries: int = 3
    ) -> bool:
        """
        自动处理验证码（使用指定的选择器）
        Args:
            page: Playwright页面对象
            captcha_selector: 验证码元素选择器
            input_selector: 验证码输入框选择器
            max_retries: 最大重试次数
        Returns:
            是否成功处理验证码
        """
        for attempt in range(max_retries):
            # 截取验证码
            captcha_image = await CaptchaService.screenshot_captcha(page, captcha_selector)
            if not captcha_image:
                print(f"尝试 {attempt + 1}: 无法截取验证码")
                continue

            # 识别验证码
            captcha_text = await CaptchaService.recognize_captcha(captcha_image)
            if not captcha_text or captcha_text == "CAPTCHA_NOT_FOUND":
                print(f"尝试 {attempt + 1}: 无法识别验证码")
                continue

            print(f"尝试 {attempt + 1}: 识别到验证码: {captcha_text}")

            # 填入验证码
            try:
                await page.fill(input_selector, captcha_text)
                return True
            except Exception as e:
                print(f"尝试 {attempt + 1}: 填入验证码失败: {e}")
                continue

        print(f"验证码处理失败，已重试 {max_retries} 次")
        return False


# 创建全局实例
captcha_service = CaptchaService()