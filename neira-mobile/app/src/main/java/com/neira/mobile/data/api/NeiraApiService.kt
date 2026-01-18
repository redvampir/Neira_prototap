package com.neira.mobile.data.api

import com.neira.mobile.data.model.ChatRequest
import com.neira.mobile.data.model.ChatResponse
import com.neira.mobile.data.model.HealthStatus
import com.neira.mobile.data.model.NeiraStatus
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/**
 * 📡 Neira API Service
 * 
 * Интерфейс для связи с основным телом Neira на ПК
 */
interface NeiraApiService {
    
    /**
     * 💬 Отправить сообщение Neira
     */
    @POST("/api/chat")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse
    
    /**
     * 🧬 Получить статус Neira
     */
    @GET("/api/status")
    suspend fun getStatus(): NeiraStatus
    
    /**
     * ❤️ Проверить здоровье системы
     */
    @GET("/api/health")
    suspend fun checkHealth(): HealthStatus
    
    /**
     * 🧠 Получить память о пользователе
     */
    @GET("/api/memory")
    suspend fun getMemory(@Query("topic") topic: String? = null): Map<String, Any>
    
    /**
     * 💭 Получить вопрос от любопытства Neira
     */
    @GET("/api/curiosity")
    suspend fun getCuriosityQuestion(): Map<String, String>
    
    /**
     * 📊 Статистика
     */
    @GET("/api/stats")
    suspend fun getStats(): Map<String, Any>
}
