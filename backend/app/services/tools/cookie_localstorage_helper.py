"""Cookie 和 LocalStorage 辅助工具类"""
import json
import os


class CookieLocalStorageHelper:
    @staticmethod
    async def save_cookies(page, filepath="saved_cookies.json"):
        """保存 cookies 到文件"""
        cookies = await page.context.cookies()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f'Cookies 已保存到 {filepath}')

    @staticmethod
    async def load_cookies(page, filepath="saved_cookies.json"):
        """从文件加载 cookies"""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await page.context.add_cookies(cookies)
            print(f'Cookies 已从 {filepath} 加载')
        else:
            print(f'Cookie 文件 {filepath} 不存在，跳过加载')

    @staticmethod
    async def save_localstorage(page, filepath="saved_localstorage.json"):
        """保存 localStorage 到文件"""
        ls_data = await page.evaluate("() => JSON.stringify(localStorage)")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(ls_data)
        print(f'LocalStorage 已保存到 {filepath}')

    @staticmethod
    async def load_localstorage(page, filepath="saved_localstorage.json"):
        """从文件加载 localStorage"""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                ls_data = f.read()
            await page.evaluate(f"() => {{ localStorage.clear(); const data = {ls_data}; for (const key in data) {{ localStorage.setItem(key, data[key]); }} }}")
            print(f'LocalStorage 已从 {filepath} 加载')
        else:
            print(f'LocalStorage 文件 {filepath} 不存在，跳过加载')
