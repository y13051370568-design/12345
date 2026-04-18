"""
统一异常处理模块
定义业务异常类型，提供友好的错误信息给前端
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class BusinessException(Exception):
    """
    业务异常基类
    用于业务逻辑中可预期的错误场景
    """

    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationException(BusinessException):
    """认证异常"""

    def __init__(self, message: str = "身份认证失败"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationException(BusinessException):
    """权限异常"""

    def __init__(self, message: str = "无权限访问此资源"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ResourceNotFoundException(BusinessException):
    """资源不存在异常"""

    def __init__(self, message: str = "请求的资源不存在"):
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class DataValidationException(BusinessException):
    """数据校验异常"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="DATA_VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class FileUploadException(BusinessException):
    """文件上传异常"""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="FILE_UPLOAD_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class TaskExecutionException(BusinessException):
    """任务执行异常"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="TASK_EXECUTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class QuotaExceededException(BusinessException):
    """配额超限异常"""

    def __init__(self, message: str = "API调用配额已用尽"):
        super().__init__(
            message=message,
            code="QUOTA_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ConcurrentLimitException(BusinessException):
    """并发限制异常"""

    def __init__(self, message: str = "系统繁忙，请稍后再试"):
        super().__init__(
            message=message,
            code="CONCURRENT_LIMIT_EXCEEDED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# 全局异常处理器
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": "HTTP_ERROR",
            "message": exc.detail,
            "path": str(request.url),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求参数校验异常处理器"""
    errors = []
    for error in exc.errors():
        errors.append(
            {"field": ".".join(str(x) for x in error["loc"]), "message": error["msg"]}
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "details": {"errors": errors},
            "path": str(request.url),
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器（兜底）"""
    from app.core.logger import logger

    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "code": "INTERNAL_SERVER_ERROR",
            "message": "服务器内部错误，请联系管理员",
            "path": str(request.url),
        },
    )
