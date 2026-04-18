"""
统一日志模块
配置结构化日志记录，支持控制台和文件输出
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（用于控制台输出）"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger() -> logging.Logger:
    """
    配置并返回应用日志器

    功能特性：
    - 控制台输出：带颜色的格式化日志
    - 文件输出：按大小自动轮转（最大10MB，保留5个备份）
    - 日志级别：从配置文件读取
    """
    # 创建日志器
    logger = logging.getLogger("ai4ml")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = ColoredFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=settings.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# 全局日志器实例
logger = setup_logger()


# 请求日志中间件辅助函数
def log_request(method: str, path: str, status_code: int, duration: float):
    """记录HTTP请求日志"""
    logger.info(
        f"{method} {path} - Status: {status_code} - Duration: {duration:.3f}s"
    )


def log_task_execution(task_id: str, node: str, status: str, duration: float = None):
    """记录任务执行日志"""
    if duration:
        logger.info(
            f"Task {task_id} - Node: {node} - Status: {status} - Duration: {duration:.2f}s"
        )
    else:
        logger.info(f"Task {task_id} - Node: {node} - Status: {status}")


def log_database_operation(operation: str, table: str, record_id: str = None):
    """记录数据库操作日志"""
    if record_id:
        logger.debug(f"DB Operation: {operation} - Table: {table} - ID: {record_id}")
    else:
        logger.debug(f"DB Operation: {operation} - Table: {table}")
