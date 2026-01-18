# -*- coding: utf-8 -*-
"""
Мини-бенч автономности через HTTP API сервера Neira.

Запускает набор сценариев (по умолчанию: "писательница") и измеряет:
- долю ответов model=autonomous
- латентность
- основные метрики из /autonomy/stats
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests


DEFAULT_SERVER_URL = "http://127.0.0.1:8766"
DEFAULT_TIMEOUT_SEC = 120


def _load_scenarios(path: str) -> list[str]:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(str(src))
    lines = src.read_text(encoding="utf-8").splitlines()
    prompts = [line.strip() for line in lines if line.strip()]
    if not prompts:
        raise ValueError("Пустой файл сценариев")
    return prompts


def _default_writer_scenarios() -> list[str]:
    return [
        "Привет. Я пишу роман. Помоги придумать конфликт первого акта и ставки для героини.",
        "Мир: альтернативная Россия 2040. Тема: цена бессмертия. Придумай логлайн в 1-2 предложения.",
        "Дай 5 вариантов главной героини с мотивацией и внутренней травмой.",
        "Сделай краткий синопсис на 12 сцен (по 1 строке на сцену).",
        "Предложи 3 неожиданных поворота в середине истории, но без магии и без клише.",
        "Помоги переписать диалог: героиня скрывает правду, собеседник почти догадался.",
        "Составь список вопросов, чтобы уточнить тон романа и аудиторию.",
        "Дай план главы 1: крючок, экспозиция, инцидент, мини-кульминация.",
    ]


def _post_chat(server_url: str, message: str, user_id: str) -> dict[str, Any]:
    payload = {"message": message, "user_id": user_id, "request_id": f"bench-{int(time.time()*1000)%1_000_000:06d}"}
    r = requests.post(f"{server_url}/chat", json=payload, timeout=DEFAULT_TIMEOUT_SEC)
    r.raise_for_status()
    data = r.json()
    if not data.get("success", False):
        raise RuntimeError(data.get("error") or "Unknown error")
    return data.get("data", {})


def _get_autonomy_stats(server_url: str) -> dict[str, Any]:
    r = requests.get(f"{server_url}/autonomy/stats", timeout=DEFAULT_TIMEOUT_SEC)
    r.raise_for_status()
    payload = r.json()
    return payload.get("data", {}) if payload.get("success") else {"error": payload.get("error")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help="База URL сервера (например http://127.0.0.1:8766)")
    parser.add_argument("--user-id", default="writer_bench", help="user_id для контекстного кеша")
    parser.add_argument("--scenarios", help="Файл со сценариями (по одной строке на запрос)")
    parser.add_argument("--save", help="Куда сохранить JSON (например artifacts/autonomy_bench.json)")
    args = parser.parse_args()

    scenarios = _load_scenarios(args.scenarios) if args.scenarios else _default_writer_scenarios()

    results: list[dict[str, Any]] = []
    autonomous = 0

    t0 = time.perf_counter()
    for idx, prompt in enumerate(scenarios, start=1):
        start = time.perf_counter()
        out = _post_chat(args.url, prompt, args.user_id)
        dt_ms = (time.perf_counter() - start) * 1000
        model = out.get("model") or "unknown"
        if model == "autonomous":
            autonomous += 1
        results.append(
            {
                "i": idx,
                "prompt": prompt,
                "model": model,
                "latency_ms": round(dt_ms, 1),
                "response_preview": (out.get("response") or "")[:200],
            }
        )
        print(f"[{idx}/{len(scenarios)}] model={model} latency_ms={dt_ms:.1f}")

    total_s = time.perf_counter() - t0
    autonomy_rate = (autonomous / len(scenarios)) if scenarios else 0.0
    stats = _get_autonomy_stats(args.url)

    report = {
        "server_url": args.url,
        "user_id": args.user_id,
        "scenarios_total": len(scenarios),
        "autonomous_count": autonomous,
        "autonomy_rate": autonomy_rate,
        "total_time_sec": round(total_s, 2),
        "results": results,
        "autonomy_stats": stats,
    }

    print("-" * 60)
    print(f"Autonomy (bench): {autonomous}/{len(scenarios)} = {autonomy_rate:.0%}")
    if isinstance(stats, dict) and stats:
        metrics = stats.get("metrics", {})
        if isinstance(metrics, dict) and metrics:
            strict = metrics.get("autonomy_rate_strict", metrics.get("autonomy_rate"))
            print(f"Autonomy (engine): {strict}%")

    if args.save:
        dst = Path(args.save)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
