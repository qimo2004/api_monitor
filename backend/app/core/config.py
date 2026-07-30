"""配置管理模块：从环境变量加载数据库连接、JWT密钥等配置，提供 get_db 依赖注入"""
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./api_monitor.db"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时
    MAX_CONCURRENT_CHECKS: int = 20  # 最大并发巡检数
    ALERT_ESCALATION_HOURS: int = 2   # 告警升级阈值（小时）

    # 邮件通知配置
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
