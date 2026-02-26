"""
Fix captcha recognition to extract just the number
"""
import re

# Read the file
with open('D:/researches/e2etest/backend/app/utils/browser_util.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the captcha_text line to add extraction logic
old_code = '''            captcha_text = response.choices[0].message.content.strip()
            print(f'[BrowserUtil] 识别到验证码: {captcha_text}')'''

new_code = '''            captcha_text_raw = response.choices[0].message.content.strip()
            print(f'[BrowserUtil] 识别到验证码(原始): {captcha_text_raw}')
            
            # 提取数字：如果返回的是 "4*7=28" 或 "4+5=9" 之类的结果，只提取最后的数字
            captcha_text = captcha_text_raw
            # 匹配数学运算结果，如 "4*7=28" -> 提取 28
            match = re.search(r'[=:]\\s*(\\d+)', captcha_text_raw)
            if match:
                captcha_text = match.group(1)
            # 如果只是纯数字，直接使用
            elif captcha_text_raw.isdigit():
                captcha_text = captcha_text_raw
            # 尝试提取所有数字中的最后几个连续数字
            else:
                numbers = re.findall(r'\\d+', captcha_text_raw)
                if numbers:
                    captcha_text = numbers[-1]  # 取最后一个数字序列
            
            print(f'[BrowserUtil] 提取后的验证码: {captcha_text}')'''

content = content.replace(old_code, new_code)

# Write the file back
with open('D:/researches/e2etest/backend/app/utils/browser_util.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Fixed captcha recognition")
