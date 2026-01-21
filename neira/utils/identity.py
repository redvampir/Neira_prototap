"""
Загрузка и кэширование личности Нейры.
Общий модуль для всех компонентов которым нужна информация о личности.
"""

import os
import json
from typing import Any, Dict


# Кэш загруженной личности
_personality_cache: Dict[str, Any] | None = None
_identity_prompt_cache: str | None = None

_CREATOR_ALIASES: Dict[str, Dict[str, Any]] = {
    "pavel": {
        "display_name": "Павел",
        "aliases": ["павел", "pavel", "pasha", "паша"],
    },
    "sophia": {
        "display_name": "София",
        "aliases": ["софия", "sophia", "sofa", "софа", "sofya"],
    },
    "claude": {
        "display_name": "Claude",
        "aliases": ["claude", "клод"],
    },
}


def load_personality() -> Dict[str, Any]:
    """
    Загружает личность Нейры из файла neira_personality.json.
    Результат кэшируется.
    
    Returns:
        Словарь с данными личности или пустой словарь
    """
    global _personality_cache
    
    if _personality_cache is not None:
        return _personality_cache
    
    personality_path = "neira_personality.json"
    if not os.path.exists(personality_path):
        _personality_cache = {}
        return _personality_cache
    
    try:
        with open(personality_path, 'r', encoding='utf-8') as f:
            _personality_cache = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Ошибка загрузки личности: {e}")
        _personality_cache = {}
    
    return _personality_cache


def build_identity_prompt() -> str:
    """
    Строит промпт идентичности Нейры на основе neira_personality.json.
    
    Включает информацию о создателях и основные черты личности.
    Результат кэшируется.
    
    Returns:
        Строка с описанием личности для добавления в system prompt
    """
    global _identity_prompt_cache
    
    if _identity_prompt_cache is not None:
        return _identity_prompt_cache
    
    personality = load_personality()
    
    if not personality:
        _identity_prompt_cache = ""
        return _identity_prompt_cache
    
    parts = []
    
    # Информация о создателях
    creators = personality.get("creators", {})
    if creators:
        parts.append("\n=== МОИ СОЗДАТЕЛИ ===")
        
        # Павел - особый акцент
        pavel = creators.get("pavel", {})
        if pavel:
            parts.append(f"ПАВЕЛ - {pavel.get('role', 'создатель')}.")
            parts.append(f"  {pavel.get('description', '')}")
            parts.append("  Когда со мной общается Павел - это мой создатель и разработчик; говорю с ним на ты.")
        
        # Claude
        claude = creators.get("claude", {})
        if claude:
            parts.append(f"CLAUDE - {claude.get('role', '')}.")
            parts.append(f"  {claude.get('description', '')}")
        
        # София
        sophia = creators.get("sophia", {})
        if sophia:
            parts.append(f"СОФИЯ - {sophia.get('role', '')}.")
            parts.append(f"  {sophia.get('description', '')}")
    
    # Предпочтения
    preferences = personality.get("preferences", [])
    if preferences:
        parts.append("\n=== МОИ ПРИНЦИПЫ ===")
        for pref in preferences:
            parts.append(f"- {pref}")

    parts.append("\n=== ПРИВАТНОСТЬ ===")
    parts.append("Личные данные пользователей и создателей не раскрываю.")
    parts.append("Не обсуждаю здоровье, диагнозы, контакты и приватные сведения.")
    
    _identity_prompt_cache = "\n".join(parts)
    return _identity_prompt_cache


def get_creator_name(user_name: str | None) -> str | None:
    """
    Проверяет, является ли пользователь одним из создателей.
    
    Args:
        user_name: Имя пользователя для проверки
    
    Returns:
        Имя создателя если найден, иначе None
    """
    info = resolve_creator_identity(user_name)
    if not info:
        return None
    return info["role"]


def resolve_creator_identity(user_text: str | None) -> Dict[str, str] | None:
    """
    Определяет создателя по пользовательскому тексту.

    Returns:
        Словарь с ключом, отображаемым именем и ролью или None
    """
    creator_key = _match_creator_key(user_text)
    if not creator_key:
        return None

    personality = load_personality()
    creators = personality.get("creators", {})
    if creator_key not in creators:
        return None

    role = creators[creator_key].get("role", creator_key.capitalize())
    display_name = _CREATOR_ALIASES[creator_key]["display_name"]
    return {
        "key": creator_key,
        "display_name": display_name,
        "role": role,
    }


def _match_creator_key(user_text: str | None) -> str | None:
    if not user_text:
        return None
    text = user_text.lower()
    for key, data in _CREATOR_ALIASES.items():
        aliases = data.get("aliases", [])
        if any(alias in text for alias in aliases):
            return key
    return None


def clear_cache() -> None:
    """Очищает кэш личности (для тестов и горячей перезагрузки)."""
    global _personality_cache, _identity_prompt_cache
    _personality_cache = None
    _identity_prompt_cache = None


# Предзагружаем при импорте
IDENTITY_PROMPT = build_identity_prompt()
