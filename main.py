"""
Neira v0.5 — Главный модуль (ОБНОВЛЕНО)
Оркестратор с памятью, опытом, обучением и улучшениями.

ИЗМЕНЕНИЯ v0.5:
- Четыре модели (code + reason + personality + cloud)
- Динамическое управление VRAM через ModelManager
- Умная маршрутизация по типу задачи
- Облачная модель для сложных задач
- Retry-логика при низкой оценке
- Принудительное использование инструментов

Запуск: python main.py
"""

import sys
import re
from typing import Optional, Tuple

try:
    from cells import (
        Cell, CellResult, MemoryCell,
        AnalyzerCell, PlannerCell, ExecutorCell,
        VerifierCell, FactExtractorCell,
        ensure_models_installed,
        OLLAMA_URL, MODEL_CODE, MODEL_REASON, MODEL_ROUTING,
        TIMEOUT, MAX_RETRIES, MIN_ACCEPTABLE_SCORE, USE_CLOUD_IF
    )
except ImportError:
    from cells import (
        Cell, CellResult, MemoryCell,
        AnalyzerCell, PlannerCell, ExecutorCell,
        VerifierCell, FactExtractorCell,
        ensure_models_installed,
        OLLAMA_URL
    )
    MODEL_CODE = "qwen2.5-coder:7b"
    MODEL_REASON = "mistral:7b-instruct"
    MODEL_ROUTING = {}
    TIMEOUT = 180
    MAX_RETRIES = 2
    MIN_ACCEPTABLE_SCORE = 7
    USE_CLOUD_IF = {"complexity": 5, "retries": 2}

# Model Manager
try:
    from model_manager import ModelManager
    MANAGER_AVAILABLE = True
except ImportError as e:
    MANAGER_AVAILABLE = False
    print(f"⚠️ ModelManager недоступен: {e}")


# Опциональные модули
try:
    from web_cell import WebSearchCell, WebLearnerCell
    WEB_AVAILABLE = True
except ImportError as e:
    WEB_AVAILABLE = False
    print(f"⚠️ Веб-клетки недоступны: {e}")

try:
    from code_cell import CodeCell, SelfModifyCell
    CODE_AVAILABLE = True
except ImportError as e:
    CODE_AVAILABLE = False
    print(f"⚠️ Код-клетки недоступны: {e}")

try:
    from experience import ExperienceSystem
    EXPERIENCE_AVAILABLE = True
except ImportError as e:
    EXPERIENCE_AVAILABLE = False
    print(f"⚠️ Система опыта недоступна: {e}")

try:
    from evolution_manager import EvolutionManager
    EVOLUTION_AVAILABLE = True
except ImportError as e:
    EVOLUTION_AVAILABLE = False
    print(f"⚠️ Система эволюции недоступна: {e}")


class Neira:
    """Главный класс — связывает все клетки"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        # Память
        self.memory = MemoryCell()

        # Система опыта
        if EXPERIENCE_AVAILABLE:
            self.experience = ExperienceSystem()
        else:
            self.experience = None

        # Model Manager (v0.5)
        if MANAGER_AVAILABLE:
            self.model_manager = ModelManager(max_vram_gb=8.0, verbose=verbose)
            if verbose:
                print("🔧 ModelManager инициализирован (VRAM: 8GB)")
        else:
            self.model_manager = None
            if verbose:
                print("⚠️ ModelManager недоступен, используются модели без управления VRAM")

        # Базовые клетки
        self.analyzer = AnalyzerCell(self.memory)
        self.planner = PlannerCell(self.memory)
        self.executor = ExecutorCell(self.memory)
        self.verifier = VerifierCell(self.memory)
        self.fact_extractor = FactExtractorCell(self.memory)
        
        # Обновляем системный промпт исполнителя с учётом личности
        if self.experience:
            personality_prompt = self.experience.get_personality_prompt()
            self.executor.system_prompt = personality_prompt + """
Выполни задачу по плану. В разговоре ты — участник диалога.
Если тебя спрашивают — отвечай о себе, от первого лица.
Используй контекст из памяти и свой опыт.

