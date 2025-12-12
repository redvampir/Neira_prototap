"""
Telegram Alerter v1.0 — Отправка алертов и SOS в Telegram

Используется нервной и иммунной системами для оповещения администратора
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

# aiohttp опционален
try:
    import aiohttp  # type: ignore[import-not-found]
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramAlerter")

# Загрузка конфигурации
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_ID", "")


@dataclass
class AlertMessage:
    """Сообщение алерта"""
    severity: str  # info, warning, error, critical, sos
    title: str
    message: str
    source: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None


class TelegramAlerter:
    """
    Отправка алертов в Telegram
    
    Поддерживает:
    - Обычные алерты (info, warning, error, critical)
    - SOS сообщения (с особым форматированием)
    - Health reports (периодические отчёты)
    """
    
    SEVERITY_EMOJI = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🔴",
        "critical": "💀",
        "sos": "🆘"
    }
    
    def __init__(self, bot_token: str = "", admin_chat_id: str = ""):
        self.bot_token = bot_token or BOT_TOKEN
        self.admin_chat_id = admin_chat_id or ADMIN_CHAT_ID
        self.enabled = bool(self.bot_token and self.admin_chat_id)
        self.alert_history: list = []
        self.rate_limit_window = 60  # секунд
        self.max_alerts_per_window = 10
        
        if not self.enabled:
            logger.warning("Telegram Alerter: токен или chat_id не настроены")
    
    def _format_alert(self, alert: AlertMessage) -> str:
        """Форматирование алерта для Telegram"""
        emoji = self.SEVERITY_EMOJI.get(alert.severity, "❓")
        
        text = f"{emoji} *{alert.title}*\n\n"
        text += f"📍 Источник: `{alert.source}`\n"
        text += f"⏰ Время: {alert.timestamp.strftime('%H:%M:%S')}\n\n"
        text += f"{alert.message}\n"
        
        if alert.context:
            text += "\n📋 *Контекст:*\n"
            for key, value in list(alert.context.items())[:5]:
                text += f"  • {key}: `{str(value)[:50]}`\n"
        
        return text
    
    def _format_sos(self, alert: AlertMessage) -> str:
        """Особое форматирование для SOS"""
        text = "🆘🆘🆘 *NEIRA SOS* 🆘🆘🆘\n\n"
        text += f"⚠️ *Проблема:* {alert.title}\n\n"
        text += f"{alert.message}\n\n"
        text += f"📍 Источник: `{alert.source}`\n"
        text += f"⏰ Время: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if alert.context:
            text += "\n📋 *Диагностика:*\n"
            for key, value in list(alert.context.items())[:10]:
                text += f"  • {key}: `{str(value)[:100]}`\n"
        
        text += "\n🔧 *Требуется вмешательство!*"
        return text
    
    def _check_rate_limit(self) -> bool:
        """Проверка rate limit"""
        now = datetime.now()
        # Очистка старых записей
        self.alert_history = [
            t for t in self.alert_history 
            if (now - t).total_seconds() < self.rate_limit_window
        ]
        
        if len(self.alert_history) >= self.max_alerts_per_window:
            logger.warning("Rate limit exceeded for Telegram alerts")
            return False
        
        self.alert_history.append(now)
        return True
    
    async def send_alert_async(self, alert: AlertMessage) -> bool:
        """Асинхронная отправка алерта"""
        if not self.enabled:
            logger.info(f"Alert (disabled): [{alert.severity}] {alert.title}")
            return False
        
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not installed, using sync fallback")
            return self._send_sync(alert)
        
        if not self._check_rate_limit():
            return False
        
        # Форматируем
        if alert.severity == "sos":
            text = self._format_sos(alert)
        else:
            text = self._format_alert(alert)
        
        # Отправляем
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            async with aiohttp.ClientSession() as session:  # type: ignore[union-attr]
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:  # type: ignore[union-attr]
                    if resp.status == 200:
                        logger.info(f"Alert sent: [{alert.severity}] {alert.title}")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Failed to send alert: {resp.status} - {error}")
                        return False
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    def _send_sync(self, alert: AlertMessage) -> bool:
        """Синхронная отправка через urllib (fallback без aiohttp)"""
        import urllib.request
        import urllib.parse
        
        if not self._check_rate_limit():
            return False
        
        if alert.severity == "sos":
            text = self._format_sos(alert)
        else:
            text = self._format_alert(alert)
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": self.admin_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }).encode('utf-8')
        
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"Alert sent (sync): [{alert.severity}] {alert.title}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error sending alert (sync): {e}")
            return False
    
    def send_alert(self, alert: AlertMessage) -> bool:
        """Синхронная обёртка для отправки алерта"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если уже в async контексте
                asyncio.create_task(self.send_alert_async(alert))
                return True
            else:
                return loop.run_until_complete(self.send_alert_async(alert))
        except RuntimeError:
            # Создаём новый event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.send_alert_async(alert))
            finally:
                loop.close()
    
    # === Удобные методы ===
    
    def info(self, title: str, message: str, source: str = "system"):
        """Отправить info алерт"""
        alert = AlertMessage(
            severity="info",
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now()
        )
        return self.send_alert(alert)
    
    def warning(self, title: str, message: str, source: str = "system", context: Optional[Dict[str, Any]] = None):
        """Отправить warning алерт"""
        alert = AlertMessage(
            severity="warning",
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now(),
            context=context or {}
        )
        return self.send_alert(alert)
    
    def error(self, title: str, message: str, source: str = "system", context: Optional[Dict[str, Any]] = None):
        """Отправить error алерт"""
        alert = AlertMessage(
            severity="error",
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now(),
            context=context or {}
        )
        return self.send_alert(alert)
    
    def critical(self, title: str, message: str, source: str = "system", context: Optional[Dict[str, Any]] = None):
        """Отправить critical алерт"""
        alert = AlertMessage(
            severity="critical",
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now(),
            context=context or {}
        )
        return self.send_alert(alert)
    
    def sos(self, problem: str, details: str = "", source: str = "immune_system", context: Optional[Dict[str, Any]] = None):
        """Отправить SOS"""
        alert = AlertMessage(
            severity="sos",
            title=problem,
            message=details or "Требуется немедленная помощь!",
            source=source,
            timestamp=datetime.now(),
            context=context or {}
        )
        return self.send_alert(alert)
    
    async def send_health_report_async(self, health_data: Dict[str, Any]) -> bool:
        """Отправить отчёт о здоровье"""
        if not self.enabled:
            return False
        
        status = health_data.get("status", "unknown")
        status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "🔴"}.get(status, "❓")
        
        text = f"📊 *Отчёт о здоровье Neira*\n\n"
        text += f"Статус: {status_emoji} {status}\n\n"
        
        if "metrics" in health_data:
            text += "*Метрики:*\n"
            for name, data in health_data["metrics"].items():
                metric_status = data.get("status", "unknown")
                metric_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "🔴"}.get(metric_status, "❓")
                text += f"  {metric_emoji} {name}: {data['value']}{data.get('unit', '')}\n"
        
        if "errors" in health_data:
            err = health_data["errors"]
            text += f"\n*Ошибки:* {err.get('total', 0)} всего, {err.get('last_hour', 0)} за час\n"
        
        if "active_alerts" in health_data and health_data["active_alerts"] > 0:
            text += f"\n⚠️ *Активных алертов:* {health_data['active_alerts']}\n"
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            async with aiohttp.ClientSession() as session:  # type: ignore[union-attr]
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:  # type: ignore[union-attr]
                    return resp.status == 200
        except:
            return False


# === Глобальный экземпляр ===
_alerter: Optional[TelegramAlerter] = None


def get_alerter() -> TelegramAlerter:
    """Получить глобальный alerter"""
    global _alerter
    if _alerter is None:
        _alerter = TelegramAlerter()
    return _alerter


# === Тестирование ===
if __name__ == "__main__":
    print("📱 Testing Telegram Alerter v1.0\n")
    
    alerter = TelegramAlerter()
    
    if not alerter.enabled:
        print("❌ Alerter отключен — нужны TELEGRAM_BOT_TOKEN и TELEGRAM_ADMIN_ID в .env")
        print("\nПример .env:")
        print("  TELEGRAM_BOT_TOKEN=123456:ABC...")
        print("  TELEGRAM_ADMIN_ID=123456789")
    else:
        print("✅ Alerter настроен")
        
        # Тест отправки
        print("\n📤 Отправляю тестовый алерт...")
        success = alerter.info(
            title="Тест Alerter",
            message="Это тестовое сообщение от Neira Alerter",
            source="test"
        )
        
        if success:
            print("✅ Алерт отправлен!")
        else:
            print("❌ Не удалось отправить")
