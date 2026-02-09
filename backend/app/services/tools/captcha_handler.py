"""验证码处理工具类提供验证码检测和识别功能"""
import base64


class CaptchaHandler:
    def __init__(self, api_key: str, base_url: str, vl_model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.vl_model = vl_model

    async def detect_and_handle_captcha(self, page):
        """
        检测并处理验证码
        Args:
            page: Playwright page 对象
        Returns:
            是否成功处理验证码
        """
        try:
            captcha_img = page.locator('img[src*="captcha"], img[id*="captcha"], .captcha img').first
            if await captcha_img.is_visible(timeout=3000):
                print('检测到验证码')
                captcha_bytes = await captcha_img.screenshot()
                captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')

                import openai
                client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

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
                print(f'识别到验证码: {captcha_text}')

                captcha_input = page.locator('input[name*="captcha"], input[id*="captcha"], input[placeholder*="验证码"]').first
                if await captcha_input.is_visible(timeout=3000):
                    await captcha_input.fill(captcha_text)
                    print('验证码已填写')
                    return True
        except Exception as e:
            print(f'验证码处理失败: {e}')
        return False
