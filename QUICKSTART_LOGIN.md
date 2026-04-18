# 登录功能快速开始指南

## 一、启动服务

### 1. 安装依赖（如果还没安装）

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改数据库配置：

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

### 4. 初始化测试用户

```bash
python scripts/init_users.py
```

这会创建3个测试账号：

- **管理员**: admin / admin123
- **开发者**: developer / dev123
- **普通用户**: user / user123

### 5. 启动服务

```bash
python app/main.py
```

访问 http://localhost:8000/docs 查看API文档

---

## 二、API测试（使用curl）

### 1. 管理员登录

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

**响应示例**:

```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "user": {
      "id": 1,
      "username": "admin",
      "role": "ADMIN",
      "status": 1
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "redirect_route": "/admin/dashboard",
    "permissions": ["admin:all", "user:manage", ...]
  }
}
```

### 2. 获取当前用户信息

```bash
# 将上面返回的access_token替换到这里
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <your_access_token>"
```

### 3. 测试权限控制

```bash
# 使用管理员Token访问管理接口（成功）
curl -X GET http://localhost:8000/api/users \
  -H "Authorization: Bearer <admin_access_token>"

# 使用普通用户Token访问管理接口（失败，403）
curl -X GET http://localhost:8000/api/users \
  -H "Authorization: Bearer <user_access_token>"
```

---

## 三、前端对接示例

### 1. 登录（JavaScript）

```javascript
async function login(username, password) {
  try {
    const response = await fetch('http://localhost:8000/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });

    const result = await response.json();

    if (result.success) {
      // 保存Token
      localStorage.setItem('access_token', result.data.access_token);
      localStorage.setItem('refresh_token', result.data.refresh_token);
      localStorage.setItem('user', JSON.stringify(result.data.user));
    
      // 跳转到对应页面
      window.location.href = result.data.redirect_route;
    } else {
      alert('登录失败：' + result.message);
    }
  } catch (error) {
    console.error('登录错误：', error);
  }
}

// 使用
login('admin', 'admin123');
```

### 2. 携带Token请求

```javascript
async function getUserInfo() {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('http://localhost:8000/api/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  return response.json();
}
```

### 3. Axios配置（推荐）

```javascript
import axios from 'axios';

// 创建axios实例
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000
});

// 请求拦截器 - 添加Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 处理Token过期
api.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      // Token过期，尝试刷新
      const refreshToken = localStorage.getItem('refresh_token');
    
      try {
        const response = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken
        });
      
        // 保存新Token
        localStorage.setItem('access_token', response.data.data.access_token);
      
        // 重试原请求
        error.config.headers['Authorization'] = 
          `Bearer ${response.data.data.access_token}`;
        return axios.request(error.config);
      } catch (refreshError) {
        // 刷新失败，跳转登录页
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// 使用
api.post('/api/auth/login', { username: 'admin', password: 'admin123' });
api.get('/api/auth/me');
```

---

## 四、核心API接口

| 接口                      | 方法 | 说明             | 需要认证 |
| ------------------------- | ---- | ---------------- | -------- |
| `/api/auth/register`    | POST | 用户注册         | ✗       |
| `/api/auth/login`       | POST | 用户登录         | ✗       |
| `/api/auth/logout`      | POST | 用户登出         | ✓       |
| `/api/auth/refresh`     | POST | 刷新Token        | ✗       |
| `/api/auth/me`          | GET  | 获取当前用户信息 | ✓       |
| `/api/auth/permissions` | GET  | 获取权限列表     | ✓       |
| `/api/auth/routes`      | GET  | 获取路由配置     | ✓       |

---

## 五、角色与跳转路由

| 角色       | 角色代码   | 登录后跳转           | 说明         |
| ---------- | ---------- | -------------------- | ------------ |
| 零基础用户 | ZERO_BASIS | `/tasks`           | 任务中心     |
| 开发者     | DEVELOPER  | `/developer`       | 开发者工作台 |
| 管理员     | ADMIN      | `/admin/dashboard` | 管理后台     |

---

## 六、常用命令

### 重置数据库（清空后重新初始化）

```bash
# 1. 删除数据库
mysql -u root -p -e "DROP DATABASE IF EXISTS ai4ml_community;"

# 2. 重新创建
mysql -u root -p -e "CREATE DATABASE ai4ml_community DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"

# 3. 重新初始化用户
python scripts/init_users.py
```

### 查看日志

```bash
tail -f logs/app.log
```

---

## 七、在线API文档

启动服务后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

可以在文档中直接测试所有接口！

---

## 八、故障排查

### 问题1: 数据库连接失败

**解决**: 检查 `.env` 中的数据库配置是否正确

### 问题2: Token验证失败

**解决**:

- 检查Token是否正确携带在Header中
- 检查Token格式：`Authorization: Bearer <token>`
- 检查Token是否过期（30分钟）

### 问题3: 导入模块失败

**解决**:

```bash
pip install -r requirements.txt
```

### 问题4: SECRET_KEY警告

**解决**: 生产环境必须修改 `.env` 中的 `SECRET_KEY` 为强随机字符串

生成随机密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 九、下一步

1. 完善前端登录页面
2. 实现任务管理模块API
3. 实现社区资源模块API
4. 集成Agent流水线

详细文档请查看：

- [后端框架搭建工作记录.md](后端框架搭建工作记录.md)
- [用户登录功能实现文档.md](用户登录功能实现文档.md)
- [后端设计.md](后端设计.md)

---

**快速支持**: 查看在线文档 http://localhost:8000/docs 🚀
