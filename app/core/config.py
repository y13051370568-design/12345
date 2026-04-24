"""
系统配置管理模块
从环境变量中加载配置，确保敏感信息不硬编码
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ai4ml_community"

    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = True

    # 安全配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 业务约束
    MAX_CONCURRENT_TASKS: int = 5
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_ROWS_PER_CSV: int = 100000

    # Agent 大模型配置；默认读取后端目录内部的本地密钥文件。
    AGENT_LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    AGENT_LLM_MODEL: str = "deepseek-chat"
    AGENT_LLM_API_KEY_FILE: str = "config/api_key.txt"
    AGENT_LLM_TIMEOUT_SECONDS: int = 60

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()
