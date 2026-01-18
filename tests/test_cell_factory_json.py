"""Тест улучшенного парсинга JSON в CellFactory"""

from cell_factory import _extract_json_block

def test_extract_json():
    tests = [
        # Markdown блок
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        # Простой JSON
        ('{"direct": true}', '{"direct": true}'),
        # JSON в тексте
        ('Вот спецификация: {"cell_name": "test", "value": 123}', '{"cell_name": "test", "value": 123}'),
        # Без JSON
        ('No JSON here', None),
        # Markdown без json тега
        ('```\n{"b": 2}\n```', '{"b": 2}'),
        # Сложный вложенный JSON
        ('{"outer": {"inner": [1, 2, 3]}}', '{"outer": {"inner": [1, 2, 3]}}'),
    ]
    
    passed = 0
    for input_text, expected in tests:
        result = _extract_json_block(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Input: {repr(input_text[:50])}...")
        print(f"   Expected: {expected}")
        print(f"   Got: {result}")
        if result == expected:
            passed += 1
        print()
    
    print(f"\n🎯 Passed: {passed}/{len(tests)}")
    return passed == len(tests)

if __name__ == "__main__":
    success = test_extract_json()
    exit(0 if success else 1)
