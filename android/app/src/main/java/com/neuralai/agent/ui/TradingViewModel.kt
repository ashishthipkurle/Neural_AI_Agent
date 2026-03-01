package com.neuralai.agent.ui

import android.content.Context
import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.neuralai.agent.core.llm.OllamaClient
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import javax.inject.Inject

data class TradingSignal(
    val id: String,
    val asset: String,
    val direction: String,
    val type: String,
    val confidence: Float,
    val entryPrice: Float,
    val stopPrice: Float = 0f,
    val targetPrice: Float = 0f,
    val state: String = "STAGED",
    val reason: String = ""
)

data class RagStats(
    val direction: String,
    val dominance: Float,
    val totalMatches: String
)

@HiltViewModel
class TradingViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val ollamaClient: OllamaClient
) : ViewModel() {

    private val prefs = context.getSharedPreferences("neural_settings", Context.MODE_PRIVATE)

    private val _scanStatus = MutableStateFlow("STANDBY")
    val scanStatus = _scanStatus.asStateFlow()

    private val _scanCount = MutableStateFlow(0)
    val scanCount = _scanCount.asStateFlow()

    private val _analysisSummary = MutableStateFlow("Waiting for first chart scan...")
    val analysisSummary = _analysisSummary.asStateFlow()

    private val _ragStats = MutableStateFlow<RagStats?>(null)
    val ragStats = _ragStats.asStateFlow()

    private val _activeSignals = MutableStateFlow<List<TradingSignal>>(emptyList())
    val activeSignals = _activeSignals.asStateFlow()

    private val _chartYMin = MutableStateFlow(0f)
    val chartYMin = _chartYMin.asStateFlow()

    private val _chartYMax = MutableStateFlow(100f)
    val chartYMax = _chartYMax.asStateFlow()

    // Terminal logging
    private val _logs = MutableStateFlow<List<String>>(listOf("> NEURAL_VISION INITIALIZED", "> STATUS: STANDBY"))
    val logs = _logs.asStateFlow()

    private fun getModel(): String {
        return prefs.getString("trading_model", "qwen2.5:0.5b") ?: "qwen2.5:0.5b"
    }

    private fun addLog(msg: String) {
        val currentLogs = _logs.value.toMutableList()
        if (currentLogs.size > 15) currentLogs.removeAt(0)
        currentLogs.add("> $msg")
        _logs.value = currentLogs
    }

    fun clearChartData() {
        _scanStatus.value = "STANDBY"
        _analysisSummary.value = "Waiting for first chart scan..."
        _ragStats.value = null
        _activeSignals.value = emptyList()
        _chartYMin.value = 0f
        _chartYMax.value = 100f
        addLog("Cleared stale data")
    }

    fun runScan(bitmap: Bitmap, currentUrl: String) {
        if (_scanStatus.value == "CAPTURING" || _scanStatus.value == "ANALYZING") return

        _scanStatus.value = "CAPTURING"
        addLog("capture_screen: running")

        viewModelScope.launch(Dispatchers.IO) {
            try {
                // 1. Convert Bitmap to Base64
                val outputStream = ByteArrayOutputStream()
                bitmap.compress(Bitmap.CompressFormat.JPEG, 60, outputStream)
                val byteArray = outputStream.toByteArray()
                val base64Encoded = Base64.encodeToString(byteArray, Base64.NO_WRAP)

                _scanStatus.value = "ANALYZING"
                val assetName = currentUrl.substringAfterLast("/").uppercase()
                addLog("analysis: sending to local Ollama (${getModel()}) for $assetName")

                val systemPrompt = """You are an expert technical analyst. Analyze the chart and respond ONLY with a single valid JSON object. No explanation text, no markdown, just pure JSON.

CRITICAL RULES:
- support_level and resistance_level MUST be REAL price numbers from the chart (e.g. 25100.0, 25350.0 for NIFTY). NEVER use small decimals like 0.75.
- recommendation must be exactly one of: "BUY", "SELL", or "HOLD" (pick only ONE).
- direction must be exactly one of: "UPWARD", "DOWNWARD", or "SIDEWAYS".
- confidence is an integer from 0 to 100.

Example for NIFTY at ~25181:
{"direction":"DOWNWARD","confidence":70,"recommendation":"SELL","analysis_summary":"NIFTY showing bearish momentum with breakdown below 25200 support.","support_level":25100.0,"resistance_level":25350.0,"reason":"Price rejected at resistance and forming lower highs."}"""

                val userMessage = "Chart: $assetName from $currentUrl. The current visible price is around ${assetName}'s typical range. Return ONLY valid JSON with real price levels from the chart."

                // 2. Call local Ollama with the chart image
                val response = ollamaClient.chat(
                    model = getModel(),
                    systemPrompt = systemPrompt,
                    userMessage = userMessage,
                    images = listOf(base64Encoded)
                )

                // Debug: log exact response from Ollama
                Log.d("TradingViewModel", "Ollama response (${response.length} chars): ${response.take(200)}")

                // Check for Ollama error responses (e.g. model not found, connection errors)
                val isError = response.startsWith("Ollama error") ||
                              response.startsWith("Error communicating") ||
                              response.startsWith("Scan failed") ||
                              (response.contains("error", ignoreCase = true) && !response.contains("direction"))
                
                if (isError) {
                    _analysisSummary.value = response
                    addLog("analysis: FAILED - ${response.take(60)}")
                    _scanStatus.value = "STANDBY"
                    return@launch
                }

                addLog("analysis: response received")

                // 3. Try to parse structured JSON response
                try {
                    // Find JSON block in the response
                    val jsonStr = extractJson(response)
                    if (jsonStr != null) {
                        val json = JSONObject(jsonStr)
                        val direction = json.optString("direction", "UNKNOWN")
                        val confidence = json.optDouble("confidence", 50.0).toFloat()
                        val recommendation = json.optString("recommendation", "HOLD")
                        val summary = json.optString("analysis_summary", response.take(300))
                        val support = json.optDouble("support_level", 0.0).toFloat()
                        val resistance = json.optDouble("resistance_level", 0.0).toFloat()
                        val reason = json.optString("reason", "")

                        _analysisSummary.value = summary
                        _ragStats.value = RagStats(
                            direction = direction,
                            dominance = confidence,
                            totalMatches = "LOCAL"
                        )

                        // Generate a signal from the recommendation
                        if (recommendation != "HOLD" && (support > 0f || resistance > 0f)) {
                            val signal = TradingSignal(
                                id = "local_${System.currentTimeMillis()}",
                                asset = currentUrl.substringAfterLast("/").uppercase(),
                                direction = if (recommendation == "BUY") "LONG" else "SHORT",
                                type = "AI_VISION",
                                confidence = confidence / 100f,
                                entryPrice = if (recommendation == "BUY") support else resistance,
                                stopPrice = if (recommendation == "BUY") (support * 0.98f) else (resistance * 1.02f),
                                targetPrice = if (recommendation == "BUY") resistance else support,
                                state = "STAGED",
                                reason = reason
                            )
                            _activeSignals.value = listOf(signal)

                            // Set chart bounds for overlay
                            if (support > 0f && resistance > 0f) {
                                val range = resistance - support
                                _chartYMin.value = support - range * 0.2f
                                _chartYMax.value = resistance + range * 0.2f
                            }
                        }
                    } else {
                        // Not valid JSON, just use the raw text response
                        _analysisSummary.value = response.take(500)
                    }
                } catch (e: Exception) {
                    Log.w("TradingViewModel", "Could not parse structured response, using raw text", e)
                    _analysisSummary.value = response.take(500)
                }

                _scanCount.value += 1
                _scanStatus.value = "DONE"
                addLog("analysis: DONE (total: ${_scanCount.value})")

                kotlinx.coroutines.delay(3000)
                _scanStatus.value = "STANDBY"

            } catch (e: Exception) {
                Log.e("TradingViewModel", "Scan failed", e)
                _scanStatus.value = "STANDBY"
                _analysisSummary.value = "Scan failed: ${e.message}"
                addLog("analysis: FAILED - ${e.message}")
            }
        }
    }

    /** Extract first JSON object from a string that may contain markdown fences or surrounding text */
    private fun extractJson(text: String): String? {
        // Try to find JSON in code fences first
        val fencePattern = Regex("```(?:json)?\\s*\\n?(\\{.*?\\})\\s*```", RegexOption.DOT_MATCHES_ALL)
        fencePattern.find(text)?.let { return it.groupValues[1] }

        // Try to find a raw JSON object
        val braceStart = text.indexOf('{')
        val braceEnd = text.lastIndexOf('}')
        if (braceStart >= 0 && braceEnd > braceStart) {
            val candidate = text.substring(braceStart, braceEnd + 1)
            // Validate it's parseable
            try {
                JSONObject(candidate)
                return candidate
            } catch (_: Exception) {}
        }
        return null
    }
}
