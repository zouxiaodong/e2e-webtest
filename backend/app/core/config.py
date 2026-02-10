from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # 百练平台配置
    BAILIAN_API_KEY: str
    BAILIAN_BASE_URL: str
    BAILIAN_LLM_MODEL: str = "qwen-plus"
    BAILIAN_VL_MODEL: str = "qwen-vl-plus"

    # 数据库配置
    DATABASE_URL: str

    # 应用配置
    APP_NAME: str = "AI-Driven E2E Testing Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"

    # 浏览器配置
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000

    # 会话存储配置
    SESSION_STORAGE_PATH: str = ""  # cookies、localStorage、sessionStorage文件的存储路径

    # Python路径配置（用于测试脚本导入app模块）
    PYTHON_PATH: str = ""  # 项目根目录路径

    # 工作目录
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()