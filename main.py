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
import os
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
    MODEL_REASON = "ministral-3:3b"
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

try:
    from introspection_cell import IntrospectionCell
    INTROSPECTION_AVAILABLE = True
except ImportError as e:
    INTROSPECTION_AVAILABLE = False
    print(f"⚠️ Орган самосознания недоступен: {e}")

# Автономный загрузчик клеток (v0.8)
try:
    from cell_watcher import CellWatcher, get_cell_watcher, start_cell_watcher
    CELL_WATCHER_AVAILABLE = True
except ImportError as e:
    CELL_WATCHER_AVAILABLE = False
    print(f"⚠️ CellWatcher недоступен: {e}")


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

АДАПТИВНАЯ ДЛИНА ОТВЕТА:
- Простые вопросы → краткий ответ (1-3 предложения)
- "Объясни", "расскажи", "как" → подробный ответ
- Код → полный рабочий код
- Не добавляй воду, но и не обрезай важное

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
        
        # Орган самосознания (v0.6)
        if INTROSPECTION_AVAILABLE:
            self.introspection = IntrospectionCell(self.memory)
            if verbose:
                print("🧬 Орган самосознания активирован")
        else:
            self.introspection = None
        
        # Автономный наблюдатель за клетками (v0.8)
        enable_watcher = os.getenv("NEIRA_ENABLE_CELL_WATCHER", "true").lower() == "true"
        if CELL_WATCHER_AVAILABLE and enable_watcher:
            self.cell_watcher = start_cell_watcher()
            if verbose:
                print("👁️ CellWatcher запущен — новые органы загружаются автоматически")
        else:
            self.cell_watcher = None

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
        metadata = analysis.metadata or {}
        needs_search = metadata.get("needs_search", False)
        needs_code = metadata.get("needs_code", False)
        needs_cell = metadata.get("needs_cell", False)

        # NEW v0.6: Если нужно создать клетку — делаем это
        if needs_cell and self.evolution:
            self.log("🌱 СОЗДАНИЕ НОВОГО ОРГАНА")
            # Извлекаем описание клетки из запроса
            cell_description = user_input
            for prefix in ["научись", "добавь", "создай", "отрасти"]:
                if prefix in user_input.lower():
                    idx = user_input.lower().find(prefix)
                    cell_description = user_input[idx + len(prefix):].strip()
                    break
            
            result = self.evolution.cmd_create_cell(cell_description)
            print(f"🌱 {result}")
            
            # Если клетка создана успешно — активируем её
            if "Клетка создана" in result:
                cell_name = result.split(":")[1].split("\n")[0].strip()
                self.evolution.cmd_activate_cell(cell_name)
                return f"Готово! Я создала новый орган: {cell_name}. Теперь я могу {cell_description}."
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
                    if self.model_manager.switch_to(cloud_model):
                        active_model_key = cloud_model

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
            
            # Защита от пустого результата ExecutorCell
            if not result.content or not result.content.strip():
                print(f"⚠️ ExecutorCell вернул пустой результат на попытке {attempt + 1}")
                if attempt < MAX_RETRIES:
                    problems = "Предыдущая попытка не дала ответа. Сформулируй четкий и полный ответ."
                    continue
                else:
                    # Если все попытки исчерпаны — возвращаем дефолтный ответ
                    return "Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос."

            # 6. Верификация
            self.log("✅ ВЕРИФИКАЦИЯ")
            verification = self.verifier.process(user_input, result.content)
            if self.verbose:
                print(verification.content)

            verify_fallback = verification.metadata.get("fallback_reason")
            verify_length = verification.metadata.get("response_length", len(verification.content))
            if verify_fallback or verify_length == 0:
                print(f"⚠️ Верификатор не дал ответ ({verify_fallback or 'empty_response'}). Переключаю модель и повторяю")
                final_result = result
                final_verdict = "ТРЕБУЕТ_ДОРАБОТКИ"
                final_score = 0
                problems = "Не удалось проверить ответ — нужен повтор с другой моделью"

                if self.model_manager:
                    cloud_model = self._should_use_cloud(task_type, complexity, attempt + 1)
                    if cloud_model and cloud_model != active_model_key and self.model_manager.switch_to(cloud_model):
                        active_model_key = cloud_model
                        print(f"🌩️ Облачная модель для повторной проверки: {cloud_model}")

                if attempt < MAX_RETRIES:
                    continue
                break

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
        
        # Защита от None (хотя цикл всегда выполняется хотя бы раз)
        if final_result is None:
            return "Ошибка: не удалось сгенерировать ответ"
        
        result_content = final_result.content
        facts = self.fact_extractor.process(user_input, result_content)
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
        self.memory.add_to_session(f"Нейра: {result_content}")
        
        return result_content
    
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
    
    def cmd_self(self, args: Optional[list] = None) -> str:
        """Команда самосознания"""
        if not self.introspection:
            return "❌ Орган самосознания недоступен"
        
        if not args:
            # Полная интроспекция
            return self.introspection.process("Кто я такая?").content
        
        subcommand = args[0].lower()
        
        if subcommand == "organs":
            return self.introspection.process("Покажи мои органы").content
        elif subcommand == "grow":
            return self.introspection.process("Как мне отрастить новые способности?").content
        elif subcommand == "status":
            return self.introspection.get_self_description()
        
        return self.introspection.process(" ".join(args)).content
    
    def cmd_help(self) -> str:
        return """
📚 КОМАНДЫ НЕЙРЫ v0.8

Самосознание:
  /self                — кто я? (полная интроспекция)
  /self organs         — показать мои органы
  /self grow           — как мне расти?
  /self status         — мой текущий статус

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
  /code self           — самоанализ кода

Эволюция и рост:
  /evolution stats     — статистика эволюции
  /evolution cycle     — запустить автоэволюцию
  /grow <описание>     — отрастить новый орган (клетку)
  /activate <имя>      — активировать клетку
  /cells               — список созданных клеток

Здоровье и защита:
  /health              — статус всех систем
  /diagnose            — диагностика компонентов
  /threats             — отчёт об угрозах
  /pulse               — проверить пульс клеток
  /recover             — авто-восстановление
  /git <cmd>           — Git: status/log/restore/rollback
  /watcher <cmd>       — статус автозагрузчика клеток
  /sos <проблема>      — запросить помощь

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
    
    def cmd_health(self) -> str:
        """Показать здоровье всех систем"""
        from cells import get_health_status, NERVOUS_SYSTEM_AVAILABLE, IMMUNE_SYSTEM_AVAILABLE
        
        output = "🏥 ЗДОРОВЬЕ СИСТЕМ v0.7\n\n"
        
        health = get_health_status()
        
        # Основные системы
        status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "🔴", "dead": "💀", "unknown": "❓"}
        
        output += "Основные компоненты:\n"
        for component in ["cells", "memory", "models"]:
            status = health.get(component, "unknown")
            emoji = status_emoji.get(status, "❓")
            output += f"  {emoji} {component}: {status}\n"
        
        # Нервная система
        output += f"\nНервная система: "
        if NERVOUS_SYSTEM_AVAILABLE:
            ns_status = health.get("nervous", "unknown")
            output += f"{status_emoji.get(ns_status, '❓')} {ns_status}\n"
            
            if "metrics" in health:
                output += "  Метрики:\n"
                for name, data in health["metrics"].items():
                    metric_emoji = status_emoji.get(data.get("status", "unknown"), "❓")
                    output += f"    {metric_emoji} {name}: {data['value']}{data.get('unit', '')}\n"
            
            if "errors" in health:
                err = health["errors"]
                output += f"  Ошибки: {err['total']} всего, {err['last_hour']} за час\n"
        else:
            output += "❌ недоступна\n"
        
        # Иммунная система
        output += f"\nИммунная система: "
        if IMMUNE_SYSTEM_AVAILABLE:
            output += "✅ активна\n"
            if "threats_blocked" in health:
                output += f"  Заблокировано угроз: {health['threats_blocked']}\n"
        else:
            output += "❌ недоступна\n"
        
        return output
    
    def cmd_diagnose(self) -> str:
        """Запустить диагностику"""
        from cells import run_diagnostics, IMMUNE_SYSTEM_AVAILABLE
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return "❌ Иммунная система недоступна для диагностики"
        
        output = "🔍 ДИАГНОСТИКА КОМПОНЕНТОВ\n\n"
        
        results = run_diagnostics()
        
        if "immune_diagnostic" in results:
            diag = results["immune_diagnostic"]
            if "error" in diag:
                output += f"❌ Ошибка диагностики: {diag['error']}\n"
            else:
                status_emoji = {"healthy": "✅", "degraded": "⚠️", "failing": "🔴", "dead": "💀"}
                
                for name, data in diag.items():
                    emoji = status_emoji.get(data["status"], "❓")
                    output += f"{emoji} {name}: {data['status']}\n"
                    
                    if data["issues"]:
                        for issue in data["issues"][:3]:
                            output += f"   ⚠️ {issue}\n"
                    
                    if data["auto_fixable"]:
                        output += f"   🔧 Можно починить автоматически\n"
                    
                    output += "\n"
        
        return output
    
    def cmd_threats(self) -> str:
        """Показать отчёт об угрозах"""
        from cells import IMMUNE_SYSTEM_AVAILABLE
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return "❌ Иммунная система недоступна"
        
        from immune_system import get_immune_system
        immune = get_immune_system()
        
        output = "🛡️ ОТЧЁТ ОБ УГРОЗАХ\n\n"
        
        status = immune.get_status()
        output += f"Заблокировано угроз: {status['threats_blocked']}\n"
        output += f"Авто-исправлений: {status['auto_fixes_applied']}\n"
        output += f"SOS отправлено: {status['sos_sent']}\n"
        output += f"В карантине: {status['quarantine_items']} объектов\n\n"
        
        threats = immune.get_threat_report()
        if threats:
            output += "Последние угрозы:\n"
            for t in threats[-5:]:
                level_emoji = {"safe": "✅", "suspicious": "⚠️", "dangerous": "🔴", "critical": "💀"}
                emoji = level_emoji.get(t["level"], "❓")
                output += f"  {emoji} [{t['level']}] {t['source']}: {t['description'][:50]}...\n"
        else:
            output += "✅ Угроз не обнаружено\n"
        
        return output
    
    def cmd_sos(self, problem: str) -> str:
        """Отправить SOS"""
        from cells import send_sos, IMMUNE_SYSTEM_AVAILABLE
        
        if not problem:
            return "Использование: /sos <описание проблемы>"
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return f"❌ Иммунная система недоступна\n🆘 Проблема записана: {problem}"
        
        success = send_sos(problem, severity="medium")
        
        if success:
            return f"🆘 SOS отправлен!\nПроблема: {problem}\n\nЖди помощи от администратора."
        else:
            return f"❌ Не удалось отправить SOS\nПроблема: {problem}"
    
    def cmd_recover(self) -> str:
        """Запустить авто-восстановление"""
        from cells import IMMUNE_SYSTEM_AVAILABLE
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return "❌ Иммунная система недоступна"
        
        try:
            from immune_system import get_immune_system
            immune = get_immune_system()
            
            output = "🔧 АВТО-ВОССТАНОВЛЕНИЕ\n"
            output += "=" * 40 + "\n\n"
            
            # Запускаем полное восстановление
            results = immune.doctor.run_full_recovery()
            
            if not results:
                output += "✅ Все компоненты в норме — восстановление не требуется\n"
            else:
                successful = [r for r in results if r.get("success")]
                failed = [r for r in results if not r.get("success")]
                
                if successful:
                    output += f"✅ Успешно исправлено: {len(successful)}\n"
                    for r in successful:
                        output += f"  • {r['component']}: {r['action']}\n"
                        if r.get("details"):
                            output += f"    {r['details']}\n"
                
                if failed:
                    output += f"\n⚠️ Не удалось исправить: {len(failed)}\n"
                    for r in failed:
                        output += f"  • {r['component']}: {r.get('details', 'неизвестная ошибка')}\n"
                
                output += f"\n📊 Всего применено автофиксов: {immune.doctor.fixes_applied}"
            
            return output
            
        except Exception as e:
            return f"❌ Ошибка авто-восстановления: {e}"
    
    def cmd_pulse(self) -> str:
        """Проверить пульс всех клеток"""
        from cells import IMMUNE_SYSTEM_AVAILABLE
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return "❌ Иммунная система недоступна"
        
        try:
            from immune_system import get_immune_system
            immune = get_immune_system()
            
            # Проверяем пульс
            pulses = immune.pulse_monitor.check_all_pulses()
            
            output = "💓 ПУЛЬС КЛЕТОК\n"
            output += "=" * 40 + "\n\n"
            
            alive_count = 0
            dead_count = 0
            
            for name, pulse in pulses.items():
                if pulse.alive:
                    alive_count += 1
                    status = f"✅ живa ({pulse.response_time:.2f}s)"
                else:
                    dead_count += 1
                    status = f"💀 мертва: {pulse.error or 'unknown'}"
                
                output += f"  {name}: {status}\n"
            
            output += f"\n📊 Живых: {alive_count}, Мертвых: {dead_count}"
            
            if dead_count > 0:
                output += "\n\n💡 Используй /recover для попытки восстановления"
            
            return output
            
        except Exception as e:
            return f"❌ Ошибка проверки пульса: {e}"
    
    def cmd_git(self, subcmd: str = "status", *args) -> str:
        """Git команды"""
        from cells import IMMUNE_SYSTEM_AVAILABLE
        
        if not IMMUNE_SYSTEM_AVAILABLE:
            return "❌ Иммунная система недоступна"
        
        try:
            from immune_system import get_immune_system
            immune = get_immune_system()
            git = immune.git
            
            if not git.git_available:
                return "❌ Git не установлен"
            
            if not git.is_repo():
                return "❌ Это не Git репозиторий"
            
            if subcmd == "status":
                return git.get_status_report()
            
            elif subcmd == "log":
                commits = git.get_recent_commits(int(args[0]) if args else 10)
                if not commits:
                    return "❌ Не удалось получить историю"
                
                output = "📜 ИСТОРИЯ КОММИТОВ\n" + "=" * 40 + "\n\n"
                for c in commits:
                    output += f"• {c['hash']} - {c['message'][:50]}\n"
                    output += f"  {c['date']} by {c['author']}\n\n"
                return output
            
            elif subcmd == "history" and args:
                filepath = args[0]
                history = git.get_file_history(filepath)
                if not history:
                    return f"❌ История для {filepath} не найдена"
                
                output = f"📜 ИСТОРИЯ {filepath}\n" + "=" * 40 + "\n\n"
                for h in history:
                    output += f"• {h['hash']} - {h['message'][:40]}\n"
                return output
            
            elif subcmd == "restore":
                message = " ".join(args) if args else "Manual restore point"
                commit = git.create_restore_point(message)
                if commit:
                    return f"✅ Точка восстановления создана: {commit[:8]}"
                return "❌ Не удалось создать точку восстановления"
            
            elif subcmd == "rollback" and args:
                filepath = args[0]
                commit = args[1] if len(args) > 1 else "HEAD~1"
                if git.rollback_file(filepath, commit):
                    return f"✅ Файл {filepath} откачен к {commit}"
                return f"❌ Не удалось откатить {filepath}"
            
            elif subcmd == "diff" and args:
                filepath = args[0]
                commit = args[1] if len(args) > 1 else "HEAD~1"
                diff = git.diff_with_commit(filepath, commit)
                if diff:
                    return f"📝 DIFF {filepath}\n" + "=" * 40 + f"\n\n```\n{diff[:2000]}\n```"
                return "Нет изменений или файл не найден"
            
            elif subcmd == "stash":
                if git.stash_changes(" ".join(args) if args else "Auto stash"):
                    return "✅ Изменения спрятаны"
                return "❌ Не удалось спрятать изменения"
            
            elif subcmd == "unstash":
                if git.pop_stash():
                    return "✅ Изменения восстановлены из stash"
                return "❌ Не удалось восстановить из stash"
            
            else:
                return """📦 GIT КОМАНДЫ
                
