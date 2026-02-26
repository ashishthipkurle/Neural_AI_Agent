package com.neuralai.agent.core.llm

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.client.request.header
import io.ktor.client.plugins.timeout
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OllamaClient @Inject constructor(
    private val httpClient: HttpClient
) {
    // Base URL pointing to the phone's native localhost (Termux)
    private val baseUrl = "http://127.0.0.1:11434/api"
    
    suspend fun chat(
        model: String,
        systemPrompt: String,
        userMessage: String,
        images: List<String>? = null
    ): String {
        return try {
            val messages = mutableListOf(
                ChatMsg(role = "system", content = systemPrompt)
            )
            
            if (images.isNullOrEmpty()) {
                messages.add(ChatMsg(role = "user", content = userMessage))
            } else {
                messages.add(ChatMsg(role = "user", content = userMessage, images = images))
            }
            
            val response = httpClient.post("$baseUrl/chat") {
                contentType(ContentType.Application.Json)
                header(io.ktor.http.HttpHeaders.Accept, "application/json")
                timeout {
                    requestTimeoutMillis = 300000 // 5 minutes
                    socketTimeoutMillis = 300000
                }
                setBody(
                    ChatRequest(
                        model = model,
                        messages = messages,
                        stream = false
                    )
                )
            }
            
            val responseText: String = response.body()
            
            // Ollama might return multiple JSON objects in one stream (ndjson) even when stream=false
            // We split by newline and parse each valid JSON object
            val jsonDecoder = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }
            val lines = responseText.trim().split("\n")
            
            var fullContent = ""
            for (line in lines) {
                if (line.isNotBlank()) {
                    try {
                        val chunk = jsonDecoder.decodeFromString<ChatResponse>(line)
                        fullContent += chunk.message.content
                    } catch (e: Exception) {
                        // Skip malformed chunks
                    }
                }
            }
            
            if (fullContent.isEmpty()) {
                throw Exception("Failed to parse response body")
            }
            
            fullContent
        } catch (e: Exception) {
            "Error communicating with Neural Core: ${e.message}"
        }
    }
}
