from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base


class TestSession(Base):
    \"\"\"测试会话模型 - 用于存储登录后的会话状态\"\"\"
    __tablename__ = \"test_sessions\"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment=\"会话名称\")
    description = Column(Text, comment=\"会话描述\")
    
    # 会话数据
    cookies = Column(JSON, comment=\"浏览器 cookies\")
    local_storage = Column(JSON, comment=\"localStorage 数据\")
    session_storage = Column(JSON, comment=\"sessionStorage 数据\")
    
    # 关联信息
    target_url = Column(String(500), comment=\"目标URL\")
    login_scenario_id = Column(Integer, ForeignKey(\"test_scenarios.id\", ondelete=\"SET NULL\"), comment=\"登录场景ID\")
    
    # 状态
    is_active = Column(Boolean, default=True, comment=\"是否活跃\")
    expires_at = Column(DateTime, comment=\"过期时间\")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment=\"创建时间\")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment=\"更新时间\")
    last_used_at = Column(DateTime, comment=\"最后使用时间\")
    
    # 关系
    login_scenario = relationship(\"TestScenario\", foreign_keys=[login_scenario_id])
    
    def __repr__(self):
        return f\"<TestSession {self.name}>\"


# 登录配置枚举
class LoginConfig:
    \"\"\"登录配置选项\"\"\"
    NO_LOGIN = \"no_login\"  # 不需要登录
    PERFORM_LOGIN = \"perform_login\"  # 执行登录
    USE_GLOBAL_SESSION = \"use_global_session\"  # 使用全局会话
    USE_SESSION = \"use_session\"  # 使用指定会话
