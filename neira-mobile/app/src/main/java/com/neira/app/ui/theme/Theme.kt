package com.neira.app.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// Цвета Neira — фиолетово-розовые оттенки
private val NeiraPurple = Color(0xFF9C27B0)
private val NeiraPink = Color(0xFFE91E63)
private val NeiraLight = Color(0xFFF3E5F5)
private val NeiraDark = Color(0xFF4A148C)

private val DarkColorScheme = darkColorScheme(
    primary = NeiraPurple,
    secondary = NeiraPink,
    tertiary = Color(0xFF03DAC6),
    background = Color(0xFF1A1A2E),
    surface = Color(0xFF16213E),
    primaryContainer = Color(0xFF2D2D44),
    secondaryContainer = Color(0xFF3D3D5C),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = Color.White,
    onSurface = Color.White
)

private val LightColorScheme = lightColorScheme(
    primary = NeiraPurple,
    secondary = NeiraPink,
    tertiary = Color(0xFF00BCD4),
    background = Color(0xFFFFFBFE),
    surface = Color(0xFFFFFBFE),
    primaryContainer = NeiraLight,
    secondaryContainer = Color(0xFFFCE4EC),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = Color(0xFF1C1B1F),
    onSurface = Color(0xFF1C1B1F)
)

@Composable
fun NeiraTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,  // Отключаем для консистентности
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primaryContainer.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
