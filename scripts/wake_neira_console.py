#!/usr/bin/env python3
"""Лёгкий прогрев перед запуском Desktop UI.

Важно: прогрев именно *модели* через Ollama, без запуска Neira.
Причина: запуск Neira поднимает фоновые потоки (watchers) и в консольном
режиме иногда даёт некрасивое завершение интерпретатора на Windows.

Запуск:
  python wake_neira_console.py
"""

from __future__ import annotations

import json
import os
import urllib.request


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("NEIRA_OLLAMA_WARMUP_MODEL", "ministral-3:3b")

    try:
        result = _post_json(
            f"{base_url}/api/generate",
            {
                "model": model,
                "prompt": "ping",
                "stream": False,
            },
            timeout_seconds=30.0,
        )
        text = (result.get("response") or "").strip()
        print(f"✅ Ollama прогрета. Модель: {model}")
        if text:
            print(f"Ответ: {text[:200]}")
        return 0
    except Exception as e:
        print(f"⚠️ Прогрев Ollama не удался: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
