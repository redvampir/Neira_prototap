import pytest
from cells import Cell

@pytest.mark.parametrize("user_input,expect_identity", [
    ("Кто ты?", True),
    ("Расскажи о себе", True),
    ("Ты создан Павлом?", True),
    ("Подходит ли утеплитель 200 г/м² для -20?", False),
    ("Как выбрать куртку для -20?", False),
])
def test_is_identity_query(user_input, expect_identity):
    from cells import is_identity_query
    assert is_identity_query(user_input) == expect_identity


def test_no_bio_in_expert_answer(monkeypatch):
    """Проверяет, что в экспертном ответе нет автобиографии."""
    class DummyCell(Cell):
        system_prompt = "Ты — эксперт по одежде."
        def call_llm(self, prompt, *a, **kw):
            # Симулируем генерацию ответа
            return "Для -20°C подходит утеплитель 200-250 г/м²."
    cell = DummyCell()
    # monkeypatch _merge_system_prompt чтобы отследить include_identity
    from cells import _merge_system_prompt
    called = {}
    def fake_merge(base, layer, include_organs=True, include_identity=False):
        called['identity'] = include_identity
        return base
    monkeypatch.setattr("cells._merge_system_prompt", fake_merge)
    cell._call_ollama_legacy("Подходит ли утеплитель 200 г/м² для -20?", 0.7, False, "")
    assert called['identity'] is False


def test_bio_in_identity_answer(monkeypatch):
    """Проверяет, что автобиография добавляется по запросу 'кто ты'."""
    class DummyCell(Cell):
        system_prompt = "Ты — ассистент."
        def call_llm(self, prompt, *a, **kw):
            return "Я — программа, созданная Павлом."
    cell = DummyCell()
    from cells import _merge_system_prompt
    called = {}
    def fake_merge(base, layer, include_organs=True, include_identity=False):
        called['identity'] = include_identity
        return base
    monkeypatch.setattr("cells._merge_system_prompt", fake_merge)
    cell._call_ollama_legacy("Кто ты?", 0.7, False, "")
    assert called['identity'] is True


def test_expert_answer_structure(monkeypatch):
    """Проверяет, что экспертные ответы структурированы с разделами."""
    from cells import ExecutorCell

    class MockExecutorCell(ExecutorCell):
        def call_llm(self, prompt, *a, **kw):
            # Симулируем структурированный экспертный ответ
            return """## 📋 КРАТКИЙ ВЫВОД
Утеплитель 200 г/м² подходит для температуры до -15°C.

## 📖 ПОДРОБНОЕ ОБЪЯСНЕНИЕ
Для суровых зимних условий (-20°C) требуется минимум 250 г/м².

## ✅ РЕКОМЕНДАЦИИ
Выберите утеплитель 300 г/м² для максимальной защиты.

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ
Учитывайте влажность и ветер при выборе.

## ❓ ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ
**Можно ли использовать 200 г/м² в -20?** Нет, лучше 250+.

## 🔗 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ
Изучите стандарты ГОСТ Р 12.4.236-2011."""

    cell = MockExecutorCell()
    result = cell.process(
        input_data="Подходит ли утеплитель 200 г/м² для -20?",
        plan="Оценить пригодность утеплителя для заданной температуры"
    )

    response = result.content

    # Проверяем наличие основных разделов структурированного ответа
    assert "## 📋 КРАТКИЙ ВЫВОД" in response
    assert "## 📖 ПОДРОБНОЕ ОБЪЯСНЕНИЕ" in response
    assert "## ✅ РЕКОМЕНДАЦИИ" in response
    assert "## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ" in response
    assert "## ❓ ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ" in response
    assert "## 🔗 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ" in response
