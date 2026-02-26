package com.neuralai.agent.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.SlateText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
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
        Column(modifier = Modifier.padding(padding)) {
            Text("Settings: API Keys, Endpoints, Permissions", color = SlateText)
        }
    }
}
