import pytest
from playwright.async_api import async_playwright, expect
import asyncio
import traceback

@pytest.mark.asyncio
async def test_generated():
    print("[TEST] Test started")
    browser = None
    try:
        async with async_playwright() as p:
            print("[TEST] Launching browser")
            # Launch browser
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            print("[TEST] Browser launched")

            # Action 0: Navigate to target page
            print("[TEST] Navigating to: https://xas.stelguard.com/")
            await page.goto("https://xas.stelguard.com/")
            print("[TEST] Page loaded")
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state("networkidle")
            print("[TEST] Page network idle")
            
            # Additional wait to ensure page is visible
            await asyncio.sleep(3)
            print("[TEST] Initial wait completed")
            
            try:
                # Execute all actions
                # 等待页面加载
                await page.wait_for_timeout(2000)
                # 自动检测并处理验证码
                try:
                    # 检查是否存在验证码图片
                    captcha_img = page.locator('img[src*="captcha"], img[id*="captcha"], .captcha img').first
                    if await captcha_img.is_visible(timeout=3000):
                        print('检测到验证码')
                        # 截取验证码图片
                        captcha_bytes = await captcha_img.screenshot()
                        import base64
                        captcha_base64 = base64.b64encode(captcha_bytes).decode('utf-8')

                        # 调用LLM识别验证码
                        import openai
                        client = openai.OpenAI(api_key='sk-e36a99bd871148cd94827fdf18a9dc62', base_url='https://dashscope.aliyuncs.com/compatible-mode/v1')

                        response = client.chat.completions.create(
                            model='qwen-vl-plus',
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

                        # 查找验证码输入框并填写
                        captcha_input = page.locator('input[name*="captcha"], input[id*="captcha"], input[placeholder*="验证码"]').first
                        if await captcha_input.is_visible(timeout=3000):
                            await captcha_input.fill(captcha_text)
                            print('验证码已填写')
                except Exception as e:
                    print(f'验证码处理失败: {e}')
                    pass  # 没有验证码或处理失败
                # Action 1: 定位并在'username'输入框中输入'admin'
                print('[TEST] Action 1 started')
                username_input = page.locator("input[type='text']").first
                await username_input.fill("admin")
                await page.wait_for_timeout(2000)
                await asyncio.sleep(3)
                print('[TEST] Action 1 completed')
                # Action 2: 定位并在'password'输入框中输入'PGzVdj8WnN'
                print('[TEST] Action 2 started')
                password_input = page.locator("input[type='password']").first
                await password_input.fill("PGzVdj8WnN")
                await page.wait_for_timeout(2000)
                await asyncio.sleep(3)
                print('[TEST] Action 2 completed')
                # Action 5: 点击'登录'按钮提交凭据
                print('[TEST] Action 5 started')
                login_button = page.locator("button:has-text('登录')")
                await login_button.click()
                await page.wait_for_timeout(2000)
                await asyncio.sleep(3)
                print('[TEST] Action 5 completed')
                # Action 6: 通过期望页面跳转到登录后首页（如包含'首页'或'/dashboard'等典型路径）或出现登录成功提示来验证登录成功
                print('[TEST] Action 6 started')
                await expect(page).to_have_url("**/dashboard**", timeout=10000)
                await expect(page.get_by_text("首页")).to_be_visible(timeout=10000)
                await asyncio.sleep(3)
                print('[TEST] Action 6 completed')
            except Exception as e:
                print(f"[TEST] ERROR during actions: {e}")
                print(f"[TEST] Traceback: {traceback.format_exc()}")
                # Take screenshot on error
                try:
                    await page.screenshot(path="error_screenshot.png")
                    print("[TEST] Screenshot saved to error_screenshot.png")
                except:
                    pass
                raise

            # Final wait before closing
            print("[TEST] Final wait before closing")
            await asyncio.sleep(5)
            
            # Close browser
            print("[TEST] Closing browser")
            await browser.close()
            print("[TEST] Test completed")
    except Exception as e:
        print(f"[TEST] FATAL ERROR: {e}")
        print(f"[TEST] Traceback: {traceback.format_exc()}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
