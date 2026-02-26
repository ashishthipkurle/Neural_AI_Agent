package com.neuralai.agent.data.repository

import com.neuralai.agent.data.local.MemoryDao
import com.neuralai.agent.data.local.MemoryEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MemoryRepository @Inject constructor(
    private val memoryDao: MemoryDao
) {
    
    suspend fun storeMemory(text: String, importanceScore: Float = 1.0f) {
        val memory = MemoryEntity(
            text = text,
            importanceScore = importanceScore
        )
        memoryDao.insertMemory(memory)
    }

    suspend fun searchContext(query: String, topK: Int = 3): String {
        val allMemories = memoryDao.getAllMemories()
        if (allMemories.isEmpty()) return "No specific memories found."

        // Basic keyword matching / pseudo-semantic search
        val queryWords = query.lowercase().split("\\s+".toRegex()).filter { it.length > 3 }
        
        val scoredMemories = allMemories.map { memory ->
            val memoryLower = memory.text.lowercase()
            var score = 0
            for (word in queryWords) {
                if (memoryLower.contains(word)) score++
            }
            // Boost exact phrase matches
            if (memoryLower.contains(query.lowercase())) score += 5
            
            // Factor in manual importance
            val finalScore = score * memory.importanceScore
            Pair(memory, finalScore)
        }.filter { it.second > 0 } // Only keep relevant memories
        
        val topMemories = scoredMemories
            .sortedByDescending { it.second }
            .take(topK)
            .map { it.first.text }

        return if (topMemories.isNotEmpty()) {
            "Relevant memories: " + topMemories.joinToString("; ")
        } else {
            "No specific memories found."
        }
    }
    
    fun getMemoriesFlow(limit: Int = 50): Flow<List<MemoryEntity>> {
        return memoryDao.getMemoriesFlow(limit)
    }
    
    suspend fun clearMemories() {
        memoryDao.clearMemories()
    }
}
