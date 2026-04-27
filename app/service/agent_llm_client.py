from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json

import httpx

from app.core.config import settings
from app.core.exceptions import DataValidationException


class AgentLLMClient:
    def __init__(self) -> None:
        # 支持两种 Key 文件格式：单行 api_key，或 base_url/api_key/model 三行格式。
        config = self._load_config()
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key"]
        self.model = config["model"]

    def chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        # 要求模型返回严格 JSON；若返回 Markdown 代码块则做兼容剥离。
        raw_text = self.chat_text(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1).strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise DataValidationException("真实 LLM 未返回合法 JSON", {"raw_text": raw_text, "error": str(exc)})

    def chat_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        # 使用 OpenAI-compatible Chat Completions 协议，兼容 DeepSeek 等平台。
        try:
            with httpx.Client(timeout=settings.AGENT_LLM_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "temperature": temperature,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return payload["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            raise DataValidationException("真实 LLM 调用返回错误状态", {"status_code": exc.response.status_code, "body": exc.response.text[:1000]})
        except Exception as exc:
            raise DataValidationException("真实 LLM 调用失败", {"error": str(exc)})

    def _load_config(self) -> Dict[str, str]:
        # 优先读取环境变量；未配置时读取后端目录内部的本地密钥文件。
        config_path = Path(settings.AGENT_LLM_API_KEY_FILE)
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path
        lines = []
        if config_path.exists():
            lines = [line.strip() for line in config_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        if len(lines) >= 2:
            return {
                "base_url": lines[0],
                "api_key": lines[1],
                "model": lines[2] if len(lines) >= 3 else settings.AGENT_LLM_MODEL,
            }
        if len(lines) == 1:
            return {
                "base_url": settings.AGENT_LLM_BASE_URL,
                "api_key": lines[0],
                "model": settings.AGENT_LLM_MODEL,
            }
        raise DataValidationException("未找到真实 LLM API Key，请配置 AGENT_LLM_API_KEY_FILE 或 backend/base/config/api_key.txt")
