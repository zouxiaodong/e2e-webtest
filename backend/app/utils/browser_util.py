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


# 全局实例（单例模式）
_browser_util_instance = None


def get_browser_util() -> BrowserUtil:
    """获取BrowserUtil单例实例"""
    global _browser_util_instance
    if _browser_util_instance is None:
        _browser_util_instance = BrowserUtil()
    return _browser_util_instance
