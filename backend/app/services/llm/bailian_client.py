from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional, List, Dict, Any
import time
import json
from ...core.config import settings
from ...core.llm_logger import llm_logger


class BailianClient:
    """百练平台客户端"""

    def __init__(self):
        self.api_key = settings.BAILIAN_API_KEY
        self.base_url = settings.BAILIAN_BASE_URL
        self.llm_model = settings.BAILIAN_LLM_MODEL
        self.vl_model = settings.BAILIAN_VL_MODEL

        # 创建 LangChain ChatOpenAI 实例
        self.chat_llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.llm_model,
            temperature=0.0,
        )

        # 创建原生 OpenAI 客户端用于多模态
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _convert_messages_to_dict(self, messages: List) -> List[Dict]:
        """将LangChain消息转换为字典格式用于日志记录"""
        result = []
        for msg in messages:
            if hasattr(msg, 'type'):
                # LangChain消息对象
                result.append({
                    'role': msg.type,
                    'content': msg.content
                })
            else:
                # 已经是字典格式
                result.append(msg)
        return result

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成文本
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
        Returns:
            生成的文本
        """
        # 构建消息
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # 记录请求
        messages_dict = self._convert_messages_to_dict(messages)
        llm_logger.log_request(
            model=self.llm_model,
            messages=messages_dict,
            method="generate_text"
        )

        # 调用LLM
        start_time = time.time()
        try:
            response = await self.chat_llm.ainvoke(messages)
            duration_ms = (time.time() - start_time) * 1000

            # 记录响应
            llm_logger.log_response(
                model=self.llm_model,
                response=response,
                duration_ms=duration_ms
            )

            return response.content
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            llm_logger.log_error(self.llm_model, e)
            raise

    async def generate_actions(self, user_query: str, target_url: str) -> List[str]:
        """
        将用户查询转换为操作步骤
        Args:
            user_query: 用户自然语言查询
            target_url: 目标URL
        Returns:
            操作步骤列表
        """
        system_prompt = """你是一个端到端测试专家。你的目标是将通用的业务端到端测试任务分解为更小的、明确定义的操作。
这些操作将用于编写实际执行测试的代码。"""

        prompt = f"""将以下输入转换为包含"actions"键和原子步骤列表作为值的JSON字典。
这些步骤将用于生成端到端测试脚本。
每个操作都应该是一个清晰的、原子步骤，可以转换为代码。
尽量生成完成用户测试意图所需的最少操作数量。
第一个操作必须始终是导航到目标URL。
最后一个操作应该始终是断言测试的预期结果。
**重要**：如果用户查询中包含了具体的值（如用户名'admin'、密码'PGzVdj8WnN'等），必须在操作步骤中使用这些具体值，不要使用占位符或描述性文字。
不要在这个JSON结构之外添加任何额外的字符、注释或解释。只输出JSON结果。

示例:
输入: "验证用户在登录页输入正确的用户名'admin'、密码'PGzVdj8WnN'及有效验证码后，点击'登录'按钮可成功登录系统。"
输出: {{
    "actions": [
        "通过URL导航到登录页面。",
        "定位并在'username'输入框中输入'admin'",
        "在'password'输入框中输入'PGzVdj8WnN'",
        "截取验证码图片并调用VL模型识别",
        "在'captcha'输入框中填写识别结果",
        "点击'登录'按钮提交凭据",
        "验证页面跳转至登录后首页或显示登录成功状态"
    ]
}}

输入: "测试将商品添加到购物车。"
输出: {{
    "actions": [
        "通过URL导航到商品列表页面。",
        "点击列表中的第一个商品以打开商品详情",
        "点击'Add to Cart'按钮添加选定的商品",
        "期望选定的商品名称出现在购物车侧边栏或页面中"
    ]
}}

