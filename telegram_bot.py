"""Телеграм-бот для Neira v0.7: общение, обучение, самосознание, картинки и защита."""

import asyncio
import logging
import os
import re
import time
import hashlib
import secrets
import base64
import io
from pathlib import Path
from typing import Iterable, List, Set, Optional
from functools import wraps
from datetime import datetime

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
from telegram.error import TimedOut, NetworkError
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
from memory_system import EMBED_MODEL
from autonomous_learning import AutonomousLearningSystem
from emoji_feedback import EmojiFeedbackSystem, EmojiMap

# 🧠 Neira Cortex v2.0 - Автономная когнитивная система
try:
    from neira_cortex import NeiraCortex, ProcessingResult, ResponseStrategy
    CORTEX_AVAILABLE = True
except ImportError:
    CORTEX_AVAILABLE = False
    print("⚠️ Neira Cortex недоступен - используем legacy режим")


# === Инициализация ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

load_dotenv()

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
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "NEIRA_ADMIN_PASSWORD"):
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
                "🔐 Требуется доступ.\n\n"
                f"Твой user_id: `{user_id}`\n\n"
                "Если ты администратор: `/auth 0 <пароль>`\n"
                "Если нет — попроси администратора добавить тебя: `/admin add <user_id|@username>`",
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

    placeholder_markers = (
        "не нашла подходящий фрагмент ответа",
        "дай мне секунду подумать",
        "интересный вопрос! дай подумать",
        "дай подумать над этим",
        "понял задачу, работаю над этим",
        "сейчас напишу код для тебя",
        "расскажи подробнее",
        "не совсем поняла",
    )

    return any(marker in normalized for marker in placeholder_markers)


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
    except:
        pass
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
    except:
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
            "*🔐 Авторизация:*\n"
            "/auth <пароль> — авторизовать пользователя\n"
            "/admin users — список пользователей\n"
            "/admin add <@username|id> — добавить\n"
            "/admin remove <id> — удалить\n"
            "/admin mode <open|whitelist|admin\\_only>\n"
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
            "/learn <тема> — из интернета\n"
            "/learn\\_auto start/stop — автономное\n"
            "/learn\\_auto stats — статистика\n"
            "/learn\\_auto quarantine — карантин\n"
            "/learn\\_auto approve/reject <id>\n\n"
            "*🧬 Самосознание:*\n"
            "/self — самоанализ\n"
            "/organs — статус органов\n"
            "/grow — создание органов\n"
            "/code list/read — управление кодом\n\n"
            "*💡 Хештеги:*\n"
            "#создай\\_орган <описание>\n"
            "#научись <тема>\n"
        )
    
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


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает обучение по теме."""
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await update.message.reply_text("📖 Укажите тему: /learn <тема>")
        return

    await show_typing(update, context)
    async with processing_lock:
        try:
            result = neira_wrapper.neira.cmd_learn(topic)
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


_AUTH_MAX_ATTEMPTS = max(1, _get_int_env("NEIRA_TG_AUTH_MAX_ATTEMPTS", 5))
_AUTH_WINDOW_SECONDS = max(10, _get_int_env("NEIRA_TG_AUTH_WINDOW_SECONDS", 300))
_AUTH_BLOCK_SECONDS = max(10, _get_int_env("NEIRA_TG_AUTH_BLOCK_SECONDS", 900))

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
        description = neira_wrapper.get_self_description()
        # Отправляем без Markdown чтобы избежать ошибок парсинга
        await update.message.reply_text(f"🧠 Кто я такая?\n\n{description}")
    except Exception as e:
        logging.exception("Ошибка в /self")
        await update.message.reply_text("❌ Не удалось получить описание")


async def organs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать органы Нейры."""
    await show_typing(update, context)
    
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
        
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logging.exception("Ошибка в /organs")
        await update.message.reply_text("❌ Не удалось получить список органов")


