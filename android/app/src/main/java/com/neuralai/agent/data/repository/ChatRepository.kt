package com.neuralai.agent.data.repository

import com.neuralai.agent.data.entities.ChatMessage
import com.neuralai.agent.data.local.ChatDao
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ChatRepository @Inject constructor(
    private val chatDao: ChatDao
) {
    
    suspend fun getRecentHistory(limit: Int = 10): List<ChatMessage> {
        return chatDao.getRecentMessages(limit).reversed() // Order by desc in query for limit, reverse for display
    }
    
    fun getAllMessagesFlow(): Flow<List<ChatMessage>> {
        return chatDao.getAllMessagesFlow()
    }
    
    suspend fun addMessage(message: ChatMessage) {
        chatDao.insertMessage(message)
    }
    
    suspend fun clearHistory() {
        chatDao.clearHistory()
    }

    suspend fun deleteMessage(message: ChatMessage) {
        chatDao.deleteMessage(message)
    }
}
