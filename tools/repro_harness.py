"""Простой прогон 20 запросов для воспроизведения поведения Neira.

Формат вывода: request_id | task_type | model | fallback_reason | len_raw | preview
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from main import Neira


def _collect_prompts() -> List[str]:
    return [
        "Сгенерируй список из 5 идей стартапов в сфере образования",
        "Напиши функцию Python для суммы чисел массива",
        "Сделай краткий пересказ новости о технологиях",
        "Расскажи шутку про программистов",
        "Нужно ли искать в интернете последние курсы валют?",
        "Переведи фразу 'Hello, world' на испанский",
        "Составь план путешествия в Токио на 3 дня",
        "Определи сложность задачи сортировки списка",
        "Как оптимизировать SQL запрос на JOIN двух таблиц?",
        "Предложи вопрос для собеседования по Python",
        "Спроси у пользователя его любимый фильм",
        "Объясни разницу между TCP и UDP",
        "Сгенерируй шаблон README для проекта Flask",
        "Найди идеи для подарка разработчику",
        "Придумай название для приложения заметок",
        "Объясни, что такое асимптотическая сложность",
        "Нужно ли писать тесты для функции деления?",
        "Какие источники лучше для изучения Rust?",
        "Составь SQL запрос для выборки пользователей старше 30 лет",
        "Как настроить кэширование HTTP ответа?",
    ]


def _format_table(rows: List[Dict[str, Any]]) -> str:
    headers = ["request_id", "task_type", "model", "fallback_reason", "len_raw", "preview"]
    col_widths = {h: max(len(h), *(len(str(row.get(h, ""))) for row in rows)) for h in headers}

    def _render_row(row: Dict[str, Any]) -> str:
        cells = []
        for h in headers:
            value = str(row.get(h, ""))
            cells.append(value.ljust(col_widths[h]))
        return " | ".join(cells)

    lines = [" | ".join(h.ljust(col_widths[h]) for h in headers)]
    lines.append("-+-".join("-" * col_widths[h] for h in headers))
    lines.extend(_render_row(r) for r in rows)
    return "\n".join(lines)


def main() -> int:
    prompts = _collect_prompts()
    neira = Neira(verbose=False)
    rows: List[Dict[str, Any]] = []

    for prompt in prompts:
        try:
            _response, meta = neira.process(prompt, return_meta=True)
        except Exception as exc:  # noqa: BLE001
            meta = {
                "request_id": "error",
                "task_type": "unknown",
                "model": "n/a",
                "fallback_reason": str(exc),
                "len_raw": 0,
                "preview": "",
            }
        preview = (meta.get("preview") or "")[:60].replace("\n", " ")
        rows.append(
            {
                "request_id": meta.get("request_id", "-"),
                "task_type": meta.get("task_type", "-"),
                "model": meta.get("model", "-"),
                "fallback_reason": meta.get("fallback_reason", ""),
                "len_raw": meta.get("len_raw", 0),
                "preview": preview,
            }
        )

    print(_format_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
