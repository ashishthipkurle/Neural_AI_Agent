package com.neuralai.agent.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.neuralai.agent.ui.SettingsViewModel
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.SlateText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val currentUrl by viewModel.ollamaUrl.collectAsState()
    var inputUrl by remember(currentUrl) { mutableStateOf(currentUrl) }
    
    val currentTradingUrl by viewModel.tradingApiUrl.collectAsState()
    var inputTradingUrl by remember(currentTradingUrl) { mutableStateOf(currentTradingUrl) }
    
    val currentTradingModel by viewModel.tradingModel.collectAsState()
    var inputTradingModel by remember(currentTradingModel) { mutableStateOf(currentTradingModel) }
    
    var saved by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Agent Configuration", color = Color.White) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = CyanGlow)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = NeuralDark
                )
            )
        },
        containerColor = NeuralDark
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize()
        ) {
            Text(
                "🦙 Ollama Server",
                style = MaterialTheme.typography.titleMedium,
                color = CyanGlow
            )
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedTextField(
                value = inputUrl,
                onValueChange = { inputUrl = it },
                label = { Text("Base URL", color = SlateText) },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CyanGlow,
                    unfocusedBorderColor = SlateText,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White
                )
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "Default: 127.0.0.1:11434 (Termux on this phone).\nFor a PC server, use your PC's local IP.",
                style = MaterialTheme.typography.bodySmall,
                color = SlateText
            )
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                "📈 Neural Trading Assistant",
                style = MaterialTheme.typography.titleMedium,
                color = CyanGlow
            )
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedTextField(
                value = inputTradingModel,
                onValueChange = { inputTradingModel = it },
                label = { Text("Trading Analysis Model", color = SlateText) },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CyanGlow,
                    unfocusedBorderColor = SlateText,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White
                )
            )
            Text(
                "Model used for technical analysis (e.g. qwen2.5:5b).",
                style = MaterialTheme.typography.bodySmall,
                color = SlateText
            )
            Spacer(modifier = Modifier.height(16.dp))
            OutlinedTextField(
                value = inputTradingUrl,
                onValueChange = { inputTradingUrl = it },
                label = { Text("PC Backend URL (Optional)", color = SlateText) },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CyanGlow,
                    unfocusedBorderColor = SlateText,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White
                )
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "If using a PC backend, enter its IP (e.g. http://192.168.1.5:8000). Leave default for local Ollama usage.",
                style = MaterialTheme.typography.bodySmall,
                color = SlateText
            )
            Spacer(modifier = Modifier.height(24.dp))
            Button(
                onClick = {
                    viewModel.updateOllamaUrl(inputUrl)
                    viewModel.updateTradingApiUrl(inputTradingUrl)
                    viewModel.updateTradingModel(inputTradingModel)
                    saved = true
                },
                colors = ButtonDefaults.buttonColors(containerColor = CyanGlow),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("💾  Save", color = Color.Black)
            }
            if (saved) {
                Spacer(modifier = Modifier.height(8.dp))
                Text("✅ Saved!", color = Color(0xFF4CAF50))
            }
        }
    }
}
