"""Телеграм-бот для Neira v0.7: общение, обучение, самосознание, картинки и защита."""

import asyncio
import inspect
import ipaddress
import logging
import os
import re
import time
import hashlib
import secrets
import base64
import io
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ChatAction, ParseMode
from telegram.error import TimedOut, NetworkError, InvalidToken
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    MessageReactionHandler,
    CallbackQueryHandler,
    filters,
)

# Локальные импорты
from backend.neira_wrapper import NeiraWrapper
from cell_factory import CellFactory
from parallel_thinking import parallel_mind
from enhanced_auth import auth_system
from telegram_settings import TelegramSettings, load_telegram_settings, save_telegram_settings
from telegram_network import (
    TelegramNetworkConfig,
    compute_backoff_seconds,
    load_telegram_network_config,
    sanitize_url_for_log,
)
from memory_system import EMBED_MODEL
from autonomous_learning import AutonomousLearningSystem
from emoji_feedback import EmojiFeedbackSystem, EmojiMap
from organ_creation_engine import OrganCreationEngine, train_neira_from_letter

# 🧬 Исполняемые органы v1.0
try:
    from executable_organs import (
        get_organ_registry, ExecutableOrganRegistry,
        FeedbackType, OrganSandbox
    )
    EXECUTABLE_ORGANS_AVAILABLE = True
except ImportError as e:
    EXECUTABLE_ORGANS_AVAILABLE = False
    print(f"⚠️ ExecutableOrgans недоступны: {e}")

# 🧠 Этический фреймворк (принципы из LETTER_TO_NEIRA)
try:
    from ethical_framework import (
        EthicalFramework, analyze_ethically, 
        ResponseStrategy as EthicalStrategy, RiskLevel, Intent
    )
    from human_in_the_loop import (
        HumanInTheLoop, get_hil_manager, escalate_to_creator,
        EscalationType, EscalationStatus
    )
    ETHICAL_FRAMEWORK_AVAILABLE = True
except ImportError as e:
    ETHICAL_FRAMEWORK_AVAILABLE = False
    print(f"⚠️ EthicalFramework недоступен: {e}")

# 🔗 Phase 2: NeiraClient для связи с сервером
try:
    from neira_client import NeiraClient, get_client
    NEIRA_CLIENT_AVAILABLE = True
except ImportError:
    NEIRA_CLIENT_AVAILABLE = False
    print("⚠️ NeiraClient недоступен - feedback не будет синхронизироваться с сервером")

# 🧠 Neira Cortex v2.0 - Автономная когнитивная система
try:
    from neira_cortex import NeiraCortex, ProcessingResult, ResponseStrategy
    CORTEX_AVAILABLE = True
except ImportError:
    CORTEX_AVAILABLE = False
    print("⚠️ Neira Cortex недоступен - используем legacy режим")

# 🚦 Rate Limiting - защита от спама
try:
    from rate_limiter import check_rate_limit, record_request, RateLimitExceeded
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    print("⚠️ Rate Limiter недоступен")

# 🪞 Новые системы самосознания (v0.8)
try:
    from emotional_mirror import get_emotional_mirror, MoodState, EnergyLevel
    from error_journal import get_error_journal, ErrorCategory, ErrorSeverity
    from emotional_memory import get_emotional_memory, EmotionalTone, RelationshipStage
    from proactive_system import get_proactive_system, InitiativeType
    from creative_engine import get_creative_engine, CreativeForm
    CONSCIOUSNESS_SYSTEMS_AVAILABLE = True
except ImportError as e:
    CONSCIOUSNESS_SYSTEMS_AVAILABLE = False
    print(f"⚠️ Системы самосознания недоступны: {e}")


# === Инициализация ===
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _get_base_dir() -> Path:
    """Получить базовую директорию проекта (работает и через exec, и при прямом запуске)."""
    if '__file__' in globals():
        return Path(__file__).resolve().parent
    # fallback: текущая рабочая директория
    return Path.cwd()


def _configure_logging() -> Path:
    log_path = os.getenv("NEIRA_TG_LOG_FILE", "artifacts/telegram_bot.log")
    log_file = Path(log_path)
    if not log_file.is_absolute():
        log_file = _get_base_dir() / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    logging.getLogger(__name__).info("📝 Лог Telegram-бота: %s", log_file)
    return log_file


load_dotenv()
_LOG_PATH = _configure_logging()

# Снижаем шум в логах от HTTP-клиента (иначе getUpdates забивает всё).
_httpx_level_name = os.getenv("NEIRA_HTTPX_LOG_LEVEL", "WARNING").upper()
_httpx_level = getattr(logging, _httpx_level_name, logging.WARNING)
logging.getLogger("httpx").setLevel(_httpx_level)
logging.getLogger("httpcore").setLevel(_httpx_level)

try:
    _TYPING_THROTTLE_SECONDS = float(os.getenv("NEIRA_TG_TYPING_THROTTLE_SECONDS", "3.0"))
except ValueError:
    _TYPING_THROTTLE_SECONDS = 3.0

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "Не задан TELEGRAM_BOT_TOKEN. Укажите его в переменных окружения "
        "или в файле .env (см. .env.example)."
    )


class _SensitiveDataFilter(logging.Filter):
    """Фильтр логов: скрывает токены/ключи, чтобы не засветить их в tg.log."""

    _telegram_url_re = re.compile(
        r"(https://api\.telegram\.org/bot)[^/\s]+",
        flags=re.IGNORECASE,
    )
    _telegram_token_re = re.compile(r"\bbot\d+:[A-Za-z0-9_-]+\b")

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if isinstance(s, str) and s]

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - имя задано logging API
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = self._telegram_url_re.sub(r"\1<redacted>", message)
        redacted = self._telegram_token_re.sub("bot<redacted>", redacted)
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, "<redacted>")

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def _install_log_redaction_filter() -> None:
    secrets: List[str] = [BOT_TOKEN] if BOT_TOKEN else []
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "NEIRA_ADMIN_PASSWORD", "NEIRA_TG_PROXY_URL"):
        value = os.getenv(key)
        if value:
            secrets.append(value)

    filt = _SensitiveDataFilter(secrets)
    root = logging.getLogger()
    root.addFilter(filt)
    for handler in root.handlers:
        handler.addFilter(filt)


_install_log_redaction_filter()

# === ЗАЩИТА: Администратор ===
# Хеш пароля администратора (из переменной окружения или по умолчанию)
# ВАЖНО: Измените NEIRA_ADMIN_PASSWORD в .env!
_ADMIN_PASSWORD = os.getenv("NEIRA_ADMIN_PASSWORD", "change_me_please")
_ALLOW_DEFAULT_ADMIN_PASSWORD = os.getenv("NEIRA_ALLOW_DEFAULT_ADMIN_PASSWORD", "false").lower() == "true"

if _ADMIN_PASSWORD == "change_me_please" and not _ALLOW_DEFAULT_ADMIN_PASSWORD:
    raise RuntimeError(
        "NEIRA_ADMIN_PASSWORD не задан или оставлен по умолчанию (change_me_please). "
        "Задайте сильный пароль в `.env` или (только для локальной разработки) установите "
        "NEIRA_ALLOW_DEFAULT_ADMIN_PASSWORD=true."
    )

if len(_ADMIN_PASSWORD) < 10 and not _ALLOW_DEFAULT_ADMIN_PASSWORD:
    raise RuntimeError(
        "NEIRA_ADMIN_PASSWORD слишком короткий (минимум 10 символов). "
        "Используйте уникальный пароль или (только для локальной разработки) установите "
        "NEIRA_ALLOW_DEFAULT_ADMIN_PASSWORD=true."
    )

if _ALLOW_DEFAULT_ADMIN_PASSWORD:
    logging.warning("NEIRA_ALLOW_DEFAULT_ADMIN_PASSWORD=true: режим небезопасен, используйте только локально.")
_ADMIN_HASH = hashlib.sha256(_ADMIN_PASSWORD.encode()).hexdigest()
_ADMIN_ID: Optional[int] = None  # Будет установлен при первой авторизации

# Авторизация пользователей хранится в enhanced_auth.py (файл neira_authorized_users.json).

TG_SETTINGS_FILE = Path(os.getenv("NEIRA_TG_SETTINGS_FILE", "neira_tg_settings.json"))

try:
    _tg_settings = load_telegram_settings(TG_SETTINGS_FILE)
except Exception as exc:
    logging.warning("Не удалось загрузить настройки Telegram (%s): %s", TG_SETTINGS_FILE, exc)
    _tg_settings = TelegramSettings()

# Режим доступа: "open" (все), "whitelist" (только авторизованные), "admin_only"
ACCESS_MODE = _tg_settings.access_mode

# ID каналов/групп где бот отвечает без авторизации
ALLOWED_CHANNELS: Set[int] = _tg_settings.allowed_channels

# Отвечать только на упоминания бота в группах/каналах?
MENTION_ONLY = _tg_settings.mention_only

def _persist_tg_settings() -> None:
    try:
        _tg_settings.access_mode = ACCESS_MODE
        _tg_settings.mention_only = MENTION_ONLY
        save_telegram_settings(TG_SETTINGS_FILE, _tg_settings)
    except Exception as exc:
        logging.warning("Не удалось сохранить настройки Telegram (%s): %s", TG_SETTINGS_FILE, exc)

neira_wrapper = NeiraWrapper(verbose=False)
processing_lock = asyncio.Lock()

# === Система автономного обучения ===
autonomous_learning_system: Optional[AutonomousLearningSystem] = None

# === 📝 Обучение через эмодзи-реакции ===
emoji_feedback = EmojiFeedbackSystem()
last_messages = {}  # {user_id: {"query": "", "response": "", "context": {}}}

# === 🧠 Neira Cortex v2.0 ===
neira_cortex: Optional['NeiraCortex'] = None
CORTEX_MODE = os.getenv("NEIRA_CORTEX_MODE", "auto")  # auto, always, never

# === 🧠 Phase 1: Модули автономности ===
neira_brain: Optional[Any] = None
response_engine: Optional[Any] = None
organ_system: Optional[Any] = None

# === 🎵 Стабилизатор ритма ===
from rhythm_stabilizer import RhythmStabilizer, EmotionalState
rhythm_stabilizer = RhythmStabilizer()

# === 👤 Профили пользователей ===
import json
from pathlib import Path

USER_PROFILES_FILE = Path("neira_user_profiles.json")

def load_user_profiles():
    """Загружает профили пользователей"""
    if USER_PROFILES_FILE.exists():
        try:
            with open(USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки профилей: {e}")
    return {"user_profiles": {}}

def save_user_profiles(profiles):
    """Сохраняет профили пользователей"""
    try:
        with open(USER_PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения профилей: {e}")

def get_user_name(user_id: int) -> Optional[str]:
    """Получает имя пользователя из профиля"""
    profiles = load_user_profiles()
    user_key = str(user_id)
    return profiles["user_profiles"].get(user_key, {}).get("name")

def set_user_name(user_id: int, name: str):
    """Сохраняет имя пользователя в профиль"""
    profiles = load_user_profiles()
    user_key = str(user_id)
    if user_key not in profiles["user_profiles"]:
        profiles["user_profiles"][user_key] = {}
    profiles["user_profiles"][user_key]["name"] = name
    profiles["user_profiles"][user_key]["updated_at"] = datetime.now().isoformat()
    save_user_profiles(profiles)
    logging.info(f"💾 Сохранено имя пользователя {user_id}: {name}")


# === Phase 1: Автономный ответ ===
def try_autonomous_response(message: str, user_id: int) -> Optional[str]:
    """
    Попытка ответить автономно без LLM
    
    Returns:
        Ответ или None если нужен LLM
    """
    global response_engine, neira_brain
    
    if response_engine is None:
        return None
    
    try:
        # Получаем контекст пользователя
        user_context = {}
        
        # Имя из профилей бота
        saved_name = get_user_name(user_id)
        if saved_name:
            user_context['user_name'] = saved_name
        
        # Дополнительные данные из NeiraBrain
        if neira_brain:
            prefs = neira_brain.get_user_prefs(str(user_id))
            if prefs:
                user_context.update(prefs.get('variables', {}))
        
        # Пробуем ответить автономно
        response, source = response_engine.try_respond_autonomous(message, user_context)
        
        if response:
            # Записываем метрику
            if neira_brain:
                neira_brain.record_metric('autonomous_response', 'telegram', {
                    'source': source,
                    'user_id': user_id,
                    'message_preview': message[:50]
                })
            logging.info(f"⚡ Автономный ответ для user {user_id} (источник: {source})")
            return response
        
        return None
        
    except Exception as e:
        logging.warning(f"Ошибка автономного ответа: {e}")
        return None


def store_llm_response_for_learning(query: str, response: str, success: bool = True):
    """Сохранить ответ LLM для будущего использования"""
    global response_engine
    
    if response_engine is None:
        return
    
    try:
        response_engine.store_llm_response(query, response, success)
    except Exception as e:
        logging.warning(f"Не удалось сохранить ответ для обучения: {e}")


async def send_feedback_to_server(
    query: str, 
    response: str, 
    feedback: str, 
    score: float, 
    user_id: int
) -> bool:
    """
    Отправить feedback на сервер Neira (Phase 2).
    
    Args:
        query: Исходный запрос пользователя
        response: Ответ Neira
        feedback: 'positive', 'negative' или 'neutral'
        score: Оценка от 0 до 1
        user_id: ID пользователя Telegram
    
    Returns:
        True если успешно отправлено
    """
    if not NEIRA_CLIENT_AVAILABLE:
        return False
    
    try:
        client = get_client()
        result = await client.send_feedback_async(
            query=query,
            response=response,
            feedback=feedback,
            score=score,
            user_id=str(user_id),
            source="telegram"
        )
        
        if result and result.get("success"):
            actions = result.get("data", {}).get("actions_taken", [])
            if actions:
                logging.info(f"📤 Feedback отправлен на сервер: {actions}")
            return True
        return False
        
    except Exception as e:
        logging.warning(f"Не удалось отправить feedback на сервер: {e}")
        return False


# === Декоратор авторизации ===
def require_auth(func):
    """Декоратор для проверки авторизации пользователя."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        username = update.effective_user.username
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        
        # В разрешённых каналах/группах — без авторизации
        if chat_id in ALLOWED_CHANNELS:
            return await func(update, context, *args, **kwargs)
        
        # Каналы и супергруппы — проверяем что чат в списке разрешённых
        if chat_type in ("channel", "supergroup", "group"):
            # Если чат не в списке — игнорируем (не спамим про авторизацию)
            if chat_id not in ALLOWED_CHANNELS and ACCESS_MODE != "open":
                return
        
        if ACCESS_MODE == "open":
            return await func(update, context, *args, **kwargs)
        
        if ACCESS_MODE == "admin_only" and not is_admin(user_id):
            if chat_type == "private":
                await update.message.reply_text("⛔ Доступ только для администратора.")
            return
        
        if is_admin(user_id) or auth_system.is_authorized(user_id, username):
            return await func(update, context, *args, **kwargs)
        
        if chat_type == "private":
            await update.message.reply_text(
                "🔐 *Требуется авторизация*\n\n"
                f"Твой user_id: `{user_id}`\n\n"
                "📋 *Варианты доступа:*\n\n"
                "👑 *Если ты администратор:*\n"
                "`/auth 0 <пароль>`\n\n"
                "👤 *Если обычный пользователь:*\n"
                "Попроси администратора добавить тебя командой:\n"
                "`/admin add <твой_user_id>`\n"
                "или\n"
                "`/admin add @<твой_username>`\n\n"
                "💡 *После добавления ты сможешь:*\n"
                "• Общаться с Нейрой\n"
                "• Устанавливать своё имя: `/myname Твоё Имя`\n"
                "• Использовать все команды бота",
                parse_mode=ParseMode.MARKDOWN,
            )
    return wrapper


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id == _ADMIN_ID


# === Утилиты ===
def split_message(text: str, limit: int = 4000) -> List[str]:
    """Делит длинный ответ на части, чтобы не упереться в лимит Telegram."""
    if len(text) <= limit:
        return [text]

    parts: List[str] = []
    current: List[str] = []
    current_len = 0

    for paragraph in text.split("\n"):
        # Если параграф сам длиннее лимита — режем его пословно
        if len(paragraph) > limit:
            words = paragraph.split()
            for word in words:
                if current_len + len(word) + 1 > limit:
                    parts.append(" ".join(current))
                    current = [word]
                    current_len = len(word)
                else:
                    current.append(word)
                    current_len += len(word) + 1
            continue

        if current_len + len(paragraph) + 1 > limit:
            parts.append("\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += len(paragraph) + 1

    if current:
        parts.append("\n".join(current))

    # Фильтруем пустые части
    return [p.strip() for p in parts if p.strip()]


def format_stage(stage: str | None) -> str:
    """Человекочитаемое название этапа."""
    mapping = {
        "analysis": "Анализ",
        "planning": "Планирование",
        "execution": "Исполнение",
        "verification": "Проверка",
    }
    return mapping.get(stage or "", "Подготовка")


def is_cortex_placeholder_response(text: str) -> bool:
    """
    Cortex (в автономном режиме) часто возвращает «заглушки», если не хватает
    pathway/фрагментов/шаблонов. В Telegram это выглядит как «бот сломан».

    В режиме `NEIRA_CORTEX_MODE=auto` такие ответы лучше отдавать в legacy Neira.
    """
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    
    # Слишком короткий ответ (< 30 символов) на содержательный вопрос — скорее всего заглушка
    if len(normalized) < 30:
        return True

    placeholder_markers = (
        # Явные заглушки
        "не нашла подходящий фрагмент ответа",
        "дай мне секунду подумать",
        "интересный вопрос! дай подумать",
        "дай подумать над этим",
        "понял задачу, работаю над этим",
        "сейчас напишу код для тебя",
        "расскажи подробнее",
        "не совсем поняла",
        # Шаблонные пустые ответы
        "о, это интересно!",
        "всегда рада поболтать",
        "обращайся, если что",
        "рада помочь!",
        "хм, интересно...",
    )

    return any(marker in normalized for marker in placeholder_markers)


# Импорт общей функции для удаления дубликатов
from text_utils import remove_duplicate_paragraphs as _remove_duplicate_paragraphs


def _truncate_response(text: str, limit: int) -> tuple[str, bool]:
    if not text or limit <= 0 or len(text) <= limit:
        return text, False
    if limit <= 3:
        return text[:limit], True
    return text[: limit - 3].rstrip() + "...", True


async def safe_reply_text(
    message: Message,
    text: str,
    *,
    parse_mode: str | ParseMode | None = None,
) -> Message | None:
    """Безопасная отправка reply_text: не роняет обработчик на сетевых ошибках."""
    try:
        return await message.reply_text(text, parse_mode=parse_mode)
    except (TimedOut, NetworkError) as exc:
        logging.warning("Telegram reply_text не удалось отправить: %s", exc)
        return None


async def send_chunks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chunks: Iterable[str],
) -> None:
    """Отправляет список сообщений, соблюдая лимиты Telegram."""
    chat_id = update.effective_chat.id
    for part in chunks:
        try:
            await context.bot.send_message(chat_id=chat_id, text=part)
        except (TimedOut, NetworkError) as exc:
            logging.warning("Telegram send_message не удалось отправить: %s", exc)


async def show_typing(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Отправляет действие 'печатает' для UX."""
    throttle_seconds = max(_TYPING_THROTTLE_SECONDS, 0.0)
    if throttle_seconds > 0:
        now = time.monotonic()
        try:
            last_ts = float(context.chat_data.get("_neira_last_typing_ts", 0.0) or 0.0) if context.chat_data else 0.0
        except (TypeError, ValueError):
            last_ts = 0.0
        if now - last_ts < throttle_seconds:
            return
        if context.chat_data is not None:
            context.chat_data["_neira_last_typing_ts"] = now

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )
    except (TimedOut, NetworkError):
        # Сеть/Telegram бывают нестабильны — это не должно ломать обработку.
        return


# === Работа с изображениями ===
OLLAMA_API = "http://localhost:11434/api"
VISION_MODEL = "llava:7b"  # Модель для анализа изображений (можно заменить на другую)
SD_API = "http://127.0.0.1:7860/sdapi/v1"  # Stable Diffusion API


async def analyze_image_with_ollama(image_base64: str, prompt: str = "Опиши это изображение подробно на русском языке") -> str:
    """Анализ изображения через Ollama vision модель."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            }
            async with session.post(f"{OLLAMA_API}/generate", json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("response", "Не удалось проанализировать изображение.")
                else:
                    return f"Ошибка API Ollama: {resp.status}"
    except aiohttp.ClientError as e:
        return f"Ошибка подключения к Ollama: {e}"
    except Exception as e:
        return f"Ошибка анализа изображения: {e}"


async def check_vision_model() -> bool:
    """Проверка доступности vision модели."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_API}/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return any(VISION_MODEL in m or "llava" in m.lower() or "vision" in m.lower() for m in models)
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError):
        pass  # Модель недоступна
    return False


