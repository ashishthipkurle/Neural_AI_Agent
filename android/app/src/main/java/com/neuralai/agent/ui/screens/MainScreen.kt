package com.neuralai.agent.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.neuralai.agent.core.AIState
import com.neuralai.agent.data.entities.ChatMessage
import com.neuralai.agent.ui.components.AIGlobe
import com.neuralai.agent.ui.components.CommandFeed
import com.neuralai.agent.ui.components.StatusHUD
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark

import com.neuralai.agent.ui.components.GeometricBackground

@Composable
fun MainScreen(
    aiState: AIState,
    systemStatus: String,
    messages: List<ChatMessage>,
    isProcessing: Boolean,
    currentSpeechText: String,
    audioRms: Float = 0f,
    isWakeListening: Boolean = false,
    onSendMessage: (String) -> Unit,
    onStopProcessing: () -> Unit,
    onMicClick: () -> Unit,
    onDashboardClick: () -> Unit,
    onCameraClick: () -> Unit,
    onSettingsClick: () -> Unit,
    onHistoryClick: () -> Unit = {}
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(NeuralDark)
    ) {
        GeometricBackground(modifier = Modifier.fillMaxSize())

        Column(modifier = Modifier.fillMaxSize()) {
            Box(modifier = Modifier.fillMaxWidth()) {
                StatusHUD(aiState = aiState, systemStatus = systemStatus)
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(top = 8.dp, end = 8.dp)
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(CyanGlow.copy(alpha = 0.12f))
                        .clickable { onHistoryClick() },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Filled.History,
                        contentDescription = "History",
                        tint = CyanGlow,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                AIGlobe(
                    aiState = aiState,
                    audioRms = audioRms,
                    modifier = Modifier.size(300.dp)
                )
            }
            
            Box(modifier = Modifier.fillMaxHeight(0.40f)) {
                CommandFeed(
                    messages = messages,
                    isProcessing = isProcessing,
                    currentSpeechText = currentSpeechText,
                    isWakeListening = isWakeListening,
                    onSendMessage = onSendMessage,
                    onStopProcessing = onStopProcessing,
                    onMicClick = onMicClick
                )
            }
        }
    }
}
