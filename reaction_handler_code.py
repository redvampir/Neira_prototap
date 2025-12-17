# Обработчик эмодзи-реакций для telegram_bot.py
# Вставить в telegram_bot.py после функции myname_command

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


async def feedback_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
