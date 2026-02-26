package com.neuralai.agent.data.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "chat_messages")
data class ChatMessage(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val text: String,
    val sender: String, // "user", "agent", "system"
    val timestamp: Long = System.currentTimeMillis()
)
