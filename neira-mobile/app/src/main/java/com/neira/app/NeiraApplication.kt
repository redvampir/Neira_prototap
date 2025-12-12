package com.neira.app

import android.app.Application
import com.neira.app.data.NeiraRepository

/**
 * NeiraApplication — инициализация приложения
 */
class NeiraApplication : Application() {
    
    lateinit var repository: NeiraRepository
        private set
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        repository = NeiraRepository()
    }
    
    companion object {
        lateinit var instance: NeiraApplication
            private set
    }
}
