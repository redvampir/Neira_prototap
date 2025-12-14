"""Телеграм-бот для Neira v0.7: общение, обучение, самосознание, картинки и защита."""

import asyncio
import logging
import os
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Локальные импорты
from backend.neira_wrapper import NeiraWrapper
from cell_factory import CellFactory
from parallel_thinking import parallel_mind
from enhanced_auth import auth_system
from memory_system import EMBED_MODEL
from autonomous_learning import AutonomousLearningSystem

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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "Не задан TELEGRAM_BOT_TOKEN. Укажите его в переменных окружения "
        "или в файле .env (см. .env.example)."
    )

# === ЗАЩИТА: Администратор ===
# Хеш пароля администратора (из переменной окружения или по умолчанию)
# ВАЖНО: Измените NEIRA_ADMIN_PASSWORD в .env!
_ADMIN_PASSWORD = os.getenv("NEIRA_ADMIN_PASSWORD", "change_me_please")
_ADMIN_HASH = hashlib.sha256(_ADMIN_PASSWORD.encode()).hexdigest()
_ADMIN_ID: Optional[int] = None  # Будет установлен при первой авторизации

# Авторизованные пользователи (Telegram user_id)
AUTHORIZED_USERS: Set[int] = set()

# Режим доступа: "open" (все), "whitelist" (только авторизованные), "admin_only"
ACCESS_MODE = os.getenv("NEIRA_TG_ACCESS", "whitelist")

# ID каналов/групп где бот отвечает без авторизации (через запятую)
# Например: NEIRA_TG_CHANNELS=-1001234567890,-1009876543210
ALLOWED_CHANNELS: Set[int] = set()
_channels_env = os.getenv("NEIRA_TG_CHANNELS", "")
if _channels_env:
    for ch in _channels_env.split(","):
        try:
            ALLOWED_CHANNELS.add(int(ch.strip()))
        except ValueError:
            pass

# Отвечать только на упоминания бота в группах/каналах?
MENTION_ONLY = os.getenv("NEIRA_TG_MENTION_ONLY", "true").lower() == "true"

neira_wrapper = NeiraWrapper(verbose=False)
processing_lock = asyncio.Lock()

# === Система автономного обучения ===
autonomous_learning_system: Optional[AutonomousLearningSystem] = None

# === 🧠 Neira Cortex v2.0 ===
neira_cortex: Optional['NeiraCortex'] = None
CORTEX_MODE = os.getenv("NEIRA_CORTEX_MODE", "auto")  # auto, always, never


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
        
        if ACCESS_MODE == "admin_only" and user_id != _ADMIN_ID:
            if chat_type == "private":
                await update.message.reply_text("⛔ Доступ только для администратора.")
            return
        
        if user_id in AUTHORIZED_USERS or user_id == _ADMIN_ID:
            return await func(update, context, *args, **kwargs)
        
        if chat_type == "private":
            await update.message.reply_text(
                "🔐 Требуется авторизация.\n"
                "Используй /auth <логин> <пароль>"
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


async def send_chunks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chunks: Iterable[str],
) -> None:
    """Отправляет список сообщений, соблюдая лимиты Telegram."""
    chat_id = update.effective_chat.id
    for part in chunks:
        await context.bot.send_message(chat_id=chat_id, text=part)


