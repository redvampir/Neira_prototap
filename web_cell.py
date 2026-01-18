"""
Neira Web Cell v0.4
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from dataclasses import dataclass
from html import unescape
from typing import Any, Dict, List, Optional, Sequence, Tuple

from neira.utils.web_search_utils import (
    env_bool,
    env_int,
    env_str,
    is_allowed_domain,
    normalize_domains,
    resolve_ddg_url,
)

logger = logging.getLogger(__name__)


def _module_available(name: str) -> bool:
    if name in sys.modules:
        return True
    return importlib.util.find_spec(name) is not None


REQUESTS_AVAILABLE = _module_available("requests")
DDGS_AVAILABLE = _module_available("ddgs")

if REQUESTS_AVAILABLE:
    import requests
else:
    requests = None  # type: ignore

if DDGS_AVAILABLE:
    from ddgs import DDGS
    try:
        from ddgs.exceptions import DDGSException
    except (ImportError, AttributeError):
        DDGSException = None  # type: ignore
else:
    DDGS = None  # type: ignore
    DDGSException = None  # type: ignore

if REQUESTS_AVAILABLE and requests is not None:
    _request_exc = getattr(requests, "RequestException", Exception)
    REQUESTS_ERROR = (_request_exc, Exception)
else:
    REQUESTS_ERROR = (RuntimeError, OSError, Exception)

DDGS_ERROR = (RuntimeError, OSError, ValueError, TypeError, AttributeError)
if DDGSException is not None:
    DDGS_ERROR = DDGS_ERROR + (DDGSException,)
REQUESTS_PARSE_ERROR = REQUESTS_ERROR + (ValueError, TypeError)

from cells import (
    DEFAULT_MAX_RESPONSE_TOKENS,
    OLLAMA_NUM_CTX,
    Cell,
    CellResult,
    MemoryCell,
    MODEL_REASON,
    OLLAMA_URL,
    TIMEOUT,
    _MODEL_LAYERS,
    _merge_system_prompt,
)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DEFAULT_MAX_RESULTS = 5
DEFAULT_LEARN_RESULTS = 7
MAX_REQUEST_TIMEOUT = 60
DEFAULT_REQUEST_TIMEOUT = env_int("NEIRA_WEB_REQUEST_TIMEOUT", 10, min_value=1, max_value=MAX_REQUEST_TIMEOUT)
DEFAULT_SUMMARY_MAX_TOKENS = 2048
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
WEB_SEARCH_BACKEND = env_str("NEIRA_WEB_SEARCH_BACKEND", "auto").lower()
if WEB_SEARCH_BACKEND not in {"auto", "ddgs", "html"}:
    WEB_SEARCH_BACKEND = "auto"
WEB_SEARCH_DOMAIN_FALLBACK = env_bool("NEIRA_WEB_SEARCH_DOMAIN_FALLBACK", True)

HTML_TAG_RE = re.compile(r"<[^>]+>")
DDG_RESULT_RE = re.compile(r'<div[^>]*class="result__body"[^>]*>(.*?)</div>', re.S)
DDG_TITLE_RE = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
DDG_SNIPPET_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</', re.S)


def _build_ollama_options(temperature: float, max_tokens: int) -> Dict[str, Any]:
    options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
    if OLLAMA_NUM_CTX:
        options["num_ctx"] = OLLAMA_NUM_CTX
    if _MODEL_LAYERS is not None:
        adapter = _MODEL_LAYERS.get_active_adapter(MODEL_REASON)
        if adapter:
            options["adapter"] = adapter
    return options


def _merge_layer_system_prompt(base_prompt: str) -> str:
    if _MODEL_LAYERS is None:
        return base_prompt
    layer_prompt = _MODEL_LAYERS.get_active_prompt(MODEL_REASON)
    return _merge_system_prompt(base_prompt, layer_prompt)


def _build_reason(reason_code: str, reason_detail: str) -> Dict[str, str]:
    return {"reason_code": reason_code, "reason_detail": reason_detail}


def _strip_html(text: str) -> str:
    return HTML_TAG_RE.sub("", unescape(text or "")).strip()


def _parse_ddg_html(html_text: str, max_results: int) -> List["SearchResult"]:
    results: List[SearchResult] = []
    for block in DDG_RESULT_RE.findall(html_text):
        title_match = DDG_TITLE_RE.search(block)
        if not title_match:
            continue
        url = resolve_ddg_url(unescape(title_match.group(1)))
        title = _strip_html(title_match.group(2))
        snippet_match = DDG_SNIPPET_RE.search(block)
        snippet = _strip_html(snippet_match.group(1) if snippet_match else "")
        results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break
    return results


@dataclass
class SearchResult:
    """\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u043f\u043e\u0438\u0441\u043a\u0430."""

    title: str
    url: str
    snippet: str


class WebSearchCell(Cell):
    """\u041a\u043b\u0435\u0442\u043a\u0430 \u0432\u0435\u0431-\u043f\u043e\u0438\u0441\u043a\u0430."""

    name = "web_search"
    system_prompt = (
        "\u0422\u044b \u0438\u0449\u0435\u0448\u044c \u043e\u0442\u0432\u0435\u0442 \u0438 \u043a\u0440\u0430\u0442\u043a\u043e \u043e\u0431\u043e\u0431\u0449\u0430\u0435\u0448\u044c \u0441\u0443\u0442\u044c. "
        "\u041e\u043f\u0438\u0440\u0430\u0439\u0441\u044f \u043d\u0430 \u0444\u0430\u043a\u0442\u044b \u0438 \u0443\u043a\u0430\u0437\u044b\u0432\u0430\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438."
    )

    def __init__(self, memory: Optional[MemoryCell] = None):
        super().__init__(memory)
        self.ddgs = None
        self._ddg_error: Optional[str] = None
        self._use_ddgs = WEB_SEARCH_BACKEND in {"auto", "ddgs"}
        if not self._use_ddgs:
            self._ddg_error = "ddgs disabled"
        if self._use_ddgs and DDGS_AVAILABLE and DDGS is not None:
            try:
                self.ddgs = DDGS()
            except DDGS_ERROR as exc:
                self.ddgs = None
                self._ddg_error = str(exc)
                logger.warning("DDGS init failed: %s", exc)

    def _search_ddgs(
        self,
        query: str,
        max_results: int,
        allowed_domains: Sequence[str],
    ) -> Tuple[List[SearchResult], Dict[str, str]]:
        if not self.ddgs:
            reason_detail = self._ddg_error or "ddgs module not available"
            return [], _build_reason("ddg_unavailable", reason_detail)
        try:
            results: List[SearchResult] = []
            for item in self.ddgs.text(query, max_results=max_results):
                url = resolve_ddg_url(str(item.get("href", "")))
                if not url or not is_allowed_domain(url, allowed_domains):
                    continue
                results.append(
                    SearchResult(
                        title=str(item.get("title", "")),
                        url=url,
                        snippet=str(item.get("body", "")),
                    )
                )
                if len(results) >= max_results:
                    break
            if results:
                return results, {}
            return [], _build_reason("no_results", "no results from ddgs")
        except DDGS_ERROR as exc:
            return [], _build_reason("ddg_error", str(exc))

    def _search_ddg_html(
        self,
        query: str,
        max_results: int,
        allowed_domains: Sequence[str],
    ) -> Tuple[List[SearchResult], Dict[str, str]]:
        if not REQUESTS_AVAILABLE or requests is None:
            return [], _build_reason("requests_unavailable", "requests module not available")
        try:
            response = requests.get(
                DDG_HTML_URL,
                params={"q": query},
                headers={"User-Agent": DEFAULT_USER_AGENT},
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except REQUESTS_ERROR as exc:
            return [], _build_reason("requests_error", str(exc))
        results = _parse_ddg_html(response.text, max_results)
        filtered = [r for r in results if is_allowed_domain(r.url, allowed_domains)]
        if filtered:
            return filtered, {}
        return [], _build_reason("no_results", "no results after domain filter")

    def _search_with_domains(
        self,
        query: str,
        max_results: int,
        allowed_domains: Sequence[str],
        searchers: Sequence,
    ) -> Tuple[List[SearchResult], Dict[str, str]]:
        if not allowed_domains or not searchers:
            return [], _build_reason("no_results", "no domain queries")
        aggregated: List[SearchResult] = []
        seen: set[str] = set()
        last_reason: Dict[str, str] = {}
        for domain in allowed_domains:
            domain_query = f"site:{domain} {query}"
            for searcher in searchers:
                results, reason = searcher(domain_query, max_results, allowed_domains)
                if results:
                    for item in results:
                        if item.url in seen:
                            continue
                        seen.add(item.url)
                        aggregated.append(item)
                        if len(aggregated) >= max_results:
                            return aggregated, {}
                if reason:
                    last_reason = reason
            if aggregated:
                return aggregated, {}
        return [], last_reason or _build_reason("no_results", "no domain results")

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        allowed_domains: Optional[Sequence[str]] = None,
        use_html_fallback: bool = False,
    ) -> Tuple[List[SearchResult], Dict[str, str]]:
        """\u0418\u0449\u0435\u0442 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0438 \u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u0442 (results, reason)."""

        allowed = normalize_domains(allowed_domains)
        searchers: List = []
        if self._use_ddgs:
            searchers.append(self._search_ddgs)
        use_html = use_html_fallback or WEB_SEARCH_BACKEND == "html"
        if use_html:
            searchers.append(self._search_ddg_html)
        if not searchers:
            return [], _build_reason("search_unavailable", "no search backend")

        last_reason: Dict[str, str] = {}
        for searcher in searchers:
            results, reason = searcher(query, max_results, allowed)
            if results:
                return results, {}
            if reason:
                last_reason = reason

        if WEB_SEARCH_DOMAIN_FALLBACK and allowed:
            domain_results, domain_reason = self._search_with_domains(
                query, max_results, allowed, searchers
            )
            if domain_results:
                return domain_results, {}
            if domain_reason:
                last_reason = domain_reason

        return [], last_reason or _build_reason("no_results", "no results")

    def _build_context(self, results: List[SearchResult]) -> str:
        lines = ["\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u043f\u043e\u0438\u0441\u043a\u0430:\n"]
        for idx, result in enumerate(results, 1):
            lines.append(f"{idx}. {result.title}\n{result.snippet}\n\u0421\u0441\u044b\u043b\u043a\u0430: {result.url}\n")
        return "\n".join(lines)

    def _summarize(self, query: str, context: str) -> Tuple[str, Dict[str, str]]:
        if not REQUESTS_AVAILABLE or requests is None:
            return "", _build_reason("requests_unavailable", "requests module not available")
        prompt = (
            "\u0412\u043e\u043f\u0440\u043e\u0441: "
            f"{query}\n\n{context}\n\n"
            "\u0421\u043e\u0441\u0442\u0430\u0432\u044c \u043a\u0440\u0430\u0442\u043a\u0438\u0439 \u043e\u0442\u0432\u0435\u0442 \u0441 \u0443\u043a\u0430\u0437\u0430\u043d\u0438\u0435\u043c \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432."
        )
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": _merge_layer_system_prompt(self.system_prompt),
                    "stream": False,
                    "options": _build_ollama_options(
                        0.5, min(DEFAULT_MAX_RESPONSE_TOKENS, DEFAULT_SUMMARY_MAX_TOKENS)
                    ),
                },
                timeout=TIMEOUT,
            )
            data = response.json()
        except REQUESTS_PARSE_ERROR as exc:
            return "", _build_reason("requests_error", str(exc))
        return str(data.get("response", "")), {}

    def search_and_summarize(self, query: str) -> CellResult:
        """\u041f\u043e\u0438\u0441\u043a + \u043a\u0440\u0430\u0442\u043a\u043e\u0435 \u043e\u0431\u043e\u0431\u0449\u0435\u043d\u0438\u0435."""

        results, reason = self.search(query, max_results=DEFAULT_MAX_RESULTS)
        if not results:
            reason = reason or _build_reason("no_results", "no results")
            code = reason.get("reason_code", "unknown")
            detail = reason.get("reason_detail", "")
            content = (
                "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0432\u0435\u0431-\u043f\u043e\u0438\u0441\u043a "
                f"(\u043f\u0440\u0438\u0447\u0438\u043d\u0430: {code}; reason_code: {code}). {detail}"
            )
            return CellResult(content=content, confidence=0.1, cell_name=self.name, metadata=reason)

        context = self._build_context(results)
        answer, summary_reason = self._summarize(query, context)
        if summary_reason:
            code = summary_reason.get("reason_code", "unknown")
            detail = summary_reason.get("reason_detail", "")
            content = (
                "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u043a\u0440\u0430\u0442\u043a\u0438\u0439 \u043e\u0442\u0432\u0435\u0442 "
                f"(reason_code: {code}). {detail}"
            )
            return CellResult(content=content, confidence=0.1, cell_name=self.name, metadata=summary_reason)

        return CellResult(
            content=answer,
            confidence=0.7,
            cell_name=self.name,
            metadata={
                "query": query,
                "sources": [r.url for r in results],
                "results_count": len(results),
            },
        )

    def learn_topic(
        self,
        topic: str,
        max_results: int = DEFAULT_LEARN_RESULTS,
        allowed_domains: Optional[Sequence[str]] = None,
        use_html_fallback: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """\u0421\u043e\u0431\u0438\u0440\u0430\u0435\u0442 \u0444\u0430\u043a\u0442\u044b \u043f\u043e \u0442\u0435\u043c\u0435."""

        results, reason = self.search(
            topic,
            max_results=max_results,
            allowed_domains=allowed_domains,
            use_html_fallback=use_html_fallback,
        )
        if not results:
            return [], reason or _build_reason("no_results", "no results")
        if not REQUESTS_AVAILABLE or requests is None:
            return [], _build_reason("requests_unavailable", "requests module not available")

        all_text = "\n".join([f"{r.title}: {r.snippet}" for r in results])
        prompt = (
            "\u0422\u0435\u043c\u0430: "
            f"{topic}\n\n"
            "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438:\n"
            f"{all_text}\n\n"
            "\u0412\u044b\u0434\u0435\u043b\u0438 \u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0435 \u0444\u0430\u043a\u0442\u044b. \u041e\u0442\u0432\u0435\u0442 \u0441\u0442\u0440\u043e\u0433\u043e JSON:\n"
            "{\"facts\": [{\"text\": \"...\", \"importance\": 0.0}] }"
        )
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": _merge_layer_system_prompt("\u0422\u043e\u043b\u044c\u043a\u043e JSON."),
                    "stream": False,
                    "options": _build_ollama_options(0.3, min(DEFAULT_MAX_RESPONSE_TOKENS, 1024)),
                },
                timeout=TIMEOUT,
            )
            result = response.json().get("response", "")
        except REQUESTS_PARSE_ERROR as exc:
            return [], _build_reason("requests_error", str(exc))

        start = result.find("{")
        end = result.rfind("}") + 1
        if start < 0 or end <= start:
            return [], _build_reason("parse_error", "no JSON in response")
        try:
            data = json.loads(result[start:end])
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return [], _build_reason("parse_error", str(exc))
        facts = data.get("facts", []) if isinstance(data, dict) else []
        for fact in facts:
            fact["source"] = "web"
            fact["category"] = "learned"
            fact["topic"] = topic
        return facts, {}

    def process(self, query: str) -> CellResult:
        return self.search_and_summarize(query)


class WebLearnerCell(Cell):
    """\u041a\u043b\u0435\u0442\u043a\u0430 \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u044f \u0441 \u0432\u0435\u0431\u0430."""

    name = "web_learner"

    def __init__(self, memory: MemoryCell):
        super().__init__(memory)
        self.searcher = WebSearchCell(memory)

    def learn(self, topic: str) -> CellResult:
        facts, reason = self.searcher.learn_topic(topic)
        if not facts:
            meta = reason or {}
            content = (
                "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043d\u0430\u0439\u0442\u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u043f\u043e \u0442\u0435\u043c\u0435: "
                f"{topic}"
            )
            return CellResult(content=content, confidence=0.2, cell_name=self.name, metadata=meta)

        saved = 0
        for fact in facts:
            if fact.get("importance", 0) >= 0.5:
                self.memory.remember(
                    text=fact["text"],
                    importance=fact.get("importance", 0.6),
                    category="learned",
                    source="web",
                )
                saved += 1

        summary = (
            "\u0422\u0435\u043c\u0430: "
            f"{topic}\n"
            f"\u0424\u0430\u043a\u0442\u043e\u0432: {len(facts)}\n"
            f"\u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {saved}\n\n"
            "\u041f\u0440\u0438\u043c\u0435\u0440\u044b:\n"
        )
        for fact in facts[:5]:
            summary += f"- {fact['text']}\n"

        return CellResult(
            content=summary,
            confidence=0.8,
            cell_name=self.name,
            metadata={"topic": topic, "facts_found": len(facts), "facts_saved": saved},
        )

    def process(self, topic: str) -> CellResult:
        return self.learn(topic)


if __name__ == "__main__":
    print("=" * 50)
    print("WebSearchCell")
    print("=" * 50)

    cell = WebSearchCell()
    result = cell.process("\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043f\u043e\u0438\u0441\u043a\u0430")
    print(result.content)
