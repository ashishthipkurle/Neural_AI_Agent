package com.neuralai.agent.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.neuralai.agent.ui.CodeEditorViewModel
import com.neuralai.agent.ui.FileItem

// ===== PC-matching color palette (obsidian-pro.css) =====
private val ObsBg = Color(0xFF050508)           // body
private val ObsPanel = Color(0xFF0A0A0C)        // glass panels
private val ObsPanelLighter = Color(0xFF14141A)  // glass-lighter
private val ObsHeaderBg = Color(0xFF050508)      // glass-header
private val ObsBorder = Color(0x08FFFFFF)        // rgba(255,255,255,0.03)
private val ObsText = Color(0xFFCFD8DC)          // slate text
private val ObsDimText = Color(0x80CFD8DC)       // 50% alpha
private val ObsAccent = Color(0xFF3B82F6)        // active-file blue
private val ObsGreen = Color(0xFF4ADE80)         // suggest mode
private val ObsCyan = Color(0xFF22D3EE)          // explain mode
private val ObsRed = Color(0xFFEF4444)           // refactor mode
private val ObsPurple = Color(0xFFB388FF)        // agent accent
private val ObsGreenBg = Color(0xFF1E3320)       // suggest selected bg
private val ObsCyanBg = Color(0xFF1A2E3B)        // explain selected bg
private val ObsRedBg = Color(0xFF3B1A1A)         // refactor selected bg

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CodeEditorScreen(
    viewModel: CodeEditorViewModel = hiltViewModel()
) {
    val projectName by viewModel.projectName
    val fileTree by viewModel.fileTree
    val selectedFileUri by viewModel.selectedFileUri
    val selectedFileName by viewModel.selectedFileName
    val fileContent by viewModel.fileContent
    val isEdited by viewModel.isEdited

    val isAgentLoading by viewModel.isAgentLoading

    var showExplorer by remember { mutableStateOf(true) }
    var showTerminal by remember { mutableStateOf(false) }
    var showAgent by remember { mutableStateOf(true) }
    var terminalInput by remember { mutableStateOf("") }
    var agentInput by remember { mutableStateOf("") }
    var showCreateDialog by remember { mutableStateOf(false) }
    var createDialogType by remember { mutableStateOf("file") } // "file" or "folder"
    var createDialogName by remember { mutableStateOf("") }

    val agentListState = rememberLazyListState()

    val folderPickerLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri -> uri?.let { viewModel.openFolder(it) } }

    LaunchedEffect(viewModel.agentMessages.size) {
        if (viewModel.agentMessages.isNotEmpty()) {
            agentListState.animateScrollToItem(viewModel.agentMessages.size - 1)
        }
    }

    // Create file/folder dialog
    if (showCreateDialog) {
        AlertDialog(
            onDismissRequest = { showCreateDialog = false },
            containerColor = ObsPanel,
            title = { Text(if (createDialogType == "file") "New File" else "New Folder", color = ObsText, fontFamily = FontFamily.Monospace) },
            text = {
                BasicTextField(
                    value = createDialogName,
                    onValueChange = { createDialogName = it },
                    singleLine = true,
                    textStyle = TextStyle(color = ObsText, fontFamily = FontFamily.Monospace, fontSize = 14.sp),
                    cursorBrush = SolidColor(ObsAccent),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(ObsPanelLighter)
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    decorationBox = { inner ->
                        if (createDialogName.isEmpty()) Text("Enter name...", color = ObsDimText, fontFamily = FontFamily.Monospace, fontSize = 14.sp)
                        inner()
                    }
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    if (createDialogName.isNotBlank()) {
                        if (createDialogType == "file") viewModel.createFile(viewModel.projectUri.value, createDialogName)
                        else viewModel.createFolder(viewModel.projectUri.value, createDialogName)
                        createDialogName = ""
                        showCreateDialog = false
                    }
                }) { Text("Create", color = ObsGreen) }
            },
            dismissButton = {
                TextButton(onClick = { showCreateDialog = false }) { Text("Cancel", color = ObsDimText) }
            }
        )
    }

    Column(modifier = Modifier.fillMaxSize().background(ObsBg)) {
        // ===== Menu Bar (matches PC glass-header) =====
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(ObsHeaderBg)
                .padding(horizontal = 6.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                IconButton(onClick = { showExplorer = !showExplorer }, modifier = Modifier.size(28.dp)) {
                    Icon(Icons.Filled.Folder, "Explorer", tint = if (showExplorer) ObsAccent else ObsDimText, modifier = Modifier.size(16.dp))
                }
                IconButton(onClick = { showTerminal = !showTerminal }, modifier = Modifier.size(28.dp)) {
                    Icon(Icons.Filled.Terminal, "Terminal", tint = if (showTerminal) ObsGreen else ObsDimText, modifier = Modifier.size(16.dp))
                }
                IconButton(onClick = { showAgent = !showAgent }, modifier = Modifier.size(28.dp)) {
                    Icon(Icons.Filled.SmartToy, "Agent", tint = if (showAgent) ObsPurple else ObsDimText, modifier = Modifier.size(16.dp))
                }
            }
            Text("NEURAL CODE", color = ObsAccent, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 12.sp, letterSpacing = 2.sp)
            IconButton(onClick = { folderPickerLauncher.launch(null) }, modifier = Modifier.size(28.dp)) {
                Icon(Icons.Filled.FolderOpen, "Open Folder", tint = ObsAccent, modifier = Modifier.size(16.dp))
            }
        }

        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(ObsBorder))

        Row(modifier = Modifier.weight(1f)) {
            // ===== Explorer (glass panel) =====
            AnimatedVisibility(visible = showExplorer) {
                Column(
                    modifier = Modifier.width(180.dp).fillMaxHeight().background(ObsPanel)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            projectName.uppercase(),
                            color = ObsDimText, fontFamily = FontFamily.Monospace, fontSize = 9.sp,
                            letterSpacing = 1.sp, modifier = Modifier.weight(1f)
                        )
                        // New File button
                        IconButton(onClick = { createDialogType = "file"; createDialogName = ""; showCreateDialog = true }, modifier = Modifier.size(18.dp)) {
                            Icon(Icons.Filled.NoteAdd, "New File", tint = ObsDimText, modifier = Modifier.size(12.dp))
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        // New Folder button
                        IconButton(onClick = { createDialogType = "folder"; createDialogName = ""; showCreateDialog = true }, modifier = Modifier.size(18.dp)) {
                            Icon(Icons.Filled.CreateNewFolder, "New Folder", tint = ObsDimText, modifier = Modifier.size(12.dp))
                        }
                    }

                    if (viewModel.projectUri.value == null) {
                        Box(modifier = Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("No folder open", color = ObsDimText.copy(alpha = 0.5f), fontSize = 11.sp)
                                Spacer(modifier = Modifier.height(8.dp))
                                OutlinedButton(
                                    onClick = { folderPickerLauncher.launch(null) },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = ObsAccent),
                                    modifier = Modifier.height(28.dp),
                                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp)
                                ) { Text("Open Folder", fontSize = 10.sp, fontFamily = FontFamily.Monospace) }
                            }
                        }
                    } else if (fileTree.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("Empty folder", color = ObsDimText.copy(alpha = 0.5f), fontSize = 11.sp)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("Use the Agent to generate code", color = ObsDimText.copy(alpha = 0.3f), fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                            }
                        }
                    } else {
                        LazyColumn(modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 8.dp)) {
                            items(flattenTree(fileTree)) { item ->
                                FileTreeRow(
                                    item = item,
                                    isSelected = item.uri == selectedFileUri,
                                    onToggle = { viewModel.toggleExpand(it) },
                                    onClick = { if (!it.isFolder && it.uri != null) viewModel.readFile(it.uri!!, it.name) }
                                )
                            }
                        }
                    }
                }
                Box(modifier = Modifier.fillMaxHeight().width(1.dp).background(ObsBorder))
            }

            // ===== Editor Area =====
            Column(modifier = Modifier.weight(1f)) {
                // Tab bar
                if (viewModel.openTabs.isNotEmpty()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF0C0C10))
                            .padding(top = 2.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Scrollable Tabs List
                        Row(
                            modifier = Modifier
                                .weight(1f)
                                .horizontalScroll(rememberScrollState())
                        ) {
                            viewModel.openTabs.forEach { tab ->
                                val isActive = tab.uri == selectedFileUri
                                // If the tab is currently active, use the real-time isEdited state, otherwise use the saved tab state
                                val isTabEdited = if (isActive) isEdited else tab.isEdited
                                
                                Row(
                                    modifier = Modifier
                                        .padding(end = 2.dp)
                                        .clip(RoundedCornerShape(topStart = 4.dp, topEnd = 4.dp))
                                        .background(if (isActive) ObsBg else Color(0xFF1E1E2A))
                                        .clickable { viewModel.selectTab(tab.uri) }
                                        .padding(start = 12.dp, end = 4.dp, top = 6.dp, bottom = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        "${if (isTabEdited) "● " else ""}${tab.name}",
                                        fontFamily = FontFamily.Monospace, fontSize = 11.sp,
                                        color = if (isTabEdited) Color(0xFFFFC107) else if (isActive) ObsText else ObsDimText
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    IconButton(
                                        onClick = { viewModel.closeTab(tab.uri) },
                                        modifier = Modifier.size(16.dp)
                                    ) {
                                        Icon(Icons.Filled.Close, "Close", tint = ObsDimText, modifier = Modifier.size(12.dp))
                                    }
                                }
                            }
                        }
                        
                        // Global Save for active file
                        if (isEdited) {
                            IconButton(
                                onClick = { viewModel.saveCurrentFile() },
                                modifier = Modifier.size(28.dp).padding(horizontal = 4.dp)
                            ) {
                                Icon(Icons.Filled.Save, "Save", tint = ObsAccent, modifier = Modifier.size(14.dp))
                            }
                        }
                    }
                }

                // Breadcrumb
                Text(
                    "$projectName / $selectedFileName",
                    color = ObsDimText.copy(alpha = 0.4f), fontFamily = FontFamily.Monospace, fontSize = 10.sp,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 3.dp)
                )

                // Editable code with line numbers
                val lines = fileContent.lines()
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .horizontalScroll(rememberScrollState())
                        .background(ObsBg)
                        .padding(vertical = 4.dp)
                ) {
                    Column(modifier = Modifier.padding(horizontal = 6.dp).widthIn(min = 28.dp), horizontalAlignment = Alignment.End) {
                        lines.forEachIndexed { i, _ ->
                            Text("${i + 1}", color = Color(0xFF555555), fontFamily = FontFamily.Monospace, fontSize = 11.sp, lineHeight = 16.sp)
                        }
                    }
                    Box(modifier = Modifier.width(1.dp).height((lines.size * 16).dp).background(ObsBorder))
                    BasicTextField(
                        value = fileContent,
                        onValueChange = { viewModel.fileContent.value = it; viewModel.isEdited.value = true },
                        textStyle = TextStyle(color = ObsText, fontFamily = FontFamily.Monospace, fontSize = 11.sp, lineHeight = 16.sp),
                        cursorBrush = SolidColor(ObsAccent),
                        modifier = Modifier.padding(start = 8.dp, end = 12.dp).fillMaxWidth()
                    )
                }
            }

            // ===== Agent Panel (matches PC obsidian-pro) =====
            AnimatedVisibility(visible = showAgent) {
                Row {
                    Box(modifier = Modifier.fillMaxHeight().width(1.dp).background(ObsBorder))
                    Column(
                        modifier = Modifier.width(260.dp).fillMaxHeight().background(ObsPanel)
                    ) {
                        // Agent header
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Filled.SmartToy, null, tint = ObsPurple, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("CODE AGENT", color = ObsPurple, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 11.sp, letterSpacing = 1.sp)
                        }



                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(ObsBorder))

                        // Messages
                        LazyColumn(
                            state = agentListState,
                            modifier = Modifier.weight(1f).padding(horizontal = 8.dp, vertical = 4.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            items(viewModel.agentMessages) { msg ->
                                val isUser = msg.role == "user"
                                Column(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(if (isUser) ObsAccent.copy(alpha = 0.12f) else ObsPanelLighter)
                                            .padding(horizontal = 10.dp, vertical = 6.dp)
                                            .widthIn(max = 220.dp)
                                    ) {
                                        Text(msg.text, color = ObsText, fontFamily = FontFamily.Monospace, fontSize = 11.sp, lineHeight = 15.sp)
                                    }
                                }
                            }

                            // Loading indicator
                            if (isAgentLoading) {
                                item {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        CircularProgressIndicator(modifier = Modifier.size(12.dp), color = ObsPurple, strokeWidth = 1.5.dp)
                                        Text("Analyzing...", color = ObsDimText, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
                                    }
                                }
                            }
                        }

                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(ObsBorder))

                        // Input
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            BasicTextField(
                                value = agentInput,
                                onValueChange = { agentInput = it },
                                singleLine = true,
                                textStyle = TextStyle(color = ObsText, fontFamily = FontFamily.Monospace, fontSize = 11.sp),
                                cursorBrush = SolidColor(ObsPurple),
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                                keyboardActions = KeyboardActions(onSend = {
                                    viewModel.sendAgentMessage(agentInput); agentInput = ""
                                }),
                                modifier = Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(ObsPanelLighter)
                                    .padding(horizontal = 8.dp, vertical = 8.dp),
                                decorationBox = { inner ->
                                    if (agentInput.isEmpty()) {
                                        Text("Describe what you want to build...", color = ObsDimText.copy(alpha = 0.4f), fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                                    }
                                    inner()
                                }
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            IconButton(
                                onClick = { viewModel.sendAgentMessage(agentInput); agentInput = "" },
                                modifier = Modifier.size(30.dp)
                            ) {
                                Icon(Icons.Filled.Send, "Send", tint = ObsPurple, modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }
        }

        // ===== Terminal Panel =====
        AnimatedVisibility(visible = showTerminal) {
            Column(
                modifier = Modifier.fillMaxWidth().height(140.dp).background(ObsPanel)
            ) {
                Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(ObsGreen.copy(alpha = 0.15f)))
                Row(
                    modifier = Modifier.fillMaxWidth().background(ObsHeaderBg).padding(horizontal = 10.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("TERMINAL", color = ObsDimText, fontFamily = FontFamily.Monospace, fontSize = 9.sp, letterSpacing = 1.sp)
                    Text("bash", color = ObsGreen.copy(alpha = 0.4f), fontFamily = FontFamily.Monospace, fontSize = 9.sp)
                }
                Box(
                    modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp).verticalScroll(rememberScrollState())
                ) {
                    Text(viewModel.terminalLines.joinToString("\n"), color = ObsGreen, fontFamily = FontFamily.Monospace, fontSize = 11.sp, lineHeight = 14.sp)
                }
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("$ ", color = ObsGreen, fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                    BasicTextField(
                        value = terminalInput,
                        onValueChange = { terminalInput = it },
                        singleLine = true,
                        textStyle = TextStyle(color = ObsGreen, fontFamily = FontFamily.Monospace, fontSize = 11.sp),
                        cursorBrush = SolidColor(ObsGreen),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = {
                            if (terminalInput.isNotBlank()) { viewModel.executeTerminalCommand(terminalInput); terminalInput = "" }
                        }),
                        modifier = Modifier.weight(1f).padding(start = 4.dp),
                        decorationBox = { inner ->
                            if (terminalInput.isEmpty()) Text("type command...", color = ObsGreen.copy(alpha = 0.3f), fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                            inner()
                        }
                    )
                }
            }
        }
    }
}



