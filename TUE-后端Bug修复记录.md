# TUE-智算社区-2 后端 Bug 修复记录

**日期**: 2026-06-01
**范围**: 测试报告 `TUE-智算社区-2-0526.docx` 中 004–012 号 Bug（排除 Agent 工作流 001–003）

---

## 归因总表

| ID | 描述 | 归因 | 处理 |
|---|---|---|---|
| 004 | 管理员工作流审核管理页无内容 | 前端 | 后端 `GET /agents/admin/workflows` 正常分页返回 |
| 005 | 模型详情弹出 example.com | 数据/前端 | `resource_url` 种子数据，前端直接打开 |
| 006 | 个人中心 API token 不消耗 | **后端** | 已修复 |
| 007 | 社区数据集"推荐优先"加载失败 | **后端** | 已修复 |
| 008 | 社区公开数据集无法预览 | **后端** | 已修复 |
| 009 | 导出 PDF 特征重要性显示不全 | 前端 | 后端只生成 markdown，PDF 由前端渲染 |
| 010 | 中文表头数据集上传失败 | **后端** | 已修复 |
| 011 | 上传的 csv 文件无法下载 | **后端** | 已修复 |
| 012 | admin 调用消耗记录无内容 | **后端连带** | 随 006 修复 |

---

## 修复详情

### 006 — API Token 不计费

**根因**: 只有 `task_api.py` 的 CSV 上传路径调了 `consume_quota`，Agent 任务执行链路完全没接入。

**修改文件**:

1. `app/service/agent_service.py:87-91` — `run_task` 入口加前置额度检查，超限直接拒绝，避免空跑一轮再失败。
   ```python
   if not offline:
       quota_check = quota_service.check_quota(db, current_user.id, required_tokens=1)
       if not quota_check["allowed"]:
           raise QuotaExceededException(quota_check["message"])
   ```

2. `app/service/agent_workflow_engine.py:253-272` — 此前已实现 `_chat_json_for_node` 中每次 LLM 调用后 `consume_quota`，token 数优先取 API 返回的 `usage.total_tokens`，缺失时按字符数 /4 粗估。

**连带修复**: 012（admin 消耗记录有数据了）。

---

### 007 — 社区数据集"推荐优先" 500 错误

**根因**: `community_service.py:57` 对 DATASET 类型也执行 `desc(model_class.is_recommended)`，但 `Dataset` 模型没有 `is_recommended` 字段 → SQL/属性错误。

**修改**: `app/service/community_service.py:57-61`
```python
elif sort_by == "recommended":
    if hasattr(model_class, "is_recommended"):
        query = query.order_by(desc(model_class.is_recommended), desc(model_class.created_at))
    else:
        query = query.order_by(desc(model_class.created_at))
```

---

### 008 — 公开 Agent 数据集无法预览

**根因**: `agent_api.py:71` 的预览端点对 Agent Dataset 强制 `_assert_owner_or_admin`，即使 `is_public=1` 也禁止他人预览。

**修改**:

1. `app/service/agent_service.py:580-584` — 新增 `_assert_can_view` helper：
   ```python
   def _assert_can_view(self, owner_id, is_public, current_user):
       if is_public == 1:
           return
       self._assert_owner_or_admin(owner_id, current_user)
   ```

2. `app/api/agent_api.py:71` — 预览端点改用 `_assert_can_view`。

写入、运行、下载产物等敏感操作仍走原 `_assert_owner_or_admin`。

---

### 010 — 中文表头 CSV 上传失败

**根因**: 两处 CSV 解析硬编码 UTF-8 解码，GBK 编码文件直接 `UnicodeDecodeError`。

**修改**:

1. `app/service/agent_storage.py:41-49` — `pd.read_csv` 加 UTF-8 → GBK → GB18030 fallback。

2. `app/api/task_api.py:60-66` — `content.decode` 同上三级 fallback。

---

### 011 — 上传 CSV 无法下载

**根因**: `task_api.py` 只存文件没有下载端点；Agent 数据集也只有预览没有原始文件下载。

**修改**:

1. `app/api/task_api.py:94-110` — 新增 `GET /tasks/download/{file_id}`，按前缀匹配 `uploads/csv/` 目录文件，`FileResponse` 返回。

2. `app/api/agent_api.py:76-98` — 新增 `GET /agent/datasets/{dataset_id}/download`，鉴权走 `_assert_can_view`（公开可下，私有限 owner/admin）。

---

## 修改文件清单

| 文件 | 改动 |
|---|---|
| `app/service/agent_service.py` | +quota import, run_task 前置检查, _assert_can_view helper |
| `app/service/community_service.py` | recommended 排序 hasattr 保护 |
| `app/service/agent_storage.py` | CSV 编码 fallback |
| `app/api/task_api.py` | +FileResponse import, 编码 fallback, +下载端点 |
| `app/api/agent_api.py` | +Path import, 预览改用 _assert_can_view, +数据集下载端点 |

---

## 验证要点

- **006/012**: 跑一次 Agent 任务 → `GET /quota/me` 的 `api_token_used` 应增长；`GET /quota/admin/logs` 出现 `action=agent_llm_*` 记录。
- **007**: `GET /community/resources?type=DATASET&sort_by=recommended` 返回 200。
- **008**: 非 owner 用户调 `GET /agent/datasets/{public_id}/preview` 返回 200；私有数据集仍 403。
- **010**: 上传 GBK 中文表头 CSV 不报错。
- **011**: `POST /tasks/upload` 后用 `GET /tasks/download/{file_id}` 拿回原始 CSV；`POST /agent/datasets/upload` 后用 `GET /agent/datasets/{id}/download` 拿回原始 CSV。
