package com.neuralai.agent.ui

import android.app.Application
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import android.os.Environment
import android.content.Context
import java.io.File
import java.io.BufferedReader
import java.io.InputStreamReader
import com.neuralai.agent.core.NeuralAgent
import com.neuralai.agent.core.llm.OllamaClient
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
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

data class OpenTab(
    val uri: Uri,
    val name: String,
    var content: String,
    var isEdited: Boolean = false
)



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
    
    // Editor Tabs State
    val openTabs = mutableStateListOf<OpenTab>()
    var selectedFileUri = mutableStateOf<Uri?>(null)
    var selectedFileName = mutableStateOf("")
    var fileContent = mutableStateOf("// Select a file or open a project folder")
    var isEdited = mutableStateOf(false)
    

    var isAgentLoading = mutableStateOf(false)

    val agentMessages = mutableStateListOf(
        AgentMsg("agent", "Hello! I can help with:\n• Generate, modify & refactor code\n• Explain code & answer questions\n• Debug & fix issues\n\nJust describe what you need!")
    )

    val terminalLines = mutableStateListOf("> Neural Agent CLI ready.", "> ")

    private val prefs: SharedPreferences =
        application.getSharedPreferences("code_editor_prefs", Context.MODE_PRIVATE)

    /** Resolve the project root as a java.io.File (works for file:// URIs) */
    private fun getProjectDir(): File? {
        val uri = projectUri.value ?: return null
        if (uri.scheme == "file") return File(uri.path ?: return null)
        return null
    }

    init {
        try {
            // Restore previously selected project from SharedPreferences
            val savedUri = prefs.getString("last_project_uri", null)
            val savedName = prefs.getString("last_project_name", null)

            var projectRestored = false
            if (savedUri != null && savedName != null) {
                val uri = Uri.parse(savedUri)
                if (uri.scheme == "file") {
                    val dir = File(uri.path!!)
                    if (dir.exists() && dir.canRead()) {
                        projectUri.value = uri
                        projectName.value = savedName
                        fileTree.value = buildFileTreeFromFile(dir, 0)
                        loadProjectHistory(uri.toString())
                        android.util.Log.d("CodeEditor", "Restored project: $savedName at ${dir.absolutePath}")
                        projectRestored = true
                    }
                } else if (uri.scheme == "content") {
                    // Restore SAF-selected folder
                    val doc = DocumentFile.fromTreeUri(application, uri)
                    if (doc != null && doc.exists()) {
                        projectUri.value = uri
                        projectName.value = savedName
                        fileTree.value = buildFileTree(doc, 0)
                        loadProjectHistory(uri.toString())
                        android.util.Log.d("CodeEditor", "Restored SAF project: $savedName")
                        projectRestored = true
                    }
                }
            }

            if (!projectRestored) {
                // Fallback: use app-private NeuralProjects dir
                val baseDir = application.getExternalFilesDir(null)
                    ?: application.filesDir
                val defaultDir = File(baseDir, "NeuralProjects")
                if (!defaultDir.exists()) defaultDir.mkdirs()

                if (defaultDir.exists() && defaultDir.canWrite()) {
                    val defaultUri = Uri.fromFile(defaultDir)
                    projectUri.value = defaultUri
                    projectName.value = "NeuralProjects"
                    fileTree.value = buildFileTreeFromFile(defaultDir, 0)
                    loadProjectHistory(defaultUri.toString())
                    android.util.Log.d("CodeEditor", "Default project: ${defaultDir.absolutePath}")
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("CodeEditor", "Init failed", e)
        }
    }

    // ========== PER-PROJECT AGENT HISTORY ==========

    /** Consistent key for per-project history — always uses the URI string */
    private fun getProjectHistoryKey(uriString: String): String {
        val safe = uriString.replace(Regex("[^a-zA-Z0-9]"), "_").takeLast(120).lowercase()
        return "agent_history_$safe"
    }

    /** Load saved agent chat history for a project (identified by URI string) */
    private fun loadProjectHistory(uriString: String) {
        try {
            val key = getProjectHistoryKey(uriString)
            val saved = prefs.getString(key, null)
            agentMessages.clear()
            if (saved != null) {
                val arr = JSONArray(saved)
                for (i in 0 until arr.length()) {
                    val obj = arr.getJSONObject(i)
                    agentMessages.add(AgentMsg(obj.getString("role"), obj.getString("text")))
                }
                android.util.Log.d("CodeEditor", "Loaded ${arr.length()} messages for project")
            } else {
                agentMessages.add(
                    AgentMsg(
                        "agent",
                        "Hello! I can help with:\n• Generate new code\n• Explain code\n• Debug & refactor\n\nProject: ${projectName.value}\n\nTry: \"create a calculator\""
                    )
                )
            }
        } catch (_: Exception) {
            agentMessages.clear()
            agentMessages.add(AgentMsg("agent", "Code Agent ready."))
        }
    }

    /** Save current agent chat history for the active project */
    private fun saveProjectHistory() {
        val uriStr = projectUri.value?.toString() ?: return
        try {
            val key = getProjectHistoryKey(uriStr)
            val arr = JSONArray()
            // Keep last 50 messages
            val msgs = agentMessages.takeLast(50)
            for (msg in msgs) {
                val obj = JSONObject()
                obj.put("role", msg.role)
                obj.put("text", msg.text)
                arr.put(obj)
            }
            prefs.edit().putString(key, arr.toString()).apply()
            android.util.Log.d("CodeEditor", "Saved ${msgs.size} messages for project")
        } catch (_: Exception) {}
    }

    // ========== FILE OPERATIONS (java.io.File based) ==========

    fun openFolder(uri: Uri) {
        val context = application.applicationContext
        // Save current project history before switching
        saveProjectHistory()

        try {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        } catch (_: Exception) {}

        projectUri.value = uri
        // Clear current tabs when switching projects
        openTabs.clear()
        selectedFileUri.value = null
        selectedFileName.value = ""
        fileContent.value = "// Select a file or open a project folder"
        isEdited.value = false

        if (uri.scheme == "file") {
            val dir = File(uri.path!!)
            projectName.value = dir.name
            fileTree.value = buildFileTreeFromFile(dir, 0)
        } else {
            val doc = DocumentFile.fromTreeUri(context, uri)
            projectName.value = doc?.name ?: "Project"
            fileTree.value = buildFileTree(doc, 0)
        }

        // Load project-specific chat history (always uses URI string as key)
        loadProjectHistory(uri.toString())

        // Persist selected project so it survives app restart
        prefs.edit()
            .putString("last_project_uri", uri.toString())
            .putString("last_project_name", projectName.value)
            .apply()
    }

    /** Select an already open tab */
    fun selectTab(uri: Uri) {
        val tab = openTabs.find { it.uri == uri }
        if (tab != null) {
            // Save current editor state into its tab before switching
            val currentUri = selectedFileUri.value
            if (currentUri != null && currentUri != uri) {
                val currentTab = openTabs.find { it.uri == currentUri }
                if (currentTab != null) {
                    currentTab.content = fileContent.value
                    currentTab.isEdited = isEdited.value
                }
            }

            selectedFileUri.value = uri
            selectedFileName.value = tab.name
            fileContent.value = tab.content
            isEdited.value = tab.isEdited
        }
    }

    /** Close a specific tab */
    fun closeTab(uri: Uri) {
        val index = openTabs.indexOfFirst { it.uri == uri }
        if (index != -1) {
            openTabs.removeAt(index)
            if (openTabs.isEmpty()) {
                selectedFileUri.value = null
                selectedFileName.value = ""
                fileContent.value = "// Select a file or open a project folder"
                isEdited.value = false
            } else if (selectedFileUri.value == uri) {
                // If closing the currently selected tab, select the previous or next adjacent tab
                val newIndex = if (index > 0) index - 1 else 0
                selectTab(openTabs[newIndex].uri)
            }
        }
    }

    /** Close the currently open file (legacy support) */
    fun closeCurrentFile() {
        val uri = selectedFileUri.value
        if (uri != null) {
            closeTab(uri)
        }
    }

    fun readFile(uri: Uri, name: String) {
        // If already open, just switch to it
        if (openTabs.any { it.uri == uri }) {
            selectTab(uri)
            return
        }

        try {
            val text = if (uri.scheme == "file") {
                val f = File(uri.path!!)
                if (f.exists()) f.readText() else "// File not found"
            } else {
                val inputStream = application.contentResolver.openInputStream(uri)
                val t = inputStream?.bufferedReader()?.readText() ?: "// Could not read file"
                inputStream?.close()
                t
            }
            
            // Save current editor state to its tab before opening a new one
            val currentUri = selectedFileUri.value
            if (currentUri != null) {
                val currentTab = openTabs.find { it.uri == currentUri }
                if (currentTab != null) {
                    currentTab.content = fileContent.value
                    currentTab.isEdited = isEdited.value
                }
            }

            val newTab = OpenTab(uri, name, text, isEdited = false)
            openTabs.add(newTab)
            
            fileContent.value = text
            selectedFileUri.value = uri
            selectedFileName.value = name
            isEdited.value = false
        } catch (e: Exception) {
            fileContent.value = "// Error reading file: ${e.message}"
        }
    }

    fun saveCurrentFile() {
        val uri = selectedFileUri.value ?: return
        try {
            if (uri.scheme == "file") {
                File(uri.path!!).writeText(fileContent.value)
            } else {
                application.contentResolver.openOutputStream(uri, "wt")?.use { os ->
                    os.write(fileContent.value.toByteArray())
                }
            }
            isEdited.value = false
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun toggleExpand(target: FileItem) {
        fileTree.value = toggleExpandInTree(fileTree.value, target)
    }

    /** Create a new file inside the project. Handles both java.io.File and content:// DocumentTree URIs */
    fun createFileOnDisk(filePath: String, content: String = ""): Uri? {
        val uri = projectUri.value ?: return null
        try {
            if (uri.scheme == "file") {
                val projectDir = File(uri.path!!)
                val targetFile = File(projectDir, filePath)
                targetFile.parentFile?.mkdirs()
                targetFile.writeText(content)
                fileTree.value = buildFileTreeFromFile(projectDir, 0)
                return Uri.fromFile(targetFile)
            } else {
                val context = application.applicationContext
                val docTree = DocumentFile.fromTreeUri(context, uri) ?: return null
                
                // Handle nested paths like "src/main.kt" by creating subdirectories
                val parts = filePath.split("/")
                val fileName = parts.last()
                var currentDir = docTree
                
                for (i in 0 until parts.size - 1) {
                    val dirName = parts[i]
                    var nextDir = currentDir.findFile(dirName)
                    if (nextDir == null) {
                        nextDir = currentDir.createDirectory(dirName)
                    }
                    if (nextDir != null) currentDir = nextDir else return null
                }
                
                // Check if file already exists; if so, delete it before creating a new one (or just overwrite)
                val existingFile = currentDir.findFile(fileName)
                existingFile?.delete()
                
                val newFile = currentDir.createFile("text/plain", fileName) ?: return null
                context.contentResolver.openOutputStream(newFile.uri, "wt")?.use { os ->
                    os.write(content.toByteArray())
                }
                
                fileTree.value = buildFileTree(docTree, 0)
                return newFile.uri
            }
        } catch (e: Exception) {
            e.printStackTrace()
            return null
        }
    }

    /** Create a new file (for dialog / UI button — no content) */
    fun createFile(parentUri: Uri?, filePath: String) {
        createFileOnDisk(filePath, "")
    }

    /** Create a new folder */
    fun createFolder(parentUri: Uri?, folderName: String) {
        val projectDir = getProjectDir() ?: return
        try {
            File(projectDir, folderName).mkdirs()
            fileTree.value = buildFileTreeFromFile(projectDir, 0)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    // ========== CODE AGENT (matches PC CodeEditorView.tsx sendToAgent) ==========

    fun sendAgentMessage(text: String) {
        if (text.isBlank()) return
        agentMessages.add(AgentMsg("user", text))
        isAgentLoading.value = true
        val userMessage = text.lowercase()

        viewModelScope.launch {
            try {
                // Build code context from current file
                val codeContext = if (fileContent.value.isNotBlank() && !fileContent.value.startsWith("//")) {
                    "\n\nCurrent file (${selectedFileName.value}):\n```\n${fileContent.value.take(2000)}\n```"
                } else ""

                // Build file tree context (like PC's serializeFileTree)
                val treeContext = buildTreeContext(fileTree.value, 0)
                val fileTreeStr = if (treeContext.isNotEmpty()) treeContext else "(No files loaded)"

                // Single intelligent prompt — agent decides what to do
                val systemPrompt = """You are an expert AI coding assistant embedded in an IDE.

PROJECT FILES:
$fileTreeStr
$codeContext

INSTRUCTIONS:
- If the user asks to "scan", "list", "show", "describe", or "tell me about" the project, summarize the file tree above. Do NOT generate code.
- If the user asks to "explain" code, explain it clearly without generating new code.
- If the user asks to "refactor" or "improve" code, return the complete refactored file content in a code block.
- If the user asks to "generate", "create", "write", or "build" something, provide complete, runnable code in a code block.
- For each code block, specify the language after the opening triple backticks (e.g. ```python).
- For multiple files, use separate code blocks with a filename comment on the first line like: // filename: path/to/file.ext
- Be concise and helpful. Match your response to the user's intent."""

                val response = ollamaClient.chat(
                    model = "qwen2.5:0.5b",
                    systemPrompt = systemPrompt,
                    userMessage = text
                )

                // Extract ALL code blocks from the response (matches PC codeBlockRegex)
                var allCodeBlocks = extractAllCodeBlocks(response)
                android.util.Log.d("CodeEditor", "Found ${allCodeBlocks.size} fenced code blocks in response")

                // FALLBACK: If no fenced code blocks found, check if the response is raw code
                if (allCodeBlocks.isEmpty() && looksLikeCode(response)) {
                    val lang = guessLanguageFromCode(response, text)
                    allCodeBlocks = listOf(CodeBlock(lang, response.trim()))
                    android.util.Log.d("CodeEditor", "Unfenced code detected, treating as $lang code block")
                }

                // Add the response text to chat (only if it's NOT pure code that will be filed)
                if (allCodeBlocks.isEmpty()) {
                    agentMessages.add(AgentMsg("agent", response))
                }

                // Single handler for all code blocks
                handleSuggestMode(allCodeBlocks, userMessage, text)

                saveProjectHistory()

            } catch (e: Exception) {
                agentMessages.add(AgentMsg("agent", "Error communicating with Neural Core: ${e.message}"))
                android.util.Log.e("CodeEditor", "Agent error", e)
            } finally {
                isAgentLoading.value = false
            }
        }
    }

    /** Handles Suggest mode — matches PC's createNewFile + modification detection logic */
    private suspend fun handleSuggestMode(codeBlocks: List<CodeBlock>, userMessage: String, originalText: String) {
        if (codeBlocks.isEmpty()) return

        // Modification detection keywords — agent auto-detects code changes
        val modKeywords = listOf(
            "modify", "refine", "update", "change", "fix", "improve", "refactor",
            "redesign", "restyle", "rework", "redo", "rewrite", "optimize", "simplify",
            "add ", "add a ", "add the ", "add to", "insert",
            "in this", "to this", "this file", "this code",
            "edit", "replace", "remove", "delete from",
            "make it", "make the", "convert", "transform", "clean up"
        )
        val isModification = modKeywords.any { userMessage.contains(it) }
        val hasActiveFile = selectedFileUri.value != null && selectedFileName.value.isNotBlank()

        // Single code block + modification request + active file → update existing file
        if (hasActiveFile && codeBlocks.size == 1 && isModification) {
            val code = codeBlocks[0].content
            fileContent.value = code
            isEdited.value = true
            // Auto-save on Android (no Ctrl+S)
            selectedFileUri.value?.let { uri ->
                if (uri.scheme == "file") {
                    File(uri.path!!).writeText(code)
                    isEdited.value = false
                }
            }
            agentMessages.add(AgentMsg("agent", "✅ Updated ${selectedFileName.value}"))
            return
        }

        // Single code block + active file + same language → update existing
        if (hasActiveFile && codeBlocks.size == 1 && !isModification) {
            val block = codeBlocks[0]
            val currentLang = getLanguageFromName(selectedFileName.value)
            val blockLang = block.language
            val langMatches = blockLang == currentLang ||
                    (blockLang == "javascript" && currentLang in listOf("javascript", "jsx")) ||
                    (blockLang == "typescript" && currentLang in listOf("typescript", "tsx"))

            if (langMatches) {
                fileContent.value = block.content
                isEdited.value = true
                selectedFileUri.value?.let { uri ->
                    if (uri.scheme == "file") {
                        File(uri.path!!).writeText(block.content)
                        isEdited.value = false
                    }
                }
                agentMessages.add(AgentMsg("agent", "✅ Updated ${selectedFileName.value}"))
                return
            }
        }

        // Create new file(s) for each code block — matches PC's forEach + createNewFile
        var fileCount = 0
        var lastCreatedUri: Uri? = null
        var lastCreatedName: String? = null

        for ((index, block) in codeBlocks.withIndex()) {
            val filename = determineFileName(block, index, codeBlocks, originalText)
            val createdUri = createFileOnDisk(filename, block.content)
            if (createdUri != null) {
                fileCount++
                lastCreatedUri = createdUri
                lastCreatedName = filename
                android.util.Log.d("CodeEditor", "Created file URI: $createdUri")
            }
        }

        // Open the last created file in the editor
        if (lastCreatedUri != null && lastCreatedName != null) {
            withContext(Dispatchers.Main) {
                readFile(lastCreatedUri, lastCreatedName)
                isEdited.value = false
            }
        }

        when {
            fileCount > 1 -> agentMessages.add(AgentMsg("agent", "✅ Created $fileCount files!"))
            fileCount == 1 -> agentMessages.add(AgentMsg("agent", "✅ Created new file: $lastCreatedName"))
            else -> agentMessages.add(AgentMsg("agent", "📝 Could not save files to disk."))
        }
    }



    // ========== CODE BLOCK EXTRACTION (matches PC codeBlockRegex) ==========

    data class CodeBlock(val language: String, val content: String)

    /** Extract ALL code blocks from markdown response */
    private fun extractAllCodeBlocks(text: String): List<CodeBlock> {
        val regex = Regex("```(\\w+)?\\n([\\s\\S]*?)```")
        return regex.findAll(text).map { match ->
            CodeBlock(
                language = match.groupValues[1].ifBlank { "text" },
                content = match.groupValues[2].trim()
            )
        }.toList()
    }

    /** Check if a response looks like code (for unfenced code detection) */
    private fun looksLikeCode(text: String): Boolean {
        val trimmed = text.trim()
        if (trimmed.length < 20) return false

        val codeIndicators = listOf(
            "function ", "def ", "class ", "import ", "from ", "var ", "let ", "const ",
            "return ", "if (", "for (", "while (", "switch (",
            "public ", "private ", "protected ", "static ",
            "<html", "<div", "<head", "<!DOCTYPE",
            "document.", "console.", "window.",
            "#include", "#import", "package ",
            "fun ", "val ", "suspend ",
            "print(", "println(", "System.out",
            ".addEventListener", ".getElementById", ".querySelector"
        )

        val lines = trimmed.lines()
        val codeLineCount = lines.count { line ->
            val l = line.trim()
            l.endsWith(";") || l.endsWith("{") || l.endsWith("}") ||
            l.endsWith(")") || l.endsWith(":") ||
            l.startsWith("//") || l.startsWith("#") || l.startsWith("/*") ||
            codeIndicators.any { indicator -> l.contains(indicator) }
        }

        // If more than 40% of lines look like code, treat it as code
        return codeLineCount.toFloat() / lines.size.coerceAtLeast(1) > 0.4
    }

    /** Guess the programming language from code content and user request */
    private fun guessLanguageFromCode(code: String, userRequest: String): String {
        val lower = code.lowercase()
        val req = userRequest.lowercase()

        return when {
            lower.contains("<html") || lower.contains("<!doctype") || lower.contains("<div") -> "html"
            lower.contains("document.getelementby") || lower.contains("function ") || lower.contains("const ") || lower.contains("let ") -> "javascript"
            lower.contains("def ") || lower.contains("import ") && lower.contains("print(") -> "python"
            lower.contains("fun ") || lower.contains("val ") || lower.contains("package ") -> "kotlin"
            lower.contains("public class") || lower.contains("system.out") -> "java"
            lower.contains("#include") -> "cpp"
            req.contains("python") -> "python"
            req.contains("html") || req.contains("web") -> "html"
            req.contains("kotlin") -> "kotlin"
            req.contains("java") -> "java"
            else -> "javascript" // safe default for most code generation
        }
    }

    /** Determine filename for a code block — matches PC's extMap + filename logic */
    private fun determineFileName(block: CodeBlock, index: Int, allBlocks: List<CodeBlock>, userRequest: String): String {
        // Check for inline filename comment
        val filenameMatch = Regex("//\\s*filename:\\s*(\\S+)").find(block.content)
            ?: Regex("#\\s*filename:\\s*(\\S+)").find(block.content)
        if (filenameMatch != null) return filenameMatch.groupValues[1]

        // Map language to extension (matches PC's extMap)
        val extMap = mapOf(
            "javascript" to "js", "typescript" to "ts", "python" to "py",
            "html" to "html", "css" to "css", "json" to "json",
            "jsx" to "jsx", "tsx" to "tsx", "kotlin" to "kt",
            "java" to "java", "rust" to "rs", "go" to "go",
            "cpp" to "cpp", "c" to "c", "swift" to "swift",
            "ruby" to "rb", "php" to "php", "shell" to "sh",
            "bash" to "sh", "sql" to "sql", "yaml" to "yml",
            "xml" to "xml", "dart" to "dart"
        )
        val ext = extMap[block.language] ?: block.language

        // Smart filename based on language (matches PC logic)
        var filename = when (block.language) {
            "html" -> "index"
            "css" -> "styles"
            "python" -> "app"
            "javascript", "js", "jsx" -> "script"
            "typescript", "ts", "tsx" -> "app"
            "kotlin", "kt" -> "Main"
            "java" -> "Main"
            else -> "generated"
        }

        // Add index suffix if multiple blocks of same language
        val sameTypeCnt = allBlocks.count { it.language == block.language }
        if (sameTypeCnt > 1) {
            filename += "_${index + 1}"
        }

        return "$filename.$ext"
    }

    /** Get language string from filename */
    private fun getLanguageFromName(filename: String): String {
        val ext = filename.substringAfterLast('.', "").lowercase()
        return mapOf(
            "js" to "javascript", "jsx" to "javascript", "ts" to "typescript", "tsx" to "typescript",
            "py" to "python", "kt" to "kotlin", "java" to "java", "html" to "html",
            "css" to "css", "rs" to "rust", "go" to "go", "cpp" to "cpp", "swift" to "swift"
        )[ext] ?: "text"
    }

    /** Build text representation of file tree for LLM context */
    private fun buildTreeContext(items: List<FileItem>, depth: Int): String {
        return items.joinToString("\n") { item ->
            val indent = "  ".repeat(depth)
            if (item.isFolder) {
                val children = if (item.isExpanded && item.children.isNotEmpty()) "\n" + buildTreeContext(item.children, depth + 1) else ""
                "${indent}📁 ${item.name}/$children"
            } else {
                "${indent}📄 ${item.name}"
            }
        }
    }

    // ========== TERMINAL ==========

    fun executeTerminalCommand(cmd: String) {
        terminalLines.add("$ $cmd")
        
        if (cmd.startsWith("clear")) {
            terminalLines.clear()
            terminalLines.add("> ")
            return
        }
        
        viewModelScope.launch {
            val output = withContext(Dispatchers.IO) {
                try {
                    val projectDir = getProjectDir()
                    val fileDir = projectDir ?: Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
                    
                    val process = ProcessBuilder("/system/bin/sh", "-c", cmd)
                        .directory(fileDir)
                        .redirectErrorStream(true)
                        .start()

                    val reader = BufferedReader(InputStreamReader(process.inputStream))
                    val result = StringBuilder()
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        result.append(line).append("\n")
                    }
                    process.waitFor()
                    val outputStr = result.toString().trim()
                    if (outputStr.isEmpty()) "[No output]" else outputStr
                } catch (e: Exception) {
                    "Error executing command: ${e.message}"
                }
            }
            if (output.isNotEmpty()) {
                val lines = output.split("\n")
                if (lines.size > 50) {
                    terminalLines.addAll(lines.take(25) + listOf("... [output truncated] ...") + lines.takeLast(25))
                } else {
                    terminalLines.addAll(lines)
                }
            }
            terminalLines.add("> ")
        }
    }

    // ========== TREE BUILDING ==========

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

    /** File-based tree builder for local file:// URIs (more reliable than DocumentFile) */
    private fun buildFileTreeFromFile(dir: File, indent: Int): List<FileItem> {
        if (!dir.isDirectory) return emptyList()
        val items = mutableListOf<FileItem>()
        val children = dir.listFiles() ?: return emptyList()
        children
            .sortedWith(compareBy<File> { !it.isDirectory }.thenBy { it.name.lowercase() })
            .forEach { file ->
                if (file.name.startsWith(".")) return@forEach
                items.add(
                    FileItem(
                        name = file.name,
                        uri = Uri.fromFile(file),
                        isFolder = file.isDirectory,
                        indent = indent,
                        children = if (file.isDirectory) buildFileTreeFromFile(file, indent + 1) else emptyList(),
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
