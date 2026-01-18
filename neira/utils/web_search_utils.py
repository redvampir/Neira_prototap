from __future__ import annotations

import os
from typing import Optional, Sequence, List
from urllib.parse import parse_qs, unquote, urlparse


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def env_int(name: str, default: int, min_value: int = 1, max_value: Optional[int] = None) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    if parsed < min_value:
        return min_value
    if max_value is not None and parsed > max_value:
        return max_value
    return parsed


def normalize_domains(domains: Optional[Sequence[str]]) -> List[str]:
    if not domains:
        return []
    normalized: List[str] = []
    for domain in domains:
        if not domain:
            continue
        value = domain.strip().lower()
        if not value:
            continue
        if "://" in value:
            value = urlparse(value).netloc
        if "/" in value:
            value = value.split("/")[0]
        if ":" in value:
            value = value.split(":")[0]
        if value.startswith("www."):
            value = value[4:]
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def is_allowed_domain(url: str, allowed_domains: Sequence[str]) -> bool:
    if not allowed_domains:
        return True
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def resolve_ddg_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
        params = parse_qs(parsed.query)
        target = params.get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url
