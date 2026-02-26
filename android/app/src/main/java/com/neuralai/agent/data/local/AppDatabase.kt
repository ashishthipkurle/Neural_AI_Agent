package com.neuralai.agent.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.neuralai.agent.data.entities.ChatMessage

@Database(
    entities = [ChatMessage::class, MemoryEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun chatDao(): ChatDao
    abstract fun memoryDao(): MemoryDao
}
