"""
AI4ML社区平台 - 后端主应用
基于FastAPI构建的RESTful API服务
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time

from app.core.config import settings
from app.core.logger import logger, log_request
from app.core.exceptions import (
    BusinessException,
    business_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.api import user_api
from app.api import auth_api
from app.api import task_api
from app.api import model_api
from app.api import quota_api
from app.api import dataset_api
from app.api import agent_api


# 创建FastAPI应用实例
app = FastAPI(
    title="AI4ML社区平台",
    description="智算AI4ML社区平台后端API服务",
    version="1.0.0",
    debug=settings.DEBUG,
)


# 配置CORS中间件（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录每个HTTP请求的信息"""
    start_time = time.time()

    # 处理请求
    response = await call_next(request)

    # 计算处理时长
    duration = time.time() - start_time

    # 记录日志
    log_request(request.method, str(request.url.path), response.status_code, duration)

    return response


# 注册异常处理器
app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# 注册路由
from app.api import auth_api

app.include_router(auth_api.router, prefix="/api")
app.include_router(user_api.router, prefix="/api", tags=["用户管理"])
app.include_router(task_api.router, prefix="/api", tags=["任务中心"])
app.include_router(model_api.router, prefix="/api", tags=["模型广场管理"])
app.include_router(quota_api.router, prefix="/api", tags=["API 额度管理"])
app.include_router(dataset_api.router, prefix="/api", tags=["数据中心审核与管理"])
app.include_router(agent_api.router, prefix="/api", tags=["Agent 工作流"])


# 健康检查接口
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return JSONResponse(
        content={
            "success": True,
            "message": "服务运行正常",
            "version": "1.0.0",
            "debug": settings.DEBUG,
        }
    )


# 根路径
@app.get("/", tags=["系统"])
async def root():
    """根路径欢迎信息"""
    return JSONResponse(
        content={
            "success": True,
            "message": "欢迎使用AI4ML社区平台API",
            "docs": "/docs",
            "health": "/health",
        }
    )


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("=" * 60)
    logger.info("AI4ML Community Platform Starting...")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"Server: {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info("=" * 60)


# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("AI4ML Community Platform Shutting Down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )
