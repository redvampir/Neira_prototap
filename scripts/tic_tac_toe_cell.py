"""
TicTacToe Cell v1.0 — Орган игры в крестики-нолики для Neira

Создан Claude как учебный пример для Neira.
Демонстрирует как создавать новые клетки/органы.
"""

import random
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class GameResult:
    """Результат игры"""
    winner: Optional[str]  # 'X', 'O', или None (ничья)
    moves_count: int
    board_final: List[str]


class TicTacToeCell:
    """
    Клетка игры в крестики-нолики
    
    Neira может играть с людьми или сама с собой!
    Использует простую тактику с элементами стратегии.
    """
    
    VERSION = "1.0"
    
    # Выигрышные комбинации (индексы)
    WIN_PATTERNS = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # горизонтали
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # вертикали
        [0, 4, 8], [2, 4, 6]              # диагонали
    ]
    
    def __init__(self):
        self.board = [' '] * 9  # 9 клеток
        self.current_player = 'X'
        self.games_played = 0
        self.wins = {'X': 0, 'O': 0, 'draw': 0}
        self.move_history: List[Tuple[str, int]] = []
    
    def reset(self):
        """Начать новую игру"""
        self.board = [' '] * 9
        self.current_player = 'X'
        self.move_history = []
    
    def display(self) -> str:
        """Красиво показать поле"""
        b = self.board
        lines = [
            "┌───┬───┬───┐",
            f"│ {b[0]} │ {b[1]} │ {b[2]} │  0 1 2",
            "├───┼───┼───┤",
            f"│ {b[3]} │ {b[4]} │ {b[5]} │  3 4 5",
            "├───┼───┼───┤",
            f"│ {b[6]} │ {b[7]} │ {b[8]} │  6 7 8",
            "└───┴───┴───┘"
        ]
        return '\n'.join(lines)
    
    def make_move(self, position: int) -> bool:
        """Сделать ход (0-8)"""
        if position < 0 or position > 8:
            return False
        if self.board[position] != ' ':
            return False
        
        self.board[position] = self.current_player
        self.move_history.append((self.current_player, position))
        self.current_player = 'O' if self.current_player == 'X' else 'X'
        return True
    
    def check_winner(self) -> Optional[str]:
        """Проверить победителя"""
        for pattern in self.WIN_PATTERNS:
            a, b, c = pattern
            if self.board[a] == self.board[b] == self.board[c] != ' ':
                return self.board[a]
        return None
    
    def is_draw(self) -> bool:
        """Проверка на ничью"""
        return ' ' not in self.board and self.check_winner() is None
    
    def get_empty_cells(self) -> List[int]:
        """Получить пустые клетки"""
        return [i for i, cell in enumerate(self.board) if cell == ' ']
    
    # === ТАКТИКА NEIRA ===
    
    def find_winning_move(self, player: str) -> Optional[int]:
        """Найти выигрышный ход для игрока"""
        for pos in self.get_empty_cells():
            # Симулируем ход
            self.board[pos] = player
            if self.check_winner() == player:
                self.board[pos] = ' '
                return pos
            self.board[pos] = ' '
        return None
    
    def ai_move(self) -> int:
        """
        Умный ход ИИ (Neira)
        
        Приоритеты:
        1. Выиграть если можно
        2. Блокировать победу противника
        3. Занять центр
        4. Занять угол
        5. Случайный ход
        """
        me = self.current_player
        opponent = 'O' if me == 'X' else 'X'
        empty = self.get_empty_cells()
        
        if not empty:
            return -1
        
        # 1. Можем выиграть?
        win_move = self.find_winning_move(me)
        if win_move is not None:
            return win_move
        
        # 2. Нужно блокировать?
        block_move = self.find_winning_move(opponent)
        if block_move is not None:
            return block_move
        
        # 3. Центр свободен?
        if 4 in empty:
            return 4
        
        # 4. Углы
        corners = [0, 2, 6, 8]
        free_corners = [c for c in corners if c in empty]
        if free_corners:
            return random.choice(free_corners)
        
        # 5. Что осталось
        return random.choice(empty)
    
    def play_game_interactive(self) -> str:
        """Интерактивная игра (для консоли)"""
        self.reset()
        output = ["🎮 КРЕСТИКИ-НОЛИКИ", "=" * 30, ""]
        output.append(self.display())
        output.append("")
        
        while True:
            winner = self.check_winner()
            if winner:
                self.wins[winner] += 1
                self.games_played += 1
                output.append(f"🏆 Победил {winner}!")
                break
            
            if self.is_draw():
                self.wins['draw'] += 1
                self.games_played += 1
                output.append("🤝 Ничья!")
                break
            
            output.append(f"Ход: {self.current_player}")
        
        return '\n'.join(output)
    
    def play_vs_ai(self, human_symbol: str = 'X') -> GameResult:
        """Игра человек vs AI"""
        self.reset()
        ai_symbol = 'O' if human_symbol == 'X' else 'X'
        
        # Если AI ходит первым
        if ai_symbol == 'X':
            move = self.ai_move()
            self.make_move(move)
        
        return GameResult(
            winner=None,
            moves_count=len(self.move_history),
            board_final=self.board.copy()
        )
    
    def play_ai_vs_ai(self) -> GameResult:
        """AI vs AI (для демонстрации)"""
        self.reset()
        
        while True:
            winner = self.check_winner()
            if winner:
                self.wins[winner] += 1
                self.games_played += 1
                return GameResult(winner=winner, moves_count=len(self.move_history), board_final=self.board.copy())
            
            if self.is_draw():
                self.wins['draw'] += 1
                self.games_played += 1
                return GameResult(winner=None, moves_count=len(self.move_history), board_final=self.board.copy())
            
            move = self.ai_move()
            self.make_move(move)
    
    def get_stats(self) -> str:
        """Статистика игр"""
        return f"""📊 Статистика:
  Сыграно: {self.games_played}
  X побед: {self.wins['X']}
  O побед: {self.wins['O']}
  Ничьих: {self.wins['draw']}"""


# === Глобальный доступ ===
_game_cell: Optional[TicTacToeCell] = None

def get_game_cell() -> TicTacToeCell:
    """Получить клетку игры"""
    global _game_cell
    if _game_cell is None:
        _game_cell = TicTacToeCell()
    return _game_cell


# === Тестирование ===
if __name__ == "__main__":
    print("🎮 TicTacToe Cell v1.0")
    print("=" * 40)
    
    game = TicTacToeCell()
    
    # Демо: AI vs AI
    print("\n🤖 AI vs AI демо:")
    result = game.play_ai_vs_ai()
    print(game.display())
    if result.winner:
        print(f"Победитель: {result.winner}")
    else:
        print("Ничья!")
    
    print(f"\n{game.get_stats()}")
