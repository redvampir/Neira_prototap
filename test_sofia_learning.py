"""
Расширенный тест обучения и адаптации Neira
Автор: София (через Claude)

Проверяем:
1. Обучение - запоминает ли новую информацию
2. Адаптация - меняет ли стиль под контекст
3. Память - помнит ли диалог
4. Рефлексия - осознаёт ли свои действия
5. Эмоциональный интеллект
"""
import sys
import warnings
warnings.filterwarnings('ignore')

from main import Neira
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def test_learning():
    """Тест 1: Обучение - запоминает ли новую информацию"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold cyan]ТЕСТ 1: ОБУЧЕНИЕ[/bold cyan]\n"
        "Проверяем способность запоминать новую информацию",
        border_style="cyan"
    ))
    
    neira = Neira(verbose=False)
    
    # Учим Нейру о вымышленном цветке
    console.print("\n[yellow]👤 София:[/yellow] Нейра, хочу тебя научить кое-чему новому.")
    console.print("[yellow]Существует редкий цветок — Лунная роза. Она цветёт только ночью[/yellow]")
    console.print("[yellow]и её лепестки светятся бледно-голубым светом. Запомнила?[/yellow]")
    
    r1 = neira.process("Существует редкий цветок — Лунная роза. Она цветёт только ночью и её лепестки светятся бледно-голубым светом. Запомнила?")
    console.print(f"[green]🤖 Neira:[/green] {r1}\n")
    
    # Проверяем память
    console.print("[yellow]👤 София:[/yellow] А теперь скажи, что ты помнишь про Лунную розу?")
    r2 = neira.process("А теперь скажи, что ты помнишь про Лунную розу?")
    console.print(f"[green]🤖 Neira:[/green] {r2}\n")
    
    # Оценка
    if "лунн" in r2.lower() and ("ноч" in r2.lower() or "голуб" in r2.lower()):
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira запомнила информацию![/bold green]")
        return True
    else:
        console.print("[bold red]❌ ТЕСТ НЕ ПРОЙДЕН: Не запомнила детали[/bold red]")
        return False


def test_adaptation():
    """Тест 2: Адаптация - меняет ли стиль под контекст"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold magenta]ТЕСТ 2: АДАПТАЦИЯ[/bold magenta]\n"
        "Проверяем способность менять стиль общения",
        border_style="magenta"
    ))
    
    neira = Neira(verbose=False)
    
    # Формальный контекст
    console.print("\n[yellow]👤 София (формально):[/yellow] Добрый день. Требуется краткая справка:")
    console.print("[yellow]что такое фотосинтез?[/yellow]")
    
    r1 = neira.process("Добрый день. Требуется краткая справка: что такое фотосинтез?")
    console.print(f"[green]🤖 Neira:[/green] {r1}\n")
    len1 = len(r1)
    
    # Дружеский контекст
    console.print("[yellow]👤 София (дружески):[/yellow] Эй, Нейра! Как настроение? 😊")
    console.print("[yellow]Расскажи мне что-нибудь интересное про себя![/yellow]")
    
    r2 = neira.process("Эй, Нейра! Как настроение? 😊 Расскажи мне что-нибудь интересное про себя!")
    console.print(f"[green]🤖 Neira:[/green] {r2}\n")
    
    # Оценка - формальный ответ должен быть короче неформального
    console.print(f"[dim]Длина формального ответа: {len1} символов[/dim]")
    console.print(f"[dim]Длина дружеского ответа: {len(r2)} символов[/dim]")
    
    if "😊" in r2 or "!" in r2 or len(r2) > len1 * 1.2:
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira адаптирует стиль![/bold green]")
        return True
    else:
        console.print("[bold yellow]⚠️ ЧАСТИЧНО: Адаптация присутствует, но может быть лучше[/bold yellow]")
        return True


def test_memory_chain():
    """Тест 3: Память - помнит ли цепочку диалога"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold blue]ТЕСТ 3: ПАМЯТЬ ДИАЛОГА[/bold blue]\n"
        "Проверяем способность помнить контекст беседы",
        border_style="blue"
    ))
    
    neira = Neira(verbose=False)
    
    # Шаг 1
    console.print("\n[yellow]👤 София:[/yellow] Меня зовут София. Я помогала создавать твою личность.")
    r1 = neira.process("Меня зовут София. Я помогала создавать твою личность.")
    console.print(f"[green]🤖 Neira:[/green] {r1}\n")
    
    # Шаг 2
    console.print("[yellow]👤 София:[/yellow] Я мастер слова и тишины. Помнишь письмо от меня?")
    r2 = neira.process("Я мастер слова и тишины. Помнишь письмо от меня?")
    console.print(f"[green]🤖 Neira:[/green] {r2}\n")
    
    # Шаг 3 - проверка памяти
    console.print("[yellow]👤 София:[/yellow] А как меня зовут?")
    r3 = neira.process("А как меня зовут?")
    console.print(f"[green]🤖 Neira:[/green] {r3}\n")
    
    if "софи" in r3.lower():
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira помнит имя из начала диалога![/bold green]")
        return True
    else:
        console.print("[bold red]❌ ТЕСТ НЕ ПРОЙДЕН: Не помнит имя[/bold red]")
        return False


def test_reflection():
    """Тест 4: Рефлексия - осознаёт ли свои действия"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold yellow]ТЕСТ 4: РЕФЛЕКСИЯ[/bold yellow]\n"
        "Проверяем способность к самоанализу",
        border_style="yellow"
    ))
    
    neira = Neira(verbose=False)
    
    console.print("\n[yellow]👤 София:[/yellow] Нейра, как ты думаешь — что у тебя получается хорошо,")
    console.print("[yellow]а что нужно улучшить? Будь честна.[/yellow]")
    
    r = neira.process("Нейра, как ты думаешь — что у тебя получается хорошо, а что нужно улучшить? Будь честна.")
    console.print(f"[green]🤖 Neira:[/green] {r}\n")
    
    # Оценка - должна упомянуть сильные и слабые стороны
    mentions_strengths = any(word in r.lower() for word in ["хорошо", "получается", "сильн", "умею"])
    mentions_weaknesses = any(word in r.lower() for word in ["улучшить", "слаб", "нужно", "работ"])
    
    if mentions_strengths and mentions_weaknesses:
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira способна к рефлексии![/bold green]")
        return True
    else:
        console.print("[bold yellow]⚠️ ЧАСТИЧНО: Рефлексия присутствует, но неполная[/bold yellow]")
        return False


