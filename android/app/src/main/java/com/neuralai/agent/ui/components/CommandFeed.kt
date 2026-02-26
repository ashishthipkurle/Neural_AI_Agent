package com.neuralai.agent.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.StopCircle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.neuralai.agent.data.entities.ChatMessage
import com.neuralai.agent.ui.theme.CyanDim
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.SlateText

@Composable
fun CommandFeed(
    messages: List<ChatMessage>,
    isProcessing: Boolean,
    currentSpeechText: String,
    isWakeListening: Boolean,
    onSendMessage: (String) -> Unit,
    onStopProcessing: () -> Unit,
    onMicClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    var inputText by remember { mutableStateOf("") }

    LaunchedEffect(currentSpeechText) {
        if (currentSpeechText.isNotBlank()) {
            inputText = currentSpeechText
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(NeuralDark.copy(alpha = 0.8f))
            .padding(16.dp)
    ) {
        // Message List
        LazyColumn(
            modifier = Modifier.weight(1f),
            reverseLayout = true
        ) {
            items(messages.reversed()) { msg ->
                MessageBubble(message = msg)
                Spacer(modifier = Modifier.height(8.dp))
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Input Area
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onMicClick) {
                Icon(
                    imageVector = if (isWakeListening) Icons.Default.Mic else Icons.Default.MicOff,
                    contentDescription = if (isWakeListening) "Turn Off 24/7 Listening" else "Turn On 24/7 Listening",
                    tint = if (isWakeListening) CyanGlow else SlateText
                )
            }
            
            OutlinedTextField(
                value = inputText,
                onValueChange = { inputText = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Command Neural Agent...", color = SlateText.copy(alpha = 0.5f)) },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CyanGlow,
                    unfocusedBorderColor = CyanDim,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = SlateText
                ),
                shape = RoundedCornerShape(24.dp),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(
                    onSend = {
                        if (inputText.isNotBlank() && !isProcessing) {
                            onSendMessage(inputText)
                            inputText = ""
                        }
                    }
                ),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.width(8.dp))
            
            if (isProcessing) {
                IconButton(onClick = onStopProcessing) {
                    Icon(
                        imageVector = Icons.Default.StopCircle,
                        contentDescription = "Stop",
                        tint = Color.Red
                    )
                }
            } else {
                IconButton(
                    onClick = {
                        if (inputText.isNotBlank()) {
                            onSendMessage(inputText)
                            inputText = ""
                        }
                    },
                    enabled = inputText.isNotBlank()
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (inputText.isNotBlank()) CyanGlow else SlateText.copy(alpha = 0.5f)
                    )
                }
            }
        }
    }
}

@Composable
fun MessageBubble(message: ChatMessage) {
    val isUser = message.sender == "user"
    val isSystem = message.sender == "system"
    
    val backgroundColor = when {
        isUser -> CyanDim.copy(alpha = 0.3f)
        isSystem -> Color.DarkGray.copy(alpha = 0.3f)
        else -> Color.Transparent
    }
    
    val alignment = if (isUser) Alignment.CenterEnd else Alignment.CenterStart
    val textColor = if (isSystem) SlateText.copy(alpha = 0.7f) else Color.White

    Box(
        modifier = Modifier.fillMaxWidth(),
        contentAlignment = alignment
    ) {
        Surface(
            color = backgroundColor,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.widthIn(max = 300.dp)
        ) {
            Text(
                text = message.text,
                color = textColor,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyLarge
            )
        }
    }
}
