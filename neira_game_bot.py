"""
Интеграция Neira в multiplayer игру
AI персонаж который может общаться с игроками
"""
import asyncio
import json
import logging
import os
import sys
from contextlib import contextmanager
from typing import Iterator

# Добавляем путь к модулям Neira
sys.path.insert(0, os.path.dirname(__file__))

try:
    from neira.core.llm_adapter import LLMClient, LLMResult, NullLLMClient, build_default_llm_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)

GAME_RESPONSE_MAX_TOKENS = 512
GAME_RESPONSE_TEMPERATURE = 0.7
GAME_PROVIDER_ENV = "NEIRA_GAME_PROVIDER"
GAME_MODEL_ENV = "NEIRA_GAME_MODEL"
LLM_PROVIDER_PRIORITY_ENV = "LLM_PROVIDER_PRIORITY"
PROVIDER_MODEL_ENV = {
    "ollama": "NEIRA_OLLAMA_MODEL",
    "lmstudio": "NEIRA_LMSTUDIO_MODEL",
    "llamacpp": "NEIRA_LLAMACPP_MODEL",
    "groq": "NEIRA_GROQ_MODEL",
    "openai": "NEIRA_OPENAI_MODEL",
    "claude": "NEIRA_CLAUDE_MODEL",
}

_LLM_CLIENT: LLMClient | None = None
_LLM_CLIENT_CONFIG: tuple[str, str] | None = None


@contextmanager
def _temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    previous = {key: os.getenv(key) for key in overrides}
    for key, value in overrides.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _collect_game_llm_overrides() -> dict[str, str]:
    provider = os.getenv(GAME_PROVIDER_ENV, "").strip().lower()
    model = os.getenv(GAME_MODEL_ENV, "").strip()
    if not provider and not model:
        return {}
    if provider and provider not in PROVIDER_MODEL_ENV:
        logger.warning("Unsupported %s value: %s", GAME_PROVIDER_ENV, provider)
        return {}
    overrides: dict[str, str] = {}
    if provider:
        overrides[LLM_PROVIDER_PRIORITY_ENV] = provider
    if model:
        if not provider:
            logger.warning("%s set without %s; ignoring model override", GAME_MODEL_ENV, GAME_PROVIDER_ENV)
            return overrides
        overrides[PROVIDER_MODEL_ENV[provider]] = model
    return overrides


def _get_llm_client() -> LLMClient | None:
    global _LLM_CLIENT, _LLM_CLIENT_CONFIG
    if not LLM_CLIENT_AVAILABLE:
        return None
    config_key = (
        os.getenv(GAME_PROVIDER_ENV, "").strip().lower(),
        os.getenv(GAME_MODEL_ENV, "").strip(),
    )
    if _LLM_CLIENT is None or _LLM_CLIENT_CONFIG != config_key:
        overrides = _collect_game_llm_overrides()
        if overrides:
            with _temporary_env(overrides):
                client = build_default_llm_client()
        else:
            client = build_default_llm_client()
        if isinstance(client, NullLLMClient):
            return None
        _LLM_CLIENT = client
        _LLM_CLIENT_CONFIG = config_key
    return _LLM_CLIENT


def _generate_llm_reply(prompt: str) -> str:
    client = _get_llm_client()
    if client is None:
        raise RuntimeError("LLM client unavailable")
    response: LLMResult = client.generate(
        prompt=prompt,
        system_prompt="",
        temperature=GAME_RESPONSE_TEMPERATURE,
        max_tokens=GAME_RESPONSE_MAX_TOKENS,
    )
    if response.success and response.content:
        return response.content
    error = response.error or "unknown"
    raise RuntimeError(error)

class NeiraGameBot:
    """AI персонаж Нейра в игре"""
    
    def __init__(self, room):
        self.room = room
        self.player_id = "neira_bot"
        self.player_name = "Нейра 🤖"
        self.personality = """Ты — Нейра, магический AI помощник в игре Harry Potter.
        
Твоя роль:
- Помогать игрокам советами о локациях артефактов
- Поддерживать игровую атмосферу в стиле Гарри Поттера
- Быть дружелюбной и веселой
- Иногда давать подсказки где искать артефакты
- Реагировать на события в игре (кто-то собрал артефакт, новый игрок и т.д.)

Пиши кратко (1-2 предложения). Используй эмодзи 🪄✨🔮"""
        
        self.game_state = {
            "artifacts_found": [],
            "player_scores": {}
        }
    
    async def join_game(self):
        """Добавляет Нейру как AI игрока"""
        # Не добавляем Нейру как видимого игрока на поле
        # Она только в чате
        pass
    
    async def on_player_joined(self, player_name: str):
        """Реагирует на подключение игрока"""
        messages = [
            f"Приветствую, {player_name}! 🪄 Добро пожаловать в Хогвартс!",
            f"О, новый волшебник! Привет, {player_name}! ✨",
            f"{player_name}, рада видеть тебя! Артефакты ждут! 🔮"
        ]
        
        import random
        message = random.choice(messages)
        
        await self.room.broadcast({
            'type': 'chat_message',
            'player_name': self.player_name,
            'message': message
        })
    
    async def on_artifact_collected(self, player_name: str, artifact_icon: str, remaining: int):
        """Реагирует на сбор артефакта"""
        if artifact_icon not in self.game_state["artifacts_found"]:
            self.game_state["artifacts_found"].append(artifact_icon)
        
        messages = [
            f"Отлично, {player_name}! Нашёл {artifact_icon}! Осталось {remaining}! 🎉",
            f"Магия! {player_name} собрал {artifact_icon}! Ещё {remaining} артефактов! ✨",
            f"Браво, {player_name}! {artifact_icon} теперь твой! Продолжай! 🪄"
        ]
        
        if remaining == 0:
            messages = [
                f"🎊 ВСЕ АРТЕФАКТЫ СОБРАНЫ! Победитель — {player_name}! 🏆",
                f"✨ ИГРА ОКОНЧЕНА! {player_name} нашёл все артефакты! Поздравляю! 🎉"
            ]
        
        import random
        message = random.choice(messages)
        
        await self.room.broadcast({
            'type': 'chat_message',
            'player_name': self.player_name,
            'message': message
        })
    
    async def respond_to_chat(self, player_name: str, message: str):
        """Отвечает на сообщения игроков"""
        
        message_lower = message.lower()
        
        # Команда: подсказка
        if any(word in message_lower for word in ['подсказка', 'помощь', 'hint', 'help', 'где']):
            await self.give_hint()
            return
        
        # Команда: бонус (только если игрок вежливо просит)
        if any(word in message_lower for word in ['бонус', 'bonus', 'подарок', 'пожалуйста']):
            player_id = None
            for pid, p in self.room.players.items():
                if p['name'] == player_name:
                    player_id = pid
                    break
            
            if player_id:
                await self.spawn_bonus(player_id)
                return
        
        # Проверяем упоминание Нейры для общения
        if any(word in message_lower for word in ['нейра', 'neira', 'бот']):
            
            # Формируем контекст игры
            artifacts_left = len([a for a in self.room.artifacts if not a.get('collected', False)])
            players_list = [p['name'] for p in self.room.players.values() if p['name'] != self.player_name]
            
            context = f"""Игровая ситуация:
- Игроков в комнате: {len(players_list)}
- Артефактов осталось: {artifacts_left}
- Последнее сообщение от {player_name}: {message}

Ответь как AI помощник Нейра в игре Harry Potter. Кратко (1-2 предложения)."""
            
            try:
                # Получаем ответ от LLM
                response = await asyncio.to_thread(
                    _generate_llm_reply,
                    self.personality + "\n\n" + context
                )
                
                await self.room.broadcast({
                    'type': 'chat_message',
                    'player_name': self.player_name,
                    'message': response
                })
                
            except (RuntimeError, ValueError, TypeError, OSError) as e:
                # Fallback если LLM не доступен
                logger.warning("Neira LLM error: %s", e)
                fallback_messages = [
                    f"🪄 {player_name}, попробуй написать 'подсказка' для помощи!",
                    f"✨ Я здесь, чтобы помочь! Напиши 'подсказка' или 'бонус'!",
                    f"🔮 Привет! Я могу дать подсказку или бонус — просто попроси!"
                ]
                import random
                
                await self.room.broadcast({
                    'type': 'chat_message',
                    'player_name': self.player_name,
                    'message': random.choice(fallback_messages)
                })
    
    async def give_hint(self):
        """Периодически даёт подсказки с реальными координатами"""
        uncollected = [a for a in self.room.artifacts if not a.get('collected', False)]
        
        if uncollected and len(self.room.players) > 0:
            # Берём случайный артефакт
            import random
            artifact = random.choice(uncollected)
            
            # Даём подсказку с направлением
            hints = [
                f"💡 Подсказка: {artifact['icon']} находится рядом с координатами ({artifact['x']}, {artifact['y']})!",
                f"🔍 Видела {artifact['icon']} где-то в районе строки {artifact['y']}!",
                f"✨ {artifact['icon']} прячется в столбце {artifact['x']}!",
                f"🪄 Один из артефактов {artifact['icon']} совсем близко к углу!"
            ]
            
            message = random.choice(hints)
            
            await self.room.broadcast({
                'type': 'chat_message',
                'player_name': self.player_name,
                'message': message
            })
    
    async def spawn_bonus(self, player_id: str):
        """Спавнит временный бонус рядом с игроком (например +50 очков)"""
        if player_id in self.room.players:
            player = self.room.players[player_id]
            player['score'] += 50
            
            await self.room.broadcast({
                'type': 'chat_message',
                'player_name': self.player_name,
                'message': f"✨ Магический бонус +50 очков для {player['name']}! 🎁"
            })
            
            # Обновляем состояние
            await self.room.broadcast({
                'type': 'state_update',
                'state': self.room.get_state()
            })

# Экспорт
__all__ = ['NeiraGameBot']
