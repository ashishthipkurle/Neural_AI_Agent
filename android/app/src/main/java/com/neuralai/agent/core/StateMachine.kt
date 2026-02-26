package com.neuralai.agent.core

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class StateMachine @Inject constructor() {
    private val _currentState = MutableStateFlow(AIState.IDLE)
    val currentState: StateFlow<AIState> = _currentState.asStateFlow()
    
    private val _systemStatus = MutableStateFlow("SYSTEM READY")
    val systemStatus: StateFlow<String> = _systemStatus.asStateFlow()

    fun setState(state: AIState, statusMessage: String? = null) {
        _currentState.value = state
        if (statusMessage != null) {
            _systemStatus.value = statusMessage
        } else {
            _systemStatus.value = when(state) {
                AIState.IDLE -> "READY"
                AIState.LISTENING -> "LISTENING..."
                AIState.THINKING -> "PROCESSING NEURAL PATHWAYS..."
                AIState.SPEAKING -> "RESPONDING..."
                AIState.EXECUTING -> "EXECUTING COMMAND..."
                AIState.ERROR -> "SYSTEM ERROR"
            }
        }
    }
}