async def grow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать возможности роста."""
    await show_typing(update, context)
    
    try:
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
    """Фоновое создание органа с проверкой безопасности."""
    try:
        from experience import ExperienceSystem
        
        user_id = update.effective_user.id
        exp_system = ExperienceSystem()
        factory = CellFactory(experience=exp_system)
        
        await update.message.reply_text(
            "🧬 Начинаю создавать новый орган...\n"
            "🔍 Проверка безопасности будет выполнена автоматически."
        )
        
        # Создаем орган с проверкой безопасности
        result = factory.create_cell(
            pattern=organ_description,
            tasks=[{"description": organ_description, "status": "planned"}],
            author_id=user_id
        )
        
        if result.get("success"):
            # ✅ БЕЗОПАСНЫЙ ОРГАН
            cell = result["cell"]
            await update.message.reply_text(
                f"✅ **Орган создан успешно!**\n\n"
                f"📝 Название: {cell.cell_name}\n"
                f"📄 Файл: {cell.file_path}\n"
                f"🎯 Назначение: {cell.description}\n\n"
                f"💡 Я научилась создавать код для себя!",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif result.get("quarantined"):
            # 🔍 В КАРАНТИНЕ
            threat = result["threat_level"]
            organ_id = result.get("organ_id")
            
            if threat == "dangerous":
                msg = (
                    f"⚠️ **Орган требует одобрения**\n\n"
                    f"Орган содержит потенциально опасные операции.\n"
                    f"ID: `{organ_id}`\n\n"
                    f"Администратор может одобрить:\n"
                    f"`/organs approve {organ_id}`"
                )
            else:
                msg = (
                    f"🔍 **Орган в 24-часовом карантине**\n\n"
                    f"Орган будет автоматически активирован через 24ч.\n"
                    f"ID: `{organ_id}`"
                )
            
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        
        else:
            # ❌ ЗАБЛОКИРОВАН
            error = result.get("error", "Орган содержит опасный код")
            await update.message.reply_text(f"❌ {error}")
    
    except Exception as e:
        logging.error(f"Ошибка создания органа: {e}")
        await update.message.reply_text(f"❌ Ошибка при создании органа")


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
        await update.message.reply_text(f"❓ Неизвестная команда: {action}")


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

            should_fallback_to_legacy = (
                CORTEX_MODE == "auto"
                and not result.llm_used
                and is_cortex_placeholder_response(full_response)
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
            
            if should_fallback_to_legacy or is_too_technical:
                logging.info(
                    "Cortex (auto) вернул заглушку/мусор (%s, len=%d) — переключаюсь на legacy",
                    result.strategy.value,
                    len(full_response)
                )
            else:
                # 🎵 ПРОВЕРКА РИТМА: анализируем резонанс перед отправкой
                rhythm_check = rhythm_stabilizer.update(user_text, full_response)
                
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
                
                # Если ответ слишком длинный — только логируем (НЕ обрезаем!)
                # Нейра должна САМА говорить кратко
                if len(full_response) > constraints["max_length"]:
                    logging.warning(
                        f"⚠️ Ответ длиннее нормы: {len(full_response)} символов "
                        f"(режим={rhythm_stabilizer.state.mode}, норма={constraints['max_length']}). "
                        f"Нейра должна сама говорить короче!"
                    )
                
                if full_response and full_response.strip():
                    parts = split_message(full_response)
                    for part in parts:
                        if part.strip():
                            await safe_reply_text(update.message, part)
                    
                    # Сохраняем в контекст
                    parallel_mind.add_message(chat_id, "assistant", full_response)
                    
                    # 📝 Сохраняем для emoji feedback
                    last_messages[user_id] = {
                        "query": user_text,
                        "response": full_response,
                        "context": {
                            "strategy": result.strategy.value,
                            "model": "cortex",
                            "pathway_tier": result.pathway_tier.value if result.pathway_tier else None,
                            "llm_used": result.llm_used,
                            "latency_ms": result.latency_ms
                        }
                    }
                    
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
    
    # 🆕 ДЕТЕКТ ТЕГОВ ДЛЯ СОЗДАНИЯ ОРГАНОВ
    organ_tags = ["#создай_орган", "#grow_organ", "#create_organ", "#новый_орган"]
    should_create_organ = any(tag in user_text.lower() for tag in organ_tags)
    
    if should_create_organ:
        # Убираем теги из текста для обработки
        clean_text = user_text
        for tag in organ_tags:
            clean_text = clean_text.replace(tag, "").replace(tag.upper(), "")
        clean_text = clean_text.strip()
        
        # Запускаем создание органа в фоне
        asyncio.create_task(create_organ_background(update, clean_text))
        
        # Продолжаем обычный диалог
        user_text = clean_text if clean_text else "Создай для меня новый орган"
    
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
                    full_response = chunk.content
                    
                    # Защита от пустого ответа
                    if not chunk.content or not chunk.content.strip():
                        await safe_reply_text(
                            update.message,
                            "🤔 Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос.",
                        )
                        return
                    
                    # 🎵 ПРОВЕРКА РИТМА для legacy режима
                    rhythm_check = rhythm_stabilizer.update(user_text, chunk.content)
                    
                    response_to_send = chunk.content
                    
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
async def context_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
        # Сохраняем feedback
        entry = emoji_feedback.add_feedback(
            user_id=user_id,
            user_query=user_data.get("query", ""),
            neira_response=user_data.get("response", ""),
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
def build_application() -> Application:
    """Настраивает Telegram-приложение."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен в переменных окружения")
    
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        # устойчивость к сетевым лагам/разрывам
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    # Базовые команды (доступны всем)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("auth", auth_command))
    
    # Команды с авторизацией
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("experience", experience_command))
    app.add_handler(CommandHandler("context", context_command))
    app.add_handler(CommandHandler("clear_context", clear_context_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("learn", learn_command))
    app.add_handler(CommandHandler("learn_auto", learn_auto_command))
    app.add_handler(CommandHandler("cortex", cortex_command))  # 🧠 Новая команда
    app.add_handler(CommandHandler("rhythm", rhythm_command))  # 🎵 Стабилизатор ритма
    app.add_handler(CommandHandler("myname", myname_command))  # 👤 Установка имени
    app.add_handler(CommandHandler("feedback", feedback_command))  # 📊 Статистика feedback
    
    # Самосознание (v0.6)
    app.add_handler(CommandHandler("self", self_command))
    app.add_handler(CommandHandler("organs", organs_command))
    app.add_handler(CommandHandler("grow", grow_command))
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

    # Глобальный обработчик ошибок: не падаем на сетевых таймаутах
    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error
        if isinstance(err, NetworkError):
            logging.warning("Network error, continue polling: %s", err)
            return
        logging.error("Unhandled error: %s", err, exc_info=True)
    app.add_error_handler(on_error)

    return app


def main() -> None:
    """Точка входа: запуск бота в режиме long polling."""
    # PTB v21 ожидает текущий event loop; создаём и назначаем вручную.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    base_dir = Path(__file__).resolve().parent
    logging.info("Запуск Neira Telegram Bot (base_dir=%s)", base_dir)
    
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

    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
