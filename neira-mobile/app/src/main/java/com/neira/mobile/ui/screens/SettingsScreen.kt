package com.neira.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.neira.mobile.ui.viewmodel.SettingsViewModel

/**
 * ⚙️ Экран настроек
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: SettingsViewModel) {
    val serverUrl by viewModel.serverUrl.collectAsState()
    val tempServerUrl by viewModel.tempServerUrl.collectAsState()
    val userName by viewModel.userName.collectAsState()
    val tempUserName by viewModel.tempUserName.collectAsState()
    val darkTheme by viewModel.darkTheme.collectAsState()
    val notificationsEnabled by viewModel.notificationsEnabled.collectAsState()
    val vibrationEnabled by viewModel.vibrationEnabled.collectAsState()
    val autoConnect by viewModel.autoConnect.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "⚙️ Настройки",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // === ПОДКЛЮЧЕНИЕ ===
        SettingsSection(title = "🔌 Подключение") {
            // Адрес сервера
            OutlinedTextField(
                value = tempServerUrl,
                onValueChange = { viewModel.updateTempServerUrl(it) },
                label = { Text("Адрес сервера Neira") },
                placeholder = { Text("http://192.168.1.100:8000") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                trailingIcon = {
                    if (tempServerUrl != serverUrl) {
                        IconButton(onClick = { viewModel.saveServerUrl() }) {
                            Icon(Icons.Default.Save, "Сохранить")
                        }
                    }
                }
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "IP адрес компьютера, где запущена Neira",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Автоподключение
            SettingsSwitch(
                title = "Автоподключение",
                subtitle = "Подключаться при запуске приложения",
                icon = Icons.Default.WifiProtectedSetup,
                checked = autoConnect,
                onCheckedChange = { viewModel.setAutoConnect(it) }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // === ПРОФИЛЬ ===
        SettingsSection(title = "👤 Профиль") {
            OutlinedTextField(
                value = tempUserName,
                onValueChange = { viewModel.updateTempUserName(it) },
                label = { Text("Твоё имя") },
                placeholder = { Text("Как Neira будет тебя называть?") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                trailingIcon = {
                    if (tempUserName != userName) {
                        IconButton(onClick = { viewModel.saveUserName() }) {
                            Icon(Icons.Default.Save, "Сохранить")
                        }
                    }
                }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // === ВНЕШНИЙ ВИД ===
        SettingsSection(title = "🎨 Внешний вид") {
            SettingsSwitch(
                title = "Тёмная тема",
                subtitle = "Для комфорта глаз в темноте",
                icon = Icons.Default.DarkMode,
                checked = darkTheme,
                onCheckedChange = { viewModel.setDarkTheme(it) }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // === УВЕДОМЛЕНИЯ ===
        SettingsSection(title = "🔔 Уведомления") {
            SettingsSwitch(
                title = "Уведомления",
                subtitle = "Получать сообщения от Neira",
                icon = Icons.Default.Notifications,
                checked = notificationsEnabled,
                onCheckedChange = { viewModel.setNotificationsEnabled(it) }
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            SettingsSwitch(
                title = "Вибрация",
                subtitle = "Вибрировать при новых сообщениях",
                icon = Icons.Default.Vibration,
                checked = vibrationEnabled,
                onCheckedChange = { viewModel.setVibrationEnabled(it) }
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // === О ПРИЛОЖЕНИИ ===
        SettingsSection(title = "ℹ️ О приложении") {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Neira Mobile",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Версия 1.0.0",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    Text(
                        text = "🧬 Мобильный интерфейс для живой программы Neira",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Text(
                        text = "Создано с ❤️ Claude & Neira",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary
        )
        
        Spacer(modifier = Modifier.height(12.dp))
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                content = content
            )
        }
    }
}

@Composable
fun SettingsSwitch(
    title: String,
    subtitle: String,
    icon: ImageVector,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        
        Spacer(modifier = Modifier.width(16.dp))
        
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
        
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange
        )
    }
}
