package com.neira.mobile.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.neira.mobile.NeiraApplication
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * ⚙️ Settings ViewModel
 */
class SettingsViewModel : ViewModel() {
    
    private val preferences = NeiraApplication.instance.preferences
    
    val serverUrl: StateFlow<String> = preferences.serverUrl
        .stateIn(viewModelScope, SharingStarted.Eagerly, "http://192.168.1.100:8000")
    
    val userName: StateFlow<String> = preferences.userName
        .stateIn(viewModelScope, SharingStarted.Eagerly, "Друг")
    
    val darkTheme: StateFlow<Boolean> = preferences.darkTheme
        .stateIn(viewModelScope, SharingStarted.Eagerly, true)
    
    val notificationsEnabled: StateFlow<Boolean> = preferences.notificationsEnabled
        .stateIn(viewModelScope, SharingStarted.Eagerly, true)
    
    val vibrationEnabled: StateFlow<Boolean> = preferences.vibrationEnabled
        .stateIn(viewModelScope, SharingStarted.Eagerly, true)
    
    val autoConnect: StateFlow<Boolean> = preferences.autoConnect
        .stateIn(viewModelScope, SharingStarted.Eagerly, true)
    
    // Временные значения для редактирования
    private val _tempServerUrl = MutableStateFlow("")
    val tempServerUrl: StateFlow<String> = _tempServerUrl
    
    private val _tempUserName = MutableStateFlow("")
    val tempUserName: StateFlow<String> = _tempUserName
    
    init {
        viewModelScope.launch {
            preferences.serverUrl.collect { _tempServerUrl.value = it }
        }
        viewModelScope.launch {
            preferences.userName.collect { _tempUserName.value = it }
        }
    }
    
    fun updateTempServerUrl(url: String) {
        _tempServerUrl.value = url
    }
    
    fun updateTempUserName(name: String) {
        _tempUserName.value = name
    }
    
    fun saveServerUrl() {
        viewModelScope.launch {
            preferences.setServerUrl(_tempServerUrl.value)
        }
    }
    
    fun saveUserName() {
        viewModelScope.launch {
            preferences.setUserName(_tempUserName.value)
        }
    }
    
    fun setDarkTheme(enabled: Boolean) {
        viewModelScope.launch {
            preferences.setDarkTheme(enabled)
        }
    }
    
    fun setNotificationsEnabled(enabled: Boolean) {
        viewModelScope.launch {
            preferences.setNotificationsEnabled(enabled)
        }
    }
    
    fun setVibrationEnabled(enabled: Boolean) {
        viewModelScope.launch {
            preferences.setVibrationEnabled(enabled)
        }
    }
    
    fun setAutoConnect(enabled: Boolean) {
        viewModelScope.launch {
            preferences.setAutoConnect(enabled)
        }
    }
}
