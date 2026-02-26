package com.neuralai.agent.core

import com.neuralai.agent.core.llm.OllamaClient
import com.neuralai.agent.data.repository.ChatRepository
import com.neuralai.agent.data.repository.MemoryRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.suspendCancellableCoroutine
import com.neuralai.agent.core.skills.appcontrol.AppControlSkill
import com.neuralai.agent.core.skills.phone.PhoneSkill
import com.neuralai.agent.core.skills.location.LocationSkill
import com.neuralai.agent.core.skills.notification.NotificationSkill
import com.neuralai.agent.core.skills.research.BrowserSkill
import com.neuralai.agent.core.skills.research.WebSearchSkill
import com.neuralai.agent.core.skills.sensor.SensorSkill
import com.neuralai.agent.core.skills.vision.VisionEngine
import com.neuralai.agent.core.graph.AgentGraph
import com.neuralai.agent.core.security.SafetyFramework
import com.neuralai.agent.core.security.AuditLogger
import com.neuralai.agent.core.voice.TTSEngine
import com.neuralai.agent.services.NeuralNotificationListener
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume

@Singleton
class NeuralAgent @Inject constructor(
    private val ollamaClient: OllamaClient,
    private val intentParser: IntentParser,
    private val stateMachine: StateMachine,
    private val chatRepository: ChatRepository,
    private val memoryRepository: MemoryRepository,
    private val ttsEngine: TTSEngine,
    private val appControlSkill: AppControlSkill,
    private val phoneSkill: PhoneSkill,
    private val locationSkill: LocationSkill,
    private val notificationSkill: NotificationSkill,
    private val webSearchSkill: WebSearchSkill,
    private val browserSkill: BrowserSkill,
    private val sensorSkill: SensorSkill,
    private val visionEngine: VisionEngine,
    private val agentGraph: AgentGraph,
    private val safetyFramework: SafetyFramework,
    private val auditLogger: AuditLogger
) {
    private val systemPrompt = """
        You are Neural, an advanced AI agent running directly on the user's Android device. 
        You are concise, highly intelligent, and capable of controlling the device when requested.
        Do not use emojis unless appropriate. Format responses in clean markdown.
    """.trimIndent()

    suspend fun processInput(input: String): String = withContext(Dispatchers.IO) {
        val subCommands = splitCompoundCommand(input)
        
        if (subCommands.size > 1) {
            val results = mutableListOf<String>()
            for (cmd in subCommands) {
                val result = executeSingleCommand(cmd.trim())
                results.add(result)
                kotlinx.coroutines.delay(500)
            }
            val combined = results.joinToString("\n")
            stateMachine.setState(AIState.IDLE, "READY")
            ttsEngine.speak(combined)
            return@withContext combined
        }
        
        val response = executeSingleCommand(input)
        stateMachine.setState(AIState.IDLE, "READY")
        ttsEngine.speak(response)
        return@withContext response
    }

    private fun splitCompoundCommand(input: String): List<String> {
        val actionKeywords = listOf("open", "launch", "start", "send", "call", "search", "turn", "play", "close", "set", "text", "message", "tap", "type", "swipe", "scroll", "take", "install", "uninstall")
        val lower = input.lowercase()
        val andIndex = lower.indexOf(" and ")
        if (andIndex > 0) {
            val afterAnd = lower.substring(andIndex + 5).trimStart()
            val startsWithAction = actionKeywords.any { afterAnd.startsWith(it) }
            if (startsWithAction) {
                val first = input.substring(0, andIndex).trim()
                val second = input.substring(andIndex + 5).trim()
                return listOf(first) + splitCompoundCommand(second)
            }
        }
        return listOf(input)
    }

    private suspend fun executeSingleCommand(input: String): String {
        stateMachine.setState(AIState.THINKING, "ANALYZING INTENT...")
        
        val safety = safetyFramework.evaluate(input)
        if (!safety.isAllowed) {
            auditLogger.log("BLOCKED", input, safety.reason)
            return "⛔ ${safety.reason}"
        }
        if (safety.requiresConsent) {
            auditLogger.log("CONSENT_REQUIRED", input, safety.reason)
        }
        
        val intent = intentParser.parse(input)
        
        return when (intent) {
            Intent.CHAT -> {
                stateMachine.setState(AIState.THINKING, "GENERATING RESPONSE...")
                val memoryContext = memoryRepository.searchContext(input)
                val dynamicPrompt = if (memoryContext.contains("No specific memories")) {
                    systemPrompt
                } else {
                    "$systemPrompt\n\n[System Context: $memoryContext]"
                }
                ollamaClient.chat(model = "qwen2.5:0.5b", systemPrompt = dynamicPrompt, userMessage = input)
            }

            Intent.WEB_SEARCH -> {
                val lower = input.lowercase()
                if (lower.contains("open") || lower.contains("go to")) {
                    stateMachine.setState(AIState.EXECUTING, "OPENING BROWSER...")
                    val targetUrl = lower.replace("open", "").replace("go to", "").trim()
                    browserSkill.openUrl(targetUrl)
                    "Opening $targetUrl in your browser."
                } else {
                    stateMachine.setState(AIState.EXECUTING, "SEARCHING THE WEB...")
                    val query = lower.replace("search", "").replace("for", "").replace("who is", "").replace("what is", "").trim()
                    val results = webSearchSkill.search(query)
                    if (results.isEmpty()) {
                        "I couldn't find any search results for '$query'."
                    } else {
                        val topResult = results.first()
                        stateMachine.setState(AIState.EXECUTING, "READING SITE DATA...")
                        val pageText = webSearchSkill.fetchPage(topResult.url)
                        stateMachine.setState(AIState.THINKING, "ANALYZING ARTICLE...")
                        ollamaClient.chat(
                            model = "qwen2.5:0.5b",
                            systemPrompt = "You are a web reading assistant. Summarize the provided text to answer the query directly.",
                            userMessage = "User Query: \"$input\"\nArticle: ${topResult.title}\n$pageText"
                        )
                    }
                }
            }

            Intent.OPEN_APP -> {
                stateMachine.setState(AIState.EXECUTING, "LAUNCHING APPLICATION...")
                val lower = input.lowercase()
                val pattern = Regex(".*(open|launch|start|run)\\s+(.+)")
                val match = pattern.find(lower)
                val appName = if (match != null) {
                    match.groupValues[2].replace(Regex("\\s+(app|application|for me|please|bro|dude|man)$"), "").trim()
                } else {
                    lower.replace(Regex("(hey|hi|hello|bro|dude|neural|please|can you|could you|open|launch|start|run|the|a|an)"), "").trim()
                }
                if (appName.isBlank()) "Please specify an app name."
                else {
                    val success = appControlSkill.launchApp(appName)
                    if (success) "Opening $appName." else "Could not find $appName on this device."
                }
            }

            // ==========================================
            // DEVICE AUTOMATION (Accessibility Service)
            // ==========================================

            Intent.TAP -> {
                stateMachine.setState(AIState.EXECUTING, "TAPPING ON SCREEN...")
                val lower = input.lowercase()
                val target = lower.replace("tap on", "").replace("click on", "").replace("press on", "")
                    .replace("tap", "").replace("click", "").replace("press", "").trim()
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled. Please enable Neural Agent in Settings > Accessibility."
                } else {
                    val success = appControlSkill.tapOnScreen(target)
                    if (success) "Tapped on \"$target\"." else "Could not find \"$target\" on screen."
                }
            }

            Intent.TYPE_TEXT -> {
                stateMachine.setState(AIState.EXECUTING, "TYPING TEXT...")
                val lower = input.lowercase()
                // Parse patterns like: "type hello in search" or "send message hi to John"
                val textToType = extractTextToType(lower)
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled. Please enable Neural Agent in Settings > Accessibility."
                } else {
                    val success = appControlSkill.findAndType(null, textToType)
                    if (success) "Typed: \"$textToType\"" else "Could not find a text field to type into."
                }
            }

            Intent.SWIPE -> {
                stateMachine.setState(AIState.EXECUTING, "SWIPING...")
                val lower = input.lowercase()
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val success = when {
                        lower.contains("up") -> appControlSkill.swipeUp()
                        lower.contains("down") -> appControlSkill.swipeDown()
                        lower.contains("left") -> appControlSkill.swipeGesture(800f, 1000f, 200f, 1000f)
                        lower.contains("right") -> appControlSkill.swipeGesture(200f, 1000f, 800f, 1000f)
                        else -> appControlSkill.swipeUp()
                    }
                    val direction = when {
                        lower.contains("up") -> "up"
                        lower.contains("down") -> "down"
                        lower.contains("left") -> "left"
                        lower.contains("right") -> "right"
                        else -> "up"
                    }
                    if (success) "Swiped $direction." else "Swipe failed."
                }
            }

            Intent.SCROLL -> {
                stateMachine.setState(AIState.EXECUTING, "SCROLLING...")
                val lower = input.lowercase()
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val success = if (lower.contains("up") || lower.contains("top")) appControlSkill.swipeDown()
                    else appControlSkill.swipeUp()
                    if (success) "Scrolled ${if (lower.contains("up")) "up" else "down"}." else "Scroll failed."
                }
            }

            Intent.SCREENSHOT -> {
                stateMachine.setState(AIState.EXECUTING, "CAPTURING SCREENSHOT...")
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    try {
                        val bitmap = suspendCancellableCoroutine<android.graphics.Bitmap?> { cont ->
                            appControlSkill.takeScreenshot { bmp -> cont.resume(bmp) }
                        }
                        if (bitmap != null) {
                            stateMachine.setState(AIState.THINKING, "ANALYZING SCREENSHOT...")
                            // Run ML Kit analysis on the screenshot
                            val objects = visionEngine.analyzeObjects(bitmap)
                            val text = visionEngine.readText(bitmap)
                            val faces = visionEngine.analyzeFaces(bitmap)

                            val sb = StringBuilder("📸 Screenshot captured and analyzed:\n")
                            if (objects.isNotEmpty()) {
                                sb.appendLine("Objects: ${objects.joinToString { it.labels.joinToString { l -> l.text } }}")
                            }
                            if (text?.text?.isNotEmpty() == true) {
                                sb.appendLine("Text found: ${text.text.take(300)}")
                            }
                            if (faces.isNotEmpty()) {
                                sb.appendLine("Faces detected: ${faces.size}")
                            }
                            sb.toString()
                        } else {
                            "Screenshot failed. Requires Android 11+ and Accessibility Service enabled."
                        }
                    } catch (e: Exception) {
                        "Screenshot error: ${e.message}"
                    }
                }
            }

            Intent.READ_SCREEN -> {
                stateMachine.setState(AIState.EXECUTING, "READING SCREEN CONTENT...")
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val content = appControlSkill.readScreen()
                    "📱 Screen Content:\n$content"
                }
            }

            // ==========================================
            // APP MANAGEMENT
            // ==========================================

            Intent.INSTALL_APP -> {
                stateMachine.setState(AIState.EXECUTING, "OPENING PLAY STORE...")
                val lower = input.lowercase()
                val appName = lower.replace("install", "").replace("app", "").replace("the", "").replace("please", "").trim()
                if (appName.isBlank()) "Please specify an app name to install."
                else {
                    val success = appControlSkill.installApp(appName)
                    if (success) "Opening Play Store to install \"$appName\"."
                    else "Could not open Play Store."
                }
            }

            Intent.UNINSTALL_APP -> {
                stateMachine.setState(AIState.EXECUTING, "UNINSTALLING APPLICATION...")
                val lower = input.lowercase()
                val appName = lower.replace("uninstall", "").replace("remove app", "").replace("delete app", "")
                    .replace("app", "").replace("the", "").replace("please", "").trim()
                if (appName.isBlank()) "Please specify an app name to uninstall."
                else {
                    val success = appControlSkill.uninstallApp(appName)
                    if (success) "Opening uninstall prompt for \"$appName\"."
                    else "Could not find \"$appName\" to uninstall."
                }
            }

            // ==========================================
            // NOTIFICATIONS & SENSORS
            // ==========================================

            Intent.READ_NOTIFICATIONS -> {
                stateMachine.setState(AIState.EXECUTING, "READING NOTIFICATIONS...")
                val notifs = NeuralNotificationListener.getFormattedNotifications()
                "🔔 Recent Notifications:\n$notifs"
            }

            Intent.SENSOR_DATA -> {
                stateMachine.setState(AIState.EXECUTING, "READING SENSORS...")
                sensorSkill.getSensorData()
            }

            // ==========================================
            // EXISTING INTENTS
            // ==========================================

            Intent.VISION_ANALYZE -> {
                stateMachine.setState(AIState.EXECUTING, "INITIALIZING OPTICS...")
                if (appControlSkill.isServiceActive()) {
                    try {
                        val bitmap = suspendCancellableCoroutine<android.graphics.Bitmap?> { cont ->
                            appControlSkill.takeScreenshot { bmp -> cont.resume(bmp) }
                        }
                        if (bitmap != null) {
                            stateMachine.setState(AIState.THINKING, "ANALYZING VISUAL DATA...")
                            val objects = visionEngine.analyzeObjects(bitmap)
                            val text = visionEngine.readText(bitmap)
                            val faces = visionEngine.analyzeFaces(bitmap)
                            val sb = StringBuilder("👁️ Visual Analysis:\n")
                            if (objects.isNotEmpty()) sb.appendLine("Objects: ${objects.joinToString { it.labels.joinToString { l -> l.text } }}")
                            if (text?.text?.isNotEmpty() == true) sb.appendLine("Text: ${text.text.take(500)}")
                            if (faces.isNotEmpty()) sb.appendLine("Faces: ${faces.size} detected")
                            if (objects.isEmpty() && (text?.text?.isEmpty() != false) && faces.isEmpty()) sb.appendLine("No significant elements detected.")
                            sb.toString()
                        } else {
                            "Optics are online. Please tap the Camera Quick Action to open the live feed."
                        }
                    } catch (_: Exception) {
                        "Optics are online. Please tap the Camera Quick Action to open the live feed."
                    }
                } else {
                    "Optics are online. Enable Accessibility Service for screenshot analysis, or tap Camera Quick Action."
                }
            }

            Intent.TRADING -> {
                stateMachine.setState(AIState.EXECUTING, "ACCESSING TERMINAL...")
                "Trading Terminal is online. Navigate to the Trading screen to view live charts and run AI analysis."
            }

            Intent.MEMORY_RECALL -> {
                val lower = input.lowercase()
                if (lower.contains("remember")) {
                    stateMachine.setState(AIState.EXECUTING, "STORING MEMORY...")
                    val factToRemember = lower.replace("remember that", "").replace("remember", "").trim()
                    memoryRepository.storeMemory(factToRemember)
                    "Memory stored: $factToRemember."
                } else {
                    stateMachine.setState(AIState.THINKING, "SEARCHING MEMORY BANKS...")
                    "I remember: " + memoryRepository.searchContext(input)
                }
            }

            Intent.SYSTEM_CONTROL -> {
                stateMachine.setState(AIState.EXECUTING, "EXECUTING SYSTEM ACTION...")
                handleSystemControl(input)
            }
        }
    }

    /**
     * Extract the text to type from user input.
     * Handles: "type hello", "send message hi", "type 'hello world' in search"
     */
    private fun extractTextToType(input: String): String {
        // Try quoted text first
        val quoted = Regex("[\"'](.+?)[\"']").find(input)
        if (quoted != null) return quoted.groupValues[1]

        // "type X into/in Y" or "type X"
        val typeMatch = Regex("type\\s+(.+?)(?:\\s+(?:into|in|on)\\s+|$)").find(input)
        if (typeMatch != null) return typeMatch.groupValues[1].trim()

        // "send message X" or "send text X"
        val sendMatch = Regex("(?:send|write)\\s+(?:message|text|sms)?\\s*(.+?)(?:\\s+to\\s+|$)").find(input)
        if (sendMatch != null) return sendMatch.groupValues[1].trim()

        // Fallback: everything after "type"
        return input.substringAfter("type ", input).trim()
    }

    private suspend fun handleSystemControl(input: String): String {
        val lower = input.lowercase()
        
        return when {
            lower.contains("location") || lower.contains("where am i") || lower.contains("gps") -> {
                locationSkill.getLocationString()
            }
            lower.contains("call") -> {
                val target = lower.replace("call", "").trim()
                val contacts = phoneSkill.readContacts(target)
                if (contacts.isNotEmpty()) {
                    val contact = contacts.first()
                    phoneSkill.makeCall(contact.phoneNumber)
                    "Calling ${contact.name} at ${contact.phoneNumber}."
                } else {
                    phoneSkill.makeCall(target)
                    "Calling $target."
                }
            }
            lower.contains("send") && (lower.contains("sms") || lower.contains("message") || lower.contains("text")) -> {
                "SMS skill is ready. Please provide a contact name and message in the format: 'send sms to [name]: [message]'."
            }
            lower.contains("notify") || lower.contains("notification") -> {
                notificationSkill.showNotification("Neural Agent", "System notification triggered by voice command.")
                "Notification posted."
            }
            lower.contains("back") -> {
                val success = appControlSkill.goBack()
                if (success) "Pressed Back." else "Back action failed."
            }
            lower.contains("home") -> {
                val success = appControlSkill.goHome()
                if (success) "Pressed Home." else "Home action failed."
            }
            else -> {
                "System control acknowledged. Available: location, call, send sms, notify, back, home."
            }
        }
    }
}
