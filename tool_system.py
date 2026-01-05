"""
Tool System — Система инструментов для Нейры

Позволяет Нейре:
- Выполнять команды в терминале
- Делать HTTP запросы
- Работать с файлами
- Выполнять поиск
- Запускать скрипты

Безопасность:
- Whitelist разрешённых команд
- Таймауты
- Sandboxing
"""

import asyncio
import subprocess
import json
import re
import os
import sys
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("neira-tools")


class ToolCategory(Enum):
    """Категории инструментов"""
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    SEARCH = "search"
    HTTP = "http"
    CODE = "code"
    SYSTEM = "system"


@dataclass
class ToolParameter:
    """Параметр инструмента"""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """Определение инструмента"""
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter]
    dangerous: bool = False  # Требует подтверждения
    
    def to_schema(self) -> Dict:
        """Конвертирует в JSON Schema для LLM"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
                
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


@dataclass
class ToolResult:
    """Результат выполнения инструмента"""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    tool_name: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ToolRegistry:
    """Реестр инструментов"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.handlers: Dict[str, Callable[..., Awaitable[ToolResult]]] = {}
        
        # Регистрируем встроенные инструменты
        self._register_builtin_tools()
    
    def register(
        self, 
        definition: ToolDefinition, 
        handler: Callable[..., Awaitable[ToolResult]]
    ):
        """Регистрирует инструмент"""
        self.tools[definition.name] = definition
        self.handlers[definition.name] = handler
    
    def get_all_schemas(self) -> List[Dict]:
        """Возвращает схемы всех инструментов для LLM"""
        return [tool.to_schema() for tool in self.tools.values()]
    
    def get_tools_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Инструменты по категории"""
        return [t for t in self.tools.values() if t.category == category]
    
    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Выполняет инструмент"""
        if tool_name not in self.handlers:
            return ToolResult(
                success=False,
                output=None,
                error=f"Инструмент '{tool_name}' не найден",
                tool_name=tool_name
            )
        
        start_time = datetime.now()
        
        try:
            handler = self.handlers[tool_name]
            result = await handler(**kwargs)
            result.tool_name = tool_name
            result.execution_time = (datetime.now() - start_time).total_seconds()
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                tool_name=tool_name,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def _register_builtin_tools(self):
        """Регистрация встроенных инструментов"""
        
        # === TERMINAL TOOLS ===
        
        # Выполнение команды
        self.register(
            ToolDefinition(
                name="run_command",
                description="Выполняет команду в терминале и возвращает результат",
                category=ToolCategory.TERMINAL,
                parameters=[
                    ToolParameter("command", "string", "Команда для выполнения"),
                    ToolParameter("cwd", "string", "Рабочая директория", required=False),
                    ToolParameter("timeout", "number", "Таймаут в секундах", required=False, default=30)
                ],
                dangerous=True
            ),
            self._handle_run_command
        )
        
        # Python код
        self.register(
            ToolDefinition(
                name="run_python",
                description="Выполняет Python код и возвращает результат",
                category=ToolCategory.CODE,
                parameters=[
                    ToolParameter("code", "string", "Python код для выполнения"),
                    ToolParameter("timeout", "number", "Таймаут в секундах", required=False, default=30)
                ],
                dangerous=True
            ),
            self._handle_run_python
        )
        
        # === SEARCH TOOLS ===
        
        # Поиск в файлах
        self.register(
            ToolDefinition(
                name="search_files",
                description="Поиск текста в файлах проекта (grep)",
                category=ToolCategory.SEARCH,
                parameters=[
                    ToolParameter("query", "string", "Текст для поиска"),
                    ToolParameter("path", "string", "Путь для поиска", required=False, default="."),
                    ToolParameter("file_pattern", "string", "Паттерн файлов (*.py)", required=False, default="*"),
                    ToolParameter("max_results", "number", "Максимум результатов", required=False, default=50)
                ]
            ),
            self._handle_search_files
        )
        
        # Поиск файла
        self.register(
            ToolDefinition(
                name="find_file",
                description="Найти файл по имени",
                category=ToolCategory.SEARCH,
                parameters=[
                    ToolParameter("filename", "string", "Имя файла или паттерн"),
                    ToolParameter("path", "string", "Путь для поиска", required=False, default=".")
                ]
            ),
            self._handle_find_file
        )
        
        # === HTTP TOOLS ===
        
        # HTTP запрос
        self.register(
            ToolDefinition(
                name="http_request",
                description="Выполняет HTTP запрос",
                category=ToolCategory.HTTP,
                parameters=[
                    ToolParameter("url", "string", "URL запроса"),
                    ToolParameter("method", "string", "HTTP метод", required=False, default="GET", 
                                  enum=["GET", "POST", "PUT", "DELETE", "PATCH"]),
                    ToolParameter("headers", "object", "Заголовки", required=False),
                    ToolParameter("body", "string", "Тело запроса", required=False),
                    ToolParameter("timeout", "number", "Таймаут в секундах", required=False, default=30)
                ]
            ),
            self._handle_http_request
        )
        
        # === SYSTEM TOOLS ===
        
        # Системная информация
        self.register(
            ToolDefinition(
                name="system_info",
                description="Получает информацию о системе",
                category=ToolCategory.SYSTEM,
                parameters=[]
            ),
            self._handle_system_info
        )
        
        # Текущее время
        self.register(
            ToolDefinition(
                name="get_time",
                description="Возвращает текущую дату и время",
                category=ToolCategory.SYSTEM,
                parameters=[
                    ToolParameter("format", "string", "Формат времени", required=False, default="%Y-%m-%d %H:%M:%S")
                ]
            ),
            self._handle_get_time
        )
        
        # === CODE TOOLS ===
        
        # Анализ кода
        self.register(
            ToolDefinition(
                name="analyze_code",
                description="Анализирует Python код на ошибки и стиль",
                category=ToolCategory.CODE,
                parameters=[
                    ToolParameter("code", "string", "Код для анализа"),
                    ToolParameter("language", "string", "Язык программирования", required=False, default="python")
                ]
            ),
            self._handle_analyze_code
        )
    
    # === HANDLERS ===
    
    async def _handle_run_command(
        self, 
        command: str, 
        cwd: str = None, 
        timeout: int = 30
    ) -> ToolResult:
        """Выполняет команду в терминале"""
        
        # Whitelist безопасных команд
        safe_prefixes = [
            "ls", "dir", "pwd", "cd", "cat", "head", "tail", "grep", "find",
            "echo", "python", "pip", "npm", "node", "git", "make", "cargo"
        ]
        
        cmd_lower = command.lower().strip()
        is_safe = any(cmd_lower.startswith(p) for p in safe_prefixes)
        
        if not is_safe:
            # Проверяем на опасные команды
            dangerous = ["rm -rf /", "format", "del /", "shutdown", "reboot"]
            if any(d in cmd_lower for d in dangerous):
                return ToolResult(
                    success=False,
                    output=None,
                    error="Команда заблокирована по соображениям безопасности"
                )
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Команда превысила таймаут ({timeout}с)"
                )
            
            output = stdout.decode('utf-8', errors='ignore')
            error = stderr.decode('utf-8', errors='ignore')
            
            return ToolResult(
                success=process.returncode == 0,
                output={
                    "stdout": output[:10000],  # Ограничиваем вывод
                    "stderr": error[:10000],
                    "return_code": process.returncode
                },
                error=error if process.returncode != 0 else None
            )
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def _handle_run_python(self, code: str, timeout: int = 30) -> ToolResult:
        """Выполняет Python код"""
        
        # Запрещённые импорты
        forbidden = ["os.system", "subprocess", "eval(", "exec(", "__import__"]
        if any(f in code for f in forbidden):
            return ToolResult(
                success=False,
                output=None,
                error="Код содержит запрещённые конструкции"
            )
        
        # Создаём временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = await self._handle_run_command(
                f'{sys.executable} "{temp_file}"',
                timeout=timeout
            )
            return result
        finally:
            try:
                os.unlink(temp_file)
            except Exception:
                pass
    
    async def _handle_search_files(
        self, 
        query: str, 
        path: str = ".", 
        file_pattern: str = "*",
        max_results: int = 50
    ) -> ToolResult:
        """Поиск в файлах"""
        try:
            # Используем grep или findstr в зависимости от ОС
            if sys.platform == "win32":
                cmd = f'findstr /S /N /I "{query}" {path}\\{file_pattern}'
            else:
                cmd = f'grep -rn --include="{file_pattern}" "{query}" "{path}" | head -{max_results}'
            
            result = await self._handle_run_command(cmd)
            
            if result.success:
                # Парсим результаты
                lines = result.output.get("stdout", "").split('\n')
                matches = []
                for line in lines[:max_results]:
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            matches.append({
                                "file": parts[0],
                                "line": parts[1],
                                "content": parts[2].strip()[:200]
                            })
                
                return ToolResult(
                    success=True,
                    output={
                        "matches": matches,
                        "total": len(matches)
                    }
                )
            
            return result
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def _handle_find_file(self, filename: str, path: str = ".") -> ToolResult:
        """Найти файл"""
        try:
            if sys.platform == "win32":
                cmd = f'dir /S /B "{path}\\{filename}" 2>nul'
            else:
                cmd = f'find "{path}" -name "{filename}" -type f 2>/dev/null'
            
            result = await self._handle_run_command(cmd)
            
            if result.success:
                files = [f.strip() for f in result.output.get("stdout", "").split('\n') if f.strip()]
                return ToolResult(
                    success=True,
                    output={"files": files[:50], "total": len(files)}
                )
            
            return result
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def _handle_http_request(
        self, 
        url: str, 
        method: str = "GET",
        headers: dict = None,
        body: str = None,
        timeout: int = 30
    ) -> ToolResult:
        """HTTP запрос"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    text = await response.text()
                    return ToolResult(
                        success=response.status < 400,
                        output={
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": text[:50000]  # Ограничиваем размер
                        }
                    )
                    
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def _handle_system_info(self) -> ToolResult:
        """Информация о системе"""
        import platform
        
        return ToolResult(
            success=True,
            output={
                "os": platform.system(),
                "os_version": platform.version(),
                "python": platform.python_version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "cwd": os.getcwd()
            }
        )
    
    async def _handle_get_time(self, format: str = "%Y-%m-%d %H:%M:%S") -> ToolResult:
        """Текущее время"""
        return ToolResult(
            success=True,
            output={
                "datetime": datetime.now().strftime(format),
                "timestamp": datetime.now().timestamp()
            }
        )
    
    async def _handle_analyze_code(self, code: str, language: str = "python") -> ToolResult:
        """Анализ кода"""
        issues = []
        
        if language == "python":
            # Базовые проверки
            lines = code.split('\n')
            
            for i, line in enumerate(lines, 1):
                # Длинные строки
                if len(line) > 120:
                    issues.append(f"Строка {i}: превышает 120 символов")
                
                # Trailing whitespace
                if line.rstrip() != line:
                    issues.append(f"Строка {i}: пробелы в конце строки")
                
                # TODO/FIXME
                if "TODO" in line or "FIXME" in line:
                    issues.append(f"Строка {i}: найден TODO/FIXME")
                
                # print() в коде
                if re.match(r'^\s*print\s*\(', line):
                    issues.append(f"Строка {i}: отладочный print()")
            
            # Проверка синтаксиса
            try:
                compile(code, '<string>', 'exec')
            except SyntaxError as e:
                issues.append(f"Синтаксическая ошибка: {e}")
        
        return ToolResult(
            success=True,
            output={
                "issues": issues,
                "total_issues": len(issues),
                "lines": len(code.split('\n'))
            }
        )


class ToolExecutor:
    """Исполнитель инструментов с интеграцией в LLM"""
    
    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry()
        self.history: List[Dict] = []
        self.require_confirmation: bool = True
    
    def get_tools_prompt(self) -> str:
        """Генерирует промпт с описанием инструментов для LLM"""
        tools_desc = []
        
        for tool in self.registry.tools.values():
            params = []
            for p in tool.parameters:
                req = "(обязательный)" if p.required else "(опциональный)"
                params.append(f"  - {p.name}: {p.description} {req}")
            
            tools_desc.append(f"""
