package com.neuralai.agent.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import com.neuralai.agent.core.llm.OllamaClient
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val ollamaClient: OllamaClient
) : ViewModel() {

    private val prefs = context.getSharedPreferences("neural_settings", Context.MODE_PRIVATE)

    private val _ollamaUrl = MutableStateFlow(prefs.getString("ollama_url", "http://127.0.0.1:11434/api") ?: "http://127.0.0.1:11434/api")
    val ollamaUrl = _ollamaUrl.asStateFlow()

    private val _tradingApiUrl = MutableStateFlow(prefs.getString("trading_api_url", "http://10.0.2.2:8000") ?: "http://10.0.2.2:8000")
    val tradingApiUrl = _tradingApiUrl.asStateFlow()

    private val _tradingModel = MutableStateFlow(prefs.getString("trading_model", "qwen2.5:0.5b") ?: "qwen2.5:0.5b")
    val tradingModel = _tradingModel.asStateFlow()

    init {
        ollamaClient.baseUrl = _ollamaUrl.value
    }

    fun updateOllamaUrl(url: String) {
        val trimmed = url.trim()
        _ollamaUrl.value = trimmed
        ollamaClient.baseUrl = trimmed
        prefs.edit().putString("ollama_url", trimmed).apply()
    }

    fun updateTradingApiUrl(url: String) {
        val trimmed = url.trim()
        _tradingApiUrl.value = trimmed
        prefs.edit().putString("trading_api_url", trimmed).apply()
    }

    fun updateTradingModel(model: String) {
        val trimmed = model.trim()
        _tradingModel.value = trimmed
        prefs.edit().putString("trading_model", trimmed).apply()
    }
}
