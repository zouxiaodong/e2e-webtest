from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from datetime import datetime
from .test_case import Base


class GlobalConfig(Base):
    """全局配置模型"""
    __tablename__ = "global_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    config_value = Column(Text, comment="配置值")
    config_type = Column(String(50), default="string", comment="配置类型: string, number, boolean, json")
    description = Column(String(500), comment="配置描述")
    is_encrypted = Column(Boolean, default=False, comment="是否加密")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<GlobalConfig {self.config_key}={self.config_value}>"


# 常用配置键定义
class ConfigKeys:
    """配置键常量"""
    TARGET_URL = "target_url"  # 目标URL
    DEFAULT_USERNAME = "default_username"  # 默认用户名
    DEFAULT_PASSWORD = "default_password"  # 默认密码
    CAPTCHA_SELECTOR = "captcha_selector"  # 验证码选择器
    CAPTCHA_INPUT_SELECTOR = "captcha_input_selector"  # 验证码输入框选择器
    AUTO_DETECT_CAPTCHA = "auto_detect_captcha"  # 自动检测验证码
    BROWSER_HEADLESS = "browser_headless"  # 浏览器无头模式
    BROWSER_TIMEOUT = "browser_timeout"  # 浏览器超时时间
    USE_COMPUTER_USE = "use_computer_use"  # 使用 Computer-Use 方案（截图+坐标）
