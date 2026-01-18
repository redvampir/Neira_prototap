#!/usr/bin/env python3
"""
Система параллельного мышления Neira для Telegram
Позволяет вести отдельные диалоги с разными пользователями
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


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


class ParallelMindSystem:
    """
    Система параллельного мышления
    
    Управляет отдельными контекстами для каждого чата/пользователя
    """
    
    def __init__(self, contexts_file: str = "neira_chat_contexts.json"):
        self.contexts_file = contexts_file
        self.contexts: Dict[int, ChatContext] = {}
        self._load_contexts()
    
    def _load_contexts(self):
        """Загружает контексты из файла"""
        if os.path.exists(self.contexts_file):
            try:
                with open(self.contexts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for chat_id_str, context_data in data.items():
                        chat_id = int(chat_id_str)
                        self.contexts[chat_id] = ChatContext(**context_data)
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
            context.context_history.append({
                "role": role,
                "content": content,
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
            self._save_contexts()
            print(f"🗑️ Контекст чата {chat_id} очищен")
    
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