ВАЖНО:
- Если СУБЪЕКТ: Нейра — значит ТЫ должна действовать
- Не перекладывай работу на пользователя
- Давай конкретные результаты, а не описания планов"""
        
        # Веб-клетки
        if WEB_AVAILABLE:
            self.web_search = WebSearchCell(self.memory)
            self.web_learner = WebLearnerCell(self.memory)
        else:
            self.web_search = None
            self.web_learner = None
        
        # Код-клетки
        if CODE_AVAILABLE:
            self.code = CodeCell(self.memory, work_dir=".")
            self.self_modify = SelfModifyCell(self.memory)
        else:
            self.code = None
            self.self_modify = None

        # Система эволюции (v0.6)
        if EVOLUTION_AVAILABLE and self.experience:
            self.evolution = EvolutionManager(self.experience, self.memory, verbose=verbose)
            self.evolution.initialize()
        else:
            self.evolution = None

    def log(self, message: str):
        if self.verbose:
            print(f"\n{'='*50}\n{message}\n{'='*50}")
    
    def _parse_verification(self, verification_text: str) -> Tuple[str, int, str]:
        """Парсим результат верификации"""
        verdict = "НЕИЗВЕСТНО"
        score = 5
        problems = ""
        
        # Ищем вердикт
        if "ПРИНЯТ" in verification_text:
            verdict = "ПРИНЯТ"
        elif "ДОРАБОТАТЬ" in verification_text or "ТРЕБУЕТ_ДОРАБОТКИ" in verification_text:
            verdict = "ТРЕБУЕТ_ДОРАБОТКИ"
        elif "ОТКЛОНЁН" in verification_text:
            verdict = "ОТКЛОНЁН"
        
        # Ищем оценку
        score_match = re.search(r'ОЦЕНКА:\s*(\d+)', verification_text)
        if score_match:
            score = int(score_match.group(1))
        
        # Ищем проблемы
        problems_match = re.search(r'ПРОБЛЕМЫ:\s*(.+?)(?=КОММЕНТАРИЙ|$)', 
                                   verification_text, re.DOTALL)
        if problems_match:
            problems = problems_match.group(1).strip()
        
        return verdict, score, problems
    
    def _extract_task_type(self, analysis_text: str) -> str:
        """Извлечь тип задачи из анализа"""
        type_match = re.search(r'ТИП:\s*(\w+)', analysis_text, re.IGNORECASE)
        if type_match:
            return type_match.group(1).lower()
        return "неизвестно"
    
    def _extract_subject(self, analysis_text: str) -> str:
        """Извлечь субъект действия из анализа"""
        if "СУБЪЕКТ: Нейра" in analysis_text or "СУБЪЕКТ: нейра" in analysis_text:
            return "neira"
        elif "СУБЪЕКТ: пользователь" in analysis_text.lower():
            return "user"
        return "unknown"

    def _extract_complexity(self, analysis_text: str) -> int:
        """Извлечь сложность задачи из анализа"""
        complexity_match = re.search(r'СЛОЖНОСТЬ:\s*(\d+)', analysis_text, re.IGNORECASE)
        if complexity_match:
            return int(complexity_match.group(1))
        return 3  # По умолчанию средняя сложность

    def _should_use_cloud(self, task_type: str, complexity: int, retry_attempt: int) -> Optional[str]:
        """
        Определить, нужно ли использовать облачную модель

        Returns:
            "cloud_code" для кода, "cloud_universal" для остального, None для локальных моделей
        """
        # После первого retry → облако
        if retry_attempt >= USE_CLOUD_IF["retries"]:
            return "cloud_code" if task_type == "код" else "cloud_universal"

        # Высокая сложность → облако
        if complexity >= USE_CLOUD_IF["complexity"]:
            return "cloud_code" if task_type == "код" else "cloud_universal"

        return None

    def process(self, user_input: str) -> str:
        """Главный метод обработки запроса"""
        
        # Добавляем в контекст сессии
        self.memory.add_to_session(f"Пользователь: {user_input}")
        
        # 1. Анализ
        self.log("🔍 АНАЛИЗ")
        analysis = self.analyzer.process(user_input)
        if self.verbose:
            print(analysis.content)
        
        task_type = self._extract_task_type(analysis.content)
        subject = self._extract_subject(analysis.content)
        complexity = self._extract_complexity(analysis.content)
        needs_search = analysis.metadata.get("needs_search", False)
        needs_code = analysis.metadata.get("needs_code", False)

        # NEW v0.5: Маршрутизация модели (начальный выбор)
        if self.model_manager and MODEL_ROUTING:
            target_model = MODEL_ROUTING.get(task_type, "reason")
            if self.verbose:
                print(f"🎯 Тип задачи: {task_type}, сложность: {complexity} → модель: {target_model}")
            self.model_manager.switch_to(target_model)

        # Получаем релевантный опыт
        experience_context = ""
        if self.experience:
            lessons = self.experience.get_relevant_experience(task_type)
            if lessons:
                experience_context = "\n[Из опыта]\n" + "\n".join(f"- {l}" for l in lessons)
                if self.verbose:
                    print(f"\n📖 Применяю опыт: {lessons}")
        
        extra_context = experience_context
        
        # Добавляем информацию о субъекте в контекст
        if subject == "neira":
            extra_context += "\n\n⚠️ СУБЪЕКТ ДЕЙСТВИЯ: ТЫ (Нейра). Ты должна выполнить действие, не пользователь!"
        
        # 2. Поиск в интернете
        if needs_search and self.web_search:
            self.log("🌐 ПОИСК В ИНТЕРНЕТЕ")
            search_result = self.web_search.process(user_input)
            if self.verbose:
                print(search_result.content[:500] + "..." if len(search_result.content) > 500 else search_result.content)
            extra_context += f"\n[Результаты поиска]\n{search_result.content}\n"
        
        # 3. ПРИНУДИТЕЛЬНАЯ работа с кодом (НОВОЕ!)
        if needs_code and self.code:
            self.log("💻 РАБОТА С КОДОМ")
            
            # Если нужно читать код — читаем автоматически
            if "прочитай" in user_input.lower() or "изучи" in user_input.lower() or "проанализируй" in user_input.lower():
                # Ищем имя файла в запросе
                files_mentioned = []
                for word in user_input.split():
                    if word.endswith(".py") or word.endswith(".json") or word.endswith(".txt"):
                        files_mentioned.append(word)
                
                # Если файл не указан — читаем основные
                if not files_mentioned:
                    files_mentioned = ["cells.py", "main.py"]
                
                code_context = ""
                for fname in files_mentioned[:2]:  # Максимум 2 файла
                    info = self.code.read_file(fname)
                    if info.exists:
                        code_context += f"\n\n=== {fname} ===\n{info.content[:3000]}\n"
                        print(f"📄 Прочитан: {fname} ({info.size} байт)")
                
                if code_context:
                    extra_context += f"\n[Код файлов]{code_context}"
            
            elif "напиши" in user_input.lower() or "создай" in user_input.lower():
                code_result = self.code.generate_code(user_input)
                if self.verbose:
                    print(code_result.content[:500] + "...")
                extra_context += f"\n[Сгенерированный код]\n{code_result.content}\n"
        
        # 4. Планирование
        self.log("📋 ПЛАНИРОВАНИЕ")
        plan = self.planner.process(user_input, analysis.content)
        if self.verbose:
            print(plan.content)
        
        # 5. Исполнение с RETRY-ЛОГИКОЙ (НОВОЕ!)
        final_result = None
        final_verdict = "НЕИЗВЕСТНО"
        final_score = 0
        problems = ""
        
        for attempt in range(MAX_RETRIES + 1):
            # NEW v0.5: Проверка, нужно ли переключиться на облачную модель
            if attempt > 0 and self.model_manager:
                cloud_model = self._should_use_cloud(task_type, complexity, attempt)
                if cloud_model:
                    if self.verbose:
                        print(f"🌩️ Переключение на облачную модель: {cloud_model}")
                    self.model_manager.switch_to(cloud_model)

            self.log(f"⚡ ИСПОЛНЕНИЕ (попытка {attempt + 1}/{MAX_RETRIES + 1})")

            # Передаём проблемы от предыдущей попытки
            result = self.executor.process(
                user_input,
                plan.content,
                extra_context,
                problems=problems if attempt > 0 else ""
            )
            if self.verbose:
                print(result.content)

            # 6. Верификация
            self.log("✅ ВЕРИФИКАЦИЯ")
            verification = self.verifier.process(user_input, result.content)
            if self.verbose:
                print(verification.content)

            verdict, score, problems = self._parse_verification(verification.content)

            final_result = result
            final_verdict = verdict
            final_score = score

            # Если оценка достаточная — выходим из цикла
            if score >= MIN_ACCEPTABLE_SCORE:
                if attempt > 0:
                    print(f"✅ Исправлено с {attempt + 1}-й попытки!")
                break

            # Если оценка низкая и есть ещё попытки — продолжаем
            if attempt < MAX_RETRIES:
                print(f"⚠️ Оценка {score}/10 < {MIN_ACCEPTABLE_SCORE}. Пробую исправить...")
            else:
                print(f"⚠️ Достигнут лимит попыток. Возвращаю лучший результат.")
        
        # 7. Записываем опыт
        if self.experience:
            self.log("📖 ЗАПИСЬ ОПЫТА")
            self.experience.record_experience(
                task_type=task_type,
                user_input=user_input,
                verdict=final_verdict,
                score=final_score,
                problems=problems
            )
        
        # 8. Извлечение фактов для памяти
        self.log("💾 ПАМЯТЬ")
        facts = self.fact_extractor.process(user_input, final_result.content)
        for fact in facts:
            if fact.get("importance", 0) >= 0.5:
                self.memory.remember(
                    text=fact["text"],
                    importance=fact.get("importance", 0.5),
                    category=fact.get("category", "general"),
                    source=fact.get("source", "conversation")
                )
        
        if not facts:
            print("Новых фактов не найдено")
        
        # Сохраняем ответ в контекст
        self.memory.add_to_session(f"Нейра: {final_result.content}")
        
        return final_result.content
    
    # === КОМАНДЫ ===
    
    def cmd_memory(self) -> str:
        """Показать память"""
        stats = self.memory.get_stats()
        output = "📚 ПАМЯТЬ НЕЙРЫ\n\n"
        output += f"Всего записей: {stats.get('total', 0)}\n"
        output += f"  - разговоры: {stats.get('conversation', 0)}\n"
        output += f"  - из веба: {stats.get('web', 0)}\n"
        output += f"  - из кода: {stats.get('code', 0)}\n\n"
        
        if self.memory.memories:
            output += "Последние записи:\n"
            for mem in self.memory.memories[-5:]:
                output += f"  [{mem.category}] {mem.text[:60]}...\n"
        
        return output
    
    def cmd_experience(self) -> str:
        """Показать опыт"""
        if not self.experience:
            return "❌ Система опыта недоступна"
        
        stats = self.experience.get_stats()
        output = "📖 ОПЫТ НЕЙРЫ\n\n"
        output += f"Всего записей: {stats.get('total', 0)}\n"
        output += f"Средняя оценка: {stats.get('avg_score', 0)}/10\n\n"
        
        if stats.get("by_type"):
            output += "По типам задач:\n"
            for t, c in stats["by_type"].items():
                output += f"  {t}: {c}\n"
        
        if stats.get("by_verdict"):
            output += "\nПо результатам:\n"
            for v, c in stats["by_verdict"].items():
                output += f"  {v}: {c}\n"
        
        return output
    
    def cmd_personality(self) -> str:
        """Показать личность"""
        if not self.experience:
            return "❌ Система опыта недоступна"
        return self.experience.show_personality()
    
    def cmd_learn(self, topic: str) -> str:
        """Изучить тему"""
        if not self.web_learner:
            return "❌ Установи: pip install duckduckgo-search"
        return self.web_learner.learn(topic).content
    
    def cmd_code(self, action: str, *args) -> str:
        """Команды работы с кодом"""
        if not self.code:
            return "❌ Код-клетка недоступна"
        
        if action == "list":
            files = self.code.list_files()
            return "Файлы:\n" + "\n".join(f"  - {f}" for f in files)
        
        elif action == "read" and args:
            info = self.code.read_file(args[0])
            if info.exists:
                return f"📄 {info.path} ({info.size} байт):\n\n{info.content}"
            return f"❌ Файл не найден: {args[0]}"
        
        elif action == "analyze" and args:
            info = self.code.read_file(args[0])
            if info.exists:
                return self.code.analyze_code(info.content).content
            return f"❌ Файл не найден: {args[0]}"
        
        elif action == "self":
            if self.self_modify:
                return self.self_modify.learn_from_self().content
            return "❌ Самомодификация недоступна"
        
        return f"❌ Неизвестная команда: {action}"
    
    def cmd_help(self) -> str:
        return """
