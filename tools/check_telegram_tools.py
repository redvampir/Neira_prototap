#!/usr/bin/env python3
"""
Быстрая самопроверка Telegram-инструментов без запуска бота.

Проверяет:
- загрузку/сохранение telegram_settings.py (с приоритетом env)
- базовые операции enhanced_auth.py (add/remove/remove_by_identifier)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from enhanced_auth import EnhancedAuthSystem
from telegram_settings import TelegramSettings, load_telegram_settings, save_telegram_settings


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_telegram_settings() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "settings.json"

        path.write_text(
            json.dumps(
                {"access_mode": "whitelist", "allowed_channels": [-1001, -1002], "mention_only": True},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        s = load_telegram_settings(path, env={})
        _assert(s.access_mode == "whitelist", "ожидался access_mode=whitelist из файла")
        _assert(s.allowed_channels == {-1001, -1002}, "ожидались allowed_channels из файла")
        _assert(s.mention_only is True, "ожидался mention_only=true из файла")

        env = {
            "NEIRA_TG_ACCESS": "open",
            "NEIRA_TG_CHANNELS": "-2001,-2002",
            "NEIRA_TG_MENTION_ONLY": "false",
        }
        s2 = load_telegram_settings(path, env=env)
        _assert(s2.access_mode == "open", "ожидался access_mode=open из env")
        _assert(s2.allowed_channels == {-2001, -2002}, "ожидались allowed_channels из env")
        _assert(s2.mention_only is False, "ожидался mention_only=false из env")

        out = TelegramSettings(access_mode="admin_only", allowed_channels={-3001}, mention_only=False)
        save_telegram_settings(path, out)
        reloaded = load_telegram_settings(path, env={})
        _assert(reloaded.access_mode == "admin_only", "ожидался access_mode после сохранения")
        _assert(reloaded.allowed_channels == {-3001}, "ожидались allowed_channels после сохранения")
        _assert(reloaded.mention_only is False, "ожидался mention_only после сохранения")


def check_auth_system() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        auth_path = Path(tmpdir) / "auth.json"
        system = EnhancedAuthSystem(auth_file=str(auth_path))

        ok, msg = system.add_user("123", authorized_by=1, note="unit-test")
        _assert(ok, f"add_user(123) не сработал: {msg}")
        _assert(system.is_authorized(123), "is_authorized(123) должен быть True")

        ok, msg = system.add_user("@some_user", authorized_by=1, note="username-test")
        _assert(ok, f"add_user(@some_user) не сработал: {msg}")

        ok, msg = system.remove_user_by_identifier("@some_user")
        _assert(ok, f"remove_user_by_identifier(@some_user) не сработал: {msg}")

        ok, msg = system.remove_user_by_identifier("123")
        _assert(ok, f"remove_user_by_identifier(123) не сработал: {msg}")
        _assert(not system.is_authorized(123), "is_authorized(123) должен быть False после удаления")


def main() -> int:
    check_telegram_settings()
    check_auth_system()
    print("OK: telegram инструменты прошли самопроверку")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
