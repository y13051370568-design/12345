"""
数据库连接池配置模块
实现MySQL连接池管理，支持并发访问控制
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator

from app.core.config import settings
from app.core.logger import logger


# 创建数据库引擎，配置连接池参数
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前测试，避免使用断开的连接
    pool_recycle=3600,  # 连接回收时间（秒）
    echo=settings.DEBUG,  # 调试模式下打印SQL
)


# 监听连接事件，记录日志
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """数据库连接建立时的回调"""
    logger.info("Database connection established")


@event.listens_for(engine, "close")
def receive_close(dbapi_conn, connection_record):
    """数据库连接关闭时的回调"""
    logger.info("Database connection closed")


# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器
    自动处理事务提交和回滚，确保连接正确释放

    使用示例:
        with get_db() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction error: {str(e)}")
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    获取数据库会话（用于FastAPI依赖注入）

    使用示例:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db_session)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()