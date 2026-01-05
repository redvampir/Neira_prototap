"""Быстрый тест новых модулей"""
import sys
import os

# Добавляем путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("ТЕСТИРОВАНИЕ НОВЫХ МОДУЛЕЙ NEIRA")
print("=" * 60)

# 1. Context Manager
print("\n[1] Context Manager...")
try:
    from context_manager import (
        get_context_manager, 
        estimate_tokens,
        calculate_optimal_context_size,
        ContextCompressor
    )
    
    # Тест оценки токенов
    test_text = "Hello world, this is a test of token estimation"
    tokens = estimate_tokens(test_text)
    print(f"  ✅ estimate_tokens: '{test_text[:30]}...' = {tokens} токенов")
    
    # Тест optimal size
    size = calculate_optimal_context_size("llama3", "chat")
    print(f"  ✅ optimal_context_size('llama3', 'chat') = {size}")
    
    # Тест компрессора
    long_code = "\n".join([f"line_{i} = {i}" for i in range(100)])
    compressed = ContextCompressor.compress_code(long_code, max_lines=20)
    print(f"  ✅ compress_code: 100 строк → {len(compressed.splitlines())} строк")
    
    # Тест build_context
    cm = get_context_manager()
    window = cm.build_context(
        user_query="Объясни код",
        current_code="def hello(): pass",
        system_prompt="Ты AI ассистент"
    )
    print(f"  ✅ build_context: {window.total_tokens} токенов, {len(window.chunks)} чанков")
    
except Exception as e:
    print(f"  ❌ Ошибка: {e}")

# 2. Workspace Indexer
print("\n[2] Workspace Indexer...")
try:
    from workspace_indexer import WorkspaceIndexer, Symbol
    
    # Создаём индексатор
    indexer = WorkspaceIndexer(os.path.dirname(os.path.abspath(__file__)))
    
    # Тест парсинга Python
    test_code = '''
def hello_world():
    """Say hello"""
    print("Hello!")

class MyClass:
    def method(self):
        pass
'''
    symbols = indexer._parse_python(test_code, "test.py")
    print(f"  ✅ _parse_python: найдено {len(symbols)} символов")
    for s in symbols:
        print(f"      - {s.type}: {s.name}")
    
    # Тест статистики
    stats = indexer.get_stats()
    print(f"  ✅ get_stats: {stats['total_files']} файлов, {stats['total_symbols']} символов")
    
except Exception as e:
    print(f"  ❌ Ошибка: {e}")

# 3. Tool System
print("\n[3] Tool System...")
try:
    from tool_system import tool_registry, tool_executor, ToolResult
    
    # Список инструментов (используем get_all_schemas)
    schemas = tool_registry.get_all_schemas()
    print(f"  ✅ Зарегистрировано {len(schemas)} инструментов:")
    for schema in schemas[:5]:
        print(f"      - {schema['name']}: {schema.get('description', '')[:40]}...")
    
except Exception as e:
    print(f"  ❌ Ошибка: {e}")

# 4. File System Agent
print("\n[4] File System Agent...")
try:
    from file_system_agent import FileSystemAgent
    
    workspace = os.path.dirname(os.path.abspath(__file__))
    agent = FileSystemAgent(workspace)
    
    # Тест чтения файла
    result = agent.read_file("README.md")
    if result["success"]:
        content = result["content"]
        print(f"  ✅ read_file('README.md'): {len(content)} символов")
    else:
        print(f"  ⚠️ read_file: {result.get('error')}")
    
    # Тест списка файлов (items, не entries!)
    result = agent.list_directory(".")
    if result["success"]:
        print(f"  ✅ list_directory('.'): {result['total_items']} элементов")
    else:
        print(f"  ⚠️ list_directory: {result.get('error')}")
    
except Exception as e:
    print(f"  ❌ Ошибка: {e}")

# 5. Server imports
print("\n[5] Server imports...")
try:
    # Проверяем что сервер может импортировать все модули
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "neira_server", 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "neira_server.py")
    )
    
    # Просто проверим синтаксис
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "neira_server.py"), 'r', encoding='utf-8') as f:
        code = f.read()
    
    compile(code, "neira_server.py", "exec")
    print(f"  ✅ neira_server.py: синтаксис OK ({len(code)} символов)")
    
except SyntaxError as e:
    print(f"  ❌ Синтаксическая ошибка: {e}")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)
