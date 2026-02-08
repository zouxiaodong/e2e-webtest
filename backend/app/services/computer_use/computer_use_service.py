"""
Computer-Use 服务
基于截图和坐标定位的自动化测试方案
"""

import base64
import json
import re
from typing import Dict, Any, List, Tuple, Optional
from playwright.async_api import Page
from ...core.llm_logger import llm_logger
import os


class ComputerUseService:
    """Computer-Use 服务，使用截图 + 坐标定位"""

    def __init__(self):
        self.vl_model = "qwen-vl-plus"  # 使用 VL 模型
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    async def analyze_page_and_generate_action(
        self,
        page: Page,
        action_description: str,
        previous_actions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析页面截图并生成操作
        Args:
            page: Playwright page 对象（支持同步和异步）
            action_description: 操作描述（如"点击登录按钮"）
            previous_actions: 之前的操作列表
        Returns:
            包含操作类型和坐标的字典
        """
        # 检测 page 对象是同步还是异步
        import inspect
        is_async = inspect.iscoroutinefunction(getattr(page, 'screenshot', lambda: None))

        # 1. 截取页面截图
        if is_async:
            screenshot_bytes = await page.screenshot(full_page=True)
        else:
            screenshot_bytes = page.screenshot(full_page=True)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        # 2. 获取页面尺寸
        if is_async:
            viewport = await page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
        else:
            viewport = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")

        # 3. 构建 prompt
        system_prompt = """你是一个网页自动化助手。你的任务是分析网页截图，识别用户指定的元素，并返回精确的坐标位置。

重要规则：
1. 坐标系以截图左上角为原点 (0, 0)，右下角为 (width, height)
2. 返回的坐标应该是元素的中心点
3. 如果元素是输入框，还需要识别它的类型（text、password、email 等）
4. 如果找不到指定元素，返回 null

输出格式必须是 JSON：
{
    "element_found": true/false,
    "action": "click" | "fill" | "scroll" | "wait",
    "coordinates": {"x": 123, "y": 456},
    "element_type": "button" | "input" | "link" | "other",
    "input_type": "text" | "password" | "email" | null,
    "text_to_fill": "要输入的文本" | null,
    "confidence": 0.95,
    "reasoning": "元素位于页面中央，红色按钮上有'登录'文字"
}"""

        user_prompt = f"""请分析以下网页截图，找到并定位这个元素："{action_description}"

页面尺寸: {viewport['width']} x {viewport['height']} 像素

请返回 JSON 格式的结果，包含元素的精确坐标。"""

        # 4. 调用 VL 模型
        import openai
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            llm_logger.log_request(
                model=self.vl_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]}
                ]
            )

            import time
            start_time = time.time()

            response = client.chat.completions.create(
                model=self.vl_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]}
                ],
                temperature=0.0,
                max_tokens=500
            )

            duration_ms = (time.time() - start_time) * 1000
            llm_logger.log_response(
                model=self.vl_model,
                response=response,
                duration_ms=duration_ms
            )

            # 5. 解析响应
            content = response.choices[0].message.content.strip()

            # 尝试提取 JSON
            try:
                # 如果响应包含 ```json 代码块
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content

                result = json.loads(json_str)
                return result
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}")
                print(f"原始响应: {content}")
                return {
                    "element_found": False,
                    "error": f"JSON 解析错误: {e}",
                    "raw_response": content
                }

        except Exception as e:
            print(f"VL 模型调用错误: {e}")
            llm_logger.log_error(self.vl_model, e)
            return {
                "element_found": False,
                "error": str(e)
            }

    async def execute_action_with_coordinates(
        self,
        page: Page,
        action_result: Dict[str, Any],
        text_to_fill: str = None
    ) -> bool:
        """
        根据坐标执行操作
        Args:
            page: Playwright page 对象（支持同步和异步）
            action_result: analyze_page_and_generate_action 返回的结果
            text_to_fill: 如果是 fill 操作，要填充的文本
        Returns:
            是否执行成功
        """
        if not action_result.get("element_found"):
            print(f"元素未找到: {action_result.get('reasoning', '未知原因')}")
            return False

        action = action_result.get("action", "click")
        coordinates = action_result.get("coordinates", {})
        x = coordinates.get("x", 0)
        y = coordinates.get("y", 0)

        # 检测 page 对象是同步还是异步
        import inspect
        is_async = inspect.iscoroutinefunction(getattr(page.mouse, 'click', lambda: None))

        try:
            if action == "click":
                # 在指定坐标点击
                if is_async:
                    await page.mouse.click(x, y)
                else:
                    page.mouse.click(x, y)
                print(f"✅ 在坐标 ({x}, {y}) 点击")
                return True

            elif action == "fill":
                # 先点击，再填充文本
                if is_async:
                    await page.mouse.click(x, y)
                    await page.keyboard.press("Control+a")  # 全选
                    await page.keyboard.press("Delete")  # 删除
                    if text_to_fill:
                        await page.keyboard.type(text_to_fill)
                else:
                    page.mouse.click(x, y)
                    page.keyboard.press("Control+a")  # 全选
                    page.keyboard.press("Delete")  # 删除
                    if text_to_fill:
                        page.keyboard.type(text_to_fill)
                print(f"✅ 在坐标 ({x}, {y}) 填充文本: {text_to_fill}")
                return True

            elif action == "scroll":
                if is_async:
                    await page.mouse.wheel(x, y, delta_x=0, delta_y=300)
                else:
                    page.mouse.wheel(x, y, delta_x=0, delta_y=300)
                print(f"✅ 在坐标 ({x}, {y}) 滚动")
                return True

            elif action == "wait":
                print(f"⏳ 等待")
                if is_async:
                    await page.wait_for_timeout(2000)
                else:
                    import time
                    time.sleep(2)
                return True

            else:
                print(f"❌ 未知的操作类型: {action}")
                return False

        except Exception as e:
            print(f"❌ 执行操作失败: {e}")
            return False

    def generate_playwright_code_from_coordinates(
        self,
        action: str,
        coordinates: Dict[str, int],
        text_to_fill: str = None,
        is_last: bool = False
    ) -> str:
        """
        根据坐标生成 Playwright 代码
        Args:
            action: 操作类型 (click, fill, scroll)
            coordinates: 坐标 {"x": 123, "y": 456}
            text_to_fill: 要填充的文本
            is_last: 是否是最后一个操作
        Returns:
            Playwright 代码字符串
        """
        x = coordinates.get("x", 0)
        y = coordinates.get("y", 0)

        code_lines = []

        if action == "click":
            code_lines.append(f"# 在坐标 ({x}, {y}) 点击")
            code_lines.append(f"await page.mouse.click({x}, {y})")
            code_lines.append("await page.wait_for_timeout(2000)")

        elif action == "fill":
            code_lines.append(f"# 在坐标 ({x}, {y}) 填充文本")
            code_lines.append(f"await page.mouse.click({x}, {y})")
            code_lines.append("await page.keyboard.press('Control+a')")
            code_lines.append("await page.keyboard.press('Delete')")
            if text_to_fill:
                escaped_text = text_to_fill.replace("'", "\\'")
                code_lines.append(f"await page.keyboard.type('{escaped_text}')")
            code_lines.append("await page.wait_for_timeout(2000)")

        elif action == "scroll":
            code_lines.append(f"# 在坐标 ({x}, {y}) 滚动")
            code_lines.append(f"await page.mouse.wheel({x}, {y}, delta_x=0, delta_y=300)")
            code_lines.append("await page.wait_for_timeout(2000)")

        if is_last and action != "wait":
            code_lines.append("# 验证操作成功")
            code_lines.append("await page.wait_for_load_state('networkidle')")

        return "\n".join(code_lines)


class SyncComputerUseService:
    """同步版本的 Computer-Use 服务，用于在单独进程中运行"""

    def __init__(self):
        self.vl_model = "qwen-vl-plus"
        from ...core.config import settings
        self.api_key = settings.BAILIAN_API_KEY
        self.base_url = settings.BAILIAN_BASE_URL

    def analyze_page_and_generate_action(
        self,
        page,
        action_description: str,
        previous_actions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析页面截图并生成操作（同步版本）
        Args:
            page: Playwright page 对象（同步）
            action_description: 操作描述（如"点击登录按钮"）
            previous_actions: 之前的操作列表
        Returns:
            包含操作类型和坐标的字典
        """
        # 1. 截取页面截图
        screenshot_bytes = page.screenshot(full_page=True)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        # 2. 获取页面尺寸
        viewport = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")

        # 3. 从操作描述中提取要输入的文本
        text_to_fill = None
        if "输入" in action_description or "填写" in action_description:
            # 尝试提取引号中的文本
            match = re.search(r"['\"]([^'\"]+)['\"]", action_description)
            if match:
                text_to_fill = match.group(1)

        # 4. 构建 prompt
        system_prompt = """你是一个网页自动化助手。你的任务是分析网页截图，识别用户指定的元素，并返回精确的坐标位置。

重要规则：
1. 坐标系以截图左上角为原点 (0, 0)，右下角为 (width, height)
2. 返回的坐标应该是元素的中心点
3. 如果元素是输入框，还需要识别它的类型（text、password、email 等）
4. 如果找不到指定元素，返回 null
5. 如果操作涉及输入文本，必须在 JSON 中包含 text_to_fill 字段

输出格式必须是 JSON：
{
    "element_found": true/false,
    "action": "click" | "fill" | "scroll" | "wait",
    "coordinates": {"x": 123, "y": 456},
    "element_type": "button" | "input" | "link" | "other",
    "input_type": "text" | "password" | "email" | null,
    "text_to_fill": "要输入的文本" | null,
    "confidence": 0.95,
    "reasoning": "元素位于页面中央，红色按钮上有'登录'文字"
}"""

        user_prompt = f"""请分析以下网页截图，找到并定位这个元素："{action_description}"

页面尺寸: {viewport['width']} x {viewport['height']} 像素

请返回 JSON 格式的结果，包含元素的精确坐标。"""

        # 5. 调用 VL 模型
        import openai
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            llm_logger.log_request(
                model=self.vl_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]}
                ]
            )

            import time
            start_time = time.time()

            response = client.chat.completions.create(
                model=self.vl_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]}
                ],
                temperature=0.0,
                max_tokens=500
            )

            duration_ms = (time.time() - start_time) * 1000
            llm_logger.log_response(
                model=self.vl_model,
                response=response,
                duration_ms=duration_ms
            )

            # 6. 解析响应
            content = response.choices[0].message.content.strip()

            # 尝试提取 JSON
            try:
                # 如果响应包含 ```json 代码块
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content

                result = json.loads(json_str)
                
                # 如果 VL 模型没有返回 text_to_fill，但我们从操作描述中提取到了，就使用提取的值
                if "text_to_fill" not in result or result.get("text_to_fill") is None:
                    if text_to_fill:
                        result["text_to_fill"] = text_to_fill
                
                return result
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}")
                print(f"原始响应: {content}")
                return {
                    "element_found": False,
                    "error": f"JSON 解析错误: {e}",
                    "raw_response": content
                }

        except Exception as e:
            print(f"VL 模型调用错误: {e}")
            llm_logger.log_error(self.vl_model, e)
            return {
                "element_found": False,
                "error": str(e)
            }

    def execute_action_with_coordinates(
        self,
        page,
        action_result: Dict[str, Any],
        text_to_fill: str = None
    ) -> bool:
        """
        根据坐标执行操作（同步版本）
        Args:
            page: Playwright page 对象（同步）
            action_result: analyze_page_and_generate_action 返回的结果
            text_to_fill: 如果是 fill 操作，要填充的文本
        Returns:
            是否执行成功
        """
        if not action_result.get("element_found"):
            print(f"元素未找到: {action_result.get('reasoning', '未知原因')}")
            return False

        action = action_result.get("action", "click")
        coordinates = action_result.get("coordinates", {})
        x = coordinates.get("x", 0)
        y = coordinates.get("y", 0)

        # 如果 action_result 中有 text_to_fill，使用它；否则使用参数传入的 text_to_fill
        fill_text = action_result.get("text_to_fill") or text_to_fill

        try:
            if action == "click":
                # 在指定坐标点击
                page.mouse.click(x, y)
                print(f"✅ 在坐标 ({x}, {y}) 点击")
                return True

            elif action == "fill":
                # 先点击，再填充文本
                page.mouse.click(x, y)
                page.keyboard.press("Control+a")  # 全选
                page.keyboard.press("Delete")  # 删除
                if fill_text:
                    page.keyboard.type(fill_text)
                print(f"✅ 在坐标 ({x}, {y}) 填充文本: {fill_text}")
                return True

            elif action == "scroll":
                page.mouse.wheel(x, y, delta_x=0, delta_y=300)
                print(f"✅ 在坐标 ({x}, {y}) 滚动")
                return True

            elif action == "wait":
                print(f"⏳ 等待")
                import time
                time.sleep(2)
                return True

            else:
                print(f"❌ 未知的操作类型: {action}")
                return False

        except Exception as e:
            print(f"❌ 执行操作失败: {e}")
            return False

    def generate_playwright_code_from_coordinates(
        self,
        action: str,
        coordinates: Dict[str, int],
        text_to_fill: str = None,
        is_last: bool = False
    ) -> str:
        """
        根据坐标生成 Playwright 代码
        Args:
            action: 操作类型 (click, fill, scroll)
            coordinates: 坐标 {"x": 123, "y": 456}
            text_to_fill: 要填充的文本
            is_last: 是否是最后一个操作
        Returns:
            Playwright 代码字符串
        """
        x = coordinates.get("x", 0)
        y = coordinates.get("y", 0)

        code_lines = []

        if action == "click":
            code_lines.append(f"# 在坐标 ({x}, {y}) 点击")
            code_lines.append(f"await page.mouse.click({x}, {y})")
            code_lines.append("await page.wait_for_timeout(2000)")

        elif action == "fill":
            code_lines.append(f"# 在坐标 ({x}, {y}) 填充文本")
            code_lines.append(f"await page.mouse.click({x}, {y})")
            code_lines.append("await page.keyboard.press('Control+a')")
            code_lines.append("await page.keyboard.press('Delete')")
            if text_to_fill:
                escaped_text = text_to_fill.replace("'", "\\'")
                code_lines.append(f"await page.keyboard.type('{escaped_text}')")
            code_lines.append("await page.wait_for_timeout(2000)")

        elif action == "scroll":
            code_lines.append(f"# 在坐标 ({x}, {y}) 滚动")
            code_lines.append(f"await page.mouse.wheel({x}, {y}, delta_x=0, delta_y=300)")
            code_lines.append("await page.wait_for_timeout(2000)")

        if is_last and action != "wait":
            code_lines.append("# 验证操作成功")
            code_lines.append("await page.wait_for_load_state('networkidle')")

        return "\n".join(code_lines)


# 全局实例
computer_use_service = ComputerUseService()
sync_computer_use_service = SyncComputerUseService()