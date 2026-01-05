"""
Скрипт для архивации устаревших .md файлов из корня проекта.
Перемещает файлы в папку docs/_archive/ для сохранения истории.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Корень проекта
ROOT = Path(r"f:\Нейронки\prototype")
ARCHIVE_DIR = ROOT / "docs" / "_archive"

# Файлы которые ОСТАВЛЯЕМ в корне (важные)
KEEP_IN_ROOT = {
    "README.md",           # Главный README
    "AGENTS.md",           # Инструкции для AI агентов
    "COPILOT_INSTRUCTIONS.md",  # Инструкции Copilot
    "LETTER_TO_NEIRA.txt", # Не .md
    "Письмо Нейре.md",     # Личное письмо
    "FROM_CLAUDE_TO_CREATOR.md",  # Личное письмо
}

# Файлы для архивации (устаревшие или перемещённые в docs/)
FILES_TO_ARCHIVE = [
    # Память - перенесено в docs/features/memory/
    "MEMORY_MANAGEMENT.md",
    "MEMORY_PROTECTION.md", 
    "MEMORY_PROTECTION_GUIDE.md",
    "MEMORY_v3_CHECKLIST.md",
    "MEMORY_v3_DEPLOYMENT_REPORT.md",
    "MEMORY_IMPROVEMENTS_PROPOSAL.md",
    "ADVANCED_MEMORY_v0.7.md",
    "РЕШЕНИЕ_ПРОБЛЕМЫ_ПАМЯТИ.md",
    
    # Telegram - перенесено в docs/integrations/telegram/
    "TELEGRAM.md",
    "TELEGRAM_BOT_COMMANDS.md",
    "TELEGRAM_v0.7_UPDATE.md",
    "TELEGRAM_SELF_GROWTH.md",
    "TELEGRAM_PARALLEL_THINKING.md",
    "BOTFATHER_SETUP.md",
    
    # Web UI - перенесено в docs/integrations/web-ui/
    "WEB_UI_GUIDE.md",
    "WEB_UI_QUICKSTART.md",
    "DESKTOP_UI_PLAN.md",
    "DESKTOP_UI_TROUBLESHOOTING.md",
    
    # Mobile - перенесено в docs/integrations/mobile/
    "MOBILE_SETUP.md",
    "QUICK_START_MOBILE.md",
    "REMOTE_ACCESS.md",
    "FOR_WIFE_PHONE.md",
    
    # Безопасность - перенесено в docs/security/
    "SECURITY_UPDATE.md",
    "SECURITY_AUDIT_REPORT.md",
    "ORGAN_SECURITY.md",
    
    # Обучение - перенесено в docs/features/learning/
    "AUTONOMOUS_LEARNING_v1.0.md",
    "AUTONOMOUS_LEARNING_SUMMARY.md",
    "QUICKSTART_AUTONOMOUS_LEARNING.md",
    "QUICKSTART_SELF_GROWTH.md",
    
    # Артефакты - перенесено в docs/features/artifacts/
    "ARTIFACT_SYSTEM_GUIDE.md",
    "ARTIFACT_PHASE2_IMPLEMENTATION.md",
    
    # Архитектура - перенесено в docs/architecture/
    "NEIRA_ARCHITECTURE_v2.md",
    "CORTEX_README.md",
    "CORTEX_CHANGELOG.md",
    "CELL_ROUTER_ARCHITECTURE.md",
    "CELL_ROUTER_SUMMARY.md",
    "CELL_ROUTER_FINAL_REPORT.md",
    "CELL_ROUTER_TEST.md",
    
    # Гайды - перенесено в docs/guides/
    "MULTI_PROVIDER_GUIDE.md",
    "MULTIPLAYER_GUIDE.md",
    "EMOJI_FEEDBACK_GUIDE.md",
    "USER_MANAGEMENT_GUIDE.md",
    
    # Changelog/версии - перенесено в docs/changelog/
    "WHATS_NEW_v0.7.md",
    "FIXES_v0.8.3.md",
    "IMPLEMENTATION_v0.7.md",
    "TESTING_v0.7.md",
    
    # Troubleshooting - перенесено в docs/troubleshooting/
    "RUSSIAN_PATH_FIX.md",
    "ANTI_LOOP_FIX.md",
    
    # Устаревшие/временные
    "CHECKLIST_OLLAMA_INDEPENDENCE.md",
    "OLLAMA_INDEPENDENCE.md",
    "OLLAMA_INDEPENDENCE_REPORT.md",
    "PHASE1_AUTONOMY.md",
    "PHASE2_UNIFIED.md",
    "PHASE2_TEST_REPORT.md",
    "PHASE3_AUTONOMY.md",
    "NEW_FEATURES.md",
    "RHYTHM_STABILIZER_README.md",
    "RUN_NEMOTRON.md",
    "SETUP.md",
    "QUICKSTART.md",
    "TEST_RESULTS.md",
    "TEST_PROBLEM_SOLVED.md",
    "TEST_HARRY_POTTER_LIVE.md",
    "TESTING_PHASE2.md",
    "END_TO_END_TEST_REPORT.md",
    "ИСПРАВЛЕНИЯ_НЕЙРЫ_14_12_2025.md",
]

def archive_files():
    """Перемещает устаревшие файлы в архив."""
    
    # Создаём папку архива
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    archived = []
    not_found = []
    
    for filename in FILES_TO_ARCHIVE:
        src = ROOT / filename
        dst = ARCHIVE_DIR / filename
        
        if src.exists():
            shutil.move(str(src), str(dst))
            archived.append(filename)
            print(f"✅ Архивирован: {filename}")
        else:
            not_found.append(filename)
    
    print(f"\n📊 Итого:")
    print(f"   Архивировано: {len(archived)}")
    print(f"   Не найдено: {len(not_found)}")
    
    if not_found:
        print(f"\n⚠️ Не найденные файлы:")
        for f in not_found[:10]:
            print(f"   - {f}")
        if len(not_found) > 10:
            print(f"   ... и ещё {len(not_found) - 10}")
    
    # Создаём README в архиве
    readme = ARCHIVE_DIR / "README.md"
    readme.write_text(f"""# 📦 Архив документации

Устаревшие файлы документации, перемещённые из корня проекта.

**Дата архивации:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Файлов архивировано:** {len(archived)}

## Актуальная документация

Актуальная документация находится в папке `docs/`:
- [docs/README.md](../README.md) — навигация по документации

## Содержимое архива

{chr(10).join(f"- {f}" for f in archived)}
""", encoding="utf-8")
    
    print(f"\n✅ Создан README в архиве")

if __name__ == "__main__":
    print("🗂️ Архивация устаревшей документации...")
    print(f"   Источник: {ROOT}")
    print(f"   Архив: {ARCHIVE_DIR}")
    print()
    
    confirm = input("Продолжить? (y/n): ").strip().lower()
    if confirm == "y":
        archive_files()
    else:
        print("Отменено")
