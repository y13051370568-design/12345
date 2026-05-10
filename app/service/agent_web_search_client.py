from __future__ import annotations

from html import unescape
from typing import Any, Dict, List
import re

import httpx

from app.core.config import settings


class AgentWebSearchClient:
    # 轻量联网检索客户端：当前使用 DuckDuckGo Instant Answer API，避免引入额外密钥依赖。
    SEARCH_URL = "https://api.duckduckgo.com/"
    GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
    BING_SEARCH_URL = "https://www.bing.com/search"

    def __init__(self) -> None:
        self.enabled = settings.AGENT_WEB_SEARCH_ENABLED
        self.max_results = max(1, int(settings.AGENT_WEB_SEARCH_MAX_RESULTS))
        self.timeout = float(settings.AGENT_WEB_SEARCH_TIMEOUT_SECONDS)

    def search_model_references(
        self,
        task_description: str,
        task_type: str | None,
        target_column: str | None,
        feature_columns: List[str] | None,
    ) -> List[Dict[str, str]]:
        # 将任务描述和字段信息组合成少量查询，找相似建模经验并压缩为提示词可用摘要。
        if not self.enabled:
            return []
        queries = self._build_queries(task_description, task_type, target_column, feature_columns or [])
        references: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        for query in queries:
            for item in self._search_once(query):
                url = item.get("url") or ""
                title = item.get("title") or ""
                if not url or url in seen_urls or not self._is_relevant_result(item):
                    continue
                seen_urls.add(url)
                references.append(
                    {
                        "title": title[:160],
                        "url": url,
                        "summary": item.get("summary", "")[:360],
                        "query": query,
                    }
                )
                if len(references) >= self.max_results:
                    return references
        return references

    def _build_queries(
        self,
        task_description: str,
        task_type: str | None,
        target_column: str | None,
        feature_columns: List[str],
    ) -> List[str]:
        # 查询词强调 sklearn、表格数据和任务类型，减少无关网页进入 LLM 上下文。
        task_keyword = "classification" if task_type == "CLASSIFICATION" else "regression"
        feature_text = " ".join(feature_columns[:4])
        target_text = target_column or "target"
        raw_queries = [
            f"sklearn {task_keyword} pipeline example",
            f"{task_description} machine learning sklearn pipeline",
            f"{target_text} prediction {task_keyword} feature engineering sklearn",
            f"tabular data {task_keyword} sklearn example {feature_text}".strip(),
        ]
        queries: List[str] = []
        for query in raw_queries:
            normalized = " ".join(str(query).split())
            if normalized and normalized not in queries:
                queries.append(normalized)
        return queries

    def _search_once(self, query: str) -> List[Dict[str, str]]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    self.SEARCH_URL,
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            payload = {}
        results = self._extract_results(payload)
        if results:
            return results
        results = self._search_github_repositories(query)
        if results:
            return results
        return self._search_bing_html(query)

    def _extract_results(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        if payload.get("AbstractURL") and payload.get("AbstractText"):
            results.append(
                {
                    "title": payload.get("Heading") or payload.get("AbstractSource") or "DuckDuckGo 摘要",
                    "url": payload.get("AbstractURL"),
                    "summary": payload.get("AbstractText") or "",
                }
            )
        for topic in payload.get("RelatedTopics") or []:
            self._append_topic(results, topic)
            if len(results) >= self.max_results:
                break
        return results[: self.max_results]

    def _append_topic(self, results: List[Dict[str, str]], topic: Dict[str, Any]) -> None:
        if "Topics" in topic:
            for child in topic.get("Topics") or []:
                self._append_topic(results, child)
            return
        text = topic.get("Text") or ""
        url = topic.get("FirstURL") or ""
        if not text or not url:
            return
        title = text.split(" - ", 1)[0].strip() or "相关资料"
        results.append({"title": title, "url": url, "summary": text})

    def _search_github_repositories(self, query: str) -> List[Dict[str, str]]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    self.GITHUB_SEARCH_URL,
                    params={"q": f"{query} sklearn", "per_page": self.max_results},
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "AI4ML-Agent"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []
        results: List[Dict[str, str]] = []
        for item in payload.get("items") or []:
            title = item.get("full_name") or item.get("name") or "GitHub 示例代码"
            url = item.get("html_url") or ""
            description = item.get("description") or "GitHub 上与当前任务相似的 sklearn 示例代码仓库。"
            language = item.get("language") or ""
            stars = item.get("stargazers_count")
            summary = f"{description} 语言：{language or '-'}，Stars：{stars if stars is not None else '-'}。"
            if url:
                results.append({"title": title, "url": url, "summary": summary})
            if len(results) >= self.max_results:
                break
        return results

    def _search_bing_html(self, query: str) -> List[Dict[str, str]]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    self.BING_SEARCH_URL,
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 AI4ML-Agent/1.0"},
                )
                response.raise_for_status()
        except Exception:
            # 联网搜索是增强能力，失败不能阻断核心建模流程。
            return []
        return self._extract_bing_results(response.text)

    def _extract_bing_results(self, html: str) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        for match in re.finditer(r'<li class="b_algo"[\s\S]*?(?=<li class="b_algo"|</ol>)', html):
            block = match.group(0)
            title_match = re.search(r"<h2[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", block, re.S)
            if not title_match:
                continue
            snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
            title = self._clean_html(title_match.group(2))
            url = unescape(title_match.group(1))
            summary = self._clean_html(snippet_match.group(1)) if snippet_match else title
            if title and url:
                results.append({"title": title, "url": url, "summary": summary})
            if len(results) >= self.max_results:
                break
        return results

    def _clean_html(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", "", value or "")
        return " ".join(unescape(text).split())

    def _is_relevant_result(self, item: Dict[str, str]) -> bool:
        text = " ".join([item.get("title", ""), item.get("summary", ""), item.get("url", "")]).lower()
        keywords = [
            "sklearn",
            "scikit",
            "machine learning",
            "classification",
            "regression",
            "pipeline",
            "classifier",
            "predict",
            "model",
            "feature",
            "github.com",
        ]
        return any(keyword in text for keyword in keywords)
