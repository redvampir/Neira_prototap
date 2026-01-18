"""
Команда /myname для установки имени пользователя
"""

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
