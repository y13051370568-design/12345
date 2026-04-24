from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple
import importlib
import sys

from app.core.config import settings


def find_project_root() -> Path:
    # 从 backend/base/app/agent 向上查找项目根目录，避免硬编码中文绝对路径。
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Agent工作流设计草案_含插图" / "demo.py").exists():
            return parent
    raise RuntimeError("未找到 Agent 工作流原型目录。")


def load_demo_module():
    # demo.py 使用同目录 mock_db 导入，因此需要先把原型目录加入 sys.path。
    prototype_dir = find_project_root() / "Agent工作流设计草案_含插图"
    prototype_path = str(prototype_dir)
    if prototype_path not in sys.path:
        sys.path.insert(0, prototype_path)
    return importlib.import_module("demo")


def build_runner_for_user(
    *,
    offline: bool,
    task_owner_username: str,
    reviewer_username: str,
) -> Tuple[Any, Any]:
    # 复用现有节点实现，但替换 MockDatabase 的用户映射，保证任务归属到当前登录用户。
    demo = load_demo_module()
    # 后端运行时不把产物写回原型目录，统一放在 backend/base/uploads 下便于部署和清理。
    demo.ARTIFACTS_DIR = Path("uploads/agent/artifacts").resolve()
    demo.DATA_DIR = Path("uploads/agent/demo_data").resolve()
    demo.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    demo.DATA_DIR.mkdir(parents=True, exist_ok=True)
    llm_client = demo.OfflineLLMClient() if offline else demo.LLMClient(demo.API_KEY_FILE)
    db = demo.MockDatabase(
        state_factory=demo.WorkflowState,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        task_owner_username=task_owner_username,
        reviewer_username=reviewer_username,
    )
    runner = demo.GraphRunner(
        nodes={
            "manager_parse": demo.ManagerNode(llm_client),
            "data_analysis": demo.DataNode(llm_client),
            "model_plan": demo.ModelPlanNode(),
            "model_training": demo.ModelNode(),
            "code_generation": demo.CodeGenerationNode(),
            "operation_report": demo.OperationNode(llm_client),
        },
        db=db,
    )
    return runner, db


def parse_hitl_config(stages: list[str] | None) -> Dict[str, bool]:
    demo = load_demo_module()
    if not stages or "all" in stages:
        return dict(demo.DEFAULT_HITL_CONFIG)
    enabled = set(stages)
    return {key: key in enabled for key in demo.DEFAULT_HITL_CONFIG}
