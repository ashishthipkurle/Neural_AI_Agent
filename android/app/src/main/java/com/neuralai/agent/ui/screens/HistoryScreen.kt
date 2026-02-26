package com.neuralai.agent.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.neuralai.agent.data.entities.ChatMessage
import com.neuralai.agent.ui.MainViewModel
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.SlateText
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(
    messages: List<ChatMessage>,
    onBack: () -> Unit,
    viewModel: MainViewModel = hiltViewModel()
) {
    val allMessages by viewModel.messages.collectAsState(initial = emptyList())
    var showDeleteAllDialog by remember { mutableStateOf(false) }

    // Group messages by date for "sessions"
    val dateFormat = remember { SimpleDateFormat("MMM dd, yyyy", Locale.getDefault()) }
    val timeFormat = remember { SimpleDateFormat("HH:mm", Locale.getDefault()) }
    
    val groupedMessages = remember(allMessages) {
        allMessages.groupBy { dateFormat.format(Date(it.timestamp)) }
            .entries
            .sortedByDescending { it.value.maxOf { m -> m.timestamp } }
    }

    // Delete all confirmation dialog
    if (showDeleteAllDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteAllDialog = false },
            title = { Text("Clear All History", color = Color.White) },
            text = { Text("This will permanently delete all chat history. This cannot be undone.", color = SlateText) },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.clearAllMessages()
                    showDeleteAllDialog = false
                }) {
                    Text("DELETE ALL", color = Color(0xFFFF5252))
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteAllDialog = false }) {
                    Text("CANCEL", color = CyanGlow)
                }
            },
            containerColor = Color(0xFF1A1A1A)
        )
    }

    Scaffold(
        containerColor = NeuralDark,
        floatingActionButton = {
            FloatingActionButton(
                onClick = {
                    viewModel.startNewChat()
                    onBack()
                },
                containerColor = CyanGlow,
                shape = CircleShape,
                modifier = Modifier.padding(bottom = 8.dp)
            ) {
                Icon(Icons.Filled.Add, "New Chat", tint = Color.Black)
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0A0A0A))
                    .padding(horizontal = 8.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack, modifier = Modifier.size(36.dp)) {
                    Icon(Icons.Filled.ArrowBack, "Back", tint = CyanGlow, modifier = Modifier.size(20.dp))
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "COMMAND HISTORY",
                    color = CyanGlow,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 16.sp,
                    letterSpacing = 2.sp,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    "${allMessages.size}",
                    color = SlateText,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(end = 8.dp)
                )
                // Clear all button
                if (allMessages.isNotEmpty()) {
                    IconButton(
                        onClick = { showDeleteAllDialog = true },
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(Icons.Filled.DeleteSweep, "Clear All", tint = Color(0xFFFF5252), modifier = Modifier.size(20.dp))
                    }
                }
            }

            HorizontalDivider(color = CyanGlow.copy(alpha = 0.2f), thickness = 1.dp)

            if (allMessages.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "NO HISTORY",
                            color = SlateText.copy(alpha = 0.5f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = 18.sp,
                            letterSpacing = 4.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "Start a conversation to see history here.",
                            color = SlateText.copy(alpha = 0.3f),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        OutlinedButton(
                            onClick = {
                                viewModel.startNewChat()
                                onBack()
                            },
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = CyanGlow)
                        ) {
                            Icon(Icons.Filled.Add, null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("NEW CHAT", fontFamily = FontFamily.Monospace, fontSize = 13.sp)
                        }
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    groupedMessages.forEach { (date, msgs) ->
                        // Date header
                        item {
                            Text(
                                text = date,
                                color = CyanGlow.copy(alpha = 0.6f),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp,
                                letterSpacing = 1.sp,
                                modifier = Modifier.padding(vertical = 8.dp, horizontal = 4.dp)
                            )
                        }

                        items(msgs.sortedByDescending { it.timestamp }) { message ->
                            HistoryMessageCard(
                                message = message,
                                timeFormat = timeFormat,
                                onDelete = { viewModel.deleteMessage(message) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryMessageCard(
    message: ChatMessage,
    timeFormat: SimpleDateFormat,
    onDelete: () -> Unit
) {
    val isUser = message.sender.equals("user", ignoreCase = true)
    val isAgent = message.sender.equals("agent", ignoreCase = true) ||
                  message.sender.equals("neural", ignoreCase = true) ||
                  message.sender.equals("system", ignoreCase = true)

    val accentColor = if (isUser) CyanGlow.copy(alpha = 0.15f) else Color(0xFF1A1A1A)
    val borderColor = if (isUser) CyanGlow.copy(alpha = 0.3f) else Color.White.copy(alpha = 0.06f)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(accentColor)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.Top
    ) {
        // Message body
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (isUser) "YOU" else "NEURAL",
                    color = if (isUser) CyanGlow else Color(0xFFB388FF),
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    timeFormat.format(Date(message.timestamp)),
                    color = SlateText.copy(alpha = 0.4f),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                message.text,
                color = Color(0xFFE0E0E0),
                fontSize = 13.sp,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                lineHeight = 18.sp
            )
        }

        // Delete button
        IconButton(
            onClick = onDelete,
            modifier = Modifier.size(28.dp)
        ) {
            Icon(
                Icons.Filled.Delete,
                "Delete",
                tint = SlateText.copy(alpha = 0.3f),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}
