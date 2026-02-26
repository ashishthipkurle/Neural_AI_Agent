package com.neuralai.agent.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import android.os.Environment
import android.content.Context
import java.io.File
import com.neuralai.agent.core.NeuralAgent
import com.neuralai.agent.core.llm.OllamaClient
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AgentMsg(val role: String, val text: String)

data class FileItem(
    val name: String,
    val uri: Uri?,
    val isFolder: Boolean,
    val indent: Int,
    val children: List<FileItem> = emptyList(),
    val isExpanded: Boolean = false
)

// Matches PC app CopilotMode: suggest | explain | refactor
enum class CopilotMode { SUGGEST, EXPLAIN, REFACTOR }

@HiltViewModel
class CodeEditorViewModel @Inject constructor(
    private val application: Application,
    private val neuralAgent: NeuralAgent,
    private val ollamaClient: OllamaClient
) : AndroidViewModel(application) {

    // Persisted across navigation
    var projectName = mutableStateOf("My Projects")
    var projectUri = mutableStateOf<Uri?>(null)
    var fileTree = mutableStateOf<List<FileItem>>(emptyList())
    var selectedFileUri = mutableStateOf<Uri?>(null)
    var selectedFileName = mutableStateOf("")
    var fileContent = mutableStateOf("// Select a file or open a project folder")
    var isEdited = mutableStateOf(false)
    var copilotMode = mutableStateOf(CopilotMode.SUGGEST)
    var isAgentLoading = mutableStateOf(false)

    val agentMessages = mutableStateListOf(
        AgentMsg("agent", "Hello! I can help with:\n• Generate new code\n• Explain code\n• Debug & refactor\n\nTry: \"create a calculator\"")
    )

    val terminalLines = mutableStateListOf("> Neural Agent CLI ready.", "> ")

    init {
        // Initialize default project folder for PC-like behavior
        try {
            val defaultDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS), "NeuralProjects")
            if (!defaultDir.exists()) {
                defaultDir.mkdirs()
            }
            projectUri.value = Uri.fromFile(defaultDir)
            projectName.value = "NeuralProjects"
            fileTree.value = buildFileTree(DocumentFile.fromFile(defaultDir), 0)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun getDocumentFile(context: Context, uri: Uri?): DocumentFile? {
        if (uri == null) return null
        return if (uri.scheme == "file") {
            DocumentFile.fromFile(File(uri.path ?: return null))
        } else {
            DocumentFile.fromTreeUri(context, uri)
        }
    }

    fun openFolder(uri: Uri) {
        val context = application.applicationContext
        try {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        } catch (_: Exception) {}

        val doc = getDocumentFile(context, uri)
        projectName.value = doc?.name ?: "Project"
        projectUri.value = uri
        fileTree.value = buildFileTree(doc, 0)
    }

    fun readFile(uri: Uri, name: String) {
        try {
            val inputStream = application.contentResolver.openInputStream(uri)
            val text = inputStream?.bufferedReader()?.readText() ?: "// Could not read file"
            inputStream?.close()
            fileContent.value = text
            selectedFileUri.value = uri
            selectedFileName.value = name
            isEdited.value = false
        } catch (e: Exception) {
            fileContent.value = "// Error reading file: ${e.message}"
        }
    }

    fun toggleExpand(target: FileItem) {
        fileTree.value = toggleExpandInTree(fileTree.value, target)
    }

    /** Create a new file inside the selected folder or project root */
    fun createFile(parentUri: Uri?, fileName: String) {
        val context = application.applicationContext
        val parentDoc = getDocumentFile(context, parentUri ?: projectUri.value)
        parentDoc?.createFile("text/plain", fileName)
        // Refresh tree
        projectUri.value?.let { 
            fileTree.value = buildFileTree(getDocumentFile(context, it), 0)
        }
    }

    /** Create a new folder inside the selected folder or project root */
    fun createFolder(parentUri: Uri?, folderName: String) {
        val context = application.applicationContext
        val parentDoc = getDocumentFile(context, parentUri ?: projectUri.value)
        parentDoc?.createDirectory(folderName)
        projectUri.value?.let { 
            fileTree.value = buildFileTree(getDocumentFile(context, it), 0)
        }
    }

    fun sendAgentMessage(text: String) {
        if (text.isBlank()) return
        agentMessages.add(AgentMsg("user", text))
        isAgentLoading.value = true

        viewModelScope.launch {
            try {
                // Build a code-specific prompt based on copilot mode
                val codeContext = if (fileContent.value.isNotBlank() && !fileContent.value.startsWith("//")) {
                    "\n\nCurrent file (${selectedFileName.value}):\n```\n${fileContent.value.take(2000)}\n```"
                } else ""

                val systemPrompt = when (copilotMode.value) {
                    CopilotMode.SUGGEST -> "You are a code generation assistant. Generate clean, working code. Wrap all code in a single markdown code block. Include a filename comment on the first line like: // filename: calculator.py"
                    CopilotMode.EXPLAIN -> "You are a code explanation assistant. Explain code clearly and concisely. Use bullet points for key concepts."
                    CopilotMode.REFACTOR -> "You are a code refactoring assistant. Return ONLY the complete refactored file content in a single markdown code block. No explanations outside the code block."
                }

                val userPrompt = text + codeContext

                // Call LLM directly — bypass NeuralAgent intent parsing
                val response = ollamaClient.chat(
                    model = "qwen2.5:0.5b",
                    systemPrompt = systemPrompt,
                    userMessage = userPrompt
                )
                agentMessages.add(AgentMsg("agent", response))

                // Extract code block from response
                val codeBlock = extractCodeBlock(response)

                when (copilotMode.value) {
                    CopilotMode.SUGGEST -> {
                        if (codeBlock != null) {
                            // Try to extract filename from code
                            val filenameMatch = Regex("//\\s*filename:\\s*(\\S+)").find(codeBlock)
                                ?: Regex("#\\s*filename:\\s*(\\S+)").find(codeBlock)
                            val fileName = filenameMatch?.groupValues?.get(1) ?: inferFileName(text)

                            // Write to project or update editor
                            if (projectUri.value != null) {
                                try {
                                    createFile(projectUri.value, fileName)
                                    // Write content to the new file
                                    val doc = getDocumentFile(application.applicationContext, projectUri.value)
                                    val newFile = doc?.findFile(fileName)
                                    newFile?.uri?.let { uri ->
                                        application.contentResolver.openOutputStream(uri)?.use { os ->
                                            os.write(codeBlock.toByteArray())
                                        }
                                        readFile(uri, fileName)
                                    }
                                    agentMessages.add(AgentMsg("agent", "✅ Created file: $fileName"))
                                } catch (e: Exception) {
                                    // Fallback: just show in editor
                                    fileContent.value = codeBlock
                                    selectedFileName.value = fileName
                                    agentMessages.add(AgentMsg("agent", "📝 Code generated. Open a project folder to save files."))
                                }
                            } else {
                                fileContent.value = codeBlock
                                selectedFileName.value = fileName
                                agentMessages.add(AgentMsg("agent", "📝 Code generated as $fileName\nOpen a project folder to save to disk."))
                            }
                        }
                    }
                    CopilotMode.REFACTOR -> {
                        if (codeBlock != null && selectedFileUri.value != null) {
                            try {
                                // Write refactored code directly to current file
                                application.contentResolver.openOutputStream(selectedFileUri.value!!, "wt")?.use { os ->
                                    os.write(codeBlock.toByteArray())
                                }
                                fileContent.value = codeBlock
                                isEdited.value = false
                                agentMessages.add(AgentMsg("agent", "✅ File refactored and saved: ${selectedFileName.value}"))
                            } catch (e: Exception) {
                                // Fallback: update editor content
                                fileContent.value = codeBlock
                                isEdited.value = true
                                agentMessages.add(AgentMsg("agent", "📝 Refactored code applied in editor. Save manually."))
                            }
                        } else if (codeBlock != null) {
                            fileContent.value = codeBlock
                            isEdited.value = true
                            agentMessages.add(AgentMsg("agent", "📝 Refactored code applied in editor."))
                        }
                    }
                    CopilotMode.EXPLAIN -> {
                        // Explain mode just shows text, no file changes
                    }
                }
            } catch (e: Exception) {
                agentMessages.add(AgentMsg("agent", "Error: ${e.message}"))
            } finally {
                isAgentLoading.value = false
            }
        }
    }

    /** Extract first code block from markdown response */
    private fun extractCodeBlock(text: String): String? {
        val regex = Regex("```[a-zA-Z]*\\n([\\s\\S]*?)```")
        return regex.find(text)?.groupValues?.get(1)?.trim()
    }

    /** Infer filename from user request */
    private fun inferFileName(request: String): String {
        val lower = request.lowercase()
        val ext = when {
            lower.contains("python") || lower.contains(".py") -> ".py"
            lower.contains("kotlin") || lower.contains(".kt") -> ".kt"
            lower.contains("java") || lower.contains(".java") -> ".java"
            lower.contains("javascript") || lower.contains(".js") -> ".js"
            lower.contains("typescript") || lower.contains(".ts") -> ".ts"
            lower.contains("html") -> ".html"
            lower.contains("css") -> ".css"
            lower.contains("rust") -> ".rs"
            lower.contains("go") || lower.contains("golang") -> ".go"
            lower.contains("c++") || lower.contains("cpp") -> ".cpp"
            lower.contains("swift") -> ".swift"
            else -> ".py"
        }
        // Extract a meaningful name from request
        val words = request.split(" ").filter { it.length > 2 && !it.startsWith("a ") }
            .take(2).joinToString("_").replace(Regex("[^a-zA-Z0-9_]"), "").lowercase()
        return if (words.isNotEmpty()) "$words$ext" else "generated$ext"
    }

    fun executeTerminalCommand(cmd: String) {
        terminalLines.add("$ $cmd")
        val output = when {
            cmd.startsWith("ls") -> "build.gradle  AndroidManifest.xml  src/"
            cmd.startsWith("pwd") -> "/app/${projectName.value.lowercase().replace(" ", "_")}"
            cmd.startsWith("echo") -> cmd.removePrefix("echo ").trim()
            cmd.startsWith("help") -> "Available: ls, pwd, echo, clear, help, build"
            cmd.startsWith("clear") -> { terminalLines.clear(); "" }
            cmd.startsWith("build") -> "BUILD SUCCESSFUL in 2.5s\n43 actionable tasks: 15 executed"
            cmd.startsWith("git") -> "git: simulated — commit hash abc123f"
            else -> "$cmd: command simulated"
        }
        if (output.isNotEmpty()) terminalLines.add(output)
        terminalLines.add("> ")
    }

    private fun buildFileTree(doc: DocumentFile?, indent: Int): List<FileItem> {
        if (doc == null || !doc.isDirectory) return emptyList()
        val items = mutableListOf<FileItem>()
        doc.listFiles()
            .sortedWith(compareBy<DocumentFile> { !it.isDirectory }.thenBy { it.name?.lowercase() ?: "" })
            .forEach { file ->
                val name = file.name ?: "unknown"
                if (name.startsWith(".")) return@forEach
                items.add(
                    FileItem(
                        name = name,
                        uri = file.uri,
                        isFolder = file.isDirectory,
                        indent = indent,
                        children = if (file.isDirectory) buildFileTree(file, indent + 1) else emptyList(),
                        isExpanded = false
                    )
                )
            }
        return items
    }

    private fun toggleExpandInTree(items: List<FileItem>, target: FileItem): List<FileItem> {
        return items.map { item ->
            if (item.uri == target.uri && item.name == target.name) {
                item.copy(isExpanded = !item.isExpanded)
            } else if (item.isFolder) {
                item.copy(children = toggleExpandInTree(item.children, target))
            } else item
        }
    }
}