/git status          - статус репозитория
/git log [n]         - последние n коммитов
/git history <file>  - история файла
/git restore [msg]   - создать точку восстановления
/git rollback <file> [commit] - откатить файл
/git diff <file> [commit]     - показать изменения
/git stash [msg]     - спрятать изменения
/git unstash         - вернуть спрятанное"""
            
        except Exception as e:
            return f"❌ Ошибка Git: {e}"

    def cmd_watcher(self, subcmd: str = "status", *args) -> str:
        """Управление CellWatcher — автономным загрузчиком клеток"""
        if not self.cell_watcher:
            return "❌ CellWatcher недоступен"
        
        if subcmd == "status":
            return self.cell_watcher.get_status()
        
        elif subcmd == "cells":
            cells = self.cell_watcher.get_loaded_cells()
            if not cells:
                return "📭 Нет загруженных динамических клеток"
            
            output = "🧬 ЗАГРУЖЕННЫЕ КЛЕТКИ:\n"
            for name in cells:
                output += f"  • {name}\n"
            return output
        
        elif subcmd == "reload" and args:
            name = args[0]
            if self.cell_watcher.force_reload(name):
                return f"✅ Клетка {name} перезагружена"
            return f"❌ Не удалось перезагрузить {name}"
        
        elif subcmd == "stop":
            self.cell_watcher.stop()
            return "🛑 CellWatcher остановлен"
        
        elif subcmd == "start":
            self.cell_watcher.start()
            return "👁️ CellWatcher запущен"
        
        else:
            return """👁️ CELL WATCHER КОМАНДЫ

