"""
OrganCreationEngine — оркестратор создания и тестирования органов/клеток

Задачи:
- Использует `CellFactory` для генерации кода клетки
- Автоматически импортирует и прогоняет базовый тест через `DynamicCellLoader`
- При неудаче делает повторную генерацию с подсказками из `ExperienceSystem` и `LETTER_TO_NEIRA.txt`
- Возвращает подробный отчёт
"""
from typing import Optional, Dict, Any, Tuple
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

    def _ensure_hybrid_registration(
        self,
        cell: Any,
        author_id: int
    ) -> Tuple[bool, str, str]:
        try:
            from neira.organs.hybrid_system import get_hybrid_organ_system
        except ImportError:
            return False, 'hybrid_unavailable', ''

        try:
            system = get_hybrid_organ_system()
        except (RuntimeError, OSError, ValueError):
            return False, 'hybrid_unavailable', ''

        try:
            entry = system.get_organ(cell.cell_name)
        except (AttributeError, RuntimeError, OSError, ValueError):
            entry = None

        if entry:
            return True, 'already_registered', entry.organ_id

        triggers = list(getattr(cell, 'command_triggers', []) or [])
        task_pattern = getattr(cell, 'task_pattern', '')
        if task_pattern:
            triggers.append(task_pattern)
        triggers = [t for t in triggers if t]
        if not triggers:
            return False, 'empty_triggers', ''

        try:
            ok, msg = system.register_custom_organ(
                name=cell.cell_name,
                description=cell.description,
                cell_type='custom',
                triggers=triggers,
                code=None,
                created_by=str(author_id),
                require_approval=False,
            )
        except (AttributeError, RuntimeError, OSError, TypeError, ValueError) as e:
            logger.warning('HybridOrganSystem registration failed: %s', e)
            return False, f'register_failed: {e}', ''

        entry = system.get_organ(cell.cell_name)
        organ_id = entry.organ_id if entry else ''
        return ok, msg, organ_id

    def create_and_test_organ(
        self,
        description: str,
        author_id: int = 0,
        max_attempts: int = 2,
        *,
        force_cell_name: Optional[str] = None,
        dependency_policy: Optional[str] = None,
        skip_duplicate_check: bool = False,
        overwrite_existing: bool = False,
    ) -> Dict[str, Any]:
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

            result = self.factory.create_cell(
                pattern=pattern,
                tasks=[{"description": description}],
                author_id=author_id,
                force_cell_name=force_cell_name,
                dependency_policy=dependency_policy,
                skip_duplicate_check=skip_duplicate_check,
                overwrite_existing=overwrite_existing,
            )

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
                missing_deps = list(getattr(self.loader, "last_missing_deps", []) or [])
                if missing_deps:
                    return {
                        "success": False,
                        "missing_deps": missing_deps,
                        "cell": gen,
                        "report": "missing_deps",
                        "entrypoints": result.get("entrypoints") or getattr(gen, "entrypoints", {}),
                        "target_platforms": result.get("target_platforms") or getattr(gen, "target_platforms", []),
                        "input_modalities": result.get("input_modalities") or getattr(gen, "input_modalities", []),
                        "dependencies": result.get("dependencies") or getattr(gen, "dependencies", []),
                        "commands": result.get("commands") or getattr(gen, "command_triggers", []),
                    }

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
                    organ_registered, organ_message, organ_id = self._ensure_hybrid_registration(gen, author_id)
                    entrypoints = result.get("entrypoints") or getattr(gen, "entrypoints", {})
                    target_platforms = result.get("target_platforms") or getattr(gen, "target_platforms", [])
                    input_modalities = result.get("input_modalities") or getattr(gen, "input_modalities", [])
                    commands = result.get("commands") or getattr(gen, "command_triggers", [])
                    dependencies = result.get("dependencies") or getattr(gen, "dependencies", [])
                    return {
                        "success": True,
                        "cell": gen,
                        "report": "Создан и протестирован",
                        "entrypoints": entrypoints,
                        "target_platforms": target_platforms,
                        "input_modalities": input_modalities,
                        "commands": commands,
                        "dependencies": dependencies,
                        "organ_registered": organ_registered,
                        "organ_message": organ_message,
                        "organ_id": organ_id,
                    }
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
