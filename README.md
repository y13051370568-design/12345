# AI4ML社区平台 - 后端服务

基于Python + FastAPI构建的智算AI4ML社区平台后端服务框架。

## 项目结构

```
app/
├── core/                    # 核心模块
│   ├── config.py           # 配置管理（环境变量加载）
│   ├── logger.py           # 统一日志模块
│   ├── exceptions.py       # 统一异常处理
│   ├── auth.py             # JWT认证与权限控制
│   └── security.py         # 安全工具
├── api/                     # API路由
│   ├── auth_api.py         # 认证API (登录/注册/Token)
│   ├── user_api.py         # 用户管理API (管理员)
│   └── task_api.py         # 任务中心API (上传/列表)
├── models/                  # 数据库模型
├── schemas/                 # Pydantic数据模型
├── service/                 # 业务逻辑层
├── db.py                    # 数据库连接池配置
└── main.py                  # FastAPI主应用
```

## 核心功能

### 1. 配置管理
- 使用 Pydantic Settings 管理环境变量
- 支持 `.env` 文件配置
- 数据库连接、服务器配置等统一管理

### 2. 数据库连接池
- 基于 SQLAlchemy 实现 MySQL 连接池
- 支持连接池大小配置（pool_size=10, max_overflow=20）
- 自动连接健康检查（pool_pre_ping）
- 连接自动回收（pool_recycle=3600秒）

### 3. 统一异常处理
- 业务异常分类：认证、权限、资源不存在、数据校验等
- 统一异常响应格式
- 友好的用户错误提示
- 防止敏感信息泄露

### 4. 统一日志模块
- 控制台彩色日志输出
- 文件日志自动轮转（10MB/文件，保留5个备份）
- 支持配置日志级别
- 请求日志、任务日志、数据库操作日志

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

修改数据库配置：
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ai4ml_community
```

### 3. 创建数据库

```sql
CREATE DATABASE ai4ml_community DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 4. 运行服务

```bash
# 开发模式（自动重载）
python app/main.py

# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

## 开发规范

### 异常处理示例

```python
from app.core.exceptions import BusinessException, DataValidationException

# 业务异常
if not user:
    raise ResourceNotFoundException("用户不存在")

# 数据校验异常
if file_size > MAX_SIZE:
    raise DataValidationException(
        message="文件大小超过限制",
        details={"max_size": MAX_SIZE, "actual_size": file_size}
    )
```

### 日志记录示例

```python
from app.core.logger import logger, log_task_execution

logger.info("开始处理任务")
logger.error(f"任务执行失败: {str(e)}", exc_info=True)

# 任务执行日志
log_task_execution(task_id="123", node="parse", status="SUCCESS", duration=2.5)
```

### 数据库操作示例

```python
from app.db import get_db_session
from fastapi import Depends
from sqlalchemy.orm import Session

@app.get("/users")
def get_users(db: Session = Depends(get_db_session)):
    users = db.query(User).all()
    return users
```

## 技术栈

- **框架**: FastAPI 0.115.0
- **数据库**: MySQL + SQLAlchemy 2.0
- **异步**: Uvicorn + asyncio
- **任务队列**: Celery + Redis
- **数据处理**: Pandas, NumPy, scikit-learn

## 性能指标

根据设计文档要求：
- 支持 50 个用户同时在线
- 同时最多执行 5 个并发任务
- API 响应时间 ≤ 30秒
- 文件上传限制 ≤ 100MB

## 下一步开发

1. ~~实现用户认证与权限控制（JWT）~~ ✅ 已完成
2. ~~实现核心业务模块API（任务管理）~~ ✅ 已完成
3. 实现任务队列与并发控制（Celery）
4. 实现数据库迁移脚本（Alembic）
5. 编写单元测试和集成测试

## 已实现API接口

### 认证模块 (`/api/auth`)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 用户注册 |
| POST | /api/auth/login | 用户登录 |
| POST | /api/auth/refresh | 刷新Token |
| GET | /api/auth/me | 获取当前用户信息 |
| GET | /api/auth/permissions | 获取用户权限 |
| GET | /api/auth/routes | 获取用户可访问路由 |
| POST | /api/auth/logout | 用户登出 |

### 用户管理模块 (`/api/admin`)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/admin/users | 获取用户列表（支持username/role/status筛选） |
| PUT | /api/admin/users/{user_id}/role | 修改用户角色（Body: {role}） |
| PATCH | /api/admin/users/{user_id}/status | 修改用户状态（Body: {status}） |

### 任务中心模块 (`/api/tasks`)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/tasks/upload | 上传CSV文件 |
| GET | /api/tasks/list | 获取任务列表 |

## 联系方式

如有问题请提交 Issue 或联系开发团队。
