from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class GlobalConfigBase(BaseModel):
    """全局配置基础模型"""
    config_key: str = Field(..., description="配置键")
    config_value: Optional[str] = Field(None, description="配置值")
    config_type: str = Field("string", description="配置类型")
    description: Optional[str] = Field(None, description="配置描述")
    is_encrypted: bool = Field(False, description="是否加密")


class GlobalConfigCreate(GlobalConfigBase):
    """创建配置请求"""
    pass


class GlobalConfigUpdate(BaseModel):
    """更新配置请求"""
    config_value: Optional[str] = None
    description: Optional[str] = None


class GlobalConfigResponse(GlobalConfigBase):
    """配置响应"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 预定义配置
class GlobalConfigSettings(BaseModel):
    """全局配置设置"""
    target_url: Optional[str] = Field(None, description="目标URL")
    default_username: Optional[str] = Field(None, description="默认用户名")
    default_password: Optional[str] = Field(None, description="默认密码")
    captcha_selector: Optional[str] = Field("", description="验证码选择器")
    captcha_input_selector: Optional[str] = Field("", description="验证码输入框选择器")
    browser_headless: bool = Field(True, description="浏览器无头模式")
    use_computer_use: bool = Field(False, description="使用Computer-Use方案（截图+坐标定位）")
    browser_timeout: int = Field(30000, description="浏览器超时时间(毫秒)")
