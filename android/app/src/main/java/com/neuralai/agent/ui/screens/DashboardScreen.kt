package com.neuralai.agent.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.SlateText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(onBack: () -> Unit) {
    var selectedTabIndex by remember { mutableStateOf(0) }
    val tabs = listOf("Tasks", "Learning", "Conformance", "Telegram")

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("System Dashboard", color = Color.White) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = CyanGlow)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = NeuralDark,
                    titleContentColor = Color.White
                )
            )
        },
        containerColor = NeuralDark
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            TabRow(
                selectedTabIndex = selectedTabIndex,
                containerColor = NeuralDark,
                contentColor = CyanGlow
            ) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTabIndex == index,
                        onClick = { selectedTabIndex = index },
                        text = { 
                            Text(
                                text = title, 
                                color = if (selectedTabIndex == index) CyanGlow else SlateText
                            ) 
                        }
                    )
                }
            }

            // Tab Content 
            Box(modifier = Modifier.fillMaxSize().background(NeuralDark)) {
                // Placeholder content for now
                when (selectedTabIndex) {
                    0 -> Text("Active Tasks / Mission Queue", color = SlateText)
                    1 -> Text("Learning Experiences & Patterns", color = SlateText)
                    2 -> Text("Architecture Conformance Checks", color = SlateText)
                    3 -> Text("Telegram Bot Status", color = SlateText)
                }
            }
        }
    }
}
