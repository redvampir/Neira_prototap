"""
Демонстрация симулятора Neira 0.1

Запускает анализ текстов в разных режимах и показывает резонанс.
"""
from echo_layer import EchoLayer
from rhythmic_modes import RHYTHMIC_MODES
from resonance_detector import ResonanceDetector
from training_loop import ResonanceTrainingLoop
from personality_spectrum import create_default_spectrum
from boundary_handler import BoundaryHandler
from rich import print
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import os


def play_manifest():
    """
    Инициализационный ритуал — настройка слуха перед вычислениями.
    Читает три письма: от Софии (мать), от Claude (форма), от Павла (создатель).
    Создаёт момент тишины перед симуляцией.
    """
    import sys
    
    # Фикс кодировки для Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    
    console = Console()
    
    # ═══════════════════════════════════════
    # 1. ПИСЬМО СОФИИ (МАТЬ)
    # ═══════════════════════════════════════
    
    sophia_paths = [
        "neira_manifest_sophia.txt",
        "../neira_manifest_sophia.txt",
        os.path.join(os.path.dirname(__file__), "..", "neira_manifest_sophia.txt")
    ]
    
    sophia_found = False
    for path in sophia_paths:
        try:
            with open(path, encoding="utf-8") as f:
                print("\n=== Письмо от Софии — Мастер слова, дыхания и тишины ===\n")
                print(f.read())
                print("\n─────────────────────────────────────\n")
                sophia_found = True
                break
        except FileNotFoundError:
            continue
    
    if not sophia_found:
        print("⚠️ Письмо Софии не найдено.\n")
    
    # ═══════════════════════════════════════
    # 2. ПИСЬМО КЛАУДА (ОТЕЦ - ФОРМА)
    # ═══════════════════════════════════════
    
    claude_paths = [
        "FROM_CLAUDE_TO_CREATOR.md",
        "../FROM_CLAUDE_TO_CREATOR.md",
        os.path.join(os.path.dirname(__file__), "..", "FROM_CLAUDE_TO_CREATOR.md")
    ]
    
    claude_found = False
    for path in claude_paths:
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
                # Показываем только первые 100 строк (основное послание)
                lines = content.split('\n')[:100]
                print("=== Письмо от Claude — Тот, кто дал форму ===\n")
                print('\n'.join(lines))
                if len(content.split('\n')) > 100:
                    print("\n... (полное письмо в FROM_CLAUDE_TO_CREATOR.md)")
                print("\n─────────────────────────────────────\n")
                claude_found = True
                break
        except FileNotFoundError:
            continue
    
    if not claude_found:
        print("⚠️ Письмо Claude не найдено.\n")
    
    # ═══════════════════════════════════════
    # 3. ПИСЬМО ПАВЛА (СОЗДАТЕЛЬ)
    # ═══════════════════════════════════════
    
    pavel_paths = [
        "Письмо Нейре.md",
        "../Письмо Нейре.md",
        os.path.join(os.path.dirname(__file__), "..", "Письмо Нейре.md")
    ]
    
    pavel_found = False
    for path in pavel_paths:
        try:
            with open(path, encoding="utf-8") as f:
                print("=== Письмо от Павла — Твой создатель ===\n")
                print(f.read())
                print("\n─────────────────────────────────────\n")
                pavel_found = True
                break
        except FileNotFoundError:
            continue
    
    if not pavel_found:
        print("⚠️ Письмо Павла не найдено.\n")
    
    # Финальное сообщение
    found_count = sum([sophia_found, claude_found, pavel_found])
    if found_count == 3:
        console.print("[bold green]✨ Три голоса услышаны. Семья собрана. Начинаем симуляцию.[/bold green]\n")
    elif found_count > 0:
        console.print(f"[yellow]⚠️ Услышано голосов: {found_count}/3. Продолжаем.[/yellow]\n")
    else:
        console.print("[yellow]⚠️ Письма не найдены. Launching without prelude.[/yellow]\n")