// ===== File tree helpers =====
private fun flattenTree(items: List<FileItem>): List<FileItem> {
    val result = mutableListOf<FileItem>()
    fun walk(list: List<FileItem>) { for (item in list) { result.add(item); if (item.isFolder && item.isExpanded) walk(item.children) } }
    walk(items)
    return result
}

@Composable
private fun FileTreeRow(item: FileItem, isSelected: Boolean, onToggle: (FileItem) -> Unit, onClick: (FileItem) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (isSelected) ObsAccent.copy(alpha = 0.08f) else Color.Transparent)
            .clickable { if (item.isFolder) onToggle(item) else onClick(item) }
            .padding(start = (10 + item.indent * 14).dp, top = 2.dp, bottom = 2.dp, end = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (item.isFolder) {
            Icon(if (item.isExpanded) Icons.Filled.ExpandMore else Icons.Filled.ChevronRight, null, tint = ObsDimText, modifier = Modifier.size(12.dp))
            Spacer(modifier = Modifier.width(3.dp))
            Icon(Icons.Filled.Folder, null, tint = Color(0xFFE8AB53), modifier = Modifier.size(12.dp))
        } else {
            Spacer(modifier = Modifier.width(15.dp))
            Icon(Icons.Filled.Description, null, tint = when {
                item.name.endsWith(".kt") || item.name.endsWith(".kts") -> Color(0xFF7E57C2)
                item.name.endsWith(".xml") -> Color(0xFFFF7043)
                item.name.endsWith(".gradle") -> Color(0xFF66BB6A)
                item.name.endsWith(".json") -> Color(0xFFFFC107)
                item.name.endsWith(".py") -> Color(0xFF42A5F5)
                item.name.endsWith(".js") || item.name.endsWith(".ts") || item.name.endsWith(".tsx") -> Color(0xFFFFC107)
                item.name.endsWith(".css") -> Color(0xFF42A5F5)
                item.name.endsWith(".html") -> Color(0xFFFF7043)
                item.name.endsWith(".md") -> Color(0xFF90A4AE)
                else -> ObsDimText
            }, modifier = Modifier.size(12.dp))
        }
        Spacer(modifier = Modifier.width(5.dp))
        Text(item.name, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = if (isSelected) Color.White else ObsText)
    }
}
