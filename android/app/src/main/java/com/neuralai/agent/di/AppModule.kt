package com.neuralai.agent.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.HttpTimeout
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideHttpClient(): HttpClient {
        return HttpClient(CIO) {
            install(ContentNegotiation) {
                json(
                    Json {
                        ignoreUnknownKeys = true
                        prettyPrint = true
                        isLenient = true
                    },
                    contentType = io.ktor.http.ContentType.parse("application/x-ndjson")
                )
                json(
                    Json {
                        ignoreUnknownKeys = true
                        prettyPrint = true
                        isLenient = true
                    }
                )
            }
            install(HttpTimeout) {
                requestTimeoutMillis = 300000 // 5 minutes
                connectTimeoutMillis = 300000 // 5 minutes
                socketTimeoutMillis = 300000  // 5 minutes
            }
        }
    }

    @Provides
    @Singleton
    fun provideAppDatabase(@dagger.hilt.android.qualifiers.ApplicationContext appContext: android.content.Context): com.neuralai.agent.data.local.AppDatabase {
        return androidx.room.Room.databaseBuilder(
            appContext,
            com.neuralai.agent.data.local.AppDatabase::class.java,
            "neural_agent.db"
        ).build()
    }

    @Provides
    fun provideChatDao(database: com.neuralai.agent.data.local.AppDatabase): com.neuralai.agent.data.local.ChatDao {
        return database.chatDao()
    }

    @Provides
    fun provideMemoryDao(database: com.neuralai.agent.data.local.AppDatabase): com.neuralai.agent.data.local.MemoryDao {
        return database.memoryDao()
    }
}
