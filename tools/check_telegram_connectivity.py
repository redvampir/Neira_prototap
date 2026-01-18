#!/usr/bin/env python3
"""
Диагностика подключения к Telegram API без запуска polling.

Что проверяет:
- доступность `getMe` по токену TELEGRAM_BOT_TOKEN
- корректность прокси/таймаутов (через переменные окружения)

Важно: токен в вывод НЕ печатается.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram_network import load_telegram_network_config, sanitize_url_for_log


_TOKEN_RE = re.compile(r"\\bbot\\d+:[A-Za-z0-9_-]+\\b")
_TG_URL_RE = re.compile(r"(https?://api\\.telegram\\.org/bot)[^/\\s]+", flags=re.IGNORECASE)
_URL_CREDENTIALS_RE = re.compile(r"(://)([^/@\\s]+@)")


def _load_env_fallback(env_path: Path) -> None:
    data = None
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            data = env_path.read_text(encoding=encoding)
            break
        except Exception:
            continue

    if data is None:
        return

    for raw in data.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key or key in os.environ:
            continue
        os.environ[key] = value


def _load_env_from_repo() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return

    if load_dotenv is not None:
        try:
            load_dotenv(dotenv_path=env_path, override=False)
            return
        except UnicodeDecodeError:
            pass
        except Exception:
            return

    _load_env_fallback(env_path)


def _mask_token(token: str) -> str:
    token = token.strip()
    if ":" in token:
        bot_id = token.split(":", 1)[0]
        if bot_id.isdigit():
            return f"{bot_id}:***"
    return "***"


def _safe_error_text(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}"
    text = _TOKEN_RE.sub("bot<redacted>", text)
    text = _TG_URL_RE.sub(r"\\1<redacted>", text)
    text = _URL_CREDENTIALS_RE.sub(r"\\1***@", text)
    return text


def _build_getme_url(token: str, base_url: str | None) -> str:
    if base_url:
        base = base_url.rstrip("/")
    else:
        base = "https://api.telegram.org"

    if base.endswith("/bot"):
        return f"{base}{token}/getMe"
    return f"{base}/bot{token}/getMe"


def main() -> int:
    _load_env_from_repo()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан в окружении/.env")
        return 2

    network = load_telegram_network_config()
    url = _build_getme_url(token, network.base_url)

    proxy_info = sanitize_url_for_log(network.proxy_url) if network.proxy_url else "нет"
    base_url_info = sanitize_url_for_log(network.base_url) if network.base_url else "по умолчанию"

    print("Проверка Telegram API: getMe")
    print(f"- Токен: {_mask_token(token)}")
    print(f"- base_url: {base_url_info}")
    print(f"- proxy: {proxy_info}")
    print(
        f"- таймауты (connect/read/write/pool): "
        f"{network.connect_timeout}/{network.read_timeout}/{network.write_timeout}/{network.pool_timeout} сек"
    )

    timeout = httpx.Timeout(
        connect=network.connect_timeout,
        read=network.read_timeout,
        write=network.write_timeout,
        pool=network.pool_timeout,
    )

    try:
        with httpx.Client(timeout=timeout, proxy=network.proxy_url) as client:
            resp = client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        print(f"Ошибка сети: {_safe_error_text(exc)}")
        print("Подсказки:")
        print("- Проверьте доступ к интернету/фаервол/VPN")
        print("- Если Telegram недоступен напрямую, задайте NEIRA_TG_PROXY_URL")
        print("- Попробуйте увеличить NEIRA_TG_CONNECT_TIMEOUT")
        return 1

    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        print(f"Ошибка: неожиданный Content-Type: {content_type!r} (status={resp.status_code})")
        return 1

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(f"Ошибка: ответ не является JSON (status={resp.status_code})")
        return 1

    ok = data.get("ok")
    if ok is True:
        result = data.get("result") or {}
        username = result.get("username")
        first_name = result.get("first_name")
        bot_id = result.get("id")
        print("OK: Telegram API доступен, getMe успешен")
        print(f"- bot_id: {bot_id}")
        print(f"- username: @{username}" if username else "- username: (не задан)")
        print(f"- first_name: {first_name!r}" if first_name else "- first_name: (не задан)")
        return 0

    error_code = data.get("error_code")
    description = data.get("description")
    print("Ошибка Telegram API:")
    print(f"- status: {resp.status_code}")
    print(f"- error_code: {error_code}")
    print(f"- description: {description!r}")

    if resp.status_code == 401 or error_code == 401:
        print("Похоже, токен неверный/отозван. Проверьте TELEGRAM_BOT_TOKEN в .env")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
