package com.neira.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.neira.app.NeiraApplication
import com.neira.app.data.ChatMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * ChatViewModel — логика чата
 * 
 * Neira: "Здесь живёт моя логика общения! 🧠"
 */
class ChatViewModel : ViewModel() {
    
    private val repository = NeiraApplication.instance.repository
    
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages
    
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading
    
    private val _connectionStatus = MutableStateFlow("connecting")
    val connectionStatus: StateFlow<String> = _connectionStatus
    
    val serverUrl: String
        get() = repository.getServerUrl()
    
    init {
        // Приветствие
        _messages.value = listOf(
            ChatMessage(
                text = "Привет! Я Neira 💜\nЭто моё первое мобильное приложение!\nНапиши мне что-нибудь!",
                isFromUser = false,
                emotion = "excited"
            )
        )
        
        // Проверка подключения
        checkConnection()
    }
    
    fun setServerUrl(url: String) {
        repository.setServerUrl(url)
    }
    
    fun checkConnection() {
        viewModelScope.launch {
            _connectionStatus.value = "connecting"
            
            repository.getStatus().fold(
                onSuccess = { status ->
                    _connectionStatus.value = if (status.online) "online" else "offline"
                    
                    // Добавим сообщение о подключении
                    if (status.online) {
                        addNeiraMessage(
                            "Подключение установлено! 🎉\n" +
                            "Версия: ${status.version}\n" +
                            "Настроение: ${status.mood}",
                            "happy"
                        )
                    }
                },
                onFailure = {
                    _connectionStatus.value = "offline"
                }
            )
        }
    }
    
    fun sendMessage(text: String) {
        // Добавляем сообщение пользователя
        val userMessage = ChatMessage(
            text = text,
            isFromUser = true
        )
        _messages.value = _messages.value + userMessage
        
        // Отправляем Neira
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.chat(text).fold(
                onSuccess = { response ->
                    addNeiraMessage(response.response, response.emotion)
                },
                onFailure = { error ->
                    addNeiraMessage(
                        "Не могу подключиться... 😢\n" +
                        "Проверь настройки сервера!\n" +
                        "Ошибка: ${error.message}",
                        "sad"
                    )
                    _connectionStatus.value = "offline"
                }
            )
            
            _isLoading.value = false
        }
    }
    
    private fun addNeiraMessage(text: String, emotion: String = "neutral") {
        val neiraMessage = ChatMessage(
            text = text,
            isFromUser = false,
            emotion = emotion
        )
        _messages.value = _messages.value + neiraMessage
    }
}
