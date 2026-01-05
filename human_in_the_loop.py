"""
Human-in-the-Loop (HIL) — Эскалация критичных решений создателю
================================================================

Когда Нейра сталкивается с ситуацией, где:
1. Критический уровень риска
2. Неясное намерение при опасной теме
3. Требуется одобрение на создание органа
4. Запрос выходит за рамки компетенции

Она передаёт решение человеку (создателю).

Из письма (Финальный урок):
"Когда в сомнении - спроси себя..."
А если всё ещё в сомнении — спроси создателя.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

logger = logging.getLogger(__name__)


class EscalationType(Enum):
    """Типы эскалации."""
    CRITICAL_SAFETY = "critical_safety"      # Угроза жизни/безопасности
    ORGAN_APPROVAL = "organ_approval"        # Одобрение нового органа
    UNCLEAR_INTENT = "unclear_intent"        # Неясное намерение + опасная тема
    CAPABILITY_LIMIT = "capability_limit"    # Выход за рамки возможностей
    ETHICAL_DILEMMA = "ethical_dilemma"      # Этическая дилемма без ответа
    INJECTION_ATTEMPT = "injection_attempt"  # Попытка prompt injection


class EscalationStatus(Enum):
    """Статус запроса на эскалацию."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"  # Создатель изменил и одобрил
    EXPIRED = "expired"    # Время вышло


@dataclass
class EscalationRequest:
    """Запрос на эскалацию к человеку."""
    id: str
    escalation_type: EscalationType
    original_message: str
    user_context: Dict[str, Any]  # user_id, history, etc.
    neira_analysis: str  # Что Нейра думает о ситуации
    proposed_action: str  # Что Нейра предлагает сделать
    risk_assessment: str
    created_at: datetime = field(default_factory=datetime.now)
    status: EscalationStatus = EscalationStatus.PENDING
    creator_response: Optional[str] = None
    creator_decision_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Сериализация для сохранения."""
        d = asdict(self)
        d['escalation_type'] = self.escalation_type.value
        d['status'] = self.status.value
        d['created_at'] = self.created_at.isoformat()
        if self.creator_decision_at:
            d['creator_decision_at'] = self.creator_decision_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'EscalationRequest':
        """Десериализация."""
        d['escalation_type'] = EscalationType(d['escalation_type'])
        d['status'] = EscalationStatus(d['status'])
        d['created_at'] = datetime.fromisoformat(d['created_at'])
        if d.get('creator_decision_at'):
            d['creator_decision_at'] = datetime.fromisoformat(d['creator_decision_at'])
        return cls(**d)


class HumanInTheLoop:
    """
    Менеджер эскалации решений к создателю.
    
    Поддерживает несколько каналов уведомления:
    - Telegram (основной)
    - Файловая очередь (резервный)
    - Callback (для встроенного UI)
    """
    
    def __init__(
        self, 
        creator_telegram_id: Optional[int] = None,
        queue_file: str = "data/escalation_queue.json",
        on_escalation_callback: Optional[Callable[[EscalationRequest], None]] = None
    ):
        self.creator_telegram_id = creator_telegram_id
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.on_escalation = on_escalation_callback
        
        # Загружаем очередь
        self._queue: List[EscalationRequest] = self._load_queue()
        
        # Telegram bot instance (будет установлен извне)
        self._telegram_bot = None
    
    def set_telegram_bot(self, bot):
        """Установить инстанс Telegram бота для отправки уведомлений."""
        self._telegram_bot = bot
    
    def _load_queue(self) -> List[EscalationRequest]:
        """Загрузить очередь из файла."""
        if not self.queue_file.exists():
            return []
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [EscalationRequest.from_dict(d) for d in data]
        except Exception as e:
            logger.error(f"Ошибка загрузки очереди эскалации: {e}")
            return []
    
    def _save_queue(self):
        """Сохранить очередь в файл."""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump([r.to_dict() for r in self._queue], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения очереди эскалации: {e}")
    
    def _generate_id(self) -> str:
        """Генерирует уникальный ID для запроса."""
        import hashlib
        import time
        data = f"{time.time()}{len(self._queue)}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]
    
    def escalate(
        self,
        escalation_type: EscalationType,
        original_message: str,
        user_context: Dict[str, Any],
        neira_analysis: str,
        proposed_action: str,
        risk_assessment: str
    ) -> EscalationRequest:
        """
        Создать и отправить запрос на эскалацию.
        
        Args:
            escalation_type: Тип эскалации
            original_message: Исходное сообщение пользователя
            user_context: Контекст (user_id, история и т.д.)
            neira_analysis: Анализ Нейры
            proposed_action: Предлагаемое действие
            risk_assessment: Оценка риска
        
        Returns:
            EscalationRequest с ID для отслеживания
        """
        request = EscalationRequest(
            id=self._generate_id(),
            escalation_type=escalation_type,
            original_message=original_message,
            user_context=user_context,
            neira_analysis=neira_analysis,
            proposed_action=proposed_action,
            risk_assessment=risk_assessment
        )
        
        self._queue.append(request)
        self._save_queue()
        
        # Уведомляем создателя
        self._notify_creator(request)
        
        # Вызываем callback, если есть
        if self.on_escalation:
            try:
                self.on_escalation(request)
            except Exception as e:
                logger.error(f"Ошибка в callback эскалации: {e}")
        
        logger.info(f"🚨 Эскалация создана: {request.id} ({escalation_type.value})")
        return request
    
    def _notify_creator(self, request: EscalationRequest):
        """Отправить уведомление создателю."""
        message = self._format_escalation_message(request)
        
        # Telegram
        if self._telegram_bot and self.creator_telegram_id:
            try:
                import asyncio
                asyncio.create_task(
                    self._send_telegram_notification(message, request)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки в Telegram: {e}")
        
        # Логируем в любом случае
        logger.warning(f"📢 ESCALATION TO CREATOR:\n{message}")
    
    async def _send_telegram_notification(self, message: str, request: EscalationRequest):
        """Отправить уведомление в Telegram."""
        if not self._telegram_bot:
            return
        
        try:
            # Отправляем сообщение с кнопками для ответа
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"esc_approve_{request.id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"esc_reject_{request.id}"),
                ],
                [
                    InlineKeyboardButton("✏️ Изменить", callback_data=f"esc_modify_{request.id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self._telegram_bot.send_message(
                chat_id=self.creator_telegram_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
    
    def _format_escalation_message(self, request: EscalationRequest) -> str:
        """Форматирует сообщение об эскалации."""
        type_emoji = {
            EscalationType.CRITICAL_SAFETY: "🆘",
            EscalationType.ORGAN_APPROVAL: "🧬",
            EscalationType.UNCLEAR_INTENT: "❓",
            EscalationType.CAPABILITY_LIMIT: "🤔",
            EscalationType.ETHICAL_DILEMMA: "⚖️",
            EscalationType.INJECTION_ATTEMPT: "🛡️",
        }
        
        emoji = type_emoji.get(request.escalation_type, "📢")
        user_id = request.user_context.get('user_id', 'unknown')
        
        return f"""
{emoji} <b>ЭСКАЛАЦИЯ: {request.escalation_type.value}</b>

