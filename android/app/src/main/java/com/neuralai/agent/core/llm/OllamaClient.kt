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
    // Base URL pointing to the phone's local Ollama (Termux).
    // Can be updated via Settings to point to a different host.
    var baseUrl = "http://127.0.0.1:11434/api"
    
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
                    requestTimeoutMillis = 1800000 // 30 minutes for slow on-device models
                    socketTimeoutMillis = 1800000
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
            
            // Log raw response for debugging
            android.util.Log.d("OllamaClient", "Raw response (${responseText.length} chars): ${responseText.take(500)}")
            
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
                        android.util.Log.w("OllamaClient", "kotlinx parse failed for line: ${line.take(200)}", e)
                    }
                }
            }
            
            // Fallback: try parsing with org.json if kotlinx failed
            if (fullContent.isEmpty()) {
                try {
                    val json = org.json.JSONObject(responseText.trim())
                    val msg = json.optJSONObject("message")
                    fullContent = msg?.optString("content", "") ?: ""
                    android.util.Log.d("OllamaClient", "Fallback JSON parse got: ${fullContent.take(200)}")
                } catch (e: Exception) {
                    android.util.Log.w("OllamaClient", "Fallback JSON parse also failed", e)
                }
            }
            
            // Last resort: if response looks like it contains text, return cleaned version
            if (fullContent.isEmpty() && responseText.isNotBlank()) {
                android.util.Log.e("OllamaClient", "All parsers failed. Raw response: $responseText")
                // Check if Ollama returned an error message
                try {
                    val json = org.json.JSONObject(responseText.trim())
                    val error = json.optString("error", "")
                    if (error.isNotEmpty()) {
                        fullContent = "Ollama error: $error"
                    }
                } catch (_: Exception) {}
                if (fullContent.isEmpty()) {
                    throw Exception("Failed to parse response body")
                }
            }
            
            fullContent
        } catch (e: Exception) {
            "Error communicating with Neural Core: ${e.message}"
        }
    }
}
 