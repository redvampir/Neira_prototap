"""
OrganCreationEngine — оркестратор создания и тестирования органов/клеток

Задачи:
- Использует `CellFactory` для генерации кода клетки
- Автоматически импортирует и прогоняет базовый тест через `DynamicCellLoader`
- При неудаче делает повторную генерацию с подсказками из `ExperienceSystem` и `LETTER_TO_NEIRA.txt`
- Возвращает подробный отчёт
"""
from typing import Optional, Dict, Any
import logging
from pathlib import Path
from time import sleep

from cell_factory import CellFactory
from dynamic_cell_loader import DynamicCellLoader
from experience import ExperienceSystem

logger = logging.getLogger("OrganCreationEngine")


LETTER_PATH = Path("LETTER_TO_NEIRA.txt")


class OrganCreationEngine:
    def __init__(self):
        self.experience = ExperienceSystem()
        self.factory = CellFactory(experience=self.experience)
        self.loader = DynamicCellLoader(memory=None)

    def _augment_with_letter(self, prompt: str) -> str:
        """Добавить выдержки из письма Claude для улучшения спецификации"""
        try:
            text = LETTER_PATH.read_text(encoding="utf-8")
        except Exception:
            return prompt

        # Берём первые 3 параграфа (ориентир) и добавляем в промпт
        paras = [p.strip() for p in text.split('\n\n') if p.strip()]
        top = "\n\n".join(paras[:3])
        return f"{prompt}\n\n#GuidingPrinciples:\n{top}"

    def create_and_test_organ(self, description: str, author_id: int = 0, max_attempts: int = 2) -> Dict[str, Any]:
        """Попытаться создать орган и протестировать его работоспособность.

        Возвращает dict с ключами: success, report, cell (если есть), quarantined
        """
        attempt = 0
        last_report = ""

        while attempt < max_attempts:
            attempt += 1
            logger.info("OrganCreation: attempt %s for '%s'", attempt, description)

            # Для первой попытки используем оригинальное описание, дальше добавляем письмо
            pattern = description if attempt == 1 else self._augment_with_letter(description)

            result = self.factory.create_cell(pattern=pattern, tasks=[{"description": description}], author_id=author_id)

            # Если был карантин или опасность — вернём как есть
            if result.get("quarantined"):
                return {"success": False, "quarantined": True, "report": result.get("message") or result.get("report"), "organ_id": result.get("organ_id")}

            if not result.get("success"):
                last_report = result.get("error", "unknown")
                logger.warning("Орган не создан: %s", last_report)
                # попробуем снова (если есть попытки)
                sleep(0.5)
                continue

            # Импортируем и тестируем
            gen = result.get("cell")
            if not gen:
                last_report = "Нет метаданных сгенерированной клетки"
                continue

            filepath = gen.file_path
            loaded = self.loader.import_cell_from_file(filepath)

            if not loaded or not loaded.instance:
                last_report = f"Ошибка импорта клетки из {filepath}"
                logger.warning(last_report)
                # удаляем файл и попробуем снова
                try:
                    Path(filepath).unlink()
                except Exception:
                    pass
                continue

            # Базовый smoke test: вызвать process с коротким вводом и проверить ответ
            try:
                inst = loaded.instance
                test_input = description[:200]
                out = inst.process(test_input)
                ok = False

                # Проверяем разные возможные форматы возврата
                if out is None:
                    ok = False
                elif isinstance(out, str):
                    ok = len(out.strip()) > 0
                elif hasattr(out, 'content'):
                    ok = bool(getattr(out, 'content', None))
                else:
                    ok = True

                if ok:
                    logger.info("Орган успешно сгенерирован и прошёл smoke-test: %s", gen.cell_name)
                    # Пометим как активный в реестре (уже активен по умолчанию для safe)
                    return {"success": True, "cell": gen, "report": "Создан и протестирован"}
                else:
                    last_report = "Smoke-test вернул пустой результат"
                    logger.warning(last_report)
                    try:
                        Path(filepath).unlink()
                    except Exception:
                        pass
                    continue

            except Exception as e:
                last_report = f"Ошибка во время теста: {e}"
                logger.exception(last_report)
                try:
                    Path(filepath).unlink()
                except Exception:
                    pass
                continue

        # Если вышли из цикла без успеха — помещаем в карантин через guardian
        logger.error("Не удалось автоматически создать работающий орган: %s", description)
        return {"success": False, "quarantined": True, "report": last_report}


def train_neira_from_letter():
    """Загрузить уроки из `LETTER_TO_NEIRA.txt` в ExperienceSystem как инсайты/правила."""
    exp = ExperienceSystem()
    try:
        text = LETTER_PATH.read_text(encoding="utf-8")
    except Exception:
        return False

    # Разбить на параграфы и добавить как инсайты
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    for p in paras[:20]:
        if p not in exp.personality.get("insights", []):
            exp.personality.setdefault("insights", []).append(p[:1000])

    exp.save_personality()
    logger.info("Neira trained with LETTER_TO_NEIRA (added %s insights)", min(len(paras), 20))
    return True
