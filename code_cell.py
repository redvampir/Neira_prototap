"""
Neira Code Cell v0.5 — Гибридная работа с кодом
Позволяет использовать мощь облака для генерации, сохраняя локальную автономность.

АРХИТЕКТУРА:
1. Попытка Cloud (Qwen-480B/GPT-4 уровень)
2. Fallback на Local (Qwen-7B) при ошибках или отсутствии сети
"""

from logging import info
import os
import subprocess
import json
import requests
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

def _env_int(name: str, default: int, min_value: int = 1, max_value: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if value < min_value:
        return min_value
    if max_value is not None and value > max_value:
        return max_value
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _merge_system_prompt(base_prompt: str, layer_prompt: Optional[str]) -> str:
    if not layer_prompt:
        return base_prompt
    if not base_prompt:
        return layer_prompt
    return f"{base_prompt}\n\n[Слой модели]\n{layer_prompt}"


try:
    from model_layers import ModelLayersRegistry

    _MODEL_LAYERS = ModelLayersRegistry("model_layers.json")
except Exception:
    _MODEL_LAYERS = None

try:
    from neira.core.llm_adapter import LLMClient, LLMResult, NullLLMClient, build_default_llm_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False

_CODE_LLM_CLIENT: Optional[LLMClient] = None


def _get_code_client() -> Optional[LLMClient]:
    global _CODE_LLM_CLIENT
    if not LLM_CLIENT_AVAILABLE:
        return None
    if _CODE_LLM_CLIENT is None:
        client = build_default_llm_client()
        if isinstance(client, NullLLMClient):
            return None
        _CODE_LLM_CLIENT = client
    return _CODE_LLM_CLIENT

# Пробуем импортировать из новой версии (cells_v3), иначе из старой (cells)
try:
    from cells_v3 import Cell, CellResult, MemoryCell, OLLAMA_URL, MODEL_CODE as LOCAL_MODEL, TIMEOUT # type: ignore
except ImportError:
    # Fallback для совместимости
    from cells import Cell, CellResult, MemoryCell, OLLAMA_URL
    # Если MODEL_CODE не определен в cells, задаем вручную
    try:
        from cells import MODEL_CODE as LOCAL_MODEL
    except ImportError:
        LOCAL_MODEL = "qwen2.5-coder:7b"
    TIMEOUT = 120

DEFAULT_MAX_RESPONSE_TOKENS = _env_int("NEIRA_MAX_RESPONSE_TOKENS", 2048, min_value=128)
CODE_MAX_TOKENS = _env_int("NEIRA_CODE_MAX_TOKENS", DEFAULT_MAX_RESPONSE_TOKENS, min_value=128)
OLLAMA_NUM_CTX = _env_int("NEIRA_OLLAMA_NUM_CTX", 0, min_value=0)
OLLAMA_DISABLED = _env_bool("NEIRA_DISABLE_OLLAMA", False)

# === НАСТРОЙКИ ОБЛАКА ===
# ВНИМАНИЕ: Ollama работает ТОЛЬКО локально (localhost:11434)
# Нет публичного облака api.ollama.ai — это был баг
CLOUD_ENABLED = False  # Отключено — используем только локальную модель

# Для облачных моделей можно интегрировать OpenRouter, Together.ai, Groq и т.д.
# Пока используем только локальный Ollama
CLOUD_API_URL = ""  # Заглушка — облако отключено
CLOUD_API_KEY = os.getenv("OLLAMA_API_KEY", "")  # Пусто по умолчанию

# Локальная модель для кода
CLOUD_MODEL = LOCAL_MODEL  # Используем локальную модель

# === ЛОКАЛЬНЫЕ НАСТРОЙКИ ===
ALLOWED_EXTENSIONS = [".py", ".json", ".txt", ".md", ".yaml", ".yml", ".toml"]
BACKUP_DIR = "backups"
MAX_FILE_SIZE = 100_000


@dataclass
class FileInfo:
    """Информация о файле"""
    path: str
    exists: bool
    size: int = 0
    extension: str = ""
    content: str = ""


class CodeCell(Cell): # pyright: ignore[reportGeneralTypeIssues]
    """Клетка для работы с кодом (Гибридная)"""
    
    name = "code"
    system_prompt = """Ты — опытный Python-разработчик. 
Твоя задача — писать работающий, чистый и безопасный код.
Всегда следуй стандартам PEP8. Комментируй неочевидные решения."""
    
    def __init__(self, memory: Optional[MemoryCell] = None, work_dir: str = "."):
        super().__init__(memory)
        self.work_dir = os.path.abspath(work_dir)
        os.makedirs(BACKUP_DIR, exist_ok=True)
    
    def _call_cloud_api(self, messages: List[Dict]) -> str:
        """Вызов облачного API (OpenAI compatible)"""
        if not CLOUD_ENABLED or not CLOUD_API_KEY or "sk-..." in CLOUD_API_KEY:
            raise ValueError("Облако не настроено (проверь CLOUD_API_KEY в code_cell.py)")

        headers = {
            "Authorization": f"Bearer {CLOUD_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": CLOUD_MODEL,
            "messages": messages,
            "temperature": 0.2, # Для кода температура ниже
            "max_tokens": CODE_MAX_TOKENS
        }
        
        # Внимание: таймаут для облака больше, так как большие модели думают дольше
        response = requests.post(CLOUD_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        # Обработка разных форматов ответа (на случай специфичных API)
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
             return data['choices'][0]['message']['content']
        else:
             raise ValueError(f"Некорректный ответ API: {data}")

    def _hybrid_generate(self, prompt: str, system: str = None) -> Tuple[str, str]: # pyright: ignore[reportArgumentType]
        """
        Пытается использовать локальную Ollama с graceful degradation.
        Возвращает: (content, source_model_name)
        """
        base_system = system or self.system_prompt
        layer_prompt = _MODEL_LAYERS.get_active_prompt(LOCAL_MODEL) if _MODEL_LAYERS else None
        system_prompt = _merge_system_prompt(base_system, layer_prompt)

        client = _get_code_client()
        if client:
            try:
                response: LLMResult = client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=CODE_MAX_TOKENS
                )
                if response.success and response.content:
                    provider = response.provider or "unknown"
                    model = response.model or "default"
                    return response.content, f"{provider}:{model}"
            except (RuntimeError, ValueError, TypeError, OSError):
                pass

        if OLLAMA_DISABLED:
            return self._offline_response(prompt, "ollama_disabled"), "OFFLINE"

        # Облако отключено — используем только локальную модель
        try:
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
            options: Dict[str, Any] = {"temperature": 0.2, "num_predict": CODE_MAX_TOKENS}
            if OLLAMA_NUM_CTX:
                options["num_ctx"] = OLLAMA_NUM_CTX
            if _MODEL_LAYERS is not None:
                adapter = _MODEL_LAYERS.get_active_adapter(LOCAL_MODEL)
                if adapter:
                    options["adapter"] = adapter
            payload = {
                "model": LOCAL_MODEL,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": options
            }
            response = requests.post(ollama_url, json=payload, timeout=TIMEOUT)
            if response.status_code != 200:
                raise Exception(f"Ошибка локальной модели: {response.text}")
            content = response.json().get("response", "")
            return content, "LOCAL:" + LOCAL_MODEL
            
        except requests.exceptions.Timeout:
            return self._offline_response(prompt, "timeout"), "OFFLINE"
            
        except requests.exceptions.ConnectionError:
            return self._offline_response(prompt, "offline"), "OFFLINE"
            
        except Exception as e:
            return self._offline_response(prompt, f"error: {e}"), "OFFLINE"
    
    def _offline_response(self, prompt: str, reason: str) -> str:
        """Ответ когда Ollama недоступна"""
        if reason == "ollama_disabled":
            return (
                "*[Автономный режим — ollama_disabled]*\n\n"
                "Ollama отключена через NEIRA_DISABLE_OLLAMA. "
                "Настрой другой провайдер (LM Studio/llama.cpp/облако) и повтори команду."
            )
        return (
            f"*[Автономный режим — {reason}]*\n\n"
            f"Не могу выполнить операцию с кодом — Ollama недоступна.\n"
            f"Запусти `ollama serve` и повтори команду."
        )

    def _safe_path(self, path: str) -> str:
        full_path = os.path.abspath(os.path.join(self.work_dir, path))
        if not full_path.startswith(self.work_dir):
            raise ValueError(f"Path traversal attempt: {path}")
        return full_path
    
    def _check_extension(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in ALLOWED_EXTENSIONS
    
    def read_file(self, path: str) -> FileInfo:
        try:
            full_path = self._safe_path(path)
            if not os.path.exists(full_path):
                return FileInfo(path=path, exists=False)
            
            size = os.path.getsize(full_path)
            if size > MAX_FILE_SIZE:
                return FileInfo(path=path, exists=True, size=size, content=f"[TOO LARGE: {size} bytes]")
            
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return FileInfo(path=path, exists=True, size=size, extension=os.path.splitext(path)[1], content=content)
        except Exception as e:
            return FileInfo(path=path, exists=False, content=f"Error: {e}")
    
    def write_file(self, path: str, content: str, backup: bool = True) -> bool:
        try:
            full_path = self._safe_path(path)
            if not self._check_extension(path):
                print(f"❌ Запрещенное расширение: {path}")
                return False
            
            if backup and os.path.exists(full_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(BACKUP_DIR, f"{timestamp}_{os.path.basename(path)}")
                with open(full_path, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
                print(f"📦 Бэкап сохранен: {backup_path}")
            
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Файл записан: {path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка записи: {e}")
            return False
    
    def list_files(self, directory: str = ".") -> List[str]:
        try:
            full_path = self._safe_path(directory)
            return [f for f in os.listdir(full_path) 
                    if os.path.isfile(os.path.join(full_path, f)) and self._check_extension(f)]
        except Exception:
            return []

    def _extract_code(self, text: str) -> str:
        """Умное извлечение кода из Markdown"""
        if "```" not in text:
            return text
        
        # Ищем блоки кода
        lines = text.split('\n')
        code_lines = []
        in_block = False
        
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                code_lines.append(line)
        
        return '\n'.join(code_lines) if code_lines else text

    def generate_code(self, task: str, language: str = "python") -> CellResult:
        """Генерация кода (Гибридная)"""
        prompt = f"Напиши код на {language} для задачи:\n{task}\n\nТолько код, без лишних слов."
        
        content, source = self._hybrid_generate(prompt)
        code = self._extract_code(content)
        
        return CellResult(
            content=code,
            confidence=0.9 if "CLOUD" in source else 0.6,
            cell_name=self.name,
            metadata={"source": source, "language": language}
        )
    
    def analyze_code(self, code: str, language: str = "python") -> CellResult:
        """Анализ кода (Гибридный)"""
        prompt = f"Проведи ревью этого кода на {language}:\n\n{code}\n\nИщи ошибки, уязвимости и плохой стиль."
        content, source = self._hybrid_generate(prompt, system="Ты строгий Senior Developer. Формат ответа: ОШИБКИ, СТИЛЬ, УЛУЧШЕНИЯ, ОЦЕНКА (1-10).")
        
        return CellResult(
            content=content,
            confidence=0.9 if "CLOUD" in source else 0.6,
            cell_name=self.name,
            metadata={"source": source}
        )

    def modify_code(self, file_path: str, instruction: str) -> CellResult:
        """Модификация файла (Гибридная)"""
        info = self.read_file(file_path)
        if not info.exists:
            return CellResult(f"Файл не найден: {file_path}", 0.0, self.name)
        
        prompt = f"""Файл: {file_path}\nСодержимое:\n{info.content}\n\nЗадача: {instruction}

Верни ПОЛНЫЙ обновленный код файла. Не сокращай код, если это не требуется.
ТОЛЬКО код:"""
        
        content, source = self._hybrid_generate(prompt)
        new_code = self._extract_code(content)
        
        return CellResult(
            content=new_code,
            confidence=0.8 if "CLOUD" in source else 0.5,
            cell_name=self.name,
            metadata={"source": source, "file": file_path}
        )

    def run_python(self, code: str, timeout: int = 30) -> CellResult:
        """Выполнить Python код (Локально)"""
        temp_file = os.path.join(self.work_dir, "_temp_run.py")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(code)
            
            result = subprocess.run(
                ["python", temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.work_dir
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n\nОШИБКИ:\n{result.stderr}"
            
            success = result.returncode == 0
            return CellResult(
                content=output if output else "(нет вывода)",
                confidence=0.9 if success else 0.3,
                cell_name=self.name,
                metadata={"returncode": result.returncode, "success": success}
            )
        except Exception as e:
            return CellResult(f"Ошибка исполнения: {e}", 0.1, self.name)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


class SelfModifyCell(CodeCell):
    name = "self_modify"
    MODIFIABLE_FILES = ["cells.py", "web_cell.py", "code_cell.py", "main.py"]
    
    def learn_from_self(self) -> CellResult:
        """Анализ собственной архитектуры"""
        report = []
        for f in self.MODIFIABLE_FILES:
            info = self.read_file(f)
            if info.exists:
                res = self.analyze_code(info.content)
                report.append(f"=== {f} ({res.metadata.get('source')}) ===\n{res.content}")
        
        return CellResult("\n\n".join(report), 1.0, self.name)


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 50)
    print("Тест CodeCell (Hybrid)")
    print("=" * 50)
    
    cell = CodeCell(work_dir=".")
    
    # Тест генерации
    print(f"\nГенерация кода через: {'CLOUD' if CLOUD_ENABLED else 'LOCAL'}...")
    result = cell.generate_code("Напиши функцию фибоначчи на python")
    print(f"Источник: {result.metadata.get('source')}")
    print(result.content)
