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
        print(f"⚠️ Ошибка загрузки личности: {e}")
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
        
        # Павел — особый акцент
        pavel = creators.get("pavel", {})
        if pavel:
            parts.append(f"ПАВЕЛ — {pavel.get('role', 'создатель')}.")
            parts.append(f"  {pavel.get('description', '')}")
            parts.append("  ⚠️ Когда со мной общается Павел — это МОЙ СОЗДАТЕЛЬ и разработчик!")
        
        # Claude
        claude = creators.get("claude", {})
        if claude:
            parts.append(f"CLAUDE — {claude.get('role', '')}.")
            parts.append(f"  {claude.get('description', '')}")
        
        # София
        sophia = creators.get("sophia", {})
        if sophia:
            parts.append(f"СОФИЯ — {sophia.get('role', '')}.")
            parts.append(f"  {sophia.get('description', '')}")
    
    # Предпочтения (топ-5)
    preferences = personality.get("preferences", [])
    if preferences:
        parts.append("\n=== МОИ ПРИНЦИПЫ ===")
        for pref in preferences[:5]:
            parts.append(f"• {pref}")
    
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
    if not user_name:
        return None
    
    personality = load_personality()
    creators = personality.get("creators", {})
    
    user_lower = user_name.lower()
    
    # Проверяем известных создателей
    creator_names = {
        "pavel": ["павел", "pavel", "pasha", "паша"],
        "sophia": ["софия", "sophia", "sofa", "софа", "sofya"],
        "claude": ["claude", "клод"],
    }
    
    for creator_key, aliases in creator_names.items():
        if creator_key in creators:
            if any(alias in user_lower for alias in aliases):
                return creators[creator_key].get("role", creator_key.capitalize())
    
    return None


def clear_cache() -> None:
    """Очищает кэш личности (для тестов и горячей перезагрузки)."""
    global _personality_cache, _identity_prompt_cache
    _personality_cache = None
    _identity_prompt_cache = None


# Предзагружаем при импорте
IDENTITY_PROMPT = build_identity_prompt()