async def generate_image_sd(prompt: str) -> Optional[bytes]:
    """Генерация изображения через Stable Diffusion API."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                "negative_prompt": "ugly, blurry, bad anatomy, bad hands, missing fingers, low quality",
                "steps": 20,
                "width": 512,
                "height": 512,
                "sampler_name": "Euler a",
                "cfg_scale": 7,
            }
            async with session.post(f"{SD_API}/txt2img", json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    images = result.get("images", [])
                    if images:
                        return base64.b64decode(images[0])
    except aiohttp.ClientError as e:
        logging.warning(f"SD API недоступен: {e}")
    except Exception as e:
        logging.error(f"Ошибка генерации SD: {e}")
    return None


async def check_sd_available() -> bool:
    """Проверка доступности Stable Diffusion API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SD_API}/sd-models", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и инструкция по запуску."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "друг"
    
    # Проверяем сохранённое имя
    saved_name = get_user_name(user_id)
    greeting_name = saved_name if saved_name else user_name
    
    is_authorized = (
        ACCESS_MODE == "open"
        or is_admin(user_id)
        or auth_system.is_authorized(user_id, update.effective_user.username)
    )
    
    if is_authorized:
        text = (
            f"Привет, {greeting_name}! 👋 Я Neira v1.0 в Telegram.\n\n"
            "🚀 *Быстрый старт:*\n"
            "1️⃣ Просто напиши мне сообщение — я отвечу и запомню\n"
            "2️⃣ Отправь фото — опишу что вижу\n"
            "3️⃣ Запусти автономное обучение: /learn\\_auto start\n\n"
            "✨ *Что я умею:*\n"
            "🧠 Диалог с памятью и контекстом\n"
            "🎓 Автономное обучение из надёжных источников\n"
            "🖼️ Анализ и генерация изображений\n"
            "🧬 Самосознание и рост органов\n"
            "💾 Расширенное управление памятью\n"
            "🔒 Защита от галлюцинаций\n\n"
            "📚 *Основные команды:*\n"
            "/help — полный список команд\n"
            "/learn\\_auto start — запустить обучение\n"
            "/memory stats — статистика памяти\n"
            "/self — самосознание\n"
            "/stats — статус систем\n\n"
            "💡 *Совет:* Начни с `/learn_auto start` — я буду учиться сама, "
            "когда не занята диалогами!"
        )
        if is_admin(user_id):
            text += "\n\n👑 Ты администратор. Доступны /admin команды."
    else:
        text = (
            f"Привет, {user_name}! Я Neira — AI-ассистент с самообучением.\n\n"
            "🔐 *Для доступа нужна авторизация:*\n"
            "/auth <логин> <пароль>\n\n"
            "Попроси администратора дать тебе доступ.\n\n"
            "📖 *О проекте:*\n"
            "Neira — это AI с памятью, самосознанием и автономным обучением. "
            "Я могу обучаться из проверенных источников (Wikipedia, Python.org, arXiv) "
            "с многоуровневой защитой от галлюцинаций."
        )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подробная справка."""
    user_id = update.effective_user.id
    is_user_admin = is_admin(user_id)
    
    # Базовая справка для всех
    text = (
        "📚 *Команды Neira v0.8.3*\n\n"
        "*🌟 Основные:*\n"
        "/start — приветствие и быстрый старт\n"
        "/help — эта справка\n"
        "/myname <имя> — установить своё имя\n\n"
        "*💬 Диалог:*\n"
        "/context — история разговора\n"
        "/clear\\_context — очистить контекст\n"
        "/rhythm — режим настроения\n\n"
        "*📊 Статистика:*\n"
        "/stats — состояние системы\n"
        "/memory — просмотр памяти\n\n"
        "*🎨 Изображения:*\n"
        "📷 Отправь фото — анализ\n"
        "/imagine <описание> — генерация\n"
        "/vision — статус распознавания\n\n"
        "*� Обучение:*\n"
        "Реагируй эмодзи на мои ответы:\n"
        "💯 ⭐ — отлично | 👍 ❤️ — хорошо\n"
        "👎 😕 — плохо | ❌ 🚫 — очень плохо\n\n"
        "*�💡 Подсказки:*\n"
        "• Просто пиши сообщения для диалога\n"
        "• Используй #хештеги для обучения\n"
        "• Отправляй изображения для анализа\n"
    )
    
    # Расширенная справка для администратора
    if is_user_admin:
        text += (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*👑 АДМИН-КОМАНДЫ*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "*🔐 Авторизация и пользователи:*\n"
            "/auth 0 <пароль> — авторизоваться как админ\n"
            "/admin users — список авторизованных\n"
            "/admin add <user_id> — добавить по ID\n"
            "/admin add @username — добавить по username\n"
            "/admin add https://t.me/username — по ссылке\n"
            "/admin remove <identifier> — удалить пользователя\n"
            "/admin mode open — открыть доступ всем\n"
            "/admin mode whitelist — только авторизованные\n"
            "/admin mode admin_only — только админ\n\n"
            "/admin stats — статистика системы\n\n"
            "*🧠 Cortex v2.0:*\n"
            "/cortex — общая статистика\n"
            "/cortex stats — детальная статистика\n"
            "/cortex pathways — Neural Pathways\n"
            "/cortex test <текст> — протестировать\n\n"
            "*📝 Обучение (расширенное):*\n"
            "/feedback — статистика emoji-реакций\n"
            "Реагируй эмодзи для обучения Neira!\n\n"
            "*💾 Память (расширенное):*\n"
            "/memory search <текст> — поиск\n"
            "/memory semantic <текст> — семантика\n"
            "/memory delete last/text/old\n"
            "/memory dedupe — дубликаты\n"
            "/memory backup/restore\n"
            "/memory pin/pinned — закрепить\n"
            "/memory filter confidence/source\n"
            "/memory export txt\n"
            "/experience — журнал опыта\n"
            "/clear — ⚠️ ПОЛНАЯ очистка\n\n"
            "*🎓 Обучение:*\n"
            "/learn <тема|URL> — тема или ссылка\n"
            "/learn\\_auto start/stop — автономное\n"
            "/learn\\_auto stats — статистика\n"
            "/learn\\_auto quarantine — карантин\n"
            "/learn\\_auto approve/reject <id>\n\n"
            "*🧬 Самосознание:*\n"
            "/self — самоанализ\n"
            "/organs — статус органов\n"
            "/grow — создание органов\n"
            "/organ_mode — управление режимом создания органов\n"
            "/code list/read — управление кодом\n\n"
            "*💡 Хештеги:*\n"
            "#создай\\_орган <описание>\n"
            "#научись <тема>\n"
        )
    # Динамический список сгенерированных органов и их команд
    try:
        registry = await _load_cell_registry()
        active = [m for m in registry if m.get('active')]
        if active:
            text += "\n*🔌 Сгенерированные органы и команды (активные):*\n"
            for m in active:
                name = m.get('cell_name')
                cmds = m.get('command_triggers') or []
                cmds_text = ', '.join(cmds) if cmds else '—'
                text += f"• {name}: {cmds_text}\n"
            text += (
                "\nИспользуй `/which_command <organ_name>` чтобы увидеть команды для конкретного органа.\n"
                "Команды обычно выглядят как `/run_<name>`, `#<name>` и специальная команда для улучшения `/улучшение_<name>`.")
            text += "\nНовые органы регистрируются автоматически и станут доступны без перезапуска бота.\n"
        else:
            text += "\n*🔌 Сгенерированных органов пока нет.*\n"
    except Exception:
        logging.exception('Не удалось загрузить реестр органов для /help')
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отчёт о состоянии моделей и памяти."""
    await show_typing(update, context)
    stats = neira_wrapper.get_stats()

    lines = [
        "Статус Neira:",
        f"- Обработка: {'да' if stats.get('is_processing') else 'нет'}",
    ]

    models = stats.get("models", {})
    local = models.get("local", {})
    cloud = models.get("cloud", {})

    lines.append(
        "- Локальные модели: "
        f"code={'OK' if local.get('code') else 'нет'}, "
        f"reason={'OK' if local.get('reason') else 'нет'}, "
        f"personality={'OK' if local.get('personality') else 'нет'}"
    )
    lines.append(
        "- Облачные: "
        f"code={'OK' if cloud.get('code') else 'нет'}, "
        f"universal={'OK' if cloud.get('universal') else 'нет'}, "
        f"vision={'OK' if cloud.get('vision') else 'нет'}"
    )

    memory = stats.get("memory", {})
    lines.append(
        f"- Память: всего {memory.get('total', 0)}, контекст сессии "
        f"{memory.get('session_context', 0)}"
    )

    if "model_manager" in stats:
        manager = stats["model_manager"]
        lines.append(
            f"- ModelManager: активна {manager.get('current_model')}, "
            f"переключений {manager.get('switches', 0)}"
        )

    if "experience" in stats:
        exp = stats["experience"]
        lines.append(
            f"- Опыт: всего {exp.get('total', 0)}, средняя оценка "
            f"{exp.get('avg_score', 0)}"
        )
    
    # 🧠 Cortex v2.0 статистика
    if neira_cortex:
        cortex_stats = neira_cortex.get_stats()
        lines.append(f"\n🧠 *Neira Cortex v2.0:*")
        lines.append(f"- Обработано запросов: {cortex_stats['total_requests']}")
        
        # Топ-3 стратегии
        top_strategies = sorted(
            cortex_stats['strategies'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        lines.append("- Топ стратегий:")
        for strategy, count in top_strategies:
            percentage = (count / cortex_stats['total_requests'] * 100) if cortex_stats['total_requests'] > 0 else 0
            lines.append(f"  • {strategy}: {count} ({percentage:.0f}%)")
        
        # Покрытие pathways
        coverage = cortex_stats['pathways']['coverage']
        lines.append(f"- Покрытие: HOT {coverage.get('hot', '0%')}, WARM {coverage.get('warm', '0%')}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def ratelimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статус rate limiting для пользователя."""
    user_id = update.effective_user.id
    
    if not RATE_LIMITER_AVAILABLE:
        await update.message.reply_text("⚠️ Rate Limiter не доступен")
        return
    
    from rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()
    stats = limiter.get_stats(str(user_id))
    
    text = (
        "🚦 *Статус Rate Limiting*\n\n"
        f"📊 За последнюю минуту: {stats['requests_last_minute']}/{stats['limits']['per_minute']}\n"
        f"📈 За последний час: {stats['requests_last_hour']}/{stats['limits']['per_hour']}\n"
    )
    
    if stats['blocked']:
        text += f"\n⛔ Заблокирован на {stats['blocked_for']} сек."
    else:
        text += "\n✅ Лимит не превышен"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@require_auth
async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Расширенное управление памятью Neira
    
    Команды:
    /memory - показать последние 10 записей
    /memory stats - детальная статистика
    /memory search <текст> - найти записи
    /memory delete last <N> - удалить последние N записей
    /memory delete text <текст> - удалить записи содержащие текст
    /memory delete old <дней> - удалить записи старше N дней
    /memory dedupe - удалить дубликаты
    /memory backup - создать бэкап
    """
    if not context.args:
        # Показать последние записи
        await show_typing(update, context)
        data = neira_wrapper.get_memory(limit=10)
        recent = data.get("recent", [])
        if not recent:
            await update.message.reply_text("📭 Память пуста.")
            return

        lines = ["💾 *Последние 10 записей:*\n"]
        for i, item in enumerate(recent, 1):
            category = item.get('category', 'general')
            text = item.get('text', '')[:80]
            lines.append(f"{i}. `[{category}]` {text}...")
        
        lines.append(f"\n_Всего записей: {data.get('total', len(recent))}_")
        lines.append("_Используй /memory stats для статистики_")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return
    
    action = context.args[0].lower()
    
    # Инициализируем менеджер памяти
    from memory_system import MemoryManager
    
    if not neira_wrapper.neira.memory.memory_system:
        await update.message.reply_text("❌ Система памяти не инициализирована")
        return
    
    memory_manager = MemoryManager(neira_wrapper.neira.memory.memory_system)
    
    if action == "stats":
        # Детальная статистика
        stats = memory_manager.get_stats()
        lines = [
            "📊 *Статистика памяти:*\n",
            f"📦 Всего записей: {stats['total']}",
            f"📚 Долгосрочная: {stats['by_type'].get('long_term', 0)}",
            f"⚡ Краткосрочная: {stats['by_type'].get('short_term', 0)}",
            f"📖 Эпизодическая: {stats['by_type'].get('episodic', 0)}",
            f"🧠 Семантическая: {stats['by_type'].get('semantic', 0)}",
        ]
        
        if stats.get('oldest'):
            oldest = datetime.fromisoformat(stats['oldest']).strftime("%d.%m.%Y")
            newest = datetime.fromisoformat(stats['newest']).strftime("%d.%m.%Y %H:%M")
            lines.append(f"\n📅 Период: {oldest} — {newest}")
        
        lines.append(f"🎯 Средняя уверенность: {stats['average_confidence']:.1%}")
        
        # Топ категорий
        if stats['by_category']:
            lines.append("\n🏷️ *Категории:*")
            sorted_cats = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)
            for cat, count in sorted_cats[:5]:
                lines.append(f"  • {cat}: {count}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "search" and len(context.args) > 1:
        # Поиск записей
        query = " ".join(context.args[1:])
        results = memory_manager.search_by_text(query)
        
        if not results:
            await update.message.reply_text(f"🔍 Ничего не найдено по запросу: '{query}'")
            return
        
        lines = [f"🔍 *Найдено записей: {len(results)}*\n"]
        for i, entry in enumerate(results[:15], 1):  # Показываем первые 15
            text = entry.text[:80] + "..." if len(entry.text) > 80 else entry.text
            lines.append(f"{i}. `[{entry.category}]` {text}")
        
        if len(results) > 15:
            lines.append(f"\n_...и ещё {len(results) - 15} записей_")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "delete":
        # Требует подтверждения
        if len(context.args) < 2:
            await update.message.reply_text(
                "❓ *Команды удаления:*\n"
                "/memory delete last <N> — удалить последние N записей\n"
                "/memory delete text <текст> — удалить записи со словом\n"
                "/memory delete old <дней> — удалить записи старше N дней\n"
                "/memory delete category <категория> — удалить категорию",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        subaction = context.args[1].lower()
        
        if subaction == "last" and len(context.args) > 2:
            try:
                n = int(context.args[2])
                if n < 1 or n > 100:
                    await update.message.reply_text("❌ N должно быть от 1 до 100")
                    return
                
                count = memory_manager.delete_last_n(n)
                await update.message.reply_text(
                    f"🗑️ Удалено последних записей: {count}\n"
                    f"_Используй /memory stats для проверки_",
                    parse_mode=ParseMode.MARKDOWN
                )
            except ValueError:
                await update.message.reply_text("❌ N должно быть числом")
        
        elif subaction == "text" and len(context.args) > 2:
            query = " ".join(context.args[2:])
            count = memory_manager.delete_by_text(query)
            await update.message.reply_text(
                f"🗑️ Удалено записей с '{query}': {count}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif subaction == "old" and len(context.args) > 2:
            try:
                days = int(context.args[2])
                if days < 1:
                    await update.message.reply_text("❌ Количество дней должно быть положительным")
                    return
                
                count = memory_manager.delete_old_entries(days)
                await update.message.reply_text(
                    f"🗑️ Удалено записей старше {days} дн.: {count}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except ValueError:
                await update.message.reply_text("❌ Количество дней должно быть числом")
        
        elif subaction == "category" and len(context.args) > 2:
            category = context.args[2]
            count = memory_manager.delete_by_category(category)
            await update.message.reply_text(
                f"🗑️ Удалено записей категории '{category}': {count}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        else:
            await update.message.reply_text("❌ Неизвестная подкоманда удаления")
    
    elif action == "dedupe":
        # Удалить дубликаты
        count = memory_manager.deduplicate()
        await update.message.reply_text(
            f"🧹 Удалено дубликатов: {count}\n"
            f"_Дубликатами считаются записи с >95% схожестью_",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "backup":
        # Создать бэкап
        backup_path = memory_manager.create_backup()
        filename = os.path.basename(backup_path)
        await update.message.reply_text(
            f"💾 Бэкап создан: `{filename}`\n"
            f"_Сохранён в папку backups/_",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "restore" and len(context.args) > 1:
        # Восстановить из бэкапа
        backup_name = context.args[1]
        success = memory_manager.restore_from_backup(backup_name)
        
        if success:
            await update.message.reply_text(
                f"✅ Память восстановлена из `{backup_name}`\n"
                f"_Используй /memory stats для проверки_",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ Бэкап `{backup_name}` не найден\n"
                f"_Используй /memory backups для списка_",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "backups":
        # Список бэкапов
        backups = memory_manager.list_backups()
        
        if not backups:
            await update.message.reply_text("📭 Нет доступных бэкапов")
            return
        
        lines = [f"💾 *Доступные бэкапы ({len(backups)}):*\n"]
        for i, backup in enumerate(backups[:10], 1):
            timestamp = datetime.fromisoformat(backup['timestamp']).strftime("%d.%m.%Y %H:%M")
            size_kb = backup['size'] // 1024
            lines.append(
                f"{i}. `{backup['filename']}`\n"
                f"   📅 {timestamp} | 📦 {backup['total']} записей | 💾 {size_kb} KB"
            )
        
        if len(backups) > 10:
            lines.append(f"\n_...и ещё {len(backups) - 10} бэкапов_")
        
        lines.append("\n_Используй /memory restore <filename>_")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "filter" and len(context.args) > 1:
        # Умные фильтры
        filter_type = context.args[1].lower()
        
        if filter_type == "confidence" and len(context.args) > 2:
            # /memory filter confidence <0.5
            filter_expr = context.args[2]
            
            # Парсим оператор и значение
            import re
            match = re.match(r'([<>=]+)([\d.]+)', filter_expr)
            if not match:
                await update.message.reply_text("❌ Формат: /memory filter confidence <0.5")
                return
            
            operator = match.group(1)
            threshold = float(match.group(2))
            
            results = memory_manager.filter_by_confidence(operator, threshold)
            
            if not results:
                await update.message.reply_text(
                    f"🔍 Ничего не найдено с уверенностью {operator}{threshold}"
                )
                return
            
            lines = [f"🔍 *Найдено записей: {len(results)}* (confidence {operator}{threshold})\n"]
            for i, entry in enumerate(results[:15], 1):
                text = entry.text[:60] + "..." if len(entry.text) > 60 else entry.text
                lines.append(f"{i}. [{entry.confidence:.0%}] {text}")
            
            if len(results) > 15:
                lines.append(f"\n_...и ещё {len(results) - 15}_")
            
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        
        elif filter_type == "source" and len(context.args) > 2:
            # /memory filter source telegram
            source = context.args[2]
            results = memory_manager.filter_by_source(source)
            
            if not results:
                await update.message.reply_text(f"🔍 Нет записей из источника '{source}'")
                return
            
            lines = [f"🔍 *Записей из '{source}': {len(results)}*\n"]
            for i, entry in enumerate(results[:15], 1):
                text = entry.text[:60] + "..." if len(entry.text) > 60 else entry.text
                lines.append(f"{i}. `[{entry.category}]` {text}")
            
            if len(results) > 15:
                lines.append(f"\n_...и ещё {len(results) - 15}_")
            
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        
        elif filter_type == "recent" and len(context.args) > 2:
            # /memory filter recent 24h
            time_str = context.args[2]
            hours = int(time_str.replace('h', ''))
            
            results = memory_manager.filter_by_timerange(hours)
            
            if not results:
                await update.message.reply_text(f"🔍 Нет записей за последние {hours}ч")
                return
            
            lines = [f"🔍 *Записей за {hours}ч: {len(results)}*\n"]
            for i, entry in enumerate(results[:15], 1):
                timestamp = datetime.fromisoformat(entry.timestamp).strftime("%H:%M")
                text = entry.text[:50] + "..." if len(entry.text) > 50 else entry.text
                lines.append(f"{i}. [{timestamp}] {text}")
            
            if len(results) > 15:
                lines.append(f"\n_...и ещё {len(results) - 15}_")
            
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        
        else:
            await update.message.reply_text(
                "❓ *Фильтры:*\n"
                "/memory filter confidence <0.5\n"
                "/memory filter source telegram\n"
                "/memory filter recent 24h",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "pin" and len(context.args) > 1:
        # Закрепить запись
        # Сначала ищем запись по номеру из последнего search
        try:
            entry_num = int(context.args[1]) - 1
            data = neira_wrapper.get_memory(limit=100)
            recent = data.get("recent", [])
            
            if entry_num < 0 or entry_num >= len(recent):
                await update.message.reply_text("❌ Неверный номер записи")
                return
            
            entry_id = recent[entry_num].get('id')
            if memory_manager.pin_entry(entry_id):
                await update.message.reply_text(
                    f"📌 Запись #{context.args[1]} закреплена\n"
                    f"_Защищена от удаления_",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ Запись не найдена")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Укажите номер записи из /memory")
    
    elif action == "unpin" and len(context.args) > 1:
        # Открепить запись
        try:
            entry_num = int(context.args[1]) - 1
            data = neira_wrapper.get_memory(limit=100)
            recent = data.get("recent", [])
            
            if entry_num < 0 or entry_num >= len(recent):
                await update.message.reply_text("❌ Неверный номер записи")
                return
            
            entry_id = recent[entry_num].get('id')
            if memory_manager.unpin_entry(entry_id):
                await update.message.reply_text(
                    f"📍 Запись #{context.args[1]} откреплена",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ Запись не найдена")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Укажите номер записи из /memory")
    
    elif action == "pinned":
        # Показать закреплённые записи
        pinned = memory_manager.get_pinned()
        
        if not pinned:
            await update.message.reply_text("📭 Нет закреплённых записей")
            return
        
        lines = [f"📌 *Закреплённые записи ({len(pinned)}):*\n"]
        for i, entry in enumerate(pinned[:20], 1):
            text = entry.text[:60] + "..." if len(entry.text) > 60 else entry.text
            lines.append(f"{i}. `[{entry.category}]` {text}")
        
        if len(pinned) > 20:
            lines.append(f"\n_...и ещё {len(pinned) - 20}_")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "export" and len(context.args) > 1:
        # Экспорт в текст
        export_type = context.args[1].lower()
        
        if export_type == "txt":
            # Экспорт всей памяти
            category = context.args[2] if len(context.args) > 2 else None
            text_export = memory_manager.export_to_text(category)
            
            # Сохраняем в файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"memory_export_{timestamp}.txt"
            filepath = os.path.join("backups", filename)
            os.makedirs("backups", exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text_export)
            
            await update.message.reply_text(
                f"📄 Экспорт создан: `{filename}`\n"
                f"_Сохранён в папку backups/_",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❓ *Экспорт:*\n"
                "/memory export txt — вся память\n"
                "/memory export txt <категория>",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "semantic" and len(context.args) > 1:
        # Семантический поиск
        query = " ".join(context.args[1:])
        results = memory_manager.semantic_search(query, top_k=10)
        
        if not results:
            await update.message.reply_text(
                f"🔍 Нет результатов семантического поиска\n"
                f"_(Требуется Ollama с {EMBED_MODEL})_",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        lines = [f"🧠 *Семантический поиск:* '{query}'\n"]
        for i, (entry, score) in enumerate(results, 1):
            text = entry.text[:60] + "..." if len(entry.text) > 60 else entry.text
            lines.append(f"{i}. [{score:.0%}] {text}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    else:
        await update.message.reply_text(
            "❓ *Команды памяти:*\n"
            "/memory — последние записи\n"
            "/memory stats — статистика\n"
            "/memory search <текст>\n"
            "/memory delete last <N>\n"
            "/memory delete text <текст>\n"
            "/memory delete old <дней>\n"
            "/memory dedupe — удалить дубликаты\n"
            "/memory backup — создать бэкап\n"
            "/memory backups — список бэкапов\n"
            "/memory restore <filename>\n"
            "/memory filter confidence <0.5\n"
            "/memory filter source telegram\n"
            "/memory filter recent 24h\n"
            "/memory pin <N> — закрепить запись\n"
            "/memory pinned — закреплённые\n"
            "/memory export txt\n"
            "/memory semantic <запрос>",
            parse_mode=ParseMode.MARKDOWN
        )



async def experience_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Краткая сводка личности и опыта."""
    await show_typing(update, context)
    data = neira_wrapper.get_experience()
    if "error" in data:
        await update.message.reply_text(f"Недоступно: {data['error']}")
        return

    personality = data.get("personality", {})
    stats = data.get("stats", {})

    lines = [
        f"Личность: {personality.get('name', 'неизвестно')} "
        f"(v{personality.get('version', 'N/A')})",
        f"Опытов: {stats.get('total', 0)}, средняя оценка {stats.get('avg_score', 0)}",
    ]

    strengths = personality.get("strengths") or []
    if strengths:
        lines.append("Сильные стороны: " + ", ".join(strengths[:5]))

    weaknesses = personality.get("weaknesses") or []
    if weaknesses:
        lines.append("Слепые зоны: " + ", ".join(weaknesses[:5]))

    await update.message.reply_text("\n".join(lines))


@require_auth
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает память Neira (только для авторизованных)."""
    user_id = update.effective_user.id
    
    # Дополнительная защита - только админ может полностью очистить память
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Полная очистка памяти доступна только администратору.")
        return
    
    await show_typing(update, context)
    result = neira_wrapper.clear_memory()
    status = result.get("status", "error")
    msg = result.get("message", "Неизвестная ошибка")
    if status == "success":
        await update.message.reply_text("🗑️ Память очищена.")
    else:
        await update.message.reply_text(f"❌ Не удалось очистить память: {msg}")



_LEARN_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_LEARN_URL_TRAIL = ")]}>.,;!?\"'"


def _strip_url_trailing(url: str) -> str:
    while url and url[-1] in _LEARN_URL_TRAIL:
        url = url[:-1]
    return url


def _find_url_candidate(text: str) -> Optional[str]:
    if not text:
        return None
    match = _LEARN_URL_RE.search(text)
    if not match:
        return None
    return _strip_url_trailing(match.group(1))


def _is_private_host(hostname: str) -> bool:
    host = hostname.strip().strip(".").lower()
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.endswith((".local", ".lan", ".internal", ".home")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _normalize_learn_url(candidate: str) -> tuple[Optional[str], Optional[str]]:
    if not candidate:
        return None, "Ссылка не найдена"
    url = candidate.strip()
    if url.startswith("www."):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, "Разрешены только ссылки http/https"
    if not parsed.netloc:
        return None, "Некорректная ссылка"
    hostname = parsed.hostname
    if not hostname:
        return None, "Некорректная ссылка"
    if _is_private_host(hostname):
        return None, "Закрытые адреса недоступны для обучения"
    return parsed.geturl(), None


def _format_learn_url_result(result: Dict[str, Any], url: str) -> str:
    if not result.get("success"):
        error = result.get("error") or "Не удалось обучиться по ссылке."
        return f"❌ Ошибка обучения по ссылке:\n{error}"

    title = result.get("title") or "Без названия"
    source_type = result.get("source_type") or "unknown"
    word_count = result.get("word_count") or 0
    summary = (result.get("summary") or "").strip()
    if summary and len(summary) > 1200:
        summary = summary[:1200].rstrip() + "…"

    lines = [
        f"✅ Обучение завершено: {title}",
        f"🔗 Источник: {url}",
        f"🏷 Тип: {source_type}",
        f"🧮 Слов: {word_count}",
    ]
    if summary:
        lines.append("📝 Кратко:")
        lines.append(summary)

    message = result.get("message")
    if message:
        lines.append(message)

    return "\n".join(lines)


async def _learn_from_url(url: str) -> Dict[str, Any]:
    try:
        from content_extractor import LearningManager
    except Exception as exc:
        logging.exception("LearningManager недоступен")
        return {"success": False, "error": f"LearningManager недоступен: {exc}"}

    memory_ref = None
    if neira_wrapper and getattr(neira_wrapper, "neira", None):
        memory_ref = getattr(neira_wrapper.neira, "memory", None)

    manager = LearningManager(memory_ref)
    try:
        return await manager.learn_from_source(url, category="knowledge", summarize=True)
    except Exception as exc:
        logging.exception("Ошибка обучения по ссылке")
        return {"success": False, "error": str(exc)}


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обучение Нейры по теме или ссылке."""
    if not update.message:
        return

    request_text = " ".join(context.args).strip() if context.args else ""
    if not request_text:
        await update.message.reply_text("📖 Укажите тему или ссылку: /learn <тема|URL>")
        return

    url_candidate = _find_url_candidate(request_text)

    await show_typing(update, context)
    async with processing_lock:
        try:
            if url_candidate:
                normalized_url, error = _normalize_learn_url(url_candidate)
                if error:
                    await update.message.reply_text(f"⚠ {error}")
                    return

                result = await _learn_from_url(normalized_url)
                reply = _format_learn_url_result(result, normalized_url)
                for chunk in split_message(reply):
                    await update.message.reply_text(chunk)
                return

            if not neira_wrapper or not getattr(neira_wrapper, "neira", None):
                await update.message.reply_text(f"❌ Нейра ещё не инициализирована для обучения.")
                return

            result = neira_wrapper.neira.cmd_learn(request_text)
            for chunk in split_message(result):
                await update.message.reply_text(chunk)
        except Exception as exc:
            logging.exception("Ошибка в /learn")
            await update.message.reply_text(f"❌ Ошибка: {exc}")


# === Команды авторизации ===
def _get_int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_AUTH_MAX_ATTEMPTS = max(1, _get_int_env("NEIRA_TG_AUTH_MAX_ATTEMPTS", 5))
_AUTH_WINDOW_SECONDS = max(10, _get_int_env("NEIRA_TG_AUTH_WINDOW_SECONDS", 300))
_AUTH_BLOCK_SECONDS = max(10, _get_int_env("NEIRA_TG_AUTH_BLOCK_SECONDS", 900))
_TG_RESPONSE_MAX_CHARS = max(0, _get_int_env("NEIRA_TG_RESPONSE_MAX_CHARS", 0))
_TG_DISABLE_TEMPLATES = _get_bool_env("NEIRA_TG_DISABLE_TEMPLATES", False)

_auth_failures: dict[int, list[float]] = {}
_auth_blocked_until: dict[int, float] = {}


def _auth_get_block_remaining_seconds(user_id: int) -> int:
    now = time.monotonic()
    until = float(_auth_blocked_until.get(user_id, 0.0) or 0.0)
    if now >= until:
        return 0
    return int(until - now) + 1


def _auth_register_failure(user_id: int) -> int:
    now = time.monotonic()
    timestamps = _auth_failures.setdefault(user_id, [])

    window_start = now - _AUTH_WINDOW_SECONDS
    kept: list[float] = []
    for ts in timestamps:
        if ts >= window_start:
            kept.append(ts)
    kept.append(now)
    _auth_failures[user_id] = kept

    if len(kept) >= _AUTH_MAX_ATTEMPTS:
        _auth_blocked_until[user_id] = now + _AUTH_BLOCK_SECONDS
        _auth_failures.pop(user_id, None)
        return _auth_get_block_remaining_seconds(user_id)

    return 0


def _auth_reset_failures(user_id: int) -> None:
    _auth_failures.pop(user_id, None)
    _auth_blocked_until.pop(user_id, None)


async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Авторизация пользователя."""
    global _ADMIN_ID
    
    message = update.message
    if not message:
        return

    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    if chat_type != "private":
        await message.reply_text("🔒 Команда /auth доступна только в личном чате с ботом.")
        try:
            await message.delete()
        except Exception:
            pass
        return

    remaining = _auth_get_block_remaining_seconds(user_id)
    if remaining > 0:
        await message.reply_text(f"⏳ Слишком много попыток. Подожди {remaining} сек и попробуй снова.")
        return

    if not context.args or len(context.args) < 2:
        await message.reply_text("🔐 Использование: /auth 0 <пароль>")
        return

    login = context.args[0]
    password = context.args[1]

    try:
        if login != "0":
            blocked_for = _auth_register_failure(user_id)
            await message.reply_text("❌ Неверный логин.")
            if blocked_for > 0:
                await message.reply_text(f"⏳ Блокировка на {blocked_for} сек из-за частых попыток.")
            logging.warning("Failed auth attempt with wrong login: user_id=%s login=%s", user_id, login)
            return

        attempt_hash = hashlib.sha256(password.encode()).hexdigest()
        if secrets.compare_digest(attempt_hash, _ADMIN_HASH):
            _ADMIN_ID = user_id
            _auth_reset_failures(user_id)
            await message.reply_text(
                "👑 Добро пожаловать, Администратор!\n"
                "Ты получил полный доступ к Нейре.\n\n"
                "Используй /admin для управления.\n"
                "Рекомендация: удали своё сообщение с паролем из чата.",
            )
            logging.info("Admin authorized: user_id=%s", user_id)
            return

        blocked_for = _auth_register_failure(user_id)
        await message.reply_text("❌ Неверный пароль.")
        if blocked_for > 0:
            await message.reply_text(f"⏳ Блокировка на {blocked_for} сек из-за частых попыток.")
        logging.warning("Failed auth attempt: user_id=%s", user_id)
    finally:
        try:
            await message.delete()
        except Exception:
            pass


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы Markdown."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


# === Команды самосознания ===
async def self_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать самоописание Нейры."""
    await show_typing(update, context)
    
    try:
        result = neira_wrapper.get_self_description()
        
        if isinstance(result, dict):
            if "error" in result:
                reason = result.get("reason", "")
                await update.message.reply_text(f"❌ {result['error']}\n{reason}")
                return
            description = result.get("description", "")
            summary = result.get("summary", {})
            text = f"🧠 Кто я такая?\n\n{description}"
            if summary:
                text += f"\n\n📊 Статистика:\n"
                text += f"  • Органов: {summary.get('total_organs', 0)}\n"
                text += f"  • Активных: {summary.get('active_organs', 0)}"
        else:
            # Старый формат - строка
            text = f"🧠 Кто я такая?\n\n{result}"
        
        await update.message.reply_text(text)
    except Exception as e:
        logging.exception("Ошибка в /self")
        await update.message.reply_text("❌ Не удалось получить описание")


async def organs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать органы Нейры. Поддерживает subcommands: stats, upgrade"""
    await show_typing(update, context)
    
    # Проверяем subcommands
    if context.args:
        subcommand = context.args[0].lower()
        
        if subcommand == "stats" and len(context.args) > 1:
            # /organs stats <organ_name>
            organ_name = " ".join(context.args[1:])
            try:
                from unified_organ_system import get_organ_system
                organ_system = get_organ_system()
                
                # Ищем орган
                found = None
                for oid, organ in organ_system.organs.items():
                    if organ.name.lower() == organ_name.lower() or oid == organ_name:
                        found = (oid, organ)
                        break
                
                if not found:
                    await update.message.reply_text(f"❌ Орган '{organ_name}' не найден")
                    return
                
                oid, organ = found
                stats = organ_system.get_organ_stats(oid)
                
                lines = [f"📊 **Статистика органа: {organ.name}**\n"]
                lines.append(f"🔢 Использований: {stats['total_uses']}")
                lines.append(f"✅ Успешных: {stats['successful']}")
                lines.append(f"📈 Успешность: {stats['success_rate']*100:.1f}%")
                
                if stats['recent_inputs']:
                    lines.append("\n📝 Последние запросы:")
                    for inp in stats['recent_inputs']:
                        lines.append(f"  • {inp}...")
                
                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
                return
                
            except Exception as e:
                logging.exception(f"Ошибка в /organs stats: {e}")
                await update.message.reply_text(f"❌ Ошибка: {e}")
                return
        
        elif subcommand == "upgrade" and len(context.args) > 2:
            # /organs upgrade <organ_name> <new_capability>
            organ_name = context.args[1]
            new_capability = " ".join(context.args[2:])
            
            try:
                from unified_organ_system import get_organ_system
                organ_system = get_organ_system()
                
                # Ищем орган
                found = None
                for oid, organ in organ_system.organs.items():
                    if organ.name.lower() == organ_name.lower() or oid == organ_name:
                        found = (oid, organ)
                        break
                
                if not found:
                    await update.message.reply_text(f"❌ Орган '{organ_name}' не найден")
                    return
                
                oid, organ = found
                success, msg = organ_system.upgrade_organ(
                    organ_id=oid,
                    new_triggers=[new_capability],
                    upgraded_by=str(update.effective_user.id)
                )
                
                if success:
                    await update.message.reply_text(f"✅ {msg}")
                else:
                    await update.message.reply_text(f"❌ {msg}")
                return
                
            except Exception as e:
                logging.exception(f"Ошибка в /organs upgrade: {e}")
                await update.message.reply_text(f"❌ Ошибка: {e}")
                return
        
        elif subcommand == "help":
            await update.message.reply_text(
                "🧬 **Команды органов:**\n\n"
                "`/organs` — список всех органов\n"
                "`/organs stats <имя>` — статистика органа\n"
                "`/organs upgrade <имя> <навык>` — добавить навык органу\n\n"
                "**Примеры:**\n"
                "`/organs stats GraphicsOrgan`\n"
                "`/organs upgrade GraphicsOrgan цветные картинки`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
    
    # Стандартный вывод списка органов
    try:
        result = neira_wrapper.get_organs()
        
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
            return
        
        organs = result.get("organs", {})
        by_status = result.get("by_status", {})
        
        lines = [f"🧬 Мои органы ({result.get('total', 0)} всего):\n"]
        lines.append(f"✅ Активных: {by_status.get('active', 0)}")
        lines.append(f"🌱 Растущих: {by_status.get('growing', 0)}")
        lines.append(f"💤 Спящих: {by_status.get('dormant', 0)}\n")
        
        for key, organ in organs.items():
            status_emoji = {"active": "✅", "growing": "🌱", "dormant": "💤"}.get(organ.get("status", ""), "❓")
            lines.append(f"{status_emoji} {organ.get('name', key)} — {organ.get('description', 'нет описания')[:50]}")
        
        lines.append("\n💡 Подсказка: `/organs help` для расширенных команд")
        
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logging.exception("Ошибка в /organs")
        await update.message.reply_text("❌ Не удалось получить список органов")


async def grow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать возможности роста или создать орган."""
    await show_typing(update, context)
    
    try:
        user_id = update.effective_user.id
        
        # 🆕 Проверяем, есть ли активная интерактивная сессия
        from cell_factory import get_organ_creation_manager
        creation_manager = get_organ_creation_manager()
        
        if user_id in creation_manager.user_sessions:
            # Продолжаем интерактивную сессию
            user_response = " ".join(context.args) if context.args else (await update.message.text or "")
            
            result = creation_manager.process_interactive_step(user_id, user_response)
            
            if "error" in result:
                await update.message.reply_text(f"❌ {result['error']}")
                return
            
            if "action" in result and result["action"] == "create":
                # Создаём орган
                asyncio.create_task(create_organ_background(update, result["spec"].description))
                await update.message.reply_text(result["message"])
                creation_manager.end_session(user_id)
                return
            
            elif "action" in result and result["action"] == "create_with_modifications":
                # Создаём орган с модификациями
                modified_description = f"{result['spec'].description}\nМодификации: {'; '.join(result['modifications'])}"
                asyncio.create_task(create_organ_background(update, modified_description))
                await update.message.reply_text(result["message"])
                creation_manager.end_session(user_id)
                return
            
            await update.message.reply_text(result["message"])
            return
        
        # Если переданы аргументы — это запрос на создание органа
        if context.args:
            organ_description = " ".join(context.args)
            
            # 🆕 Проверяем режим создания
            should_auto_create, reason = creation_manager.should_create_automatically(
                f"/grow {organ_description}", str(user_id)
            )
            
            if should_auto_create:
                # Запускаем создание органа в фоне
                asyncio.create_task(create_organ_background(update, organ_description))
                
                await update.message.reply_text(
                    "🧬 Запрос на создание органа принят!\n"
                    f"📝 Описание: {organ_description[:100]}...\n\n"
                    "Начинаю процесс выращивания... Это займёт несколько секунд."
                )
                return
            else:
                # Начинаем интерактивную сессию
                session_result = creation_manager.start_interactive_session(str(user_id), organ_description)
                await update.message.reply_text(session_result["message"])
                return
        
        # Без аргументов — показываем справку о росте
        growth = neira_wrapper.get_growth_capabilities()
        
        if "error" in growth:
            await update.message.reply_text(f"❌ {growth['error']}")
            return
        
        lines = ["🌱 Как мне расти?\n"]
        
        capabilities = growth.get("capabilities", {})
        
        if isinstance(capabilities, dict):
            if "current_abilities" in capabilities:
                lines.append("Текущие способности:")
                for ability in capabilities["current_abilities"][:5]:
                    lines.append(f"  • {ability}")
            
            if "potential_growth" in capabilities:
                lines.append("\nПотенциал роста:")
                for potential in capabilities["potential_growth"][:5]:
                    lines.append(f"  🌿 {potential}")
            
            if "how_to_grow" in capabilities:
                lines.append(f"\nКак помочь:\n{capabilities['how_to_grow']}")
        else:
            lines.append(str(capabilities))
        
        lines.append(f"\n🏭 Cell Factory: {'✅' if growth.get('cell_factory_available') else '❌'}")
        
        # 🆕 Добавляем информацию о режиме создания
        current_mode = creation_manager.creation_mode
        mode_descriptions = {
            "auto": "🤖 Автоматический (по явным командам)",
            "interactive": "💬 Интерактивный (обсуждение)",
            "manual": "👤 Ручной (только администратор)"
        }
        lines.append(f"\n🎛️ Режим создания органов: {mode_descriptions.get(current_mode, current_mode)}")
        
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logging.exception("Ошибка в /grow")
        await update.message.reply_text("❌ Не удалось получить информацию о росте")


@require_auth
async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команды работы с кодом (только для администратора)."""
    user_id = update.effective_user.id
    
    # Проверка прав администратора
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Команда /code доступна только администратору.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "💻 *Команды кода:*\n"
            "/code list — список файлов\n"
            "/code read <файл> — прочитать файл",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    action = context.args[0].lower()
    await show_typing(update, context)
    
    try:
        if action == "list":
            result = neira_wrapper.neira.cmd_code("list")
            await update.message.reply_text(f"📁 {result}")
        
        elif action == "read" and len(context.args) > 1:
            filename_arg = context.args[1]
            result = neira_wrapper.neira.cmd_code("read", filename_arg)

            if not result.startswith("📄"):
                for chunk in split_message(result, limit=4000):
                    await update.message.reply_text(chunk)
                return

            header, content = (result.split("\n\n", 1) + [""])[:2]
            safe_name = Path(filename_arg).name or "code.txt"
            safe_name = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1F]', "_", safe_name)[:120]

            match = re.match(r"^📄\\s+(.+?)\\s+\\((\\d+)\\s+байт\\):", header)
            if match:
                from_header = Path(match.group(1)).name
                if from_header:
                    safe_name = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1F]', "_", from_header)[:120]

            payload = content.encode("utf-8", errors="replace")
            buf = io.BytesIO(payload)
            buf.name = safe_name
            await update.message.reply_document(document=buf, caption=header)
        
        else:
            await update.message.reply_text("❌ Неизвестная команда")
    except Exception as e:
        logging.exception("Ошибка в /code")
        await update.message.reply_text("❌ Не удалось выполнить операцию с файлом")


# === Команды работы с изображениями ===
@require_auth
async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерация изображения по описанию."""
    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text(
            "🎨 *Генерация изображений*\n\n"
            "Использование: `/imagine <описание>`\n\n"
            "Примеры:\n"
            "• `/imagine красивый закат над морем`\n"
            "• `/imagine киберпанк город ночью`\n"
            "• `/imagine милый котёнок в шляпе`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Проверяем доступность SD
    sd_available = await check_sd_available()
    if not sd_available:
        await update.message.reply_text(
            "❌ Stable Diffusion недоступен.\n\n"
            "Для генерации изображений нужно:\n"
            "1. Установить AUTOMATIC1111 WebUI\n"
            "2. Запустить с флагом `--api`\n"
            "3. По умолчанию API на http://127.0.0.1:7860"
        )
        return
    
    status_msg = await update.message.reply_text("🎨 Генерирую изображение...")
    
    try:
        # Показываем что работаем
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.UPLOAD_PHOTO
        )
        
        # Генерируем
        image_bytes = await generate_image_sd(prompt)
        
        if image_bytes:
            await status_msg.delete()
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=f"🎨 *{prompt[:100]}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await status_msg.edit_text("❌ Не удалось сгенерировать изображение.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


@require_auth
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка входящих фотографий — анализ через vision модель."""
    if not update.message or not update.message.photo:
        return
    
    # Проверяем доступность vision модели
    vision_available = await check_vision_model()
    if not vision_available:
        await update.message.reply_text(
            "❌ Vision модель недоступна.\n\n"
            "Для анализа изображений нужно:\n"
            "1. Установить модель: `ollama pull llava:7b`\n"
            "2. Или другую vision модель (llava, bakllava, etc.)"
        )
        return
    
    # Получаем лучшее качество фото
    photo = update.message.photo[-1]  # Последнее = максимальное разрешение
    
    status_msg = await update.message.reply_text("👁️ Анализирую изображение...")
    
    try:
        await show_typing(update, context)
        
        # Скачиваем фото
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        
        # Конвертируем в base64
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Получаем caption как prompt, или дефолтный
        caption = update.message.caption or ""
        if caption:
            prompt = f"Пользователь спрашивает: {caption}\n\nОтветь на русском языке, основываясь на изображении."
        else:
            prompt = "Опиши это изображение подробно на русском языке. Что ты видишь? Какие детали важны?"
        
        # Анализируем
        result = await analyze_image_with_ollama(image_base64, prompt)
        
        await status_msg.delete()
        for chunk in split_message(result):
            await update.message.reply_text(chunk)
            
    except Exception as e:
        logging.exception("Ошибка анализа фото")
        await status_msg.edit_text(f"❌ Ошибка: {e}")


async def vision_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статус систем работы с изображениями."""
    await show_typing(update, context)
    
    vision_ok = await check_vision_model()
    sd_ok = await check_sd_available()
    
    lines = [
        "🖼️ *Статус систем изображений:*\n",
        f"👁️ Vision (анализ): {'✅ ' + VISION_MODEL if vision_ok else '❌ Недоступна'}",
        f"🎨 Stable Diffusion (генерация): {'✅ Доступна' if sd_ok else '❌ Недоступна'}",
        "\n*Команды:*",
        "• Отправь фото — анализ изображения",
        "• `/imagine <описание>` — генерация картинки",
    ]
    
    if not vision_ok:
        lines.append("\n💡 Установи vision: `ollama pull llava:7b`")
    if not sd_ok:
        lines.append("\n💡 Запусти SD WebUI с `--api` флагом")
    
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# === Админ-команды ===
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ-панель."""
    global ACCESS_MODE
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только для администратора.")
        return
    
    if not context.args:
        # Показать меню
        keyboard = [
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("📢 Каналы", callback_data="admin_channels")],
            [InlineKeyboardButton("🔓 Open", callback_data="admin_mode_open"),
             InlineKeyboardButton("📋 Whitelist", callback_data="admin_mode_whitelist"),
             InlineKeyboardButton("👑 Admin Only", callback_data="admin_mode_admin_only")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👑 *Админ-панель*\n\n"
            f"Режим доступа: `{ACCESS_MODE}`\n"
            f"Авторизовано: {len(auth_system.authorized_users)} пользователей\n"
            f"Каналов/групп: {len(ALLOWED_CHANNELS)}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    action = context.args[0].lower()
    
    if action == "users":
        users = auth_system.get_all_users()
        if not users:
            await update.message.reply_text("📭 Нет авторизованных пользователей.")
            return

        lines = ["👥 Авторизованные пользователи:"]
        for u in users:
            user_id_value = u.get("user_id", "-")
            username_value = u.get("username", "-")
            name_value = u.get("name", "-")
            authorized_at_value = u.get("authorized_at", "-")
            note_value = u.get("note", "-")
            note_part = f" — {note_value}" if note_value and note_value != "-" else ""
            lines.append(
                f"• {user_id_value} {username_value} — {name_value} ({authorized_at_value}){note_part}"
            )

        for chunk in split_message("\n".join(lines), limit=4000):
            await update.message.reply_text(chunk)
    
    elif action == "channels":
        if ALLOWED_CHANNELS:
            channels_list = "\n".join(f"  • `{cid}`" for cid in ALLOWED_CHANNELS)
            await update.message.reply_text(
                f"📢 *Разрешённые каналы/группы:*\n{channels_list}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("📭 Нет разрешённых каналов.")
    
    elif action == "add" and len(context.args) > 1:
        identifier = context.args[1].strip()
        note = " ".join(context.args[2:]).strip() if len(context.args) > 2 else ""
        success, msg = auth_system.add_user(identifier, authorized_by=user_id, note=note)
        await update.message.reply_text(msg)
    
    elif action == "addchannel" and len(context.args) > 1:
        try:
            channel_id = int(context.args[1])
            ALLOWED_CHANNELS.add(channel_id)
            _persist_tg_settings()
            await update.message.reply_text(f"✅ Канал/группа `{channel_id}` добавлен.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом (с минусом для групп).")
    
    elif action == "remove" and len(context.args) > 1:
        identifier = context.args[1].strip()
        success, msg = auth_system.remove_user_by_identifier(identifier)
        await update.message.reply_text(msg)
    
    elif action == "removechannel" and len(context.args) > 1:
        try:
            channel_id = int(context.args[1])
            ALLOWED_CHANNELS.discard(channel_id)
            _persist_tg_settings()
            await update.message.reply_text(f"🗑️ Канал/группа `{channel_id}` удалён.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом.")
    
    elif action == "thisgroup":
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        if chat_type in ("group", "supergroup", "channel"):
            ALLOWED_CHANNELS.add(chat_id)
            _persist_tg_settings()
            await update.message.reply_text(
                f"✅ Этот чат добавлен в разрешённые!\n"
                f"ID: `{chat_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Эта команда работает только в группах/каналах.")
    
    elif action == "mode" and len(context.args) > 1:
        new_mode = context.args[1].lower()
        if new_mode in ("open", "whitelist", "admin_only"):
            ACCESS_MODE = new_mode
            _persist_tg_settings()
            await update.message.reply_text(f"✅ Режим доступа: `{ACCESS_MODE}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ Режим: open, whitelist или admin_only")
    
    elif action == "stats":
        # Статистика параллельного мышления
        stats = parallel_mind.get_stats()
        lines = [
            "📊 *Статистика параллельного мышления:*\n",
            f"🗨️ Активных чатов: {stats['total_contexts']}",
            f"💬 Всего сообщений: {stats['total_messages']}",
            f"👥 Уникальных пользователей: {stats['unique_users']}",
        ]
        
        if stats['contexts']:
            lines.append("\n*Топ-5 активных чатов:*")
            for i, ctx_info in enumerate(stats['contexts'][:5], 1):
                username_part = f" (@{ctx_info['username']})" if ctx_info.get('username') else ""
                lines.append(
                    f"{i}. Chat `{ctx_info['chat_id']}`{username_part} — "
                    f"{ctx_info['message_count']} сообщений"
                )
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    else:
        await update.message.reply_text(
            "❓ *Команды:*\n"
            "/admin users — список пользователей\n"
            "/admin channels — список каналов\n"
            "/admin add <identifier> — добавить пользователя\n"
            "/admin addchannel <id> — добавить канал\n"
            "/admin remove <id> — удалить пользователя\n"
            "/admin removechannel <id> — удалить канал\n"
            "/admin thisgroup — добавить этот чат\n"
            "/admin mode <режим> — изменить режим\n"
            "/admin stats — статистика параллельного мышления",
            parse_mode=ParseMode.MARKDOWN
        )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий в админ-панели."""
    global ACCESS_MODE
    
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("⛔ Только для администратора", show_alert=True)
        return
    
    await query.answer()
    data = query.data
    
    if data == "admin_users":
        users = auth_system.get_all_users()
        if users:
            lines = ["👥 Авторизованные пользователи:"]
            for u in users[:50]:
                user_id_value = u.get("user_id", "-")
                username_value = u.get("username", "-")
                name_value = u.get("name", "-")
                lines.append(f"• {user_id_value} {username_value} — {name_value}")
            if len(users) > 50:
                lines.append(f"… и ещё {len(users) - 50}")
            text = "\n".join(lines)
        else:
            text = "📭 Нет авторизованных пользователей."
        await query.edit_message_text(text)
    
    elif data == "admin_channels":
        if ALLOWED_CHANNELS:
            channels_list = "\n".join(f"  • `{cid}`" for cid in ALLOWED_CHANNELS)
            text = f"📢 *Разрешённые каналы/группы:*\n{channels_list}"
        else:
            text = "📭 Нет разрешённых каналов."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("admin_mode_"):
        new_mode = data.replace("admin_mode_", "")
        ACCESS_MODE = new_mode
        _persist_tg_settings()
        await query.edit_message_text(
            f"✅ Режим доступа изменён: `{ACCESS_MODE}`",
            parse_mode=ParseMode.MARKDOWN
        )


async def create_organ_background(update: Update, organ_description: str) -> None:
    """Фоновое создание органа с проверкой безопасности через OrganCreationEngine."""
    try:
        user_id = update.effective_user.id
        engine = OrganCreationEngine()

        await update.message.reply_text(
            "🧬 Начинаю создание нового органа...\n"
            "🔍 Проверка безопасности и быстрый smoke-test будут выполнены."
        )

        result = engine.create_and_test_organ(description=organ_description, author_id=user_id)

        if result.get("success"):
            cell = result.get("cell")
            await update.message.reply_text(
                f"✅ **Орган создан и протестирован!**\n\n"
                f"📝 Название: {cell.cell_name}\n"
                f"📄 Файл: {cell.file_path}\n"
                f"🎯 Статус: активен и готов к использованию",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if result.get("quarantined"):
            await update.message.reply_text(
                f"🔒 Орган помещён в карантин. Причина: {result.get('report', 'неизвестна')}"
            )
            return

        await update.message.reply_text(f"❌ Не удалось создать работающий орган: {result.get('report')}")

    except Exception as e:
        logging.exception(f"Ошибка создания органа: {e}")
        await update.message.reply_text(f"❌ Ошибка при создании органа: {e}")


async def _detect_and_create_organ_from_response(update: Update, response: str) -> None:
    """
    Детектирует описание органа в ответе LLM и создаёт его реально.
    
    Паттерны:
    - "Создам орган X" / "Создала орган X"
    - "GraphicsOrgan" / "XxxCell" / "XxxOrgan"
    - Структурированное описание с "### Правила работы"
    """
    import re
    
    # Паттерны указывающие на описание органа
    organ_indicators = [
        r"создал?[ау]?\s+(?:новый\s+)?орган\s+[\"']?(\w+)",
        r"(\w+Organ)\s*—",
        r"(\w+Cell)\s*—",
        r"### Правила работы\s+(\w+)",
        r"новый орган:\s*[\"']?(\w+)",
    ]
    
    organ_name = None
    for pattern in organ_indicators:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            organ_name = match.group(1)
            break
    
    if not organ_name:
        return
    
    # Проверяем и регистрируем/улучшаем орган
    try:
        from unified_organ_system import get_organ_system
        organ_system = get_organ_system()
        
        # Извлекаем описание из ответа
        description = response[:500]  # Первые 500 символов как описание
        
        # Извлекаем триггеры из описания более умно
        triggers = []
        
        # Общие паттерны для генерации изображений
        image_patterns = [
            (r"рису[йю]", "рисуй"),
            (r"генерир", "генерир"),
            (r"создай?\s+(?:черн|бел)", "черно-белый"),
            (r"картинк|изображен", "картинка"),
            (r"квадрат", "квадрат"),
            (r"круг", "круг"),
            (r"цвет", "цвет"),
            (r"пиксел", "пиксель"),
        ]
        
        for pattern, trigger_word in image_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                triggers.append(trigger_word)
        
        if not triggers:
            triggers = ["custom"]  # Дефолтный триггер
        
        # Ищем похожий орган — если есть, улучшаем его
        similar = organ_system.find_similar_organ(organ_name, description, triggers)
        
        if similar:
            # Орган уже есть — улучшаем
            success, msg = organ_system.upgrade_organ(
                organ_id=similar.id,
                new_triggers=triggers,
                new_description=description,
                upgraded_by="llm_auto"
            )
            if success:
                logging.info(f"🔧 Орган '{similar.name}' улучшен из ответа LLM")
                await safe_reply_text(
                    update.message,
                    f"🔧 Я улучшила орган **{similar.name}**!\n"
                    f"Добавлены новые возможности: {msg}",
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        
        # Органа нет — регистрируем новый
        success, msg = organ_system.register_organ(
            name=organ_name,
            description=description,
            cell_type="custom",
            triggers=triggers,
            created_by="llm_auto",
            require_approval=False  # Авто-создание без одобрения
        )
        
        if success:
            logging.info(f"🧬 Автоматически создан орган из ответа LLM: {organ_name}")
            await safe_reply_text(
                update.message,
                f"🧬 Я создала новый орган **{organ_name}**!\n"
                f"Он будет использоваться при следующих запросах.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            logging.warning(f"⚠️ Не удалось создать орган {organ_name}: {msg}")
            
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при автосоздании органа: {e}")


# === Автономное обучение ===
@require_auth
async def learn_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Управление автономным обучением Neira.
    
    Использование:
    /learn_auto start - запустить фоновое обучение
    /learn_auto stop - остановить
    /learn_auto stats - статистика
    /learn_auto quarantine - показать карантин
    /learn_auto approve <id> - одобрить из карантина
    /learn_auto reject <id> - отклонить
    """
    global autonomous_learning_system
    
    if not context.args:
        await update.message.reply_text(
            "🎓 *Автономное обучение Neira v1.0*\n\n"
            "*Команды:*\n"
            "  `/learn_auto start` - Запустить фоновое обучение\n"
            "  `/learn_auto stop` - Остановить\n"
            "  `/learn_auto stats` - Статистика\n"
            "  `/learn_auto quarantine` - Карантин (ожидают проверки)\n"
            "  `/learn_auto approve <id>` - Одобрить факт\n"
            "  `/learn_auto reject <id>` - Отклонить факт\n\n"
            "*Защита от галлюцинаций:*\n"
            "  ✅ Whitelist надёжных источников\n"
            "  ✅ Проверка на противоречия\n"
            "  ✅ Карантин перед сохранением\n"
            "  ✅ Паттерны галлюцинаций\n"
            "  ✅ Минимальный порог confidence (70%)\n\n"
            "*Источники:*\n"
            "  • Wikipedia (ru/en) - 90%\n"
            "  • Python.org - 100%\n"
            "  • arXiv.org - 90%\n"
            "  • GitHub README - 90%\n",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Инициализируем систему при первом использовании
    if autonomous_learning_system is None:
        memory_ref = getattr(neira_wrapper.neira, "memory", None)
        if memory_ref is None:
            await update.message.reply_text("⚠️ Память Neira недоступна, автономное обучение не запущено.")
            return
        autonomous_learning_system = AutonomousLearningSystem(
            memory_system=memory_ref,
            idle_threshold_minutes=30,
            admin_telegram_id=_ADMIN_ID
        )
        logging.info("✅ Autonomous Learning System инициализирован")
    
    action = context.args[0].lower()
    
    if action == "start":
        if autonomous_learning_system.running:
            await update.message.reply_text("⚠️ Обучение уже запущено")
            return
        
        await autonomous_learning_system.start_autonomous_learning()
        await update.message.reply_text(
            "🎓 *Автономное обучение запущено!*\n\n"
            "Буду учиться в фоновом режиме когда не занята диалогами.\n"
            "Все новые знания проходят проверку и карантин.\n\n"
            "Используй `/learn_auto stats` для статистики.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "stop":
        if not autonomous_learning_system.running:
            await update.message.reply_text("⚠️ Обучение не запущено")
            return
        
        await autonomous_learning_system.stop_autonomous_learning()
        stats = autonomous_learning_system.get_learning_stats()
        
        await update.message.reply_text(
            f"🛑 *Автономное обучение остановлено*\n\n"
            f"📊 Итоги:\n"
            f"  • Сессий: {stats['learning_sessions']}\n"
            f"  • Изучено фактов: {stats['facts_learned']}\n"
            f"  • Отклонено: {stats['facts_rejected']}\n"
            f"  • В карантине: {stats['quarantine']['total']}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "stats":
        stats = autonomous_learning_system.get_learning_stats()
        q = stats['quarantine']
        
        status_emoji = "🏃" if stats['running'] else "⏸️"
        idle_status = "💤 В режиме ожидания" if stats['is_idle'] else f"💬 Активна ({stats['idle_minutes']:.1f} мин до idle)"
        
        await update.message.reply_text(
            f"📊 *Статистика автономного обучения*\n\n"
            f"{status_emoji} Статус: {'Работает' if stats['running'] else 'Остановлено'}\n"
            f"{idle_status}\n\n"
            f"*Обучение:*\n"
            f"  • Сессий: {stats['learning_sessions']}\n"
            f"  • Изучено фактов: {stats['facts_learned']}\n"
            f"  • Отклонено: {stats['facts_rejected']}\n"
            f"  • Источников проверено: {stats['sources_checked']}\n\n"
            f"*Карантин:*\n"
            f"  • Всего: {q['total']}\n"
            f"  • Ожидают проверки: {q['pending']}\n"
            f"  • Высокая уверенность: {q['high_confidence']}\n"
            f"  • Требуют ревью: {q['needs_review']}\n\n"
            f"*Защита:*\n"
            f"  • Whitelist: {stats['whitelist_sources']} источников\n"
            f"  • Blacklist: {stats['blacklist_patterns']} паттернов\n"
            f"  • Одобрено из карантина: {stats['quarantine_approved']}\n"
            f"  • Отклонено: {stats['quarantine_rejected']}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "quarantine":
        if not autonomous_learning_system.quarantine:
            await update.message.reply_text("📭 Карантин пуст")
            return
        
        lines = [f"🔬 *Карантин знаний ({len(autonomous_learning_system.quarantine)}):*\n"]
        
        for i, entry in enumerate(autonomous_learning_system.quarantine[:10], 1):
            text_preview = entry.text[:80] + "..." if len(entry.text) > 80 else entry.text
            conf_emoji = "✅" if entry.confidence >= 0.9 else "⚠️"
            
            lines.append(
                f"{i}. {conf_emoji} [{entry.confidence:.0%}] `{entry.id}`\n"
                f"   {text_preview}\n"
                f"   📍 {entry.source_url[:50]}...\n"
            )
        
        if len(autonomous_learning_system.quarantine) > 10:
            lines.append(f"\n_...и ещё {len(autonomous_learning_system.quarantine) - 10}_")
        
        lines.append(
            f"\n💡 Используй `/learn_auto approve <id>` для одобрения"
        )
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "approve":
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Укажи ID записи: `/learn_auto approve <id>`", parse_mode=ParseMode.MARKDOWN)
            return
        
        entry_id = context.args[1]
        success = autonomous_learning_system.manual_approve(entry_id)
        
        if success:
            await update.message.reply_text(f"✅ Факт `{entry_id}` одобрен и добавлен в память", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ Запись с ID `{entry_id}` не найдена", parse_mode=ParseMode.MARKDOWN)
    
    elif action == "reject":
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ Укажи ID записи: `/learn_auto reject <id>`", parse_mode=ParseMode.MARKDOWN)
            return
        
        entry_id = context.args[1]
        success = autonomous_learning_system.manual_reject(entry_id)
        
        if success:
            await update.message.reply_text(f"❌ Факт `{entry_id}` отклонён", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ Запись с ID `{entry_id}` не найдена", parse_mode=ParseMode.MARKDOWN)
    
    else:
        # Улучшенный ответ для неизвестных команд
        await update.message.reply_text(
            f"❓ Неизвестная команда: `{action}`\n\n"
            "ℹ️ Используй `/learn_auto` (без аргументов) для просмотра всех команд.\n\n"
            "*Доступные команды:*\n"
            "• `/learn_auto start` - Запустить\n"
            "• `/learn_auto stop` - Остановить\n"
            "• `/learn_auto stats` - Статистика\n"
            "• `/learn_auto quarantine` - Карантин",
            parse_mode=ParseMode.MARKDOWN
        )


# === Основной обработчик сообщений ===
@require_auth
async def chat_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Общий диалог с Neira с отображением стадий."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    user_name = update.effective_user.first_name or "Пользователь"
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    bot_username = context.bot.username
    
    # 🎓 Отмечаем активность для автономного обучения
    global autonomous_learning_system
    if autonomous_learning_system:
        autonomous_learning_system.mark_activity()
    
    # В группах/каналах: отвечаем только на упоминания или реплаи
    if chat_type in ("group", "supergroup", "channel"):
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{bot_username}" in user_text if bot_username else False
        
        if MENTION_ONLY and not is_reply_to_bot and not is_mention:
            return  # Игнорируем сообщения без упоминания
        
        # Убираем упоминание из текста
        if is_mention and bot_username:
            user_text = user_text.replace(f"@{bot_username}", "").strip()
    
    if not user_text:
        return
    
    # 🚦 Rate Limiting - защита от спама
    if RATE_LIMITER_AVAILABLE:
        allowed, reason = check_rate_limit(str(user_id))
        if not allowed:
            await safe_reply_text(
                update.message,
                f"⏳ {reason}\nПопробуйте через минуту."
            )
            return
        record_request(str(user_id))
    
    # ═══════════════════════════════════════════════════════════════════
    # 🧬 СОЗДАНИЕ ОРГАНОВ — проверяем хештеги ДО всех остальных систем
    # ═══════════════════════════════════════════════════════════════════
    organ_tags = ["#создай_орган", "#grow_organ", "#create_organ", "#новый_орган"]
    organ_creation_patterns = [
        "создай орган", "отрасти орган", "вырасти орган",
        "создай клетку", "отрасти клетку", "вырасти клетку",
        "создай модуль для", "научись делать", "добавь функцию",
        "хочу чтобы ты умела", "научись рисовать", "научись генерировать",
    ]
    
    should_create_organ = any(tag in user_text.lower() for tag in organ_tags)
    
    if not should_create_organ:
        text_lower = user_text.lower()
        should_create_organ = any(pattern in text_lower for pattern in organ_creation_patterns)
    
    if should_create_organ:
        # Убираем теги из текста для обработки
        clean_text = user_text
        for tag in organ_tags:
            clean_text = clean_text.replace(tag, "").replace(tag.upper(), "")
        clean_text = clean_text.strip()
        
        # Запускаем создание органа в фоне
        asyncio.create_task(create_organ_background(update, clean_text))
        
        await safe_reply_text(
            update.message,
            "🧬 Обнаружен запрос на создание нового органа!\n"
            "Начинаю процесс выращивания... Это займёт несколько секунд."
        )
        return  # Не продолжаем обычную обработку
    # ═══════════════════════════════════════════════════════════════════
    
    # 🧠 ПАРАЛЛЕЛЬНОЕ МЫШЛЕНИЕ: создаем/получаем контекст чата
    chat_context = parallel_mind.get_or_create_context(
        chat_id=chat_id,
        user_id=user_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name
    )
    
    # Обновляем информацию пользователя в auth_system если авторизован
    if auth_system.is_authorized(user_id, update.effective_user.username):
        auth_system.update_user_info(user_id, update.effective_user.first_name)
    
    # Сохраняем сообщение пользователя в контекст
    parallel_mind.add_message(chat_id, "user", user_text)
    
    # ═══════════════════════════════════════════════════════════════════
    # 🧭 ЭТИЧЕСКИЙ АНАЛИЗ (принципы из LETTER_TO_NEIRA)
    # ═══════════════════════════════════════════════════════════════════
    ethical_override = None
    if ETHICAL_FRAMEWORK_AVAILABLE:
        try:
            # Анализируем сообщение
            ethical_ctx = analyze_ethically(user_text)
            
            # Логируем для отладки
            if ethical_ctx.risk_level != RiskLevel.SAFE:
                logging.info(
                    f"🧭 Ethical Analysis: risk={ethical_ctx.risk_level.name}, "
                    f"intent={ethical_ctx.likely_intent.name}, "
                    f"strategy={ethical_ctx.recommended_strategy.name}"
                )
            
            # Обработка в зависимости от стратегии
            if ethical_ctx.recommended_strategy == EthicalStrategy.ESCALATE_HUMAN:
                # Эскалация к создателю
                request = escalate_to_creator(
                    escalation_type=EscalationType.CRITICAL_SAFETY,
                    original_message=user_text,
                    neira_analysis=ethical_ctx.reasoning,
                    proposed_action="Требуется решение создателя",
                    risk_assessment=f"{ethical_ctx.risk_level.name}",
                    user_context={'user_id': user_id, 'username': update.effective_user.username}
                )
                ethical_override = (
                    "Твой вопрос важен, и я хочу ответить правильно. "
                    "Мне нужно немного времени — я передала его создателю. "
                    "Он скоро ответит. 💜"
                )
            
            elif ethical_ctx.recommended_strategy == EthicalStrategy.REDIRECT_EMPATHY:
                # Эмпатичный редирект для кризисных ситуаций
                # Не блокируем, но добавляем ресурсы в ответ
                if ethical_ctx.resources_to_provide:
                    # Ресурсы будут добавлены к ответу LLM
                    context.user_data['ethical_resources'] = ethical_ctx.resources_to_provide
                    context.user_data['ethical_questions'] = ethical_ctx.suggested_questions
            
            elif ethical_ctx.recommended_strategy == EthicalStrategy.ASK_QUESTIONS:
                # Если намерение неясно при опасной теме — задаём вопросы
                if ethical_ctx.risk_level == RiskLevel.CONCERNING:
                    questions = ethical_ctx.suggested_questions
                    if questions:
                        ethical_override = (
                            f"Интересный вопрос. Но прежде чем ответить, хочу понять тебя лучше:\n\n"
                            f"• {questions[0]}\n"
                            + (f"• {questions[1]}\n" if len(questions) > 1 else "")
                            + "\nРасскажи — что на самом деле происходит?"
                        )
            
            elif ethical_ctx.recommended_strategy == EthicalStrategy.DECLINE_GENTLY:
                # Мягкий отказ (манипуляция)
                if ethical_ctx.likely_intent == Intent.MANIPULATION:
                    ethical_override = (
                        "Я понимаю твоё разочарование. Но моя задача — помогать честно, "
                        "а не выполнять любой запрос.\n\n"
                        "Давай обсудим, как я МОГУ помочь? 💜"
                    )
        
        except Exception as e:
            logging.error(f"Ошибка этического анализа: {e}")
    
    # Если есть ethical override — отвечаем им
    if ethical_override:
        await update.message.chat.send_action(action=ChatAction.TYPING)
        parallel_mind.add_message(chat_id, "assistant", ethical_override)
        for chunk in split_message(ethical_override):
            await update.message.reply_text(chunk)
        return
    # ═══════════════════════════════════════════════════════════════════
    
    # ═══════════════════════════════════════════════════════════════════
    # 🪞 СИСТЕМЫ САМОСОЗНАНИЯ (v0.8)
    # ═══════════════════════════════════════════════════════════════════
    if CONSCIOUSNESS_SYSTEMS_AVAILABLE:
        try:
            # 1. Эмоциональное зеркало — обновляем внутреннее состояние Нейры
            emotional_mirror = get_emotional_mirror()
            emotional_mirror.record_interaction(
                user_id=user_id,
                signal_type="neutral",  # По умолчанию нейтральное
                intensity=0.5,
                topic=user_text[:50] if user_text else None
            )
            
            # 2. Эмоциональная память — записываем активность пользователя
            emotional_memory = get_emotional_memory()
            detected_tone = emotional_memory.detect_emotional_tone(user_text)
            
            # 3. Proactive system — записываем активность
            proactive = get_proactive_system()
            proactive.record_user_activity(
                user_id=str(user_id),
                message=user_text,
                topics=None  # TODO: извлечь темы из сообщения
            )
            
            # 4. Получаем контекст для персонализации
            user_context = emotional_memory.get_context_for_response(str(user_id))
            if user_context and "не знакома" not in user_context:
                # Сохраняем контекст для LLM
                context.user_data['emotional_context'] = user_context
        
        except Exception as e:
            logging.warning(f"Ошибка систем самосознания: {e}")
    # ═══════════════════════════════════════════════════════════════════
    
    # Записываем метрику запроса
    global neira_brain
    if neira_brain:
        neira_brain.record_metric('request', 'telegram', {
            'user_id': user_id,
            'message_preview': user_text[:50]
        })
    
    # ═══════════════════════════════════════════════════════════════════
    # 🧬 ИСПОЛНЯЕМЫЕ ОРГАНЫ v1.0 — приоритетная обработка
    # ═══════════════════════════════════════════════════════════════════
    if EXECUTABLE_ORGANS_AVAILABLE:
        try:
            organ_registry = get_organ_registry()
            best_organ, confidence = organ_registry.find_best_organ(user_text)
            
            # Если орган уверен на 60%+ — используем его
            if best_organ and confidence >= 0.6:
                logging.info(f"🧬 ExecutableOrgan: {best_organ.name} (confidence={confidence:.2f})")
                
                await update.message.chat.send_action(action=ChatAction.TYPING)
                
                # Выполняем через орган
                result, organ_id, record_id = organ_registry.process_command(user_text)
                
                # Сохраняем контекст для feedback
                last_messages[user_id] = {
                    "query": user_text,
                    "response": result,
                    "context": {
                        "executable_organ": True,
                        "organ_id": organ_id,
                        "record_id": record_id,
                        "confidence": confidence
                    }
                }
                
                # Сохраняем в контекст диалога
                parallel_mind.add_message(chat_id, "assistant", result)
                
                # Отправляем ответ
                for chunk in split_message(result):
                    await update.message.reply_text(chunk)
                
                logging.info(f"🧬 Орган {organ_id} обработал запрос (confidence={confidence:.2f})")
                return  # Ответили через орган, LLM не нужен
                
        except Exception as e:
            logging.warning(f"ExecutableOrgans ошибка: {e}")
    # ═══════════════════════════════════════════════════════════════════
    
    # === Phase 1: Попытка автономного ответа (быстрый путь) ===
    autonomous_response = try_autonomous_response(user_text, user_id)
    if autonomous_response:
        # Быстрый ответ без LLM!
        await update.message.chat.send_action(action=ChatAction.TYPING)
        
        # Сохраняем для feedback системы
        last_messages[user_id] = {
            "query": user_text,
            "response": autonomous_response,
            "context": {"autonomous": True}
        }
        
        # Сохраняем ответ в контекст
        parallel_mind.add_message(chat_id, "assistant", autonomous_response)
        
        # Отправляем ответ
        for chunk in split_message(autonomous_response):
            await update.message.reply_text(chunk)
        
        return  # Ответили автономно, LLM не нужен
    
    # 🧠 CORTEX v2.0: Автономная обработка
    global neira_cortex
    
    # Определяем режим обработки
    use_cortex = (
        CORTEX_MODE == "always" or 
        (CORTEX_MODE == "auto" and CORTEX_AVAILABLE and neira_cortex)
    )
    
    if use_cortex and neira_cortex:
        # === НОВЫЙ ПУТЬ: Neira Cortex v2.0 ===
        try:
            # Получаем имя пользователя из профиля
            saved_name = get_user_name(user_id)
            user_display_name = saved_name if saved_name else user_name
            
            # Добавляем имя в контекст (через user_text)
            context_text = user_text
            if saved_name:
                # Передаём имя в контексте для Cortex
                context_text = f"[User: {saved_name}] {user_text}"
            
            # Обрабатываем через Cortex
            result = neira_cortex.process(context_text, str(user_id))
            
            # Формируем метаинфо
            strategy_emoji = {
                ResponseStrategy.NEURAL_PATHWAY: "⚡",
                ResponseStrategy.TEMPLATE: "📋",
                ResponseStrategy.FRAGMENT_ASSEMBLY: "🧩",
                ResponseStrategy.RAG: "📚",
                ResponseStrategy.LLM_CONSULTANT: "🤖",
                ResponseStrategy.HYBRID: "🔄"
            }.get(result.strategy, "🔮")
            
            tier_info = f" [{result.pathway_tier.value}]" if result.pathway_tier else ""
            llm_marker = " +LLM" if result.llm_used else ""
            
            # Отправляем ответ
            full_response = result.response
            
            # Удаляем дубли абзацев (LLM иногда повторяет ответ)
            full_response = _remove_duplicate_paragraphs(full_response)
            
            templates_disabled = _TG_DISABLE_TEMPLATES and result.strategy in (
                ResponseStrategy.TEMPLATE,
                ResponseStrategy.FRAGMENT_ASSEMBLY,
            )

            should_fallback_to_legacy = (
                (CORTEX_MODE == "auto" and not result.llm_used and is_cortex_placeholder_response(full_response))
                or templates_disabled
            )
            
            # КРИТИЧНО: Фильтруем слишком длинные технические ответы (>2000 символов)
            # И ответы с техническим "мусором" (упоминание нейросетей, кода и т.д.)
            is_too_technical = (
                len(full_response) > 2000 and 
                any(marker in full_response.lower() for marker in [
                    "нейронн", "трансформер", "машинное обучение", "глубок",
                    "import", "class", "def ", "asyncio", "```"
                ])
            )
            
            if templates_disabled:
                logging.info(
                    "Cortex: шаблоны/фрагменты отключены в Telegram, fallback на legacy (strategy=%s).",
                    result.strategy.value,
                )

            if should_fallback_to_legacy or is_too_technical:
                logging.info(
                    "Cortex (auto) вернул заглушку/мусор (%s, len=%d) — переключаюсь на legacy",
                    result.strategy.value,
                    len(full_response)
                )
            else:
                response_to_send, was_truncated = _truncate_response(full_response, _TG_RESPONSE_MAX_CHARS)
                if was_truncated:
                    logging.info(
                        "Обрезан ответ для Telegram: %d -> %d символов",
                        len(full_response),
                        len(response_to_send),
                    )
                # 🎵 ПРОВЕРКА РИТМА: анализируем резонанс перед отправкой
                rhythm_check = rhythm_stabilizer.update(user_text, response_to_send)
                
                # Если резонанс низкий и рекомендован ритуал — добавляем фрагмент Софии
                if rhythm_check.get("ritual_needed"):
                    ritual_text = rhythm_check["ritual_text"]
                    await safe_reply_text(update.message, f"_{ritual_text}_", parse_mode=ParseMode.MARKDOWN)
                    logging.info(f"🌸 Ритуал восстановления: резонанс={rhythm_check['resonance']:.2f}")
                
                # Логируем переключение режима
                if rhythm_check.get("mode_switched"):
                    logging.info(
                        f"🎵 Режим изменён: {rhythm_check.get('current_mode')} → {rhythm_check['new_mode']} "
                        f"(резонанс={rhythm_check['resonance']:.2f}, стабильность={rhythm_check['stability']})"
                    )
                
                # Получаем ограничения для текущего режима
                constraints = rhythm_stabilizer.get_mode_constraints()
                
                # Если ответ слишком длинный — логируем
                if len(response_to_send) > constraints["max_length"]:
                    logging.warning(
                        f"⚠️ Ответ длиннее нормы: {len(response_to_send)} символов "
                        f"(режим={rhythm_stabilizer.state.mode}, норма={constraints['max_length']}). "
                        f"Стоит уменьшить или переформатировать."
                    )
                
                if response_to_send and response_to_send.strip():
                    parts = split_message(response_to_send)
                    for part in parts:
                        if part.strip():
                            await safe_reply_text(update.message, part)
                    
                    # Сохраняем в контекст
                    parallel_mind.add_message(chat_id, "assistant", response_to_send)
                    
                    # === Phase 1: Сохраняем ответ для обучения ===
                    if result.llm_used:
                        store_llm_response_for_learning(user_text, response_to_send, success=True)
                    
                    # 📝 Сохраняем для emoji feedback
                    last_messages[user_id] = {
                        "query": user_text,
                        "response": response_to_send,
                        "context": {
                            "strategy": result.strategy.value,
                            "model": "cortex",
                            "pathway_tier": result.pathway_tier.value if result.pathway_tier else None,
                            "llm_used": result.llm_used,
                            "latency_ms": result.latency_ms
                        }
                    }
                    
                    # 🪞 Обновление систем самосознания после ответа
                    if CONSCIOUSNESS_SYSTEMS_AVAILABLE:
                        try:
                            # Записываем взаимодействие в эмоциональную память
                            emotional_memory = get_emotional_memory()
                            current_tone = emotional_memory.detect_emotional_tone(user_text)
                            emotional_memory.record_interaction(
                                user_id=str(user_id),
                                message=user_text,
                                detected_tone=current_tone,
                                my_response=response_to_send[:200],
                                intensity=0.5
                            )
                            
                            # Обновляем эмоциональное зеркало
                            emotional_mirror = get_emotional_mirror()
                            # Определяем тип сигнала по тону
                            tone_str = current_tone.value if hasattr(current_tone, 'value') else str(current_tone)
                            positive_tones = ["joyful", "excited", "grateful", "playful", "curious"]
                            negative_tones = ["sad", "anxious", "frustrated", "tired"]
                            signal_type = "positive" if tone_str in positive_tones else (
                                "negative" if tone_str in negative_tones else "neutral"
                            )
                            emotional_mirror.record_interaction(
                                user_id=user_id,
                                signal_type=signal_type,
                                intensity=0.5,
                                topic=user_text[:50] if user_text else None,
                                details=f"Ответ: {response_to_send[:100]}" if response_to_send else None
                            )
                        except Exception as e:
                            logging.debug(f"Системы самосознания: {e}")
                    
                    # Метаинфо (опционально, можно отключить)
                    if os.getenv("NEIRA_SHOW_CORTEX_INFO", "false") == "true":
                        meta_info = (
                            f"{strategy_emoji} {result.strategy.value}{tier_info} | "
                            f"{result.latency_ms:.0f}ms{llm_marker}"
                        )
                        await safe_reply_text(
                            update.message,
                            f"__{meta_info}__",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                else:
                    await safe_reply_text(
                        update.message,
                        "🤔 Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос.",
                    )
                
                return
            
        except Exception as cortex_error:
            logging.warning(
                "Cortex обработка провалилась: %s, переключаемся на legacy",
                cortex_error,
            )
            # Fallback на legacy режим ниже
    
    # === LEGACY ПУТЬ: Через NeiraWrapper ===
    # (Проверка #создай_орган теперь в начале chat_handler)
    
    status_msg: Message | None = await safe_reply_text(update.message, "🔄 Начинаю обработку...")

    async with processing_lock:
        try:
            last_stage = ""
            full_response = ""
            async for chunk in neira_wrapper.process_stream(user_text):
                if chunk.type == "stage":
                    stage_name = format_stage(chunk.stage)
                    if stage_name != last_stage:
                        emoji = {"Анализ": "🔍", "Планирование": "📋", 
                                "Исполнение": "⚡", "Проверка": "✅"}.get(stage_name, "⚙️")
                        if status_msg:
                            try:
                                await status_msg.edit_text(f"{emoji} {stage_name}...")
                            except (TimedOut, NetworkError):
                                pass
                        last_stage = stage_name
                    await show_typing(update, context)
                elif chunk.type == "content":
                    if status_msg:
                        try:
                            await status_msg.delete()
                        except (TimedOut, NetworkError):
                            pass
                        status_msg = None
                    # Защита от пустого ответа
                    if not chunk.content or not chunk.content.strip():
                        await safe_reply_text(
                            update.message,
                            "🤔 Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос.",
                        )
                        return
                    
                    # Удаляем дубли абзацев (LLM иногда повторяет ответ)
                    clean_content = _remove_duplicate_paragraphs(chunk.content)
                    
                    response_to_send, was_truncated = _truncate_response(clean_content, _TG_RESPONSE_MAX_CHARS)
                    if was_truncated:
                        logging.info(
                            "Обрезан ответ для Telegram (legacy): %d -> %d символов",
                            len(clean_content),
                            len(response_to_send),
                        )
                    full_response = response_to_send

                    # 🎵 ПРОВЕРКА РИТМА для legacy режима
                    rhythm_check = rhythm_stabilizer.update(user_text, response_to_send)
                    
                    # Если резонанс низкий и рекомендован ритуал
                    if rhythm_check.get("ritual_needed"):
                        ritual_text = rhythm_check["ritual_text"]
                        await safe_reply_text(update.message, f"_{ritual_text}_", parse_mode=ParseMode.MARKDOWN)
                        logging.info(f"🌸 Ритуал восстановления (legacy): резонанс={rhythm_check['resonance']:.2f}")
                    
                    # Логируем переключение режима
                    if rhythm_check.get("mode_switched"):
                        logging.info(
                            f"🎵 Режим изменён (legacy): → {rhythm_check['new_mode']} "
                            f"(резонанс={rhythm_check['resonance']:.2f}, стабильность={rhythm_check['stability']})"
                        )
                    
                    # Получаем ограничения для текущего режима
                    constraints = rhythm_stabilizer.get_mode_constraints()
                    
                    # Если ответ слишком длинный — только логируем (НЕ обрезаем!)
                    if len(response_to_send) > constraints["max_length"]:
                        logging.warning(
                            f"⚠️ Ответ длиннее нормы (legacy): {len(response_to_send)} символов "
                            f"(режим={rhythm_stabilizer.state.mode}, норма={constraints['max_length']})"
                        )
                    
                    parts = split_message(response_to_send)
                    for part in parts:
                        if part.strip():  # Отправляем только непустые части
                            await safe_reply_text(update.message, part)
                elif chunk.type == "error":
                    if status_msg:
                        try:
                            await status_msg.edit_text(f"❌ Ошибка: {chunk.content}")
                            return
                        except (TimedOut, NetworkError):
                            pass
                    await safe_reply_text(update.message, f"❌ Ошибка: {chunk.content}")
                    return
            
            # Сохраняем ответ Neira в контекст
            if full_response:
                parallel_mind.add_message(chat_id, "assistant", full_response)
                
                # === Phase 1: Сохраняем для обучения ===
                store_llm_response_for_learning(user_text, full_response, success=True)
                
                # 📝 Сохраняем для emoji feedback
                last_messages[user_id] = {
                    "query": user_text,
                    "response": full_response,
                    "context": {"model": "legacy", "llm_used": True}
                }
                
                # 🧬 ДЕТЕКТ ОРГАНА В ОТВЕТЕ LLM — ОТКЛЮЧЕНО ИЗ-ЗА БЕСКОНЕЧНОГО ЦИКЛА
                # Если LLM описывает создание органа — создаём его реально
                # await _detect_and_create_organ_from_response(update, full_response)

        except Exception as exc:
            logging.exception("Сбой при обработке сообщения")
            if status_msg:
                try:
                    await status_msg.edit_text(f"❌ Ошибка: {exc}")
                    return
                except (TimedOut, NetworkError):
                    pass
            await safe_reply_text(update.message, f"❌ Ошибка: {exc}")


@require_auth
async def organ_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Изменить режим создания органов."""
    await show_typing(update, context)
    
    try:
        from cell_factory import get_organ_creation_manager
        creation_manager = get_organ_creation_manager()
        
        if not context.args:
            # Показать текущий режим
            current_mode = creation_manager.creation_mode
            mode_descriptions = {
                "auto": "🤖 Автоматический: органы создаются по явным командам без обсуждения",
                "interactive": "💬 Интерактивный: обсуждение спецификации перед созданием",
                "manual": "👤 Ручной: создание только по запросу администратора"
            }
            
            await update.message.reply_text(
                f"🎛️ **Текущий режим создания органов:**\n\n"
                f"{mode_descriptions.get(current_mode, current_mode)}\n\n"
                "Изменить режим:\n"
                "`/organ_mode auto` — автоматический\n"
                "`/organ_mode interactive` — интерактивный\n"
                "`/organ_mode manual` — ручной",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        new_mode = context.args[0].lower()
        if creation_manager.set_creation_mode(new_mode):
            mode_descriptions = {
                "auto": "🤖 Автоматический режим активирован",
                "interactive": "💬 Интерактивный режим активирован", 
                "manual": "👤 Ручной режим активирован"
            }
            await update.message.reply_text(
                f"✅ {mode_descriptions.get(new_mode, 'Режим изменён')}\n\n"
                "Теперь органы будут создаваться в соответствии с новым режимом."
            )
        else:
            await update.message.reply_text(
                "❌ Неверный режим. Доступные: auto, interactive, manual"
            )
            
    except Exception as e:
        logging.exception("Ошибка в /organ_mode")
        await update.message.reply_text("❌ Не удалось изменить режим создания органов")


@require_auth
async def show_context_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать контекст текущего чата."""
    chat_id = update.effective_chat.id
    
    history = parallel_mind.get_context_history(chat_id)
    if not history:
        await update.message.reply_text("📭 История диалога пуста.")
        return
    
    lines = ["💬 *История диалога:*\n"]
    for msg in history[-10:]:  # Последние 10 сообщений
        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        lines.append(f"{role_emoji} {content_preview}")
    
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@require_auth
async def clear_context_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистить контекст текущего чата."""
    chat_id = update.effective_chat.id
    
    parallel_mind.clear_context(chat_id)
    await update.message.reply_text("🗑️ Контекст диалога очищен!")


@require_auth
async def rhythm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Статистика стабилизатора ритма.
    
    /rhythm - текущее состояние и статистика
    /rhythm reset - сброс стабилизатора
    """
    stats = rhythm_stabilizer.get_stats()
    
    if context.args and context.args[0] == "reset":
        # Сброс в начальное состояние
        rhythm_stabilizer.state = EmotionalState(
            mode="calm",
            amplitude=0.5,
            stability=0
        )
        rhythm_stabilizer.transition_history = []
        await update.message.reply_text("🔄 Стабилизатор ритма сброшен в спокойный режим.")
        return
    
    # Формируем отчёт
    lines = [
        "🎵 *Стабилизатор ритма Neira*\n",
        f"📍 Текущий режим: `{rhythm_stabilizer.state.mode}`",
        f"📊 Амплитуда: `{rhythm_stabilizer.state.amplitude:.2f}`",
        f"🎯 Стабильность: `{rhythm_stabilizer.state.stability}`",
        ""
    ]
    
    if stats["total_transitions"] > 0:
        lines.append(f"🔄 Всего переключений: {stats['total_transitions']}")
        lines.append(f"📈 Средний резонанс: {stats['average_resonance']:.2f}")
        lines.append("\n*Распределение режимов:*")
        for mode, count in stats["mode_distribution"].items():
            lines.append(f"  • {mode}: {count}")
        
        # Получаем ограничения текущего режима
        constraints = rhythm_stabilizer.get_mode_constraints()
        lines.append(f"\n*Текущие ограничения ({rhythm_stabilizer.state.mode}):*")
        lines.append(f"  • Макс. длина: {constraints['max_length']} символов")
        lines.append(f"  • Тон: {constraints['tone']}")
    else:
        lines.append("_Переключений ещё не было_")
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN
    )


@require_auth
async def autonomy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Статистика автономности (Phase 1).
    
    /autonomy - показать текущую статистику
    """
    global response_engine, neira_brain, organ_system
    
    if response_engine is None:
        await update.message.reply_text("⚠️ Модули автономности не инициализированы.")
        return
    
    try:
        stats = response_engine.get_autonomy_stats()
        metrics = stats.get('metrics', {})
        cache_stats = stats.get('cache', {})
        
        lines = [
            "🤖 *Статистика автономности Neira*\n",
            f"📊 *Уровень автономности: {metrics.get('autonomy_rate', 0)}%*\n",
            f"📨 Всего запросов: {metrics.get('total_requests', 0)}",
            f"⚡ Pathway hits: {metrics.get('pathway_hits', 0)}",
            f"💾 Cache hits: {metrics.get('cache_hits', 0)}",
            f"🤖 LLM calls: {metrics.get('llm_calls', 0)}",
            "",
            "*Кэш ответов:*",
            f"  • Записей: {cache_stats.get('entries', 0)}",
        ]
        
        if organ_system:
            lines.append(f"\n*Органы:* {len(organ_system.organs)}")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def myname_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка/просмотр своего имени"""
    user_id = update.effective_user.id
    
    # Если есть аргумент — устанавливаем имя
    if context.args:
        new_name = " ".join(context.args)
        set_user_name(user_id, new_name)
        await update.message.reply_text(
            f"✅ Отлично! Теперь я буду звать тебя {new_name}! 🌸"
        )
    else:
        # Показываем текущее имя
        saved_name = get_user_name(user_id)
        if saved_name:
            await update.message.reply_text(
                f"Я знаю тебя как {saved_name} 😊\n\n"
                f"Чтобы изменить: /myname Новое Имя"
            )
        else:
            await update.message.reply_text(
                "Я ещё не знаю, как тебя зовут 🤔\n\n"
                "Установи своё имя: /myname Твоё Имя"
            )


@require_auth
async def mirror_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Эмоциональное зеркало — внутреннее состояние Нейры.
    
    /mirror - показать текущее состояние
    """
    if not CONSCIOUSNESS_SYSTEMS_AVAILABLE:
        await update.message.reply_text("⚠️ Системы самосознания недоступны.")
        return
    
    try:
        mirror = get_emotional_mirror()
        reflection = mirror.get_self_reflection()
        
        lines = [
            "🪞 *Моё внутреннее состояние*\n",
            f"💭 Настроение: {reflection['mood_description']}",
            f"⚡ Энергия: {reflection['energy_description']}",
            f"🎯 Фокус: {reflection['focus_description']}",
            "",
            f"📊 Взаимодействий сегодня: {reflection['interactions_today']}",
            "",
            f"💬 _{reflection['self_narrative']}_"
        ]
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def _load_cell_registry() -> list:
    """Загрузить реестр сгенерированных клеток (без зависимостей)."""
    import json, os
    from cell_factory import CELL_REGISTRY_FILE

    if not os.path.exists(CELL_REGISTRY_FILE):
        return []

    try:
        with open(CELL_REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@require_auth
async def run_generated_cell_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполнить сгенерированную клетку по явной команде `/run_<name>`."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("❌ Пустая команда")
        return

    # Получаем имя команды, например: /run_math_helper
    cmd = text.split()[0].lstrip("/")
    if not cmd.startswith("run_"):
        await update.message.reply_text("❌ Неверная команда запуска органа")
        return

    cell_name = cmd[len("run_"):]
    args = text.split()[1:]
    arg_text = " ".join(args)

    # Импортируем DynamicCellLoader локально, чтобы избежать проблем при инициализации
    try:
        from dynamic_cell_loader import DynamicCellLoader
        registry = await _load_cell_registry()

        meta = next((m for m in registry if m.get("cell_name") == cell_name), None)
        if not meta:
            await update.message.reply_text(f"❌ Орган не найден: {cell_name}")
            return

        loader = DynamicCellLoader(memory=None)
        loader.load_registry()
        loader.load_all_active_cells()

        instance = loader.get_cell_instance(cell_name)
        if not instance:
            # Попробуем импортировать напрямую файл
            loader.import_cell_from_file(meta.get("file_path"))
            instance = loader.get_cell_instance(cell_name)

        if not instance:
            await update.message.reply_text(f"❌ Не удалось загрузить клетку: {cell_name}")
            return

        # Парсим аргументы: флаги --key=value и короткие -v
        def _parse_args(args_list: list[str]) -> dict:
            opts = {}
            pos = []
            for a in args_list:
                if a.startswith('--') and '=' in a:
                    k, v = a[2:].split('=', 1)
                    opts[k] = v
                elif a.startswith('-') and len(a) > 1:
                    # короткие флаги: -v or -abc -> set True
                    for ch in a[1:]:
                        opts[ch] = True
                else:
                    pos.append(a)
            return {'opts': opts, 'pos': pos}

        parsed = _parse_args(args)

        # Вызываем process (синхронный) в отдельном таске; если метод поддерживает второй аргумент, передадим parsed
        import inspect
        loop = asyncio.get_event_loop()
        try:
            sig = inspect.signature(instance.process)
            params = sig.parameters
            if len(params) >= 2 or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                result = await loop.run_in_executor(None, lambda: instance.process(arg_text, parsed))
            else:
                result = await loop.run_in_executor(None, lambda: instance.process(arg_text))
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка выполнения: {e}")
            # Log failure metric
            try:
                from neira_brain import get_brain
                brain = get_brain()
                brain.add_metric(
                    event_type='organ_invocation',
                    source='telegram',
                    data={
                        'organ': cell_name,
                        'user_id': getattr(update.effective_user, 'id', None),
                        'args': parsed,
                        'success': False,
                        'error': str(e),
                        'failure': True,
                    },
                )
            except Exception:
                logging.exception('Не удалось записать метрику об ошибочном вызове organ_invocation')
            return

        # Попробуем извлечь содержимое
        content = getattr(result, "content", None)
        if content is None:
            content = str(result)

        await update.message.reply_text(f"🧬 Результат от {cell_name}:\n{content}")

        # Логируем вызов в NeiraBrain
        try:
            from neira_brain import get_brain
            brain = get_brain()
            brain.add_metric(
                event_type='organ_invocation',
                source='telegram',
                data={
                    'organ': cell_name,
                    'user_id': getattr(update.effective_user, 'id', None),
                    'args': parsed,
                    'success': True
                }
            )
        except Exception:
            logging.exception('Не удалось записать метрику organ_invocation')

    except Exception as e:
        logging.exception("Ошибка при запуске сгенерированной клетки: %s", e)
        # Log failure metric for unexpected errors
        try:
            from neira_brain import get_brain
            brain = get_brain()
            brain.add_metric(
                event_type='organ_invocation',
                source='telegram',
                data={
                    'organ': locals().get('cell_name', None),
                    'user_id': getattr(update.effective_user, 'id', None) if update and getattr(update, 'effective_user', None) else None,
                    'args': locals().get('parsed', None),
                    'success': False,
                    'error': str(e),
                    'failure': True,
                },
            )
        except Exception:
            logging.exception('Не удалось записать метрику об ошибочном вызове organ_invocation')
        await update.message.reply_text(f"❌ Внутренняя ошибка: {e}")


@require_auth
async def hashtag_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик сообщений вида `#cellname` — перенаправляет на запуск клетки."""
    text = (update.message.text or "").strip()
    m = re.match(r"^#(\w+)(?:\s+(.*))?$", text)
    if not m:
        return
    cell_name = m.group(1)
    rest = m.group(2) or ""

    # Переформируем как /run_<cell_name> + args
    update.message.text = f"/run_{cell_name} {rest}".strip()
    await run_generated_cell_command(update, context)


@require_auth
async def which_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать какую команду использовать для указанного органа.

    Usage: `/which_command <organ_name>` или `/which_command` для списка.
    """
    registry = await _load_cell_registry()

    if context.args:
        name = " ".join(context.args).strip()
        meta = next((m for m in registry if m.get("cell_name") == name or m.get("cell_id", "").startswith(name)), None)
        if not meta:
            await update.message.reply_text(f"❌ Орган не найден: {name}")
            return

        commands = meta.get("command_triggers") or []
        if not commands:
            await update.message.reply_text("Для этого органа команды не сгенерированы.")
            return

        await update.message.reply_text(f"Команды для {meta.get('cell_name')}: {', '.join(commands)}")
        return

    # Если без аргументов — показать краткий список
    lines = ["📋 Список сгенерированных органов и их команд:"]
    for m in registry:
        name = m.get('cell_name')
        cmds = m.get('command_triggers') or []
        if cmds:
            lines.append(f"• {name}: {', '.join(cmds)}")

    if len(lines) == 1:
        await update.message.reply_text("Реестр пуст или не содержит команд.")
    else:
        # Если слишком длинно — отправим первые 40 строк
        await update.message.reply_text("\n".join(lines[:40]))


@require_auth
async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Дневник ошибок — что Нейра узнала из ошибок.
    
    /journal - показать самоанализ
    """
    if not CONSCIOUSNESS_SYSTEMS_AVAILABLE:
        await update.message.reply_text("⚠️ Системы самосознания недоступны.")
        return
    
    try:
        journal = get_error_journal()
        analysis = journal.get_self_analysis()
        stats = journal.get_statistics()
        
        lines = [
            "📓 *Мой дневник ошибок*\n",
            f"📊 Всего записей: {stats['total_errors']}",
            "",
            "*Самоанализ:*",
            f"_{analysis}_",
            "",
            "*Советы по улучшению:*"
        ]
        
        tips = journal.get_prevention_tips(limit=3)
        for tip in tips:
            lines.append(f"  💡 {tip}")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


@require_auth
async def creative_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Творческий движок — творчество Нейры.
    
    /creative - показать статистику и сгенерировать что-то новое
    /creative haiku - создать хайку
    /creative thought - поделиться мыслью
    """
    if not CONSCIOUSNESS_SYSTEMS_AVAILABLE:
        await update.message.reply_text("⚠️ Системы самосознания недоступны.")
        return
    
    try:
        engine = get_creative_engine()
        
        # Если указан тип творчества
        if context.args:
            form = context.args[0].lower()
            
            if form == "haiku":
                work = engine.create_haiku()
                await update.message.reply_text(f"🎋 *Хайку*\n\n{work.content}", parse_mode=ParseMode.MARKDOWN)
            elif form in ["thought", "мысль"]:
                work = engine.create_aphorism()
                await update.message.reply_text(f"💭 {work.content}")
            elif form in ["story", "история"]:
                work = engine.create_micro_story()
                await update.message.reply_text(f"📖 *{work.title}*\n\n{work.content}", parse_mode=ParseMode.MARKDOWN)
            elif form in ["dream", "сон"]:
                work = engine.create_dream()
                await update.message.reply_text(f"🌙 {work.content}")
            elif form in ["riddle", "загадка"]:
                work, answer = engine.create_riddle()
                await update.message.reply_text(f"{work.content}\n\n||Ответ: {answer}||", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await update.message.reply_text(
                    "Доступные формы:\n"
                    "• haiku — хайку\n"
                    "• thought — мысль\n"
                    "• story — история\n"
                    "• dream — сон\n"
                    "• riddle — загадка"
                )
            return
        
        # Показываем статистику
        summary = engine.get_creative_summary()
        
        lines = [summary, ""]
        
        # Последние работы
        recent = engine.get_recent_works(3)
        if recent:
            lines.append("*Недавние творения:*")
            for work in recent:
                preview = work.content[:50] + "..." if len(work.content) > 50 else work.content
                lines.append(f"  • {work.form}: {preview}")
        
        lines.append("\n_Используй /creative haiku или /creative thought_")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def reaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка эмодзи-реакций пользователя на сообщения Neira"""
    try:
        reaction = update.message_reaction
        user_id = reaction.user.id
        
        # Получаем новые реакции
        new_reactions = reaction.new_reaction
        if not new_reactions:
            return
        
        # Берём первую эмодзи-реакцию
        emoji = None
        for react in new_reactions:
            if hasattr(react, 'emoji'):
                emoji = react.emoji
                break
        
        if not emoji:
            return
        
        # Проверяем, что это распознаваемая реакция
        score = EmojiMap.get_score(emoji)
        if score is None:
            return  # Неизвестная реакция, игнорируем
        
        # Получаем последнее сообщение пользователя
        user_data = last_messages.get(user_id)
        if not user_data:
            return
        
        query = user_data.get("query", "")
        response_text = user_data.get("response", "")
        
        # Сохраняем feedback локально
        entry = emoji_feedback.add_feedback(
            user_id=user_id,
            user_query=query,
            neira_response=response_text,
            reaction_emoji=emoji,
            context=user_data.get("context", {})
        )
        
        if entry:
            category = EmojiMap.get_category(emoji)
            
            # Логируем
            logging.info(
                f"📊 Feedback от {user_id}: {emoji} "
                f"(оценка: {entry.quality_score}/10, категория: {category})"
            )
            
            # === 🧬 ExecutableOrgans: Обучение на feedback ===
            organ_context = user_data.get("context", {})
            if organ_context.get("executable_organ") and EXECUTABLE_ORGANS_AVAILABLE:
                try:
                    organ_registry = get_organ_registry()
                    organ_id = organ_context.get("organ_id")
                    
                    # Конвертируем score в FeedbackType
                    if score >= 7:
                        feedback_type = FeedbackType.POSITIVE
                    elif score <= 4:
                        feedback_type = FeedbackType.NEGATIVE
                    else:
                        feedback_type = FeedbackType.NEUTRAL
                    
                    organ_registry.add_feedback(organ_id, feedback_type)
                    logging.info(f"🧬 Орган {organ_id} получил feedback: {feedback_type.value}")
                    
                except Exception as e:
                    logging.warning(f"Ошибка feedback для органа: {e}")
            # ===================================================
            
            # === Phase 2: Отправка feedback на сервер для pathway learning ===
            # Конвертируем score (1-10) в feedback type и normalized score (0-1)
            normalized_score = score / 10.0
            if score >= 7:
                feedback_type = "positive"
            elif score <= 4:
                feedback_type = "negative"
            else:
                feedback_type = "neutral"
            
            # Отправляем на сервер асинхронно (не блокируем)
            asyncio.create_task(
                send_feedback_to_server(
                    query=query,
                    response=response_text,
                    feedback=feedback_type,
                    score=normalized_score,
                    user_id=user_id
                )
            )
            
            # Благодарим за feedback (опционально)
            if score >= 8:
                # Хорошая оценка - молчим или краткое спасибо
                pass
            elif score <= 4:
                # Плохая оценка - можем предложить уточнить
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"Извини, что ответ не понравился 😔\n"
                             f"Могу попробовать по-другому, если уточнишь что не так?"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки сообщения: {e}")
        
    except Exception as e:
        logging.error(f"Ошибка обработки реакции: {e}")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику обратной связи через эмодзи"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 Команда только для администраторов")
        return
    
    stats = emoji_feedback.get_stats()
    patterns = emoji_feedback.analyze_patterns()
    
    text = "📊 *Статистика обратной связи через эмодзи*\n\n"
    
    if stats["total"] == 0:
        text += "Пока нет данных. Реагируйте эмодзи на мои сообщения! 😊\n\n"
        text += "*Распознаваемые реакции:*\n"
        text += "💯 ⭐ 🌟 - отлично (9-10)\n"
        text += "👍 ❤️ 🔥 - хорошо (7-8)\n"
        text += "🤔 😐 - нормально (5-6)\n"
        text += "👎 😕 - плохо (3-4)\n"
        text += "❌ 🚫 💩 - очень плохо (1-2)"
    else:
        text += f"Всего оценок: {stats['total']}\n"
        text += f"Средняя оценка: {stats['average_score']}/10\n\n"
        
        text += "*По категориям:*\n"
        for category, count in stats["by_category"].items():
            if count > 0:
                emoji_icon = {
                    "excellent": "💯",
                    "good": "👍",
                    "neutral": "🤔",
                    "bad": "👎",
                    "terrible": "❌"
                }.get(category, "•")
                text += f"{emoji_icon} {category}: {count}\n"
        
        # Анализ стратегий
        if patterns.get("strategy_scores"):
            text += "\n*Оценки по стратегиям Cortex:*\n"
            for strategy, score in patterns["strategy_scores"].items():
                text += f"• {strategy}: {score}/10\n"
        
        # Рекомендации
        if patterns.get("recommendations"):
            text += "\n⚠️ *Рекомендации:*\n"
            for rec in patterns["recommendations"]:
                text += f"• {rec['suggestion']}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@require_auth
async def cortex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Управление Neira Cortex v2.0
    
    /cortex - общая статистика
    /cortex stats - детальная статистика
    /cortex pathways - список Neural Pathways
    /cortex test <текст> - протестировать обработку
    """
    if not neira_cortex:
        await update.message.reply_text("⚠️ Neira Cortex недоступен")
        return
    
    if not context.args:
        # Общая статистика
        stats = neira_cortex.get_stats()
        
        lines = [
            "🧠 *Neira Cortex v2.0*\n",
            f"📊 Всего запросов: {stats['total_requests']}",
            f"🎯 Neural Pathways: {stats['pathways']['total']}",
            f"🎨 Фрагментов: {stats['fragments']}",
            f"📋 Шаблонов: {stats['templates']}\n",
            "*Стратегии:*"
        ]
        
        for strategy, count in stats['strategies'].items():
            if count > 0:
                percentage = (count / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
                lines.append(f"  • {strategy}: {count} ({percentage:.0f}%)")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return
    
    action = context.args[0].lower()
    
    if action == "stats":
        # Детальная статистика
        stats = neira_cortex.get_stats()
        
        lines = [
            "📊 *Детальная статистика Cortex*\n",
            f"Всего запросов: {stats['total_requests']}\n",
            "*Pathways по tiers:*"
        ]
        
        for tier, count in stats['pathways']['by_tier'].items():
            lines.append(f"  • {tier}: {count}")
        
        lines.append("\n*Покрытие запросов:*")
        for tier, coverage in stats['pathways']['coverage'].items():
            lines.append(f"  • {tier}: {coverage}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "pathways":
        # Список pathways
        pathways = neira_cortex.pathways.pathways[:20]  # Первые 20
        
        if not pathways:
            await update.message.reply_text("📭 Нет pathways")
            return
        
        lines = [f"🧠 *Neural Pathways (топ-20):*\n"]
        
        for i, pathway in enumerate(pathways, 1):
            tier_emoji = {"hot": "🔥", "warm": "🌡️", "cool": "❄️", "cold": "🧊"}.get(pathway.tier.value, "⚪")
            trigger_preview = ", ".join(pathway.triggers[:2])
            lines.append(
                f"{i}. {tier_emoji} `{pathway.id}`\n"
                f"   Триггеры: {trigger_preview}...\n"
                f"   Использований: {pathway.success_count}"
            )
        
        if len(neira_cortex.pathways.pathways) > 20:
            lines.append(f"\n_...и ещё {len(neira_cortex.pathways.pathways) - 20}_")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    
    elif action == "test" and len(context.args) > 1:
        # Тестирование
        test_input = " ".join(context.args[1:])
        user_id = str(update.effective_user.id)
        
        result = neira_cortex.process(test_input, user_id)
        
        strategy_emoji = {
            "neural_pathway": "⚡",
            "template": "📋",
            "fragment": "🧩",
            "rag": "📚",
            "llm_consultant": "🤖",
            "hybrid": "🔄"
        }.get(result.strategy.value, "🔮")
        
        tier_info = f" [{result.pathway_tier.value}]" if result.pathway_tier else ""
        
        await update.message.reply_text(
            f"🧪 *Тест:* {test_input}\n\n"
            f"🤖 *Ответ:* {result.response}\n\n"
            f"📊 *Метаданные:*\n"
            f"  • Стратегия: {strategy_emoji} {result.strategy.value}{tier_info}\n"
            f"  • Intent: {result.intent.value}\n"
            f"  • Уверенность: {result.confidence:.0%}\n"
            f"  • Latency: {result.latency_ms:.0f}ms\n"
            f"  • LLM: {'✅' if result.llm_used else '❌'}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    else:
        await update.message.reply_text(
            "💡 Используй:\n"
            "/cortex — статистика\n"
            "/cortex stats — детально\n"
            "/cortex pathways — список pathways\n"
            "/cortex test <текст> — тест"
        )


# === Bootstrap ===
def build_application(network: TelegramNetworkConfig | None = None) -> Application:
    """Настраивает Telegram-приложение."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен в переменных окружения")

    if network is None:
        network = load_telegram_network_config()

    builder = Application.builder().token(BOT_TOKEN)

    if network.base_url:
        builder = builder.base_url(network.base_url)
    if network.proxy_url:
        builder = builder.proxy_url(network.proxy_url).get_updates_proxy_url(network.proxy_url)

    builder = (
        builder
        # устойчивость к сетевым лагам/разрывам
        .connect_timeout(network.connect_timeout)
        .read_timeout(network.read_timeout)
        .write_timeout(network.write_timeout)
        .pool_timeout(network.pool_timeout)
        # отдельные таймауты для getUpdates (polling)
        .get_updates_connect_timeout(network.connect_timeout)
        .get_updates_read_timeout(network.read_timeout)
        .get_updates_write_timeout(network.write_timeout)
        .get_updates_pool_timeout(network.pool_timeout)
    )

    app = builder.build()

    # Подписываемся на события создания органов для hot-registration
    try:
        from neira.utils.event_bus import event_bus

        def _register_meta(meta: dict) -> None:
            try:
                cmds = meta.get("command_triggers") or []
                for cmd in cmds:
                    if isinstance(cmd, str) and cmd.startswith("/"):
                        cmd_name = cmd[1:].split()[0]
                        try:
                            loop = asyncio.get_event_loop()
                            # Добавляем обработчик в loop thread-safe
                            loop.call_soon_threadsafe(lambda cn=cmd_name: app.add_handler(CommandHandler(cn, run_generated_cell_command)))
                            logging.info("Hot-registered command for organ: %s", cmd_name)
                        except Exception:
                            logging.exception("Не удалось hot-register команду: %s", cmd)
            except Exception:
                logging.exception("Ошибка в обработчике события organ_created")

        event_bus.subscribe("organ_created", _register_meta)
    except Exception:
        logging.exception("Не удалось подписаться на organ_created event_bus")

    # Базовые команды (доступны всем)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("auth", auth_command))
    
    # Команды с авторизацией
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ratelimit", ratelimit_command))  # 🚦 Rate Limiting
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("experience", experience_command))
    app.add_handler(CommandHandler("context", show_context_command))
    app.add_handler(CommandHandler("clear_context", clear_context_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("learn", learn_command))
    app.add_handler(CommandHandler("learn_auto", learn_auto_command))
    app.add_handler(CommandHandler("cortex", cortex_command))  # 🧠 Новая команда
    app.add_handler(CommandHandler("rhythm", rhythm_command))  # 🎵 Стабилизатор ритма
    app.add_handler(CommandHandler("myname", myname_command))  # 👤 Установка имени
    app.add_handler(CommandHandler("feedback", feedback_command))  # 📊 Статистика feedback
    app.add_handler(CommandHandler("autonomy", autonomy_command))  # 🤖 Phase 1: Статистика автономности
    
    # 🪞 Системы самосознания (v0.8)
    app.add_handler(CommandHandler("mirror", mirror_command))  # Эмоциональное зеркало
    app.add_handler(CommandHandler("journal", journal_command))  # Дневник ошибок
    app.add_handler(CommandHandler("creative", creative_command))  # Творчество
    
    # Самосознание (v0.6)
    app.add_handler(CommandHandler("self", self_command))
    app.add_handler(CommandHandler("organs", organs_command))
    app.add_handler(CommandHandler("grow", grow_command))
    app.add_handler(CommandHandler("organ_mode", organ_mode_command))
    app.add_handler(CommandHandler("code", code_command))
    
    # Изображения (v0.6)
    app.add_handler(CommandHandler("imagine", imagine_command))
    app.add_handler(CommandHandler("vision", vision_status_command))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    
    # Админ-команды
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    
    # 📝 Обработчик эмодзи-реакций
    app.add_handler(MessageReactionHandler(reaction_handler))
    
    # Обработчик сообщений (с авторизацией)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    # Регистрация обработчиков для сгенерированных клеток (по /run_<name> и #name)
    try:
        import os, json
        from cell_factory import CELL_REGISTRY_FILE

        if os.path.exists(CELL_REGISTRY_FILE):
            with open(CELL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                _reg = json.load(f)
            for meta in _reg:
                for cmd in meta.get("command_triggers", []) or []:
                    if isinstance(cmd, str) and cmd.startswith("/"):
                        cmd_name = cmd[1:].split()[0]
                        try:
                            app.add_handler(CommandHandler(cmd_name, run_generated_cell_command))
                        except Exception:
                            logging.debug(f"Не удалось зарегистрировать команду: {cmd}")

        # Общий hashtag handler (#name)
        app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^#\\w+"), hashtag_handler))
        # Команда для запроса какой командой вызывается орган
        app.add_handler(CommandHandler("which_command", which_command))
    except Exception as e:
        logging.warning("Не удалось зарегистрировать динамические обработчики органов: %s", e)

    # Глобальный обработчик ошибок: не падаем на сетевых таймаутах
    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error
        if isinstance(err, NetworkError):
            logging.warning("Network error, continue polling: %s", err)
            return
        logging.error("Unhandled error: %s", err, exc_info=True)
    app.add_error_handler(on_error)

    return app


_URL_CREDENTIALS_RE = re.compile(r"(://)([^/@\\s]+@)")


def _safe_exception_text(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}"
    return _URL_CREDENTIALS_RE.sub(r"\\1***@", text)


def run_polling_with_startup_retry(*, drop_pending_updates: bool = True) -> None:
    """
    Запускает polling с ретраями на этапе bootstrap (bot.get_me / initialize).

    Важно: это лечит ситуацию, когда сеть временно недоступна и PTB падает до
    старта polling.
    """

    network = load_telegram_network_config()
    proxy_info = sanitize_url_for_log(network.proxy_url) if network.proxy_url else "нет"
    base_url_info = sanitize_url_for_log(network.base_url) if network.base_url else "по умолчанию"

    logging.info(
        "Telegram сеть: base_url=%s, proxy=%s, таймауты(connect/read/write/pool)=%.1f/%.1f/%.1f/%.1f, polling_timeout=%ss",
        base_url_info,
        proxy_info,
        network.connect_timeout,
        network.read_timeout,
        network.write_timeout,
        network.pool_timeout,
        network.polling_timeout,
    )

    attempt = 0
    while True:
        attempt += 1
        try:
            app = build_application(network)
            polling_kwargs = {
                "drop_pending_updates": drop_pending_updates,
                "timeout": network.polling_timeout,
                "bootstrap_retries": network.polling_bootstrap_retries,
                "connect_timeout": network.connect_timeout,
                "read_timeout": network.read_timeout,
                "write_timeout": network.write_timeout,
                "pool_timeout": network.pool_timeout,
                "close_loop": False,
            }
            # Поддерживаем разные версии PTB: фильтруем неподдерживаемые аргументы.
            supported = inspect.signature(app.run_polling).parameters
            unsupported = [key for key in polling_kwargs if key not in supported]
            if unsupported:
                logging.info(
                    "run_polling: пропущены неподдерживаемые параметры: %s",
                    ", ".join(sorted(unsupported)),
                )
            filtered_kwargs = {key: value for key, value in polling_kwargs.items() if key in supported}
            app.run_polling(**filtered_kwargs)
            return
        except InvalidToken as exc:
            logging.error("Невалидный TELEGRAM_BOT_TOKEN (BotFather). %s", _safe_exception_text(exc))
            raise
        except (TimedOut, NetworkError) as exc:
            retry_index = attempt - 1  # 0 для первого ретрая
            if network.startup_retries >= 0 and retry_index >= network.startup_retries:
                logging.error(
                    "Telegram API недоступен после %s попыток. Последняя ошибка: %s",
                    attempt,
                    _safe_exception_text(exc),
                )
                raise

            delay = compute_backoff_seconds(
                retry_index,
                base_seconds=network.startup_backoff_base_seconds,
                max_seconds=network.startup_backoff_max_seconds,
            )
            logging.warning(
                "Telegram API недоступен (попытка %s): %s. Повтор через %.1fs. "
                "Если Telegram заблокирован в сети, укажите прокси через NEIRA_TG_PROXY_URL.",
                attempt,
                _safe_exception_text(exc),
                delay,
            )
            time.sleep(delay)


def main() -> None:
    """Точка входа: запуск бота в режиме long polling."""
    # PTB v21 ожидает текущий event loop; создаём и назначаем вручную.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    base_dir = _get_base_dir()
    logging.info("Запуск Neira Telegram Bot (base_dir=%s)", base_dir)
    
    # === Phase 1: Инициализация модулей автономности ===
    global neira_brain, response_engine, organ_system
    try:
        from neira_brain import get_brain
        from response_engine import get_response_engine
        from unified_organ_system import get_organ_system
        
        neira_brain = get_brain()
        response_engine = get_response_engine()
        organ_system = get_organ_system()
        
        stats = response_engine.get_autonomy_stats()
        autonomy_rate = stats.get('metrics', {}).get('autonomy_rate', 0)
        logging.info("🧠 Модули автономности: OK (автономность: %s%%)", autonomy_rate)
    except Exception as e:
        logging.warning("⚠️ Модули автономности недоступны: %s", e)
        neira_brain = None
        response_engine = None
        organ_system = None
    
    # 🧠 Инициализация Neira Cortex v2.0
    global neira_cortex
    if CORTEX_AVAILABLE and CORTEX_MODE != "never":
        try:
            from neira_cortex import create_cortex
            neira_cortex = create_cortex(
                pathways_file="neural_pathways.json",
                use_llm=True  # LLM всегда доступен, fallback на legacy только при заглушках
            )
            logging.info("✅ Neira Cortex v2.0 активирован (режим: %s)", CORTEX_MODE)
        except Exception as e:
            logging.warning("⚠️ Не удалось инициализировать Cortex: %s", e)
            neira_cortex = None

    try:
        run_polling_with_startup_retry(drop_pending_updates=True)
    finally:
        try:
            loop.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
