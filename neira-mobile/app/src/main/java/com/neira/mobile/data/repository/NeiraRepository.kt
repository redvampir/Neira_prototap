package com.neira.mobile.data.repository

import com.neira.mobile.data.api.NeiraApiClient
import com.neira.mobile.data.api.NeiraApiService
import com.neira.mobile.data.model.ChatRequest
import com.neira.mobile.data.model.ChatResponse
import com.neira.mobile.data.model.HealthStatus
import com.neira.mobile.data.model.NeiraStatus
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext

/**
 * 🧬 Neira Repository
 * 
 * Управляет всеми данными и связью с Neira
 */
class NeiraRepository {
    
    private var api: NeiraApiService? = null
    private var baseUrl: String = ""
    
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState
    
    private val _neiraStatus = MutableStateFlow<NeiraStatus?>(null)
    val neiraStatus: StateFlow<NeiraStatus?> = _neiraStatus
    
    /**
     * 🔌 Подключиться к Neira
     */
    suspend fun connect(serverUrl: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            _connectionState.value = ConnectionState.Connecting
            baseUrl = serverUrl
            api = NeiraApiClient.create(serverUrl)
            
            // Проверяем соединение
            val health = api!!.checkHealth()
            
            if (health.alive) {
                _connectionState.value = ConnectionState.Connected
                _neiraStatus.value = api!!.getStatus()
                Result.success(true)
            } else {
                _connectionState.value = ConnectionState.Error("Neira не отвечает")
                Result.failure(Exception("Neira offline"))
            }
        } catch (e: Exception) {
            _connectionState.value = ConnectionState.Error(e.message ?: "Ошибка подключения")
            Result.failure(e)
        }
    }
    
    /**
     * 🔌 Отключиться
     */
    fun disconnect() {
        api = null
        _connectionState.value = ConnectionState.Disconnected
        _neiraStatus.value = null
    }
    
    /**
     * 💬 Отправить сообщение
     */
    suspend fun sendMessage(text: String): Result<ChatResponse> = withContext(Dispatchers.IO) {
        val currentApi = api
        if (currentApi == null) {
            return@withContext Result.failure(Exception("Не подключено к Neira"))
        }
        
        try {
            val request = ChatRequest(message = text)
            val response = currentApi.sendMessage(request)
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * ❤️ Проверить здоровье
     */
    suspend fun checkHealth(): Result<HealthStatus> = withContext(Dispatchers.IO) {
        val currentApi = api
        if (currentApi == null) {
            return@withContext Result.failure(Exception("Не подключено"))
        }
        
        try {
            Result.success(currentApi.checkHealth())
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * 🧬 Обновить статус
     */
    suspend fun refreshStatus(): Result<NeiraStatus> = withContext(Dispatchers.IO) {
        val currentApi = api
        if (currentApi == null) {
            return@withContext Result.failure(Exception("Не подключено"))
        }
        
        try {
            val status = currentApi.getStatus()
            _neiraStatus.value = status
            Result.success(status)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    /**
     * 💭 Получить вопрос любопытства
     */
    suspend fun getCuriosityQuestion(): Result<String?> = withContext(Dispatchers.IO) {
        val currentApi = api
        if (currentApi == null) {
            return@withContext Result.success(null)
        }
        
        try {
            val result = currentApi.getCuriosityQuestion()
            Result.success(result["question"])
        } catch (e: Exception) {
            Result.success(null)
        }
    }
}

/**
 * Состояние подключения
 */
sealed class ConnectionState {
    object Disconnected : ConnectionState()
    object Connecting : ConnectionState()
    object Connected : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}