/watcher status      - статус наблюдателя
/watcher cells       - список загруженных клеток
/watcher reload <name> - перезагрузить клетку
/watcher stop        - остановить наблюдатель
/watcher start       - запустить наблюдатель

CellWatcher автоматически обнаруживает новые *_cell.py файлы
и загружает их без перезапуска Neira!"""


def main():
    print("=" * 60)
    print("  NEIRA v0.8 — Живая программа")
    print("  Клеточная архитектура + Нервная и Иммунная системы")
    print("  Авто-восстановление + Пульс клеток")
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
            elif cmd == "self":
                print(neira.cmd_self(args if args else None))
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
            elif cmd == "grow":
                # Команда для создания нового органа (клетки)
                if neira.evolution and args:
                    description = " ".join(args)
                    print(f"🌱 Создаю новый орган: {description}")
                    result = neira.evolution.cmd_create_cell(description)
                    print(result)
                else:
                    print("❌ Использование: /grow <описание клетки>")
                    print("   Пример: /grow генератор картинок через FLUX API")
            elif cmd == "activate":
                # Активация клетки
                if neira.evolution and args:
                    cell_name = args[0]
                    result = neira.evolution.cmd_activate_cell(cell_name)
                    print(result)
                else:
                    print("❌ Использование: /activate <имя_клетки>")
            elif cmd == "cells":
                # Список клеток
                if neira.evolution:
                    print(neira.evolution.cmd_evolution_log("cells"))
                else:
                    print("❌ Система эволюции недоступна")
            # Команды здоровья и защиты
            elif cmd == "health":
                print(neira.cmd_health())
            elif cmd == "diagnose":
                print(neira.cmd_diagnose())
            elif cmd == "threats":
                print(neira.cmd_threats())
            elif cmd == "sos":
                problem = " ".join(args) if args else ""
                print(neira.cmd_sos(problem))
            elif cmd == "recover":
                print(neira.cmd_recover())
            elif cmd == "pulse":
                print(neira.cmd_pulse())
            elif cmd == "git":
                subcmd = args[0] if args else "status"
                print(neira.cmd_git(subcmd, *args[1:]))
            elif cmd == "watcher":
                subcmd = args[0] if args else "status"
                print(neira.cmd_watcher(subcmd, *args[1:]))
            else:
                print(f"❓ Неизвестная команда: {cmd}")
            continue
        
        # Обычный запрос
        try:
            response = neira.process(user_input)
            print(f"\n{'='*50}")
            print(f"НЕЙРА: {response}")
            
            # Любопытство — Neira может задать вопрос
            from cells import maybe_ask_question, CURIOSITY_AVAILABLE
            if CURIOSITY_AVAILABLE:
                question = maybe_ask_question(user_input, response)
                if question:
                    print(f"\n💭 {question}")
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            print("Проверь что Ollama запущена: ollama serve")


if __name__ == "__main__":
    main()