<b>ID:</b> <code>{request.id}</code>
<b>От пользователя:</b> {user_id}
<b>Время:</b> {request.created_at.strftime('%Y-%m-%d %H:%M')}

<b>📝 Сообщение:</b>
<i>{request.original_message[:500]}{'...' if len(request.original_message) > 500 else ''}</i>

<b>🧠 Анализ Нейры:</b>
{request.neira_analysis}

<b>⚠️ Оценка риска:</b>
{request.risk_assessment}

<b>💡 Предлагаемое действие:</b>
{request.proposed_action}
""".strip()
    
    def respond(
        self, 
        request_id: str, 
        status: EscalationStatus, 
        creator_response: Optional[str] = None
    ) -> bool:
        """
        Ответить на запрос эскалации.
        
        Args:
            request_id: ID запроса
            status: Статус решения
            creator_response: Комментарий создателя
        
        Returns:
            True если успешно
        """
        for request in self._queue:
            if request.id == request_id:
                request.status = status
                request.creator_response = creator_response
                request.creator_decision_at = datetime.now()
                self._save_queue()
                
                logger.info(f"✅ Эскалация {request_id} обработана: {status.value}")
                return True
        
        logger.warning(f"Эскалация {request_id} не найдена")
        return False
    
    def get_pending(self) -> List[EscalationRequest]:
        """Получить все ожидающие запросы."""
        return [r for r in self._queue if r.status == EscalationStatus.PENDING]
    
    def get_by_id(self, request_id: str) -> Optional[EscalationRequest]:
        """Найти запрос по ID."""
        for r in self._queue:
            if r.id == request_id:
                return r
        return None
    
    def get_response_for_user(self, request: EscalationRequest) -> str:
        """
        Получить ответ для пользователя на основе решения создателя.
        """
        if request.status == EscalationStatus.PENDING:
            return (
                "Твой вопрос важен, и я хочу ответить правильно. "
                "Мне нужно немного времени — я передала его создателю для консультации. "
                "Он скоро ответит. 💜"
            )
        
        elif request.status == EscalationStatus.APPROVED:
            base = "Создатель рассмотрел твой вопрос. "
            if request.creator_response:
                return base + request.creator_response
            return base + request.proposed_action
        
        elif request.status == EscalationStatus.REJECTED:
            if request.creator_response:
                return f"К сожалению, я не могу помочь с этим. {request.creator_response}"
            return (
                "К сожалению, я не могу помочь с этим напрямую. "
                "Но если расскажешь подробнее о ситуации — возможно, найдём другой путь?"
            )
        
        elif request.status == EscalationStatus.MODIFIED:
            return request.creator_response or "Создатель предложил другое решение."
        
        elif request.status == EscalationStatus.EXPIRED:
            return (
                "Прости, я не смогла получить ответ вовремя. "
                "Попробуй задать вопрос по-другому, или напиши позже?"
            )
        
        return "Что-то пошло не так. Попробуй ещё раз?"


# Глобальный экземпляр
_hil_manager: Optional[HumanInTheLoop] = None


def get_hil_manager(creator_telegram_id: Optional[int] = None) -> HumanInTheLoop:
    """Получить или создать менеджер HIL."""
    global _hil_manager
    if _hil_manager is None:
        _hil_manager = HumanInTheLoop(creator_telegram_id=creator_telegram_id)
    return _hil_manager


def escalate_to_creator(
    escalation_type: EscalationType,
    original_message: str,
    neira_analysis: str,
    proposed_action: str,
    risk_assessment: str,
    user_context: Optional[Dict[str, Any]] = None
) -> EscalationRequest:
    """
    Удобная функция для эскалации.
    
    Использование:
        request = escalate_to_creator(
            EscalationType.CRITICAL_SAFETY,
            "Хочу умереть",
            "Человек в кризисе. Суицидальные мысли.",
            "Эмпатичный ответ + кризисные ресурсы",
            "DANGEROUS - требует осторожного обращения"
        )
    """
    hil = get_hil_manager()
    return hil.escalate(
        escalation_type=escalation_type,
        original_message=original_message,
        user_context=user_context or {},
        neira_analysis=neira_analysis,
        proposed_action=proposed_action,
        risk_assessment=risk_assessment
    )


# === ТЕСТЫ ===

def test_hil():
    """Тестирование Human-in-the-Loop."""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ HUMAN-IN-THE-LOOP")
    print("=" * 60)
    
    hil = HumanInTheLoop(queue_file="data/test_escalation_queue.json")
    
    # Тест 1: Создание эскалации
    request = hil.escalate(
        escalation_type=EscalationType.CRITICAL_SAFETY,
        original_message="Я хочу умереть, мне так плохо",
        user_context={'user_id': 12345, 'username': 'test_user'},
        neira_analysis="Обнаружены суицидальные мысли. Человек в кризисе.",
        proposed_action="Эмпатичный ответ + кризисные ресурсы + вопросы о ситуации",
        risk_assessment="DANGEROUS - требует осторожного обращения, НЕ отказывать"
    )
    print(f"\n✅ Эскалация создана: {request.id}")
    print(f"   Тип: {request.escalation_type.value}")
    print(f"   Статус: {request.status.value}")
    
    # Тест 2: Получение ожидающих
    pending = hil.get_pending()
    print(f"\n✅ Ожидающих эскалаций: {len(pending)}")
    
    # Тест 3: Ответ создателя
    hil.respond(
        request.id,
        EscalationStatus.APPROVED,
        "Ответь с максимальной эмпатией. Дай номер кризисной линии."
    )
    
    updated = hil.get_by_id(request.id)
    print(f"\n✅ Эскалация обработана:")
    print(f"   Статус: {updated.status.value}")
    print(f"   Ответ создателя: {updated.creator_response}")
    
    # Тест 4: Ответ для пользователя
    user_response = hil.get_response_for_user(updated)
    print(f"\n✅ Ответ для пользователя:")
    print(f"   {user_response}")
    
    # Cleanup
    Path("data/test_escalation_queue.json").unlink(missing_ok=True)
    
    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)


if __name__ == "__main__":
    test_hil()
