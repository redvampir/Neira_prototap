#!/usr/bin/env python3
"""
Улучшенная система авторизации для Telegram бота
Поддержка: user_id, username, ссылки, номер телефона
"""

import json
import os
import re
from typing import Set, Optional, Dict
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AuthorizedUser:
    """Авторизованный пользователь"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    phone: Optional[str] = None
    authorized_at: str = ""
    authorized_by: Optional[int] = None  # Кто добавил
    note: str = ""  # Заметка


class EnhancedAuthSystem:
    """
    Улучшенная система авторизации
    
    Поддерживает добавление пользователей по:
    - user_id (числовой ID)
    - @username
    - ссылке t.me/username
    - номеру телефона (только для поиска)
    """
    
    def __init__(self, auth_file: str = "neira_authorized_users.json"):
        self.auth_file = auth_file
        self.authorized_users: Dict[int, AuthorizedUser] = {}
        self._load_users()
    
    def _load_users(self):
        """Загружает список авторизованных пользователей"""
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id_str, user_data in data.items():
                        user_id = int(user_id_str)
                        self.authorized_users[user_id] = AuthorizedUser(**user_data)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки авторизованных пользователей: {e}")
    
    def _save_users(self):
        """Сохраняет список авторизованных пользователей"""
        try:
            data = {str(user_id): asdict(user) 
                   for user_id, user in self.authorized_users.items()}
            with open(self.auth_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения авторизованных пользователей: {e}")
    
    def parse_user_identifier(self, identifier: str) -> tuple[Optional[str], Optional[int]]:
        """
        Парсит идентификатор пользователя
        
        Returns:
            (username, user_id) - хотя бы одно значение будет не None
        """
        identifier = identifier.strip()
        
        # 1. Числовой user_id
        if identifier.isdigit():
            return None, int(identifier)
        
        # 2. @username
        if identifier.startswith('@'):
            return identifier[1:], None
        
        # 3. Ссылка t.me/username
        tme_match = re.match(r'(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,32})', identifier)
        if tme_match:
            return tme_match.group(1), None
        
        # 4. Просто username без @
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', identifier):
            return identifier, None
        
        # Не смогли распарсить
        return None, None
    
    def add_user(self, 
                 identifier: str,
                 authorized_by: int,
                 note: str = "") -> tuple[bool, str]:
        """
        Добавляет пользователя в список авторизованных
        
        Args:
            identifier: user_id, @username, ссылка или username
            authorized_by: user_id того кто добавляет
            note: заметка
        
        Returns:
            (success, message)
        """
        username, user_id = self.parse_user_identifier(identifier)
        
        if username is None and user_id is None:
            return False, "❌ Неверный формат идентификатора"
        
        # Если только username - нужно получить user_id из Telegram API
        # Пока добавляем с placeholder ID
        if user_id is None:
            # Используем отрицательный ID как placeholder для username
            # Будет обновлен при первом сообщении от пользователя
            user_id = -hash(username) % (10 ** 8)  # Временный ID
        
        # Проверяем не добавлен ли уже
        if user_id in self.authorized_users:
            return False, f"⚠️ Пользователь уже авторизован: {self.authorized_users[user_id].first_name or username or user_id}"
        
        # Добавляем
        self.authorized_users[user_id] = AuthorizedUser(
            user_id=user_id,
            username=username,
            authorized_at=datetime.now().isoformat(),
            authorized_by=authorized_by,
            note=note
        )
        
        self._save_users()
        
        display_name = f"@{username}" if username else str(user_id)
        return True, f"✅ Пользователь {display_name} добавлен в список авторизованных"
    
    def remove_user(self, user_id: int) -> tuple[bool, str]:
        """Удаляет пользователя из списка авторизованных"""
        if user_id in self.authorized_users:
            user = self.authorized_users[user_id]
            display_name = user.first_name or user.username or str(user_id)
            del self.authorized_users[user_id]
            self._save_users()
            return True, f"✅ Пользователь {display_name} удален из списка"
        else:
            return False, "❌ Пользователь не найден в списке авторизованных"
    
    def is_authorized(self, user_id: int, username: Optional[str] = None) -> bool:
        """Проверяет авторизован ли пользователь"""
        # Проверка по user_id
        if user_id in self.authorized_users:
            # Обновляем username если изменился
            if username and self.authorized_users[user_id].username != username:
                self.authorized_users[user_id].username = username
                self._save_users()
            return True
        
        # Проверка по username (для placeholder ID)
        if username:
            for user in self.authorized_users.values():
                if user.username and user.username.lower() == username.lower():
                    # Обновляем реальный user_id
                    if user.user_id < 0:  # Это был placeholder
                        del self.authorized_users[user.user_id]
                        user.user_id = user_id
                        self.authorized_users[user_id] = user
                        self._save_users()
                    return True
        
        return False
    
    def update_user_info(self, user_id: int, first_name: Optional[str] = None, phone: Optional[str] = None):
        """Обновляет информацию о пользователе"""
        if user_id in self.authorized_users:
            if first_name:
                self.authorized_users[user_id].first_name = first_name
            if phone:
                self.authorized_users[user_id].phone = phone
            self._save_users()
    
    def get_all_users(self) -> list:
        """Возвращает список всех авторизованных пользователей"""
        return [
            {
                "user_id": user.user_id if user.user_id > 0 else "pending",
                "username": f"@{user.username}" if user.username else "-",
                "name": user.first_name or "-",
                "authorized_at": user.authorized_at[:10] if user.authorized_at else "-",
                "note": user.note or "-"
            }
            for user in sorted(self.authorized_users.values(), 
                              key=lambda x: x.authorized_at, 
                              reverse=True)
        ]


# Глобальная инстанция
auth_system = EnhancedAuthSystem()