async def show_typing(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Отправляет действие 'печатает' для UX."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )


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
    
    is_authorized = user_id in AUTHORIZED_USERS or user_id == _ADMIN_ID or ACCESS_MODE == "open"
    
    if is_authorized:
        text = (
            f"Привет, {user_name}! 👋 Я Neira v1.0 в Telegram.\n\n"
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
    
    text = (
        "📚 *Команды Neira v0.7*\n\n"
        "*Общение:*\n"
        "Просто напиши сообщение — Neira ответит\n\n"
        "*Самосознание:*\n"
        "/self — кто я такая?\n"
        "/organs — список моих органов\n"
        "/grow — как мне расти?\n\n"
        "*💾 Память (расширенное управление):*\n"
        "📖 /memory — последние записи\n"
        "📊 /memory stats — статистика\n"
        "🔍 /memory search/semantic <текст>\n"
        "🗑️ /memory delete last/text/old\n"
        "🧹 /memory dedupe — дубликаты\n"
        "💾 /memory backup/restore\n"
        "📌 /memory pin/pinned — закрепить\n"
        "🔧 /memory filter confidence/source/recent\n"
        "📄 /memory export txt\n"
        "/experience — личность\n"
        "/clear — полная очистка\n\n"
        "*🧠 Контекст диалога:*\n"
        "/context — история разговора\n"
        "/clear\\_context — очистить контекст\n\n"
        "*Обучение:*\n"
        "/learn <тема> — из интернета\n\n"
        "*Изображения:*\n"
        "📷 Отправь фото — анализ\n"
        "/imagine <описание>\n"
        "/vision — статус\n\n"
        "*Код:*\n"
        "/code list/read\n\n"
        "*🧬 Самообучение:*\n"
        "#создай\\_орган <описание>\n\n"
        "*🎓 Автономное обучение (v1.0):*\n"
        "/learn\\_auto start — запустить фоновое обучение\n"
        "/learn\\_auto stop — остановить\n"
        "/learn\\_auto stats — статистика\n"
        "/learn\\_auto quarantine — карантин знаний\n"
        "/learn\\_auto approve/reject <id> — проверка\n"
    )
    
    if is_admin(user_id):
        text += (
            "\n*👑 Админ-команды:*\n"
            "/admin users — список авторизованных\n"
            "/admin add <identifier> — добавить (@username или user\\_id)\n"
            "/admin remove <user\\_id> — удалить пользователя\n"
            "/admin stats — статистика параллельного мышления\n"
            "/admin mode <open|whitelist|admin\\_only> — режим доступа\n"
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
async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Авторизация пользователя."""
    global _ADMIN_ID
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("🔐 Использование: /auth 0 <пароль>")
        return
    
    login = context.args[0]
    password = context.args[1]
    user_id = update.effective_user.id
    
    # Проверяем логин "0" и пароль из .env
    if login == "0":
        attempt_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if secrets.compare_digest(attempt_hash, _ADMIN_HASH):
            _ADMIN_ID = user_id
            AUTHORIZED_USERS.add(user_id)
            await update.message.reply_text(
                "👑 Добро пожаловать, Администратор!\n"
                "Ты получил полный доступ к Нейре.\n\n"
                "Используй /admin для управления."
            )
            # Удаляем сообщение с паролем для безопасности
            try:
                await update.message.delete()
            except:
                pass
            logging.info(f"Admin authorized: user_id={user_id}")
        else:
            await update.message.reply_text("❌ Неверный пароль.")
            logging.warning(f"Failed auth attempt from user_id={user_id}")
    else:
        await update.message.reply_text("❌ Неверный логин.")
        logging.warning(f"Failed auth attempt with wrong login: {login}")


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
            filename = context.args[1]
            result = neira_wrapper.neira.cmd_code("read", filename)
            for chunk in split_message(result, limit=4000):
                await update.message.reply_text(f"```\n{chunk}\n```", parse_mode=ParseMode.MARKDOWN)
        
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
            f"Авторизовано: {len(AUTHORIZED_USERS)} пользователей\n"
            f"Каналов/групп: {len(ALLOWED_CHANNELS)}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    action = context.args[0].lower()
    
    if action == "users":
        # Показываем обе системы авторизации
        old_users_list = "\n".join(f"  • `{uid}` (старая система)" for uid in AUTHORIZED_USERS) if AUTHORIZED_USERS else ""
        new_users = auth_system.get_all_users()
        new_users_list = "\n".join(
            f"  • `{u.user_id}`{' @' + u.username if u.username else ''} — {u.name or 'без имени'}"
            for u in new_users
        ) if new_users else ""
        
        combined = f"{old_users_list}\n{new_users_list}".strip()
        if combined:
            await update.message.reply_text(
                f"👥 *Авторизованные пользователи:*\n{combined}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("📭 Нет авторизованных пользователей.")
    
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
        # Используем улучшенную систему авторизации
        identifier = " ".join(context.args[1:])
        try:
            user = auth_system.parse_user_identifier(identifier)
            if user:
                auth_system.add_user(user.user_id, user.username, user.name)
                username_part = f" (@{user.username})" if user.username else ""
                await update.message.reply_text(
                    f"✅ Пользователь `{user.user_id}`{username_part} добавлен.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Fallback на старую систему (числовой user_id)
                new_user_id = int(context.args[1])
                AUTHORIZED_USERS.add(new_user_id)
                await update.message.reply_text(
                    f"✅ Пользователь `{new_user_id}` добавлен (старая система).",
                    parse_mode=ParseMode.MARKDOWN
                )
        except (ValueError, Exception) as e:
            await update.message.reply_text(
                f"❌ Не удалось добавить пользователя: {str(e)}\n"
                f"Используйте: user_id, @username или t.me/username"
            )
    
    elif action == "addchannel" and len(context.args) > 1:
        try:
            channel_id = int(context.args[1])
            ALLOWED_CHANNELS.add(channel_id)
            await update.message.reply_text(f"✅ Канал/группа `{channel_id}` добавлен.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом (с минусом для групп).")
    
    elif action == "remove" and len(context.args) > 1:
        try:
            remove_id = int(context.args[1])
            AUTHORIZED_USERS.discard(remove_id)
            await update.message.reply_text(f"🗑️ Пользователь `{remove_id}` удалён.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ user_id должен быть числом.")
    
    elif action == "removechannel" and len(context.args) > 1:
        try:
            channel_id = int(context.args[1])
            ALLOWED_CHANNELS.discard(channel_id)
            await update.message.reply_text(f"🗑️ Канал/группа `{channel_id}` удалён.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ ID должен быть числом.")
    
    elif action == "thisgroup":
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        if chat_type in ("group", "supergroup", "channel"):
            ALLOWED_CHANNELS.add(chat_id)
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
        if AUTHORIZED_USERS:
            users_list = "\n".join(f"  • `{uid}`" for uid in AUTHORIZED_USERS)
            text = f"👥 *Авторизованные:*\n{users_list}"
        else:
            text = "📭 Нет авторизованных пользователей."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
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
    if user_id in AUTHORIZED_USERS or auth_system.is_authorized(user_id, update.effective_user.username):
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
            # Обрабатываем через Cortex
            result = neira_cortex.process(user_text, str(user_id))
            
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
            
            if full_response and full_response.strip():
                parts = split_message(full_response)
                for part in parts:
                    if part.strip():
                        await update.message.reply_text(part)
                
                # Сохраняем в контекст
                parallel_mind.add_message(chat_id, "assistant", full_response)
                
                # Метаинфо (опционально, можно отключить)
                if os.getenv("NEIRA_SHOW_CORTEX_INFO", "false") == "true":
                    meta_info = (
                        f"{strategy_emoji} {result.strategy.value}{tier_info} | "
                        f"{result.latency_ms:.0f}ms{llm_marker}"
                    )
                    await update.message.reply_text(
                        f"__{meta_info}__",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await update.message.reply_text(
                    "🤔 Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос."
                )
            
            return
            
        except Exception as cortex_error:
            logging.warning(f"Cortex обработка провалилась: {cortex_error}, переключаемся на legacy")
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
    
    status_msg = await update.message.reply_text("🔄 Начинаю обработку...")

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
                        await status_msg.edit_text(f"{emoji} {stage_name}...")
                        last_stage = stage_name
                    await show_typing(update, context)
                elif chunk.type == "content":
                    await status_msg.delete()
                    full_response = chunk.content
                    
                    # Защита от пустого ответа
                    if not chunk.content or not chunk.content.strip():
                        await update.message.reply_text("🤔 Извини, не смогла сформулировать ответ. Попробуй переформулировать вопрос.")
                        return
                    
                    parts = split_message(chunk.content)
                    for part in parts:
                        if part.strip():  # Отправляем только непустые части
                            await update.message.reply_text(part)
                elif chunk.type == "error":
                    await status_msg.edit_text(f"❌ Ошибка: {chunk.content}")
                    return
            
            # Сохраняем ответ Neira в контекст
            if full_response:
                parallel_mind.add_message(chat_id, "assistant", full_response)

        except Exception as exc:
            logging.exception("Сбой при обработке сообщения")
            try:
                await status_msg.edit_text(f"❌ Ошибка: {exc}")
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await update.message.reply_text(f"❌ Ошибка: {exc}")


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
                use_llm=(CORTEX_MODE != "auto")  # LLM доступен только в always режиме
            )
            logging.info("✅ Neira Cortex v2.0 активирован (режим: %s)", CORTEX_MODE)
        except Exception as e:
            logging.warning("⚠️ Не удалось инициализировать Cortex: %s", e)
            neira_cortex = None

    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
