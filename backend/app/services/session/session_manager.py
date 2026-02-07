from typing import Dict, Any, Optional
from playwright.async_api import Page, BrowserContext
import json
from datetime import datetime, timedelta


class SessionManager:
    """会话管理服务 - 用于保存和恢复浏览器会话"""
    
    @staticmethod
    async def save_session(page: Page, name: str, description: str = "", save_all: bool = True) -> Dict[str, Any]:
        """
        保存当前页面的会话状态
        Args:
            page: Playwright 页面对象
            name: 会话名称
            description: 会话描述
            save_all: 是否保存所有数据（cookies、localStorage、sessionStorage）
        Returns:
            会话数据字典
        """
        context = page.context
        
        session_data = {
            "name": name,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "url": page.url,
            "cookies": None,
            "local_storage": None,
            "session_storage": None
        }
        
        # 保存 cookies
        if save_all:
            cookies = await context.cookies()
            session_data["cookies"] = cookies
        
        # 保存 localStorage
        if save_all:
            try:
                local_storage = await page.evaluate("() => { return JSON.stringify(localStorage); }")
                session_data["local_storage"] = json.loads(local_storage) if local_storage else {}
            except Exception as e:
                print(f"保存 localStorage 失败: {e}")
                session_data["local_storage"] = {}
        
        # 保存 sessionStorage
        if save_all:
            try:
                session_storage = await page.evaluate("() => { return JSON.stringify(sessionStorage); }")
                session_data["session_storage"] = json.loads(session_storage) if session_storage else {}
            except Exception as e:
                print(f"保存 sessionStorage 失败: {e}")
                session_data["session_storage"] = {}
        
        return session_data
    
    @staticmethod
    async def restore_session(page: Page, session_data: Dict[str, Any]) -> bool:
        """
        恢复会话状态到页面
        Args:
            page: Playwright 页面对象
            session_data: 会话数据
        Returns:
            是否成功
        """
        try:
            context = page.context
            
            # 恢复 cookies
            if session_data.get("cookies"):
                await context.add_cookies(session_data["cookies"])
            
            # 恢复 localStorage
            if session_data.get("local_storage"):
                local_storage_data = session_data["local_storage"]
                if local_storage_data:
                    await page.evaluate(f"(data) => {{ localStorage.clear(); Object.entries(data).forEach(([k, v]) => localStorage.setItem(k, v)); }}", local_storage_data)
            
            # 恢复 sessionStorage
            if session_data.get("session_storage"):
                session_storage_data = session_data["session_storage"]
                if session_storage_data:
                    await page.evaluate(f"(data) => {{ sessionStorage.clear(); Object.entries(data).forEach(([k, v]) => sessionStorage.setItem(k, v)); }}", session_storage_data)
            
            # 刷新页面以应用 cookies
            await page.reload(wait_until="domcontentloaded")
            
            return True
        except Exception as e:
            print(f"恢复会话失败: {e}")
            return False
    
    @staticmethod
    async def clear_session(page: Page) -> None:
        """
        清除当前页面的会话状态
        Args:
            page: Playwright 页面对象
        """
        context = page.context
        
        # 清除 cookies
        await context.clear_cookies()
        
        # 清除 localStorage
        await page.evaluate("() => { localStorage.clear(); }")
        
        # 清除 sessionStorage
        await page.evaluate("() => { sessionStorage.clear(); }")
        
        # 刷新页面
        await page.reload(wait_until="domcontentloaded")
    
    @staticmethod
    def is_session_expired(session_data: Dict[str, Any], max_age_hours: int = 24) -> bool:
        """
        检查会话是否过期
        Args:
            session_data: 会话数据
            max_age_hours: 最大有效期（小时）
        Returns:
            是否过期
        """
        created_at = session_data.get("created_at")
        if not created_at:
            return True
        
        try:
            created_time = datetime.fromisoformat(created_at)
            expiry_time = created_time + timedelta(hours=max_age_hours)
            return datetime.utcnow() > expiry_time
        except Exception:
            return True
    
    @staticmethod
    def get_session_summary(session_data: Dict[str, Any]) -> str:
        """
        获取会话摘要信息
        Args:
            session_data: 会话数据
        Returns:
            摘要信息
        """
        summary = []
        
        if session_data.get("cookies"):
            summary.append(f"Cookies: {len(session_data['cookies'])} 个")
        
        if session_data.get("local_storage"):
            summary.append(f"LocalStorage: {len(session_data['local_storage'])} 项")
        
        if session_data.get("session_storage"):
            summary.append(f"SessionStorage: {len(session_data['session_storage'])} 项")
        
        return ", ".join(summary) if summary else "无数据"


# 创建全局实例
session_manager = SessionManager()
