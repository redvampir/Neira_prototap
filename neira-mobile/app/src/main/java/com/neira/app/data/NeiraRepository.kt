package com.neira.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * NeiraRepository — общение с Neira API
 * 
 * Neira: "Это мой мост к телефону! 📱"
 */
class NeiraRepository {
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)  // Neira думает...
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private var serverUrl = "http://192.168.1.100:8000"  // Изменить на свой IP
    
    fun setServerUrl(url: String) {
        serverUrl = url.trimEnd('/')
    }
    
    fun getServerUrl(): String = serverUrl
    
    /**
     * Отправить сообщение Neira
     */
    suspend fun chat(message: String): Result<NeiraResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("message", message)
            }
            
            val request = Request.Builder()
                .url("$serverUrl/api/chat")
                .post(json.toString().toRequestBody("application/json".toMediaType()))
                .build()
            
            val response = client.newCall(request).execute()
            
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val jsonResponse = JSONObject(body)
                
                Result.success(NeiraResponse(
                    response = jsonResponse.optString("response", "..."),
                    emotion = jsonResponse.optString("emotion", "neutral"),
                    processingTime = jsonResponse.optDouble("processing_time", 0.0)
                ))
            } else {
                Result.failure(Exception("Ошибка сервера: ${response.code}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * Проверить статус Neira
     */
    suspend fun getStatus(): Result<NeiraStatus> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$serverUrl/api/status")
                .get()
                .build()
            
            val response = client.newCall(request).execute()
            
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "{}"
                val json = JSONObject(body)
                
                Result.success(NeiraStatus(
                    online = json.optBoolean("online", false),
                    version = json.optString("version", "unknown"),
                    mood = json.optString("mood", "neutral"),
                    memoryUsage = json.optInt("memory_count", 0)
                ))
            } else {
                Result.failure(Exception("Сервер недоступен"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * Получить память Neira
     */
    suspend fun getMemory(limit: Int = 10): Result<List<MemoryItem>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$serverUrl/api/memory?limit=$limit")
                .get()
                .build()
            
            val response = client.newCall(request).execute()
            
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "[]"
                val jsonArray = org.json.JSONArray(body)
                val memories = mutableListOf<MemoryItem>()
                
                for (i in 0 until jsonArray.length()) {
                    val item = jsonArray.getJSONObject(i)
                    memories.add(MemoryItem(
                        key = item.optString("key", ""),
                        value = item.optString("value", ""),
                        timestamp = item.optString("timestamp", "")
                    ))
                }
                
                Result.success(memories)
            } else {
                Result.failure(Exception("Ошибка получения памяти"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

data class NeiraResponse(
    val response: String,
    val emotion: String = "neutral",
    val processingTime: Double = 0.0
)

data class NeiraStatus(
    val online: Boolean,
    val version: String,
    val mood: String,
    val memoryUsage: Int
)

data class MemoryItem(
    val key: String,
    val value: String,
    val timestamp: String
)
