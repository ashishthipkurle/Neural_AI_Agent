package com.neuralai.agent.ui

import android.graphics.Bitmap
import android.webkit.WebView
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.neuralai.agent.core.llm.OllamaClient
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject
import android.util.Base64
import java.io.ByteArrayOutputStream

data class TradingSignal(
    val type: String,       // "BUY", "SELL", "HOLD"
    val confidence: Float,  // 0.0 - 1.0
    val reason: String
)

@HiltViewModel
class TradingViewModel @Inject constructor(
    private val ollamaClient: OllamaClient
) : ViewModel() {

    private val _analysisResult = MutableStateFlow("")
    val analysisResult: StateFlow<String> = _analysisResult.asStateFlow()

    private val _signals = MutableStateFlow<List<TradingSignal>>(emptyList())
    val signals: StateFlow<List<TradingSignal>> = _signals.asStateFlow()

    private val _riskLevel = MutableStateFlow("N/A")
    val riskLevel: StateFlow<String> = _riskLevel.asStateFlow()

    private val _isAnalyzing = MutableStateFlow(false)
    val isAnalyzing: StateFlow<Boolean> = _isAnalyzing.asStateFlow()

    fun analyzeChart(webView: WebView) {
        viewModelScope.launch {
            _isAnalyzing.value = true
            _analysisResult.value = "Capturing chart..."

            try {
                val bitmap = captureWebView(webView)
                val base64 = bitmapToBase64(bitmap)

                _analysisResult.value = "Sending to AI for analysis..."

                val response = withContext(Dispatchers.IO) {
                    ollamaClient.chat(
                        model = "qwen2.5:0.5b",
                        systemPrompt = """You are an expert financial chart analyst. Analyze the trading chart provided.
                            Identify: trend direction, support/resistance levels, key patterns, and provide a signal (BUY/SELL/HOLD) with a confidence percentage.
                            Be concise.""".trimIndent(),
                        userMessage = "Analyze this trading chart. Base64 image data: $base64"
                    )
                }

                _analysisResult.value = response

                // Parse simple signal from response
                val upper = response.uppercase()
                val signal = when {
                    upper.contains("BUY") -> TradingSignal("BUY", 0.7f, response.take(100))
                    upper.contains("SELL") -> TradingSignal("SELL", 0.7f, response.take(100))
                    else -> TradingSignal("HOLD", 0.5f, response.take(100))
                }
                _signals.value = listOf(signal)
                _riskLevel.value = if (signal.type == "HOLD") "LOW" else "MEDIUM"

            } catch (e: Exception) {
                _analysisResult.value = "Analysis failed: ${e.message}"
            } finally {
                _isAnalyzing.value = false
            }
        }
    }

    private suspend fun captureWebView(webView: WebView): Bitmap = withContext(Dispatchers.Main) {
        val bitmap = Bitmap.createBitmap(webView.width, webView.height, Bitmap.Config.ARGB_8888)
        val canvas = android.graphics.Canvas(bitmap)
        webView.draw(canvas)
        bitmap
    }

    private fun bitmapToBase64(bitmap: Bitmap): String {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 70, stream)
        return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP)
    }
}
