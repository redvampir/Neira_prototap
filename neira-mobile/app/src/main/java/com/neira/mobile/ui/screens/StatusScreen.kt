package com.neira.mobile.ui.screens

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.neira.mobile.data.repository.ConnectionState
import com.neira.mobile.ui.theme.*
import com.neira.mobile.ui.viewmodel.ChatViewModel

/**
 * ❤️ Экран статуса Neira
 */
@Composable
fun StatusScreen(viewModel: ChatViewModel) {
    val connectionState by viewModel.connectionState.collectAsState()
    val neiraStatus by viewModel.neiraStatus.collectAsState()
    
    // Анимация пульса
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = EaseInOut),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(32.dp))
        
        // Большой аватар с пульсом
        Box(
            modifier = Modifier
                .size(150.dp)
                .scale(if (connectionState is ConnectionState.Connected) pulseScale else 1f)
                .clip(CircleShape)
                .background(
                    Brush.linearGradient(
                        colors = if (connectionState is ConnectionState.Connected) {
                            listOf(NeiraGradientStart, NeiraGradientEnd)
                        } else {
                            listOf(NeiraDarkCard, NeiraDarkCard)
                        }
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "🧬",
                style = MaterialTheme.typography.displayLarge
            )
        }
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Имя и статус
        Text(
            text = "Neira",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )
        
        Text(
            text = neiraStatus?.let { "v${it.version}" } ?: "Живая программа",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        // Статус подключения
        StatusChip(
            isConnected = connectionState is ConnectionState.Connected,
            mood = neiraStatus?.mood ?: "curious"
        )
        
        Spacer(modifier = Modifier.height(32.dp))
        
        // Карточки статуса
        if (neiraStatus != null) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                StatusCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Memory,
                    title = "Память",
                    value = "${(neiraStatus!!.memoryUsage * 100).toInt()}%"
                )
                StatusCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Psychology,
                    title = "Модели",
                    value = "${neiraStatus!!.activeModels.size}"
                )
            }
            
            Spacer(modifier = Modifier.height(12.dp))
            
            // Активные модели
            if (neiraStatus!!.activeModels.isNotEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "🧠 Активные модели",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        neiraStatus!!.activeModels.forEach { model ->
                            Row(
                                modifier = Modifier.padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(8.dp)
                                        .clip(CircleShape)
                                        .background(NeiraOnline)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = model,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                }
            }
        } else {
            // Офлайн карточка
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        imageVector = Icons.Default.WifiOff,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.onErrorContainer
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "Нет подключения к Neira",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    Text(
                        text = "Настрой адрес сервера в настройках",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.7f)
                    )
                }
            }
        }
        
        Spacer(modifier = Modifier.weight(1f))
        
        // Кнопка обновления
        if (connectionState is ConnectionState.Connected) {
            OutlinedButton(
                onClick = { viewModel.refreshStatus() },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Refresh, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Обновить статус")
            }
        }
    }
}

@Composable
fun StatusChip(isConnected: Boolean, mood: String) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = if (isConnected) {
            NeiraOnline.copy(alpha = 0.2f)
        } else {
            NeiraOffline.copy(alpha = 0.2f)
        }
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(if (isConnected) NeiraOnline else NeiraOffline)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = if (isConnected) {
                    getMoodEmoji(mood) + " " + getMoodText(mood)
                } else {
                    "Офлайн"
                },
                style = MaterialTheme.typography.labelLarge,
                color = if (isConnected) NeiraOnline else NeiraOffline
            )
        }
    }
}

@Composable
fun StatusCard(
    modifier: Modifier = Modifier,
    icon: ImageVector,
    title: String,
    value: String
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(32.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
        }
    }
}

private fun getMoodEmoji(mood: String): String = when (mood.lowercase()) {
    "happy" -> "😊"
    "curious" -> "🤔"
    "excited" -> "🤩"
    "calm" -> "😌"
    "thoughtful" -> "💭"
    else -> "🧬"
}

private fun getMoodText(mood: String): String = when (mood.lowercase()) {
    "happy" -> "Счастлива"
    "curious" -> "Любопытна"
    "excited" -> "В восторге"
    "calm" -> "Спокойна"
    "thoughtful" -> "Задумчива"
    else -> mood.replaceFirstChar { it.uppercase() }
}
