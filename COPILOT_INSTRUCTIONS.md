# Инструкции для Copilot по проекту Neira

> ⚠️ **ВНИМАНИЕ:** Этот файл устарел. Используй [AGENTS.md](AGENTS.md) для полных инструкций.

---

## Быстрый старт

Основная документация для агентов находится в:
- **[AGENTS.md](AGENTS.md)** — полное руководство (читать в первую очередь)
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** — автозагрузка для GitHub Copilot

---

## Краткие правила

```
❌ Не создавай файлы в корне → neira/, scripts/, tests/
❌ Не создавай без проверки дубликатов → grep_search/file_search
❌ Не используй bare except → конкретные типы исключений
❌ Не хардкодь числа → neira/config.py
```

## Проверки

```bash
python scripts/validate_code.py файл.py  # Качество кода
python -m pytest tests/test_basic.py -x  # Базовые тесты
```

## Подсказки для промптов

- «Обнови модуль X, сохраняя структуру reason_code/reason_detail в metadata»
- «Добавь тест для функции Y в tests/»
- «Вынеси константу Z в neira/config.py»
- «Расширь существующий класс вместо создания нового»

---

**Полная документация: [AGENTS.md](AGENTS.md)**