**{tool.name}** — {tool.description}
Категория: {tool.category.value}
Параметры:
{chr(10).join(params) if params else "  Нет параметров"}
""")
        
        return """# Доступные инструменты

Вы можете использовать следующие инструменты для выполнения задач.
Для вызова инструмента используйте формат:
```tool
{
  "name": "имя_инструмента",
  "parameters": { ... }
}
```

""" + "\n".join(tools_desc)
    
    def parse_tool_calls(self, text: str) -> List[Dict]:
        """Парсит вызовы инструментов из текста LLM"""
        calls = []
        
        # Ищем блоки ```tool ... ```
        pattern = r'```tool\s*\n?(.*?)\n?```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                if "name" in data:
                    calls.append(data)
            except json.JSONDecodeError:
                continue
        
        return calls
    
    async def execute_tool_calls(
        self, 
        calls: List[Dict],
        on_confirm: Optional[Callable[[str, Dict], Awaitable[bool]]] = None
    ) -> List[ToolResult]:
        """Выполняет список вызовов инструментов"""
        results = []
        
        for call in calls:
            tool_name = call.get("name", "")
            params = call.get("parameters", {})
            
            # Проверяем, требуется ли подтверждение
            tool_def = self.registry.tools.get(tool_name)
            if tool_def and tool_def.dangerous and self.require_confirmation:
                if on_confirm:
                    confirmed = await on_confirm(tool_name, params)
                    if not confirmed:
                        results.append(ToolResult(
                            success=False,
                            output=None,
                            error="Выполнение отменено пользователем",
                            tool_name=tool_name
                        ))
                        continue
            
            # Выполняем инструмент
            result = await self.registry.execute(tool_name, **params)
            results.append(result)
            
            # Сохраняем в историю
            self.history.append({
                "call": call,
                "result": result.to_dict(),
                "timestamp": datetime.now().isoformat()
            })
        
        return results
    
    def format_results_for_llm(self, results: List[ToolResult]) -> str:
        """Форматирует результаты для отправки обратно в LLM"""
        formatted = []
        
        for result in results:
            status = "✅" if result.success else "❌"
            formatted.append(f"""
{status} **{result.tool_name}** ({result.execution_time:.2f}с)
```json
{json.dumps(result.output, ensure_ascii=False, indent=2) if result.output else "null"}
```
{f"Ошибка: {result.error}" if result.error else ""}
""")
        
        return "\n".join(formatted)


# Глобальный экземпляр
tool_registry = ToolRegistry()
tool_executor = ToolExecutor(tool_registry)
