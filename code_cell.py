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
from urllib.parse import urlparse

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

# === НАСТРОЙКИ ОБЛАКА (Ollama Cloud) ===
CLOUD_ENABLED = os.getenv("OLLAMA_CLOUD_ENABLED", "false").lower() in {"1", "true", "yes"}

# URL для Ollama Cloud (OpenAI-compatible endpoint)
CLOUD_API_URL = os.getenv("OLLAMA_CLOUD_URL", "https://api.ollama.ai/v1/chat/completions")

CLOUD_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# Используй самую мощную модель из облака Ollama (эквивалент GPT-4 уровня)
CLOUD_MODEL = "qwen3-coder:480b-cloud"   # Альтернатива: "codellama:70b" или "mistral-nemo:12b"

# === ЛОКАЛЬНЫЕ НАСТРОЙКИ ===
ALLOWED_EXTENSIONS = [".py", ".json", ".txt", ".md", ".yaml", ".yml", ".toml"]
BACKUP_DIR = "backups"
MAX_FILE_SIZE = 100_000
LOCAL_URL_ALLOWLIST = {"localhost", "127.0.0.1", "::1"}


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
    
    def __init__(self, memory: Optional[MemoryCell] = None,
                 model_manager=None, work_dir: str = "."):
        super().__init__(memory, model_manager)
        self.work_dir = os.path.abspath(work_dir)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def _validate_https_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Небезопасный CLOUD_API_URL: требуется https и хост")
        return url

    def _validate_local_url(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Недопустимая схема OLLAMA_URL")
        if host.lower() not in LOCAL_URL_ALLOWLIST:
            raise ValueError("Небезопасный OLLAMA_URL: разрешены только локальные адреса")
        return url

    def _cloud_ready(self) -> Tuple[bool, str]:
        if not CLOUD_ENABLED:
            return False, "Облако отключено через OLLAMA_CLOUD_ENABLED"
        if not CLOUD_API_KEY:
            return False, "Нет CLOUD_API_KEY"
        try:
            self._validate_https_url(CLOUD_API_URL)
        except ValueError as err:
            return False, str(err)
        return True, "ok"
    
    def _call_cloud_api(self, messages: List[Dict]) -> str:
        """Вызов облачного API (OpenAI compatible)"""
        ready, reason = self._cloud_ready()
        if not ready:
            raise ValueError(f"Облако недоступно: {reason}")

        headers = {
            "Authorization": f"Bearer {CLOUD_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": CLOUD_MODEL,
            "messages": messages,
            "temperature": 0.2, # Для кода температура ниже
            "max_tokens": 4096
        }

        # Внимание: таймаут для облака больше, так как большие модели думают дольше
        response = requests.post(self._validate_https_url(CLOUD_API_URL), headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        # Обработка разных форматов ответа (на случай специфичных API)
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
             return data['choices'][0]['message']['content']
        else:
             raise ValueError(f"Некорректный ответ API: {data}")

    def _hybrid_generate(self, prompt: str, system: str = None) -> Tuple[str, str]: # pyright: ignore[reportArgumentType]
        """
        Пытается использовать облако, при сбое падает в локальную Ollama.
        Возвращает: (content, source_model_name)
        """
        messages = [
            {"role": "system", "content": system or self.system_prompt},
            {"role": "user", "content": prompt}
        ]

        # 1. Попытка Облака
        ready, reason = self._cloud_ready()
        try:
            if ready:
                print(f"☁️ Посылаю запрос в облако ({CLOUD_MODEL})...")
                content = self._call_cloud_api(messages)
                return content, "CLOUD:" + CLOUD_MODEL
            else:
                print(f"⚠️ Облако пропущено: {reason}")
        except Exception as e:
            print(f"⚠️ Ошибка облака: {e}")
            print(f"🔄 Переключаюсь на локальную модель ({LOCAL_MODEL})...")

        # 2. Fallback на локальную модель
        try:
            ollama_url = self._validate_local_url(os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"))
            payload = {
                "model": LOCAL_MODEL,
                "prompt": f"{system or self.system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 2048}
            }
            response = requests.post(ollama_url, json=payload, timeout=TIMEOUT)
            if response.status_code != 200:
                raise Exception(f"Ошибка локальной модели: {response.text}")
            content = response.json().get("response", "")
            return content, "LOCAL:" + LOCAL_MODEL
        except Exception as e:
            raise Exception(f"Ошибка локальной генерации: {e}")

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
