"""
Fix captcha recognition in captcha_handler.py
"""
import re

# Read the file
with open('D:/researches/e2etest/backend/app/services/tools/captcha_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace
old_code = '''            captcha_text = response.choices[0].message.content.strip()
            print(f'识别到验证码: {captcha_text}')'''

new_code = '''            captcha_text_raw = response.choices[0].message.content.strip()
            print(f'识别到验证码(原始): {captcha_text_raw}')
            
            # 提取数字
            captcha_text = captcha_text_raw
            match = re.search(r'[=:]\\s*(\\d+)', captcha_text_raw)
            if match:
                captcha_text = match.group(1)
            elif captcha_text_raw.isdigit():
                captcha_text = captcha_text_raw
            else:
                numbers = re.findall(r'\\d+', captcha_text_raw)
                if numbers:
                    captcha_text = numbers[-1]
            
            print(f'提取后的验证码: {captcha_text}')'''

content = content.replace(old_code, new_code)

# Write the file back
with open('D:/researches/e2etest/backend/app/services/tools/captcha_handler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Fixed captcha_handler.py")
