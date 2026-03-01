package com.neuralai.agent.core.llm

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.client.plugins.timeout
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Client for Google Gemini API (free tier).
 * Uses the REST endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
 */
@Singleton
class GeminiClient @Inject constructor(
    private val httpClient: HttpClient
) {
    var apiKey: String = ""

    suspend fun chat(
        systemPrompt: String,
        userMessage: String,
        model: String = "gemini-2.0-flash"
    ): String {
        if (apiKey.isBlank()) {
            return "⚠️ Gemini API key not set. Go to Settings (gear icon on top-left) and enter your free API key from https://aistudio.google.com/apikey"
        }

        return try {
            val url = "https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent?key=$apiKey"
            
            // Build the request body as a JSON string manually for simplicity
            val requestBody = buildGeminiRequestJson(systemPrompt, userMessage)

            val response = httpClient.post(url) {
                contentType(ContentType.Application.Json)
                timeout {
                    requestTimeoutMillis = 120000 // 2 minutes for cloud API
                    socketTimeoutMillis = 120000
                }
                setBody(requestBody)
            }

            val responseText: String = response.body()
            android.util.Log.d("GeminiClient", "Raw response (${responseText.length} chars): ${responseText.take(500)}")

            parseGeminiResponse(responseText)
        } catch (e: Exception) {
            android.util.Log.e("GeminiClient", "Gemini API error", e)
            "Error communicating with Gemini: ${e.message}"
        }
    }

    private fun buildGeminiRequestJson(systemPrompt: String, userMessage: String): String {
        // Escape special characters for JSON
        fun escapeJson(s: String): String = s
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")

        return """
        {
            "system_instruction": {
                "parts": [{"text": "${escapeJson(systemPrompt)}"}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "${escapeJson(userMessage)}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192
            }
        }
        """.trimIndent()
    }

    private fun parseGeminiResponse(responseText: String): String {
        return try {
            val json = org.json.JSONObject(responseText)
            
            // Check for error
            if (json.has("error")) {
                val error = json.getJSONObject("error")
                return "⚠️ Gemini API error: ${error.optString("message", "Unknown error")}"
            }

            val candidates = json.optJSONArray("candidates")
            if (candidates == null || candidates.length() == 0) {
                return "No response generated. The model may have filtered the content."
            }

            val firstCandidate = candidates.getJSONObject(0)
            val content = firstCandidate.optJSONObject("content")
            val parts = content?.optJSONArray("parts")
            
            if (parts == null || parts.length() == 0) {
                return "Empty response from Gemini."
            }

            val sb = StringBuilder()
            for (i in 0 until parts.length()) {
                val part = parts.getJSONObject(i)
                if (part.has("text")) {
                    sb.append(part.getString("text"))
                }
            }

            val result = sb.toString().trim()
            if (result.isEmpty()) "Empty response from Gemini." else result
        } catch (e: Exception) {
            android.util.Log.e("GeminiClient", "Parse error", e)
            "Failed to parse Gemini response: ${e.message}"
        }
    }
}
