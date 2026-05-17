from __future__ import annotations

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT, TINYINT
from sqlalchemy import event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base
from app.models.agent import AgentDataset, AgentTask, AgentWorkflow
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.agent import WorkflowShare
from app.service.agent_service import agent_service


@compiles(TINYINT, "sqlite")
def _compile_tinyint_sqlite(_type, compiler, **kw):
    return "INTEGER"


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_sqlite(_type, compiler, **kw):
    return "TEXT"


def _user(user_id: int, username: str, role: str) -> User:
    return User(
        id=user_id,
        username=username,
        password_hash="test",
        role=role,
        api_token_limit=1000000,
        api_token_used=0,
        api_token_warning_threshold=800000,
        status=1,
    )


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            AgentDataset.__table__,
            AgentTask.__table__,
            AgentWorkflow.__table__,
            AuditLog.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    workflow_id_seq = {"value": 100}

    @event.listens_for(db, "before_flush")
    def _assign_sqlite_bigint_ids(session, _flush_context, _instances):
        for obj in session.new:
            if isinstance(obj, AgentWorkflow) and obj.id is None:
                obj.id = workflow_id_seq["value"]
                workflow_id_seq["value"] += 1

    developer = _user(1, "developer", "DEVELOPER")
    other_user = _user(2, "user", "ZERO_BASIS")
    admin = _user(3, "admin", "ADMIN")
    db.add_all([developer, other_user, admin])

    dataset = AgentDataset(
        id=10,
        user_id=developer.id,
        name="train.csv",
        file_path="uploads/agent/datasets/train.csv",
        file_size_kb=1,
        row_count=2,
        preview_json={"columns": ["age", "bought"]},
    )
    task = AgentTask(
        id=20,
        user_id=developer.id,
        dataset_id=dataset.id,
        task_description="预测用户是否购买",
        task_type="CLASSIFICATION",
        target_column="bought",
        status="COMPLETED",
        generated_code_path="uploads/agent/artifacts/task_demo/generated_model.py",
        state_json={
            "task_id": "task_demo",
            "artifacts": {"generated_code": "uploads/agent/artifacts/task_demo/generated_model.py"},
            "context": {
                "hitl_config": {"parse_review": True},
                "node_outputs": {
                    "data_analysis": {
                        "feature_columns": ["age"],
                        "numeric_columns": ["age"],
                        "row_count": 2,
                    },
                    "model_plan": {
                        "candidate_models": ["LogisticRegression"],
                        "primary_metric": "accuracy",
                    },
                    "model_training": {
                        "best_model": {"model_name": "LogisticRegression"},
                        "metrics": {"metric": "accuracy", "score": 0.95},
                    },
                    "code_generation": {
                        "generated_code": "uploads/agent/artifacts/task_demo/generated_model.py"
                    },
                },
            },
        },
    )
    db.add_all([dataset, task])
    db.commit()

    def fake_get_code(_db, task_id, current_user):
        assert task_id == "task_demo"
        assert current_user.role in {"DEVELOPER", "ADMIN"}
        return {"python_code": "def train():\n    return 'ok'\n"}

    original_get_code = agent_service.get_code
    agent_service.get_code = fake_get_code
    try:
        shared = agent_service.share_workflow(
            db,
            WorkflowShare(
                task_id="task_demo",
                title="购买预测工作流",
                description="用于二分类购买预测",
                category="分类建模",
                applicable_task_types="CLASSIFICATION",
                tags="sklearn,classification",
            ),
            developer,
        )
    finally:
        agent_service.get_code = original_get_code

    assert shared.audit_status == "PENDING"
    assert shared.is_public == 0
    assert shared.workflow_spec_json["source_task_id"] == "task_demo"
    assert shared.workflow_spec_json["model_plan"]["primary_metric"] == "accuracy"
    assert shared.default_config_json["training_metrics"]["score"] == 0.95
    assert "def train" in shared.code_content

    invisible_to_other = agent_service.list_workflows(db, other_user, scope="public")
    assert invisible_to_other["total"] == 0

    shared.audit_status = "APPROVED"
    shared.is_public = 1
    db.commit()
    db.refresh(shared)

    public_list = agent_service.list_workflows(db, other_user, scope="public", sort="latest")
    assert public_list["total"] == 1
    assert public_list["items"][0].title == "购买预测工作流"

    detail = agent_service.get_workflow(db, shared.id, other_user, increase_view=True)
    assert detail.view_count == 1
    assert detail.code_content.startswith("def train")

    forked = agent_service.fork_workflow(db, shared.id, other_user)
    assert forked.user_id == other_user.id
    assert forked.fork_from_id == shared.id
    assert forked.workflow_spec_json == shared.workflow_spec_json
    assert forked.code_content == shared.code_content
    db.refresh(shared)
    assert shared.fork_count == 1

    mine = agent_service.list_workflows(db, other_user, scope="mine")
    assert mine["total"] == 1
    assert mine["items"][0].fork_from_id == shared.id

    shared.audit_status = "OFF_SHELF"
    shared.is_public = 0
    db.commit()
    try:
        agent_service.fork_workflow(db, shared.id, admin)
    except Exception as exc:
        assert "下架" in str(exc)
    else:
        raise AssertionError("OFF_SHELF workflow should not be forkable")

    print("WORKFLOW_SHARE_FORK_TEST_OK", shared.id, forked.id, public_list["total"], mine["total"])


if __name__ == "__main__":
    main()
