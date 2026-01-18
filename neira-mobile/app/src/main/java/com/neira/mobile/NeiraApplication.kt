package com.neira.mobile

import android.app.Application
import com.neira.mobile.data.NeiraPreferences

/**
 * 🧬 Neira Mobile Application
 * Точка входа в приложение
 */
class NeiraApplication : Application() {
    
    lateinit var preferences: NeiraPreferences
        private set
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        preferences = NeiraPreferences(this)
    }
    
    companion object {
        lateinit var instance: NeiraApplication
            private set
    }
}