目标URL: {target_url}
用户查询: {user_query}
输出:"""

        response = await self.generate_text(prompt, system_prompt)

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

    async def generate_test_name(self, user_query: str, actions: List[str]) -> str:
        """
        生成测试用例名称
        Args:
            user_query: 用户查询
            actions: 操作步骤
        Returns:
            测试用例名称
        """
        prompt = f"""你的任务是根据用户测试描述和执行测试所需的操作来创建测试用例的名称。
测试名称应该是一个有效的函数名称。
只输出测试名称，不要输出其他任何内容。

用户查询: {user_query}
操作: {', '.join(actions[:3])}..."""

        test_name = await self.generate_text(prompt)
        # 清理名称使其成为有效的Python函数名
        test_name = test_name.strip().replace(" ", "_").replace("-", "_")
        if not test_name[0].isalpha():
            test_name = "test_" + test_name[1:]
        return test_name

    async def recognize_captcha(self, image_base64: str) -> str:
        """
        识别验证码
        Args:
            image_base64: base64编码的图片
        Returns:
            识别的验证码内容
        """
        system_prompt = """你是一个验证码识别专家。你的任务是识别图片中的验证码内容。

重要说明：
1. 如果验证码是简单的字符或数字（如 "ABC123"），直接返回这些字符
2. 如果验证码是数学运算（如 "2+3=?" 或 "5-1="），请计算并返回运算结果（如 "5" 或 "4"）
3. 只返回最终的验证码值或计算结果，不要添加任何解释或额外内容
4. 如果图片中没有验证码，返回 'CAPTCHA_NOT_FOUND'

示例：
- 图片显示 "7+8=" -> 返回 "15"
- 图片显示 "ABC" -> 返回 "ABC"
- 图片显示 "12-5=?" -> 返回 "7"
"""

        prompt = f"""请识别这张图片中的验证码内容。

如果是数学运算题（如加减乘除），请计算并返回结果。
如果是普通字符验证码，直接返回字符。
只返回最终结果，不要添加任何解释。"""

        # 构建消息用于日志
        messages_dict = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"[Image: {len(image_base64)} chars] {prompt}"}
        ]

        # 记录请求
        llm_logger.log_request(
            model=self.vl_model,
            messages=messages_dict,
            method="recognize_captcha",
            max_tokens=50
        )

        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.vl_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.0,
                max_tokens=50
            )
            duration_ms = (time.time() - start_time) * 1000

            # 记录响应
            llm_logger.log_response(
                model=self.vl_model,
                response=response,
                duration_ms=duration_ms
            )

            captcha_text = response.choices[0].message.content.strip()
            return captcha_text
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            llm_logger.log_error(self.vl_model, e)
            print(f"验证码识别错误: {e}")
            return ""

    async def generate_text_with_image(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        image_base64: str = None,
        max_tokens: int = 2000
    ) -> str:
        """
        使用 VL 模型生成文本（支持图片输入）
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            image_base64: base64编码的图片
            max_tokens: 最大token数
        Returns:
            生成的文本
        """
        # 构建消息用于日志
        messages_dict = [
            {"role": "system", "content": system_prompt if system_prompt else ""},
            {"role": "user", "content": f"[Image: {len(image_base64) if image_base64 else 0} chars] {prompt}"}
        ]

        # 记录请求
        llm_logger.log_request(
            model=self.vl_model,
            messages=messages_dict,
            method="generate_text_with_image",
            max_tokens=max_tokens
        )

        try:
            start_time = time.time()
            
            # 构建消息
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            user_content = [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            if image_base64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                })
            
            messages.append({
                "role": "user",
                "content": user_content
            })

            response = self.client.chat.completions.create(
                model=self.vl_model,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens
            )
            duration_ms = (time.time() - start_time) * 1000

            # 记录响应
            llm_logger.log_response(
                model=self.vl_model,
                response=response,
                duration_ms=duration_ms
            )

            return response.choices[0].message.content
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            llm_logger.log_error(self.vl_model, e)
            raise


# 创建全局实例
bailian_client = BailianClient()