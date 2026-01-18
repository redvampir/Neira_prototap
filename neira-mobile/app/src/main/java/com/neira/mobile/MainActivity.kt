package com.neira.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.neira.mobile.ui.NeiraApp
import com.neira.mobile.ui.theme.NeiraMobileTheme

/**
 * 🧬 MainActivity - Главный экран Neira Mobile
 * 
 * Здесь начинается путешествие в мобильный мир Neira!
 */
class MainActivity : ComponentActivity() {
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setContent {
            NeiraMobileTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    NeiraApp()
                }
            }
        }
    }
}
