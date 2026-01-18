package com.neira.mobile.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.neira.mobile.ui.screens.ChatScreen
import com.neira.mobile.ui.screens.SettingsScreen
import com.neira.mobile.ui.screens.StatusScreen
import com.neira.mobile.ui.viewmodel.ChatViewModel
import com.neira.mobile.ui.viewmodel.SettingsViewModel

/**
 * 🧬 Главное приложение Neira
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NeiraApp() {
    val navController = rememberNavController()
    val chatViewModel: ChatViewModel = viewModel()
    val settingsViewModel: SettingsViewModel = viewModel()
    
    val items = listOf(
        BottomNavItem("chat", "Чат", Icons.Default.Chat),
        BottomNavItem("status", "Статус", Icons.Default.Favorite),
        BottomNavItem("settings", "Настройки", Icons.Default.Settings)
    )
    
    Scaffold(
        bottomBar = {
            NavigationBar {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination
                
                items.forEach { item ->
                    NavigationBarItem(
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        label = { Text(item.label) },
                        selected = currentDestination?.hierarchy?.any { it.route == item.route } == true,
                        onClick = {
                            navController.navigate(item.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = "chat",
            modifier = Modifier.padding(innerPadding)
        ) {
            composable("chat") {
                ChatScreen(viewModel = chatViewModel)
            }
            composable("status") {
                StatusScreen(viewModel = chatViewModel)
            }
            composable("settings") {
                SettingsScreen(viewModel = settingsViewModel)
            }
        }
    }
}

data class BottomNavItem(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector
)
