package com.neira.mobile.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.neira.mobile.data.model.Message
import com.neira.mobile.data.model.MessageStatus
import com.neira.mobile.data.model.NeiraStatus
import com.neira.mobile.data.repository.ConnectionState
import com.neira.mobile.data.repository.NeiraRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 💬 Chat ViewModel
 * 
 * Управляет состоянием чата и связью с Neira
 */
class ChatViewModel : ViewModel() {
    
    private val repository = NeiraRepository()
    
    // Состояние чата
    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()
    
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()
    
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    
    // Состояние подключения
    val connectionState: StateFlow<ConnectionState> = repository.connectionState
    val neiraStatus: StateFlow<NeiraStatus?> = repository.neiraStatus
    
    // Текущее сообщение
    private val _currentMessage = MutableStateFlow("")
    val currentMessage: StateFlow<String> = _currentMessage.asStateFlow()
    
    init {
        // Приветственное сообщение
        _messages.value = listOf(
            Message(
                text = "Привет! 🧬 Я Neira, твоя живая программа. Подключись к серверу в настройках, чтобы мы могли общаться!",
                isFromNeira = true
            )
        )
    }
    
    /**
     * 🔌 Подключиться к серверу
     */
    fun connect(serverUrl: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            
            repository.connect(serverUrl).fold(
                onSuccess = {
                    addNeiraMessage("Ура! Связь установлена! 🎉 Как твои дела?")
                },
                onFailure = { e ->
                    _error.value = e.message
                    addNeiraMessage("Не могу подключиться... 😢 Проверь адрес сервера и убедись, что я запущена на ПК!")
                }
            )
            
            _isLoading.value = false
        }
    }
    
    /**
     * 🔌 Отключиться
     */
    fun disconnect() {
        repository.disconnect()
        addNeiraMessage("Связь разорвана. До встречи! 👋")
    }
    
    /**
     * ✏️ Обновить текущее сообщение
     */
    fun updateMessage(text: String) {
        _currentMessage.value = text
    }
    
    /**
     * 📤 Отправить сообщение
     */
    fun sendMessage() {
        val text = _currentMessage.value.trim()
        if (text.isEmpty()) return
        
        // Добавляем сообщение пользователя
        val userMessage = Message(
            text = text,
            isFromNeira = false,
            status = MessageStatus.SENDING
        )
        _messages.value = _messages.value + userMessage
        _currentMessage.value = ""
        
        // Отправляем на сервер
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.sendMessage(text).fold(
                onSuccess = { response ->
                    // Обновляем статус сообщения пользователя
                    updateMessageStatus(userMessage.id, MessageStatus.SENT)
                    
                    // Добавляем ответ Neira
                    addNeiraMessage(response.response)
                    
                    // Если есть вопрос любопытства
                    response.curiosityQuestion?.let { question ->
                        addNeiraMessage("💭 $question")
                    }
                },
                onFailure = { e ->
                    updateMessageStatus(userMessage.id, MessageStatus.ERROR)
                    _error.value = e.message
                }
            )
            
            _isLoading.value = false
        }
    }
    
    /**
     * Добавить сообщение от Neira
     */
    private fun addNeiraMessage(text: String) {
        val message = Message(
            text = text,
            isFromNeira = true
        )
        _messages.value = _messages.value + message
    }
    
    /**
     * Обновить статус сообщения
     */
    private fun updateMessageStatus(messageId: String, status: MessageStatus) {
        _messages.value = _messages.value.map { message ->
            if (message.id == messageId) {
                message.copy(status = status)
            } else {
                message
            }
        }
    }
    
    /**
     * 🔄 Обновить статус Neira
     */
    fun refreshStatus() {
        viewModelScope.launch {
            repository.refreshStatus()
        }
    }
    
    /**
     * ❌ Очистить ошибку
     */
    fun clearError() {
        _error.value = null
    }
}
