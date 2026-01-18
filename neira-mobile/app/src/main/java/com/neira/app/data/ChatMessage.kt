package com.neira.app.data

/**
 * ChatMessage — модель сообщения в чате
 */
data class ChatMessage(
    val id: Long = System.currentTimeMillis(),
    val text: String,
    val isFromUser: Boolean,
    val timestamp: Long = System.currentTimeMillis(),
    val emotion: String = "neutral"
)
