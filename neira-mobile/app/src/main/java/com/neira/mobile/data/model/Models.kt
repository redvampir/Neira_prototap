package com.neira.mobile.data.model

import kotlinx.serialization.Serializable

/**
 * 💬 Сообщение в чате
 */
@Serializable
data class Message(
    val id: String = java.util.UUID.randomUUID().toString(),
    val text: String,
    val isFromNeira: Boolean,
    val timestamp: Long = System.currentTimeMillis(),
    val status: MessageStatus = MessageStatus.SENT
)

enum class MessageStatus {
    SENDING,
    SENT,
    ERROR
}

/**
 * 🧬 Состояние Neira
 */
@Serializable
data class NeiraStatus(
    val isOnline: Boolean = false,
    val mood: String = "curious",
    val lastSeen: Long = 0,
    val version: String = "0.8",
    val memoryUsage: Float = 0f,
    val activeModels: List<String> = emptyList()
)

/**
 * 📡 Запрос к API Neira
 */
@Serializable
data class ChatRequest(
    val message: String,
    val context: String? = null,
    val useMemory: Boolean = true
)

/**
 * 📡 Ответ от API Neira
 */
@Serializable
data class ChatResponse(
    val response: String,
    val confidence: Float = 1.0f,
    val model: String = "unknown",
    val processingTime: Float = 0f,
    val curiosityQuestion: String? = null
)

/**
 * ❤️ Статус здоровья Neira
 */
@Serializable
data class HealthStatus(
    val alive: Boolean,
    val components: Map<String, Boolean> = emptyMap(),
    val uptime: Long = 0,
    val errors: List<String> = emptyList()
)