📚 КОМАНДЫ НЕЙРЫ v0.6

Память и опыт:
  /memory              — показать память
  /experience          — показать накопленный опыт
  /personality         — показать личность
  /clear               — очистить память

Обучение:
  /learn <тема>        — изучить тему из интернета

Работа с кодом:
  /code list           — список файлов
  /code read <файл>    — прочитать файл
  /code analyze <файл> — анализ кода
  /code self           — самоанализ

Эволюция и самосовершенствование:
  /evolution stats     — статистика эволюции
  /evolution log       — лог эволюции
  /evolution cycle     — запустить автоэволюцию
  /evolution list cls  — список изменений кода
  /evolution diff cls <индекс> — показать diff
  /vote-start <cell> <v1> <v2> <задача> — начать голосование
  /vote-record <cell> <v> <оценка> <ком.> — записать голос
  /vote-results <cell> <v1> <v2> — результаты
  /evolution help      — полная справка по эволюции

Прочее:
  /stats               — статистика
  /models              — проверить модели
  /help                — эта справка
  /exit                — выход

Или просто пиши — Нейра ответит!
"""
    
    def cmd_stats(self) -> str:
        from cells import MODEL_CODE, MODEL_REASON, get_model_status

        status = get_model_status()

        output = "📊 СТАТИСТИКА v0.5\n\n"
        output += "Локальные модели:\n"
        output += f"  Code: {MODEL_CODE} {'✅' if status['code_model_ready'] else '❌'}\n"
        output += f"  Reason: {MODEL_REASON} {'✅' if status['reason_model_ready'] else '❌'}\n"
        output += f"  Personality: нейра {'✅' if status['personality_model_ready'] else '⏳ (не обучена)'}\n\n"

        output += "Облачные модели:\n"
        output += f"  Code Cloud: qwen3-coder (480B) {'✅' if status.get('cloud_code_ready') else '❌'}\n"
        output += f"  Universal Cloud: deepseek-v3.1 (671B) {'✅' if status.get('cloud_universal_ready') else '❌'}\n"
        output += f"  Vision Cloud: qwen3-vl (235B) {'✅' if status.get('cloud_vision_ready') else '⏳ (будущее)'}\n\n"

        if self.model_manager:
            manager_stats = self.model_manager.get_stats()
            output += f"Model Manager:\n"
            output += f"  Текущая модель: {manager_stats.get('current_model', 'none')}\n"
            output += f"  Переключений: {manager_stats.get('switches', 0)}\n"
            output += f"  Загружено в VRAM: {', '.join(manager_stats.get('loaded_models', [])) or 'none'}\n\n"

        output += f"Веб-поиск: {'✅' if WEB_AVAILABLE else '❌'}\n"
        output += f"Работа с кодом: {'✅' if CODE_AVAILABLE else '❌'}\n"
        output += f"Система опыта: {'✅' if EXPERIENCE_AVAILABLE else '❌'}\n"
        output += f"Память: {self.memory.get_stats().get('total', 0)} записей\n"
        output += f"Контекст сессии: {len(self.memory.session_context)} сообщений\n"

        if self.experience:
            exp_stats = self.experience.get_stats()
            output += f"Опыт: {exp_stats.get('total', 0)} записей\n"
            output += f"Средняя оценка: {exp_stats.get('avg_score', 0)}/10\n"

        return output


def main():
    print("=" * 60)
    print("  NEIRA v0.5 — Живая программа")
    print("  Клеточная архитектура с динамическими моделями")
    print("  Code + Reason + Personality + Cloud")
    print("=" * 60)
    
    # Проверяем модели
    if not ensure_models_installed():
        print("\n⚠️ Установи недостающие модели и перезапусти!")
        print("   Ollama должна быть запущена: ollama serve")
        return
    
    print("\nВведи /help для списка команд\n")
    
    neira = Neira(verbose=True)
    
    while True:
        try:
            user_input = input("\nТЫ: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nЗавершение...")
            break
        
        if not user_input:
            continue
        
        # Команды
        if user_input.startswith("/"):
            parts = user_input[1:].split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd in ["exit", "quit", "q"]:
                print("Завершение...")
                break
            elif cmd == "help":
                print(neira.cmd_help())
            elif cmd == "memory":
                print(neira.cmd_memory())
            elif cmd == "experience" or cmd == "exp":
                print(neira.cmd_experience())
            elif cmd == "personality":
                print(neira.cmd_personality())
            elif cmd == "evolution":
                if neira.evolution:
                    if not args:
                        print(neira.evolution.cmd_help_evolution())
                    elif args[0] == "stats":
                        print(neira.evolution.cmd_evolution_stats())
                    elif args[0] == "log":
                        system = args[1] if len(args) > 1 else "all"
                        print(neira.evolution.cmd_evolution_log(system))
                    elif args[0] == "cycle":
                        neira.evolution.auto_evolution_cycle()
                    elif args[0] == "list":
                        system = args[1] if len(args) > 1 else "cls"
                        print(neira.evolution.cmd_evolution_list(system))
                    elif args[0] == "diff":
                        if len(args) < 3:
                            print("❌ Использование: /evolution diff cls <индекс>")
                        else:
                            system = args[1]
                            try:
                                entry_index = int(args[2])
                                print(neira.evolution.cmd_evolution_diff(system, entry_index))
                            except ValueError:
                                print("❌ Индекс должен быть числом")
                    elif args[0] == "help":
                        print(neira.evolution.cmd_help_evolution())
                    else:
                        print(f"❌ Неизвестная подкоманда: {args[0]}")
                else:
                    print("❌ Система эволюции недоступна")
            elif cmd == "clear":
                neira.memory.memories = []
                neira.memory.save()
                print("🗑️ Память очищена")
            elif cmd == "learn" and args:
                print(neira.cmd_learn(" ".join(args)))
            elif cmd == "code":
                print(neira.cmd_code(args[0] if args else "list", *args[1:]))
            elif cmd == "stats":
                print(neira.cmd_stats())
            elif cmd == "models":
                from cells import get_model_status
                status = get_model_status()
                print(f"Ollama: {'✅ запущена' if status['ollama_running'] else '❌ не запущена'}")
                print(f"Модели: {', '.join(status['models'][:5])}")
            elif cmd == "vote-start":
                if neira.evolution and len(args) >= 4:
                    cell_name = args[0]
                    version_1 = args[1]
                    version_2 = args[2]
                    task = " ".join(args[3:])
                    print(neira.evolution.cmd_vote_start(cell_name, version_1, version_2, task))
                else:
                    print("❌ Использование: /vote-start <cell> <version1> <version2> <задача>")
            elif cmd == "vote-record":
                if neira.evolution and len(args) >= 3:
                    cell_name = args[0]
                    version_id = args[1]
                    try:
                        score = int(args[2])
                        feedback = " ".join(args[3:]) if len(args) > 3 else ""
                        print(neira.evolution.cmd_vote_record(cell_name, version_id, score, feedback))
                    except ValueError:
                        print("❌ Оценка должна быть числом от 1 до 10")
                else:
                    print("❌ Использование: /vote-record <cell> <version> <оценка> [комментарий]")
            elif cmd == "vote-results":
                if neira.evolution and len(args) >= 3:
                    cell_name = args[0]
                    version_1 = args[1]
                    version_2 = args[2]
                    print(neira.evolution.cmd_vote_results(cell_name, version_1, version_2))
                else:
                    print("❌ Использование: /vote-results <cell> <version1> <version2>")
            else:
                print(f"❓ Неизвестная команда: {cmd}")
            continue
        
        # Обычный запрос
        try:
            response = neira.process(user_input)
            print(f"\n{'='*50}")
            print(f"НЕЙРА: {response}")
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            print("Проверь что Ollama запущена: ollama serve")


if __name__ == "__main__":
    main()
