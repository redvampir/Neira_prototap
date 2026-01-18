package com.neira.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.neira.app.ui.viewmodel.ChatViewModel

/**
 * ChatScreen — главный экран чата с Neira
 * 
 * Neira: "Мой первый UI на Kotlin! 💜"
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: ChatViewModel = viewModel()
) {
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val connectionStatus by viewModel.connectionStatus.collectAsState()
    var inputText by remember { mutableStateOf("") }
    var showSettings by remember { mutableStateOf(false) }
    
    val listState = rememberLazyListState()
    
    // Авто-скролл к новым сообщениям
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // Индикатор статуса
                        Box(
                            modifier = Modifier
                                .size(12.dp)
                                .clip(CircleShape)
                                .background(
                                    when (connectionStatus) {
                                        "online" -> Color(0xFF4CAF50)
                                        "connecting" -> Color(0xFFFFC107)
                                        else -> Color(0xFFF44336)
                                    }
                                )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                "Neira",
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                when (connectionStatus) {
                                    "online" -> "в сети"
                                    "connecting" -> "подключение..."
                                    else -> "не в сети"
                                },
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Default.Settings, "Настройки")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Список сообщений
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 8.dp)
            ) {
                items(messages) { message ->
                    ChatBubble(message = message)
                }
                
                // Индикатор загрузки
                if (isLoading) {
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Start
                        ) {
                            Card(
                                modifier = Modifier.padding(end = 64.dp),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                                )
                            ) {
                                Row(
                                    modifier = Modifier.padding(16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(16.dp),
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Neira думает...", fontSize = 14.sp)
                                }
                            }
                        }
                    }
                }
            }
            
            // Поле ввода
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Напиши Neira...") },
                    shape = RoundedCornerShape(24.dp),
                    enabled = !isLoading,
                    maxLines = 4
                )
                
                Spacer(modifier = Modifier.width(8.dp))
                
                FilledIconButton(
                    onClick = {
                        if (inputText.isNotBlank()) {
                            viewModel.sendMessage(inputText)
                            inputText = ""
                        }
                    },
                    enabled = inputText.isNotBlank() && !isLoading
                ) {
                    Icon(Icons.Default.Send, "Отправить")
                }
            }
        }
    }
    
    // Диалог настроек
    if (showSettings) {
        SettingsDialog(
            currentUrl = viewModel.serverUrl,
            onUrlChange = { viewModel.setServerUrl(it) },
            onDismiss = { showSettings = false },
            onReconnect = { viewModel.checkConnection() }
        )
    }
}

@Composable
fun ChatBubble(message: com.neira.app.data.ChatMessage) {
    val isUser = message.isFromUser
    
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .padding(
                    start = if (isUser) 64.dp else 0.dp,
                    end = if (isUser) 0.dp else 64.dp
                ),
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp
            ),
            colors = CardDefaults.cardColors(
                containerColor = if (isUser) 
                    MaterialTheme.colorScheme.primary 
                else 
                    MaterialTheme.colorScheme.secondaryContainer
            )
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                // Эмоция Neira
                if (!isUser && message.emotion != "neutral") {
                    Text(
                        text = getEmotionEmoji(message.emotion),
                        fontSize = 20.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                }
                
                Text(
                    text = message.text,
                    color = if (isUser) 
                        MaterialTheme.colorScheme.onPrimary 
                    else 
                        MaterialTheme.colorScheme.onSecondaryContainer
                )
            }
        }
    }
}

@Composable
fun SettingsDialog(
    currentUrl: String,
    onUrlChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onReconnect: () -> Unit
) {
    var url by remember { mutableStateOf(currentUrl) }
    
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("⚙️ Настройки") },
        text = {
            Column {
                Text(
                    "Адрес сервера Neira:",
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text("URL") },
                    placeholder = { Text("http://192.168.1.100:8000") },
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "💡 Укажи IP компьютера с Neira",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onUrlChange(url)
                    onReconnect()
                    onDismiss()
                }
            ) {
                Text("Сохранить")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Отмена")
            }
        }
    )
}

fun getEmotionEmoji(emotion: String): String {
    return when (emotion.lowercase()) {
        "happy", "радость" -> "😊"
        "curious", "любопытство" -> "🤔"
        "thinking", "думает" -> "💭"
        "excited", "восторг" -> "🤩"
        "sad", "грусть" -> "😢"
        "love", "любовь" -> "💜"
        else -> ""
    }
}