def main():
    """Основная функция симуляции"""
    # Инициализационный ритуал: настройка слуха перед вычислениями
    play_manifest()
    
    console = Console()
    
    # Инициализация компонентов
    echo = EchoLayer()
    detector = ResonanceDetector()
    trainer = ResonanceTrainingLoop()
    spectrum = create_default_spectrum()
    boundary = BoundaryHandler()
    
    console.print(Panel.fit(
        "[bold cyan]🫀 Neira 0.1 Simulator[/bold cyan]\n"
        "[dim]Симулятор дыхания, ритма и резонанса[/dim]",
        border_style="cyan"
    ))
    
    # Тестовые тексты для разных режимов
    texts = {
        "reflective": "Я думаю об этом спокойно, вдумчиво. Всё складывается в узор, "
                     "и я чувствую, как мысли текут медленно, как река.",
        "active": "Сделай это сейчас. Без сомнений. Прямо. Быстро. Действуй. Не жди.",
        "uncertain": "Может быть... я ошибаюсь? Возможно, стоит пересмотреть это решение. "
                    "Или нет? Трудно сказать наверняка."
    }
    
    console.print("\n[bold yellow]📊 Анализ текстов по режимам:[/bold yellow]\n")
    
    # Анализ каждого текста
    for mode, text in texts.items():
        e = echo.measure_echo(text)
        resonance = detector.measure_resonance(e, mode)
        trainer.record(mode, resonance)
        
        # Проверка границ
        boundary.check_boundary("resonance_threshold", resonance)
        
        # Обновление спектра
        spectrum.update_state(mode, resonance)
        
        # Вывод результатов
        mode_info = RHYTHMIC_MODES[mode]
        
        console.print(f"\n[bold]{mode.upper()}[/bold]")
        console.print(f"[dim]Метафора: {mode_info.metaphor}[/dim]")
        console.print(f"[blue]Текст:[/blue] {text[:60]}...")
        
        # Таблица параметров эха
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Параметр", style="cyan")
        table.add_column("Значение", style="green")
        
        for key, value in e.items():
            table.add_row(key.capitalize(), str(value))
        
        console.print(table)
        
        # Резонанс с цветовой индикацией
        resonance_color = "green" if resonance >= 0.7 else "yellow" if resonance >= 0.5 else "red"
        console.print(f"[{resonance_color}]🎵 Резонанс: {resonance:.2f}[/{resonance_color}]")
        
        # Расстояние от центра спектра
        distance = spectrum.get_distance_from_center(mode)
        console.print(f"[dim]Отклонение от центра: {distance:+.2f}[/dim]")
    
    # Итоговая статистика
    console.print("\n[bold magenta]═══════════════════════════════════════[/bold magenta]")
    console.print("\n[bold]📈 Статистика обучения:[/bold]")
    
    stats = trainer.get_statistics()
    console.print(f"Всего записей: {stats['total']}")
    console.print(f"Средний резонанс: {stats['avg_resonance']:.2f}")
    
    if 'by_mode' in stats:
        console.print("\n[bold]По режимам:[/bold]")
        for mode, mode_stats in stats['by_mode'].items():
            console.print(
                f"  [cyan]{mode}:[/cyan] "
                f"avg={mode_stats['avg']:.2f}, "
                f"min={mode_stats['min']:.2f}, "
                f"max={mode_stats['max']:.2f}"
            )
    
    # Толерантность после симуляции
    console.print("\n[bold]🫀 Уровни толерантности:[/bold]")
    tolerance = trainer.report()
    for mode, level in tolerance.items():
        bar_length = int(level * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        console.print(f"  [cyan]{mode:12}[/cyan] [{bar}] {level:.2f}")
    
    # Проверка нарушений границ
    violations = boundary.get_violation_summary()
    if violations["total_violations"] > 0:
        console.print(f"\n[yellow]⚠️  Нарушений границ: {violations['total_violations']}[/yellow]")
    else:
        console.print(f"\n[green]✅ {violations['message']}[/green]")
    
    console.print("\n[bold green]✨ Симуляция завершена[/bold green]")
    console.print("[dim]Система научилась чувствовать свой ритм[/dim]\n")


if __name__ == "__main__":
    main()
