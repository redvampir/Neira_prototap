#!/usr/bin/env python3
"""
Система параллельного мышления Neira для Telegram
Позволяет вести отдельные диалоги с разными пользователями
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class ChatContext:
    """Контекст отдельного чата"""
    chat_id: int
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    context_history: List[dict]  # История диалога
    created_at: str
    last_active: str
    message_count: int = 0
    abbreviation_expansions: Dict[str, str] = field(default_factory=dict)


class ParallelMindSystem:
    """
    Система параллельного мышления
    
    Управляет отдельными контекстами для каждого чата/пользователя
    """
    
    def __init__(self, contexts_file: str = "neira_chat_contexts.json"):
        self.contexts_file = contexts_file
        self.contexts: Dict[int, ChatContext] = {}
        self._max_message_chars = int(os.getenv("NEIRA_CONTEXT_MAX_MESSAGE_CHARS", "2000") or "2000")
        self._load_contexts()

    def _sanitize_message_content(self, content: str) -> str:
        """
        Сжимает сообщения в контексте, чтобы не раздувать историю до мегабайт.

        INVARIANT: функция не должна бросать исключения.
        """
        try:
            text = str(content or "")
            if not text:
                return ""

            # Убираем самые проблемные "портянки" (часто попадали в память при падении провайдера)
            if "Автономный режим" in text and len(text) > 800:
                first_line = text.splitlines()[0].strip()
                text = (first_line[:200].rstrip() + " (сокращено)") if first_line else "Автономный режим (сокращено)"

            limit = max(int(self._max_message_chars), 200)
            if len(text) > limit:
                text = text[: max(limit - 3, 0)].rstrip() + "..."
            return text
        except Exception:
            return ""
    
    def _load_contexts(self):
        """Загружает контексты из файла"""
        if os.path.exists(self.contexts_file):
            try:
                with open(self.contexts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    changed = False
                    for chat_id_str, context_data in data.items():
                        chat_id = int(chat_id_str)
                        ctx = ChatContext(**context_data)
                        for msg in ctx.context_history:
                            if not isinstance(msg, dict):
                                continue
                            if "content" not in msg:
                                continue
                            original = msg.get("content", "")
                            sanitized = self._sanitize_message_content(original)
                            if sanitized != original:
                                msg["content"] = sanitized
                                changed = True
                        self.contexts[chat_id] = ctx

                    if changed:
                        self._save_contexts()
            except Exception as e:
                print(f"⚠️ Ошибка загрузки контекстов: {e}")
    
    def _save_contexts(self):
        """Сохраняет контексты в файл"""
        try:
            data = {str(chat_id): asdict(context) 
                   for chat_id, context in self.contexts.items()}
            with open(self.contexts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения контекстов: {e}")
    
    def get_or_create_context(self, 
                              chat_id: int, 
                              user_id: int,
                              username: Optional[str] = None,
                              first_name: Optional[str] = None) -> ChatContext:
        """Получает существующий или создает новый контекст"""
        
        if chat_id not in self.contexts:
            # Создаем новый контекст
            self.contexts[chat_id] = ChatContext(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
                context_history=[],
                created_at=datetime.now().isoformat(),
                last_active=datetime.now().isoformat(),
                message_count=0
            )
            self._save_contexts()
            print(f"✨ Создан новый контекст для чата {chat_id} (пользователь: {first_name or username or user_id})")
        
        return self.contexts[chat_id]
    
    def add_message(self, chat_id: int, role: str, content: str):
        """Добавляет сообщение в контекст чата"""
        if chat_id in self.contexts:
            context = self.contexts[chat_id]
            safe_content = self._sanitize_message_content(content)
            context.context_history.append({
                "role": role,
                "content": safe_content,
                "timestamp": datetime.now().isoformat()
            })
            context.last_active = datetime.now().isoformat()
            context.message_count += 1
            
            # Ограничиваем историю последними 50 сообщениями
            if len(context.context_history) > 50:
                context.context_history = context.context_history[-50:]
            
            self._save_contexts()
    
    def get_context_history(self, chat_id: int, last_n: int = 10) -> List[dict]:
        """Получает историю последних N сообщений"""
        if chat_id in self.contexts:
            return self.contexts[chat_id].context_history[-last_n:]
        return []
    
    def clear_context(self, chat_id: int):
        """Очищает контекст чата"""
        if chat_id in self.contexts:
            self.contexts[chat_id].context_history = []
            self.contexts[chat_id].message_count = 0
            self.contexts[chat_id].abbreviation_expansions.clear()
            self._save_contexts()
            print(f"🗑️ Контекст чата {chat_id} очищен")

    def get_abbreviation_expansion(self, chat_id: int, abbreviation: str) -> Optional[str]:
        """
        Получить сохранённую расшифровку аббревиатуры для конкретного чата.

        Это лёгкая «дообучаемая» память: один раз уточнили → дальше подставляем автоматически.
        """
        if not abbreviation:
            return None
        ctx = self.contexts.get(chat_id)
        if not ctx:
            return None
        return ctx.abbreviation_expansions.get(abbreviation.upper())

    def set_abbreviation_expansion(self, chat_id: int, abbreviation: str, expansion: str) -> None:
        """
        Сохранить расшифровку аббревиатуры для конкретного чата.

        Args:
            chat_id: ID чата.
            abbreviation: Аббревиатура (например, "КП").
            expansion: Расшифровка (например, "Коммерческое предложение").
        """
        if not abbreviation or not expansion:
            return
        ctx = self.contexts.get(chat_id)
        if not ctx:
            return
        ctx.abbreviation_expansions[abbreviation.upper()] = expansion
        self._save_contexts()
    
    def get_stats(self) -> dict:
        """Возвращает статистику по всем чатам"""
        return {
            "total_chats": len(self.contexts),
            "total_messages": sum(ctx.message_count for ctx in self.contexts.values()),
            "active_chats": [
                {
                    "chat_id": ctx.chat_id,
                    "user": ctx.first_name or ctx.username or ctx.user_id,
                    "messages": ctx.message_count,
                    "last_active": ctx.last_active
                }
                for ctx in sorted(self.contexts.values(), 
                                 key=lambda x: x.last_active, 
                                 reverse=True)[:10]
            ]
        }


# Глобальная инстанция
parallel_mind = ParallelMindSystem()
