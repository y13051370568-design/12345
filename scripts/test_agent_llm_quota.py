from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from sqlalchemy import BigInteger, create_engine, event
from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base
from app.models.agent import AgentDataset, AgentTask
from app.models.quota_log import QuotaLog
from app.models.user import User
from app.service.agent_llm_client import AgentLLMClient
from app.service.agent_workflow_engine import AgentWorkflowEngine


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(_type, compiler, **kw):
    return "INTEGER"


@compiles(MYSQL_JSON, "sqlite")
def _compile_mysql_json_sqlite(_type, compiler, **kw):
    return "JSON"


@compiles(TINYINT, "sqlite")
def _compile_tinyint_sqlite(_type, compiler, **kw):
    return "INTEGER"


class _DummyHTTPResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "{\"ok\": true}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
        }


class _DummyHTTPClient:
    def __init__(self, timeout: int):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def post(self, *args, **kwargs):
        return _DummyHTTPResponse()


class _FakeLLMClient:
    def __init__(self, usage: dict | None = None):
        self.usage = usage or {"prompt_tokens": 20, "completion_tokens": 17, "total_tokens": 37}
        self.calls = 0

    def chat_json_with_usage(self, system_prompt: str, user_prompt: str) -> dict:
        self.calls += 1
        return {
            "content": {
                "target_column": "bought",
                "task_type": "CLASSIFICATION",
                "reason": "test",
            },
            "usage": self.usage,
        }


def _user(user_id: int, limit: int, used: int = 0) -> User:
    return User(
        id=user_id,
        username=f"user_{user_id}",
        password_hash="test",
        role="ZERO_BASIS",
        api_token_limit=limit,
        api_token_used=used,
        api_token_warning_threshold=max(1, int(limit * 0.8)),
        status=1,
    )


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__, AgentDataset.__table__, AgentTask.__table__, QuotaLog.__table__])
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    quota_id_seq = {"value": 1}

    @event.listens_for(db, "before_flush")
    def _assign_sqlite_ids(session, _flush_context, _instances):
        for obj in session.new:
            if isinstance(obj, QuotaLog) and obj.id is None:
                obj.id = quota_id_seq["value"]
                quota_id_seq["value"] += 1

    return db


def _dataset(db, user_id: int, csv_path: Path) -> AgentDataset:
    dataset = AgentDataset(
        id=10 + user_id,
        user_id=user_id,
        name="quota.csv",
        file_path=str(csv_path),
        file_size_kb=1,
        row_count=3,
        preview_json={"columns": ["age", "bought"]},
    )
    db.add(dataset)
    db.commit()
    return dataset


def _task(db, user: User, csv_path: Path) -> AgentTask:
    dataset = _dataset(db, user.id, csv_path)
    engine = AgentWorkflowEngine(db, user, offline=True)
    state = engine.create_task(dataset, "预测 bought", hitl_config={})
    return db.query(AgentTask).filter(AgentTask.state_json["task_id"].as_string() == state.task_id).first()


def test_client_reads_api_usage() -> None:
    import app.service.agent_llm_client as llm_module

    original_client = llm_module.httpx.Client
    llm_module.httpx.Client = _DummyHTTPClient
    try:
        client = AgentLLMClient.__new__(AgentLLMClient)
        client.base_url = "https://example.test/v1"
        client.api_key = "test"
        client.model = "deepseek-chat"
        client.last_usage = {}
        result = client.chat_json_with_usage("system", "user")
    finally:
        llm_module.httpx.Client = original_client

    assert result["content"] == {"ok": True}
    assert result["usage"]["total_tokens"] == 16
    assert client.last_usage["prompt_tokens"] == 11


def test_workflow_consumes_llm_quota() -> None:
    db = _build_db()
    user = _user(1, limit=1000)
    db.add(user)
    db.commit()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "quota.csv"
        csv_path.write_text("age,bought\n18,0\n30,1\n45,1\n", encoding="utf-8")
        task = _task(db, user, csv_path)

        engine = AgentWorkflowEngine(db, user, offline=True)
        engine.llm_client = _FakeLLMClient()
        engine._manager_parse(task)

    db.refresh(user)
    log = db.query(QuotaLog).one()
    node_output = task.state_json["context"]["node_outputs"]["manager_parse"]
    assert user.api_token_used == 37
    assert log.tokens_consumed == 37
    assert log.action == "agent_llm_manager_parse"
    assert log.task_id == task.state_json["task_id"]
    assert node_output["llm_usage"]["total_tokens"] == 37


def test_workflow_blocks_when_quota_exhausted() -> None:
    db = _build_db()
    user = _user(2, limit=10, used=10)
    db.add(user)
    db.commit()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "quota.csv"
        csv_path.write_text("age,bought\n18,0\n30,1\n45,1\n", encoding="utf-8")
        task = _task(db, user, csv_path)

        fake_client = _FakeLLMClient()
        engine = AgentWorkflowEngine(db, user, offline=True)
        engine.llm_client = fake_client
        try:
            engine._manager_parse(task)
        except Exception as exc:
            assert "API" in str(exc) or "额度" in str(exc)
        else:
            raise AssertionError("Quota exhausted user should not call real LLM")

    db.refresh(user)
    assert user.api_token_used == 10
    assert fake_client.calls == 0
    assert db.query(QuotaLog).count() == 0


def main() -> None:
    test_client_reads_api_usage()
    test_workflow_consumes_llm_quota()
    test_workflow_blocks_when_quota_exhausted()
    print("AGENT_LLM_QUOTA_TEST_OK", json.dumps({"usage_tokens": 16, "charged_tokens": 37}))


if __name__ == "__main__":
    main()