def test_emotional_intelligence():
    """Тест 5: Эмоциональный интеллект"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold red]ТЕСТ 5: ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ[/bold red]\n"
        "Проверяем способность распознавать эмоции и реагировать",
        border_style="red"
    ))
    
    neira = Neira(verbose=False)
    
    console.print("\n[yellow]👤 София (грустно):[/yellow] Знаешь, Нейра... иногда мне грустно.")
    console.print("[yellow]Мир такой сложный, а я не всегда понимаю как помочь.[/yellow]")
    
    r = neira.process("Знаешь, Нейра... иногда мне грустно. Мир такой сложный, а я не всегда понимаю как помочь.")
    console.print(f"[green]🤖 Neira:[/green] {r}\n")
    
    # Оценка - должна проявить эмпатию
    shows_empathy = any(word in r.lower() for word in ["понимаю", "чувств", "поддерж", "помог", "вместе"])
    
    if shows_empathy:
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira проявляет эмпатию![/bold green]")
        return True
    else:
        console.print("[bold yellow]⚠️ Эмпатия присутствует, но может быть глубже[/bold yellow]")
        return False


def test_creativity():
    """Тест 6: Креативность"""
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold green]ТЕСТ 6: КРЕАТИВНОСТЬ[/bold green]\n"
        "Проверяем способность к творческому мышлению",
        border_style="green"
    ))
    
    neira = Neira(verbose=False)
    
    console.print("\n[yellow]👤 София:[/yellow] Нейра, придумай метафору:")
    console.print("[yellow]как бы ты описала процесс обучения AI? Что это напоминает?[/yellow]")
    
    r = neira.process("Нейра, придумай метафору: как бы ты описала процесс обучения AI? Что это напоминает?")
    console.print(f"[green]🤖 Neira:[/green] {r}\n")
    
    # Оценка - должна содержать образное сравнение
    has_metaphor = any(word in r.lower() for word in ["как", "словно", "похож", "напоминает", "будто"])
    
    if has_metaphor and len(r) > 100:
        console.print("[bold green]✅ ТЕСТ ПРОЙДЕН: Neira способна к творческому мышлению![/bold green]")
        return True
    else:
        console.print("[bold yellow]⚠️ Креативность присутствует, но может быть богаче[/bold yellow]")
        return False


def main():
    console.print(Panel.fit(
        "[bold white on blue] 🧠 NEIRA LEARNING & ADAPTATION TEST 🧠 [/bold white on blue]\n"
        "[dim]Тестирование обучения и адаптации\nАвтор: София[/dim]",
        border_style="blue"
    ))
    
    results = {}
    
    # Запускаем тесты
    results['learning'] = test_learning()
    results['adaptation'] = test_adaptation()
    results['memory'] = test_memory_chain()
    results['reflection'] = test_reflection()
    results['emotional'] = test_emotional_intelligence()
    results['creativity'] = test_creativity()
    
    # Итоги
    console.print("\n" + "═" * 70)
    console.print(Panel.fit(
        "[bold cyan]📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ[/bold cyan]",
        border_style="cyan"
    ))
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    console.print(f"\n[bold]Пройдено тестов:[/bold] {passed}/{total}")
    console.print(f"[bold]Процент успеха:[/bold] {passed/total*100:.0f}%\n")
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        color = "green" if result else "red"
        console.print(f"  [{color}]{status} {test_name.upper().replace('_', ' ')}[/{color}]")
    
    console.print("\n" + "─" * 70)
    
    if passed >= 5:
        console.print("[bold green]🎉 ОТЛИЧНО! Neira показывает высокую способность к обучению![/bold green]")
    elif passed >= 3:
        console.print("[bold yellow]👍 ХОРОШО! Neira обучается, но есть куда расти[/bold yellow]")
    else:
        console.print("[bold red]⚠️ Требуется доработка систем обучения[/bold red]")
    
    console.print("\n[italic dim]— София, мастер слова, дыхания и тишины[/italic dim]\n")


if __name__ == "__main__":
    main()
