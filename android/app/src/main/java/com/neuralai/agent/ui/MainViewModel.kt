package com.neuralai.agent.ui

import android.app.Application
import android.content.Intent
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.neuralai.agent.core.AIState
import com.neuralai.agent.core.NeuralAgent
import com.neuralai.agent.core.StateMachine
import com.neuralai.agent.data.entities.ChatMessage
import com.neuralai.agent.data.repository.ChatRepository
import com.neuralai.agent.core.skills.vision.VisionEngine
import com.neuralai.agent.core.voice.TTSEngine
import com.neuralai.agent.core.voice.VoiceEngine
import com.neuralai.agent.services.WakeWordService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val application: Application,
    private val neuralAgent: NeuralAgent,
    private val stateMachine: StateMachine,
    private val chatRepository: ChatRepository,
    private val ttsEngine: TTSEngine,
    private val voiceEngine: VoiceEngine,
    val visionEngine: VisionEngine
) : AndroidViewModel(application) {

    val aiState: StateFlow<AIState> = stateMachine.currentState
    val systemStatus: StateFlow<String> = stateMachine.systemStatus
    
    val audioRms: StateFlow<Float> = WakeWordService.audioRms

    val messages = chatRepository.getAllMessagesFlow()
    
    private val _isProcessing = MutableStateFlow(false)
    val isProcessing: StateFlow<Boolean> = _isProcessing.asStateFlow()

    // 24/7 Background Listening State (Stable)
    val isWakeListening: StateFlow<Boolean> = WakeWordService.isServiceRunning

    init {
        viewModelScope.launch {
            if (chatRepository.getRecentHistory(1).isEmpty()) {
                addMessage(ChatMessage(text = "System initialized. Neural Agent ready.", sender = "system"))
            }
        }
        
        // Auto-start background listener by default
        startWakeWordService()
        
        // Sync internal AI state with the background service state
        viewModelScope.launch {
            WakeWordService.isServiceRunning.collect { running ->
                if (running && stateMachine.currentState.value == AIState.IDLE) {
                    stateMachine.setState(AIState.LISTENING, "LISTENING 24/7...")
                }
            }
        }
        
        // Observe background commands
        viewModelScope.launch {
            WakeWordService.wakeCommand.collect { command ->
                if (command.isNotBlank()) {
                    submitCommand(command)
                } else {
                    val greetings = listOf(
                        "Hey there! How can I help?",
                        "Hi, I'm listening.",
                        "Hey, what's up?",
                        "Ready for command.",
                        "Yes? I'm here.",
                        "Neural online. Go ahead."
                    )
                    val greeting = greetings.random()
                    viewModelScope.launch {
                        addMessage(ChatMessage(text = greeting, sender = "agent"))
                        ttsEngine.speak(greeting)
                        WakeWordService.extendWakeWindow()
                    }
                }
            }
        }
    }

    fun startWakeWordService() {
        try {
            val intent = Intent(application, WakeWordService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                application.startForegroundService(intent)
            } else {
                application.startService(intent)
            }
        } catch (e: Exception) {
            viewModelScope.launch {
                addMessage(ChatMessage(text = "Wake word service: ${e.message}", sender = "system"))
            }
        }
    }

    fun stopWakeWordService() {
        try {
            application.stopService(Intent(application, WakeWordService::class.java))
        } catch (_: Exception) {}
    }

    fun submitCommand(text: String) {
        if (text.isBlank()) return
        
        _isProcessing.value = true
        
        viewModelScope.launch {
            addMessage(ChatMessage(text = text, sender = "user"))
            try {
                val response = neuralAgent.processInput(text)
                addMessage(ChatMessage(text = response, sender = "agent"))
                ttsEngine.speakAndWaitForCompletion(response)
            } catch (e: Exception) {
                addMessage(ChatMessage(text = "Error: ${e.message}", sender = "system"))
                stateMachine.setState(AIState.ERROR, "SYSTEM ERROR")
            } finally {
                _isProcessing.value = false
                WakeWordService.extendWakeWindow() // Keep listening window open for next 15s after execution
                // Return to listening state if background listening is active
                if (isWakeListening.value) {
                    stateMachine.setState(AIState.LISTENING, "LISTENING 24/7...")
                } else {
                    stateMachine.setState(AIState.IDLE, "READY")
                }
            }
        }
    }
    
    fun stopProcessing() {
        _isProcessing.value = false
        if (isWakeListening.value) {
            stateMachine.setState(AIState.LISTENING, "LISTENING 24/7...")
        } else {
            stateMachine.setState(AIState.IDLE, "READY")
        }
    }
    
    val currentSpeechText: StateFlow<String> = WakeWordService.partialSpeech

    fun toggleListening() {
        if (isWakeListening.value) {
            // TURN OFF 24/7 LISTENING
            stopWakeWordService()
            stateMachine.setState(AIState.IDLE, "READY")
        } else {
            // TURN ON 24/7 LISTENING
            startWakeWordService()
            stateMachine.setState(AIState.LISTENING, "LISTENING 24/7...")
        }
    }

    private suspend fun addMessage(message: ChatMessage) {
        chatRepository.addMessage(message)
    }

    fun clearAllMessages() {
        viewModelScope.launch {
            chatRepository.clearHistory()
        }
    }

    fun deleteMessage(message: ChatMessage) {
        viewModelScope.launch {
            chatRepository.deleteMessage(message)
        }
    }

    fun startNewChat() {
        viewModelScope.launch {
            addMessage(ChatMessage(text = "New conversation started.", sender = "system"))
        }
    }
}

