package com.neuralai.agent.core

import com.neuralai.agent.core.llm.OllamaClient
import com.neuralai.agent.data.repository.ChatRepository
import com.neuralai.agent.data.repository.MemoryRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.suspendCancellableCoroutine
import com.neuralai.agent.core.skills.appcontrol.AppControlSkill
import com.neuralai.agent.core.skills.phone.PhoneSkill
import com.neuralai.agent.core.skills.phone.AutonomousCallSkill
import com.neuralai.agent.core.skills.location.LocationSkill
import com.neuralai.agent.core.skills.notification.NotificationSkill
import com.neuralai.agent.core.skills.research.BrowserSkill
import com.neuralai.agent.core.skills.research.WebSearchSkill
import com.neuralai.agent.core.skills.sensor.SensorSkill
import com.neuralai.agent.core.skills.vision.VisionEngine
import com.neuralai.agent.core.skills.device.DeviceControlSkill
import com.neuralai.agent.core.graph.AgentGraph
import com.neuralai.agent.core.security.SafetyFramework
import com.neuralai.agent.core.security.AuditLogger
import com.neuralai.agent.core.voice.TTSEngine
import com.neuralai.agent.services.NeuralNotificationListener
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.delay
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
    private val deviceControlSkill: DeviceControlSkill,
    private val agentGraph: AgentGraph,
    private val safetyFramework: SafetyFramework,
    private val auditLogger: AuditLogger,
    private val autonomousCallSkill: AutonomousCallSkill,
    @ApplicationContext private val context: Context
) {
    private val systemPrompt = """
        You are Neural, an advanced AI agent running directly on the user's Android device. 
        You are concise, highly intelligent, and capable of controlling the device when requested.
        Do not use emojis unless appropriate. Format responses in clean markdown.
    """.trimIndent()

    // Track the last opened app for context-aware command chaining
    private var lastOpenedApp: String? = null

    // ==========================================
    // PUBLIC ENTRY POINT
    // ==========================================

    suspend fun processInput(input: String): String = withContext(Dispatchers.IO) {
        val subCommands = splitCompoundCommand(input)
        
        if (subCommands.size > 1) {
            val results = mutableListOf<String>()
            lastOpenedApp = null
            
            for (cmd in subCommands) {
                val intent = resolveContextAwareIntent(cmd.trim())
                val result = executeWithIntent(cmd.trim(), intent)
                results.add(result)
                
                if (intent == Intent.OPEN_APP) {
                    lastOpenedApp = extractAppName(cmd.trim())
                }
                
                // Smart delays so the UI can catch up
                val delayTime = when (intent) {
                    Intent.OPEN_APP, Intent.INSTALL_APP, Intent.UNINSTALL_APP -> 5000L
                    Intent.TAP, Intent.LONG_PRESS -> 1500L
                    Intent.TYPE_TEXT, Intent.SWIPE -> 1000L
                    Intent.TOGGLE_SETTING, Intent.VOLUME_CONTROL, Intent.BRIGHTNESS -> 500L
                    else -> 500L
                }
                kotlinx.coroutines.delay(delayTime)
            }
            val combined = results.joinToString("\n")
            stateMachine.setState(AIState.IDLE, "READY")
            ttsEngine.speak(combined)
            lastOpenedApp = null
            return@withContext combined
        }
        
        lastOpenedApp = null
        val response = executeSingleCommand(input)
        stateMachine.setState(AIState.IDLE, "READY")
        ttsEngine.speak(response)
        lastOpenedApp = null
        return@withContext response
    }

    // ==========================================
    // CONTEXT-AWARE INTENT RESOLUTION
    // ==========================================

    private fun resolveContextAwareIntent(input: String): Intent {
        val baseIntent = intentParser.parse(input)
        
        // If we just opened an app and the next command is "search X",
        // convert it to in-app search (type into the app's search bar)
        if (lastOpenedApp != null && baseIntent == Intent.WEB_SEARCH) {
            return Intent.TYPE_TEXT
        }
        
        return baseIntent
    }

    // ==========================================
    // COMPOUND COMMAND SPLITTER
    // ==========================================

    private fun splitCompoundCommand(input: String): List<String> {
        val actionKeywords = listOf(
            "open", "launch", "start", "send", "call", "search", "turn", "play",
            "close", "exit", "set", "text", "message", "tap", "type", "swipe",
            "scroll", "take", "install", "uninstall", "click", "go to", "navigate",
            "share", "long press", "mute", "unmute", "pause", "resume", "skip",
            "next", "previous", "enable", "disable", "toggle"
        )
        val lower = input.lowercase()
        
        val delimiters = listOf(" and ", " then ", ", ", " go to ")
        
        var earliestDelim: String? = null
        var earliestIndex = Int.MAX_VALUE
        
        for (delim in delimiters) {
            val delimIndex = lower.indexOf(delim)
            if (delimIndex in 1 until earliestIndex) {
                var afterDelim = lower.substring(delimIndex + delim.length).trimStart()
                if (delim == " go to ") {
                    afterDelim = "go to $afterDelim"
                }
                
                val startsWithAction = actionKeywords.any { afterDelim.startsWith(it) } || delim == " go to "
                
                if (startsWithAction) {
                    earliestIndex = delimIndex
                    earliestDelim = delim
                }
            }
        }
        
        if (earliestDelim != null) {
            val first = lower.substring(0, earliestIndex).trim()
            var second = lower.substring(earliestIndex + earliestDelim.length).trimStart()
            if (earliestDelim == " go to ") {
                second = "go to $second"
            }
            return listOf(first) + splitCompoundCommand(second)
        }
        
        return listOf(input.lowercase().trim())
    }

    // ==========================================
    // INTENT EXECUTION
    // ==========================================

    private suspend fun executeWithIntent(input: String, intent: Intent): String {
        val safety = safetyFramework.evaluate(input)
        if (!safety.isAllowed) {
            auditLogger.log("BLOCKED", input, safety.reason)
            return "⛔ ${safety.reason}"
        }
        if (safety.requiresConsent) {
            auditLogger.log("CONSENT_REQUIRED", input, safety.reason)
        }
        return executeIntent(input, intent)
    }

    private suspend fun executeSingleCommand(input: String): String {
        val safety = safetyFramework.evaluate(input)
        if (!safety.isAllowed) {
            auditLogger.log("BLOCKED", input, safety.reason)
            return "⛔ ${safety.reason}"
        }
        if (safety.requiresConsent) {
            auditLogger.log("CONSENT_REQUIRED", input, safety.reason)
        }
        val intent = intentParser.parse(input)
        return executeIntent(input, intent)
    }

    // ==========================================
    // CORE INTENT ROUTER (ALL 28 INTENTS)
    // ==========================================

    private suspend fun executeIntent(input: String, intent: Intent): String {
        val lower = input.lowercase().trim()
        
        return when (intent) {

            // ── CHAT (LLM) ────────────────────────────────────────
            Intent.CHAT -> {
                stateMachine.setState(AIState.THINKING, "GENERATING RESPONSE...")
                val memoryContext = memoryRepository.searchContext(input)
                val dynamicPrompt = if (memoryContext.contains("No specific memories")) systemPrompt
                else "$systemPrompt\n\n[System Context: $memoryContext]"
                ollamaClient.chat(model = "qwen2.5:0.5b", systemPrompt = dynamicPrompt, userMessage = input)
            }

            // ── WEB SEARCH ────────────────────────────────────────
            Intent.WEB_SEARCH -> {
                stateMachine.setState(AIState.EXECUTING, "SEARCHING THE WEB...")
                val query = lower.replace("search", "").replace("for", "").replace("who is", "").replace("what is", "").replace("look up", "").trim()
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

            // ── OPEN APP ──────────────────────────────────────────
            Intent.OPEN_APP -> {
                stateMachine.setState(AIState.EXECUTING, "LAUNCHING APPLICATION...")
                val appName = extractAppName(lower)
                if (appName.isBlank()) "Please specify an app name."
                else {
                    val success = appControlSkill.launchApp(appName)
                    if (success) "Opening $appName." else "Could not find $appName on this device."
                }
            }

            // ── CLOSE APP ─────────────────────────────────────────
            Intent.CLOSE_APP -> {
                stateMachine.setState(AIState.EXECUTING, "CLOSING APPLICATION...")
                val appName = lower.replace(Regex("\\b(close|exit|quit|kill|force stop|the|app|please)\\b"), "").trim()
                if (appName.isBlank()) {
                    appControlSkill.goBack()
                    appControlSkill.goHome()
                    "Closed current app."
                } else {
                    val success = appControlSkill.closeApp(appName)
                    if (success) "Closed $appName." else "Could not close $appName."
                }
            }

            // ── GO BACK ───────────────────────────────────────────
            Intent.GO_BACK -> {
                val success = appControlSkill.goBack()
                if (success) "Pressed Back." else "Back action failed."
            }

            // ── GO HOME ───────────────────────────────────────────
            Intent.GO_HOME -> {
                val success = appControlSkill.goHome()
                if (success) "Returned to Home screen." else "Home action failed."
            }

            // ── TAP ───────────────────────────────────────────────
            Intent.TAP -> {
                stateMachine.setState(AIState.EXECUTING, "TAPPING ON SCREEN...")
                val target = cleanTapTarget(lower)
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled. Please enable Neural Agent in Settings > Accessibility."
                } else {
                    val success = appControlSkill.tapOnScreen(target)
                    if (success) "Tapped on \"$target\"." else "Could not find \"$target\" on screen."
                }
            }

            // ── LONG PRESS ────────────────────────────────────────
            Intent.LONG_PRESS -> {
                stateMachine.setState(AIState.EXECUTING, "LONG PRESSING...")
                val target = lower.replace(Regex("\\b(long\\s*press|long\\s*click|hold|press\\s*and\\s*hold|on|the)\\b"), "").trim()
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val success = appControlSkill.longPressOnScreen(target)
                    if (success) "Long-pressed on \"$target\"." else "Could not find \"$target\" to long-press."
                }
            }

            // ── TYPE TEXT ─────────────────────────────────────────
            Intent.TYPE_TEXT -> {
                stateMachine.setState(AIState.EXECUTING, "TYPING TEXT...")
                
                // WhatsApp contextual bypass
                val isWhatsApp = appControlSkill.lastLaunchedApp == "whatsapp" || lower.contains("whatsapp")
                if (isWhatsApp && lower.contains("send") && lower.contains(" to ")) {
                    // Ensure WhatsApp is in the foreground first
                    appControlSkill.launchApp("whatsapp")
                    kotlinx.coroutines.delay(2000)
                    
                    val msg = lower.substringAfter("send ").substringBefore(" to ").replace("message", "").replace("text", "").trim()
                    val rawContact = lower.substringAfter(" to ").trim()
                    val contacts = phoneSkill.readContacts(rawContact)
                    val phone = if (contacts.isNotEmpty()) contacts.first().phoneNumber else rawContact
                    val success = phoneSkill.openWhatsAppChat(phone, msg)
                    if (success) "Sending \"$msg\" to $rawContact on WhatsApp." else "Could not open WhatsApp chat."
                }
                // In-app search context
                else if (lastOpenedApp != null && lower.contains("search")) {
                    val query = lower.replace("search", "").replace("for", "").trim()
                    if (!appControlSkill.isServiceActive()) {
                        "⚠️ Accessibility Service not enabled."
                    } else {
                        // Tap the search icon/bar first
                        appControlSkill.tapOnScreen("Search") ||
                            appControlSkill.tapOnScreen("search") ||
                            appControlSkill.tapOnScreen("🔍")
                        kotlinx.coroutines.delay(1000)
                        val typed = appControlSkill.findAndType(null, query)
                        if (typed) "Searching for \"$query\" in $lastOpenedApp." else "Could not find a search field."
                    }
                }
                // Standard typing
                else {
                    val textToType = extractTextToType(lower)
                    if (!appControlSkill.isServiceActive()) {
                        "⚠️ Accessibility Service not enabled."
                    } else {
                        val success = appControlSkill.findAndType(null, textToType)
                        if (success) "Typed: \"$textToType\"" else "Could not find a text field to type into."
                    }
                }
            }

            // ── SWIPE ─────────────────────────────────────────────
            Intent.SWIPE -> {
                stateMachine.setState(AIState.EXECUTING, "SWIPING...")
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val direction = when {
                        lower.contains("up") -> "up"
                        lower.contains("down") -> "down"
                        lower.contains("left") -> "left"
                        lower.contains("right") -> "right"
                        else -> "up"
                    }
                    val success = when (direction) {
                        "up" -> appControlSkill.swipeUp()
                        "down" -> appControlSkill.swipeDown()
                        "left" -> appControlSkill.swipeGesture(800f, 1000f, 200f, 1000f)
                        "right" -> appControlSkill.swipeGesture(200f, 1000f, 800f, 1000f)
                        else -> appControlSkill.swipeUp()
                    }
                    if (success) "Swiped $direction." else "Swipe failed."
                }
            }

            // ── SCROLL (with optional timed loop) ─────────────────
            Intent.SCROLL -> {
                stateMachine.setState(AIState.EXECUTING, "SCROLLING...")
                if (!appControlSkill.isServiceActive()) {
                    "⚠️ Accessibility Service not enabled."
                } else {
                    val durationMs = extractDurationMs(lower)
                    if (durationMs > 0) {
                        val scrollUp = lower.contains("up") || lower.contains("top")
                        val endTime = System.currentTimeMillis() + durationMs
                        while (System.currentTimeMillis() < endTime) {
                            if (scrollUp) appControlSkill.swipeDown() else appControlSkill.swipeUp()
                            kotlinx.coroutines.delay(2500)
                        }
                        "Finished scrolling."
                    } else {
                        val success = if (lower.contains("up") || lower.contains("top")) appControlSkill.swipeDown()
                        else appControlSkill.swipeUp()
                        if (success) "Scrolled ${if (lower.contains("up")) "up" else "down"}." else "Scroll failed."
                    }
                }
            }

            // ── SCREENSHOT ────────────────────────────────────────
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
                            val objects = visionEngine.analyzeObjects(bitmap)
                            val text = visionEngine.readText(bitmap)
                            val faces = visionEngine.analyzeFaces(bitmap)
                            val sb = StringBuilder("📸 Screenshot captured:\n")
                            if (objects.isNotEmpty()) sb.appendLine("Objects: ${objects.joinToString { it.labels.joinToString { l -> l.text } }}")
                            if (text?.text?.isNotEmpty() == true) sb.appendLine("Text: ${text.text.take(300)}")
                            if (faces.isNotEmpty()) sb.appendLine("Faces: ${faces.size}")
                            sb.toString()
                        } else {
                            "Screenshot failed."
                        }
                    } catch (e: Exception) { "Screenshot error: ${e.message}" }
                }
            }

            // ── READ SCREEN ───────────────────────────────────────
            Intent.READ_SCREEN -> {
                stateMachine.setState(AIState.EXECUTING, "READING SCREEN...")
                if (!appControlSkill.isServiceActive()) "⚠️ Accessibility Service not enabled."
                else "📱 Screen Content:\n${appControlSkill.readScreen()}"
            }

            // ── INSTALL APP ───────────────────────────────────────
            Intent.INSTALL_APP -> {
                stateMachine.setState(AIState.EXECUTING, "OPENING PLAY STORE...")
                val appName = lower.replace(Regex("\\b(install|download|the|app|please)\\b"), "").trim()
                if (appName.isBlank()) "Please specify an app name."
                else {
                    val success = appControlSkill.installApp(appName)
                    if (success) "Opening Play Store for \"$appName\"." else "Could not open Play Store."
                }
            }

            // ── UNINSTALL APP ─────────────────────────────────────
            Intent.UNINSTALL_APP -> {
                stateMachine.setState(AIState.EXECUTING, "UNINSTALLING...")
                val appName = lower.replace(Regex("\\b(uninstall|remove|delete|the|app|please)\\b"), "").trim()
                if (appName.isBlank()) "Please specify an app name."
                else {
                    val success = appControlSkill.uninstallApp(appName)
                    if (success) "Uninstall prompt for \"$appName\"." else "Could not find \"$appName\"."
                }
            }

            // ── MEDIA CONTROL ─────────────────────────────────────
            Intent.MEDIA_CONTROL -> {
                stateMachine.setState(AIState.EXECUTING, "MEDIA CONTROL...")
                deviceControlSkill.mediaControl(lower)
            }

            // ── VOLUME CONTROL ────────────────────────────────────
            Intent.VOLUME_CONTROL -> {
                stateMachine.setState(AIState.EXECUTING, "ADJUSTING VOLUME...")
                deviceControlSkill.setVolume(lower)
            }

            // ── BRIGHTNESS ────────────────────────────────────────
            Intent.BRIGHTNESS -> {
                stateMachine.setState(AIState.EXECUTING, "ADJUSTING BRIGHTNESS...")
                deviceControlSkill.setBrightness(lower)
            }

            // ── TOGGLE SETTING (wifi, bluetooth, flashlight, etc.) ─
            Intent.TOGGLE_SETTING -> {
                stateMachine.setState(AIState.EXECUTING, "TOGGLING SETTING...")
                deviceControlSkill.toggleSetting(lower)
            }

            // ── ALARM / TIMER ─────────────────────────────────────
            Intent.ALARM_TIMER -> {
                stateMachine.setState(AIState.EXECUTING, "SETTING ALARM/TIMER...")
                deviceControlSkill.setAlarm(lower)
            }

            // ── TAKE PHOTO / VIDEO ────────────────────────────────
            Intent.TAKE_PHOTO -> {
                stateMachine.setState(AIState.EXECUTING, "OPENING CAMERA...")
                deviceControlSkill.openCamera(lower)
            }

            // ── SHARE ─────────────────────────────────────────────
            Intent.SHARE -> {
                stateMachine.setState(AIState.EXECUTING, "SHARING...")
                val textToShare = lower.replace(Regex("\\b(share|this|it|please)\\b"), "").trim()
                if (textToShare.isBlank()) deviceControlSkill.shareText("Shared from Neural Agent")
                else deviceControlSkill.shareText(textToShare)
            }

            // ── READ NOTIFICATIONS ────────────────────────────────
            Intent.READ_NOTIFICATIONS -> {
                stateMachine.setState(AIState.EXECUTING, "READING NOTIFICATIONS...")
                "🔔 Recent Notifications:\n${NeuralNotificationListener.getFormattedNotifications()}"
            }

            // ── SENSOR DATA ───────────────────────────────────────
            Intent.SENSOR_DATA -> {
                stateMachine.setState(AIState.EXECUTING, "READING SENSORS...")
                sensorSkill.getSensorData()
            }

            // ── VISION ANALYZE ────────────────────────────────────
            Intent.VISION_ANALYZE -> {
                stateMachine.setState(AIState.EXECUTING, "ANALYZING VISUAL DATA...")
                if (appControlSkill.isServiceActive()) {
                    try {
                        val bitmap = suspendCancellableCoroutine<android.graphics.Bitmap?> { cont ->
                            appControlSkill.takeScreenshot { bmp -> cont.resume(bmp) }
                        }
                        if (bitmap != null) {
                            val objects = visionEngine.analyzeObjects(bitmap)
                            val text = visionEngine.readText(bitmap)
                            val faces = visionEngine.analyzeFaces(bitmap)
                            val sb = StringBuilder("👁️ Visual Analysis:\n")
                            if (objects.isNotEmpty()) sb.appendLine("Objects: ${objects.joinToString { it.labels.joinToString { l -> l.text } }}")
                            if (text?.text?.isNotEmpty() == true) sb.appendLine("Text: ${text.text.take(500)}")
                            if (faces.isNotEmpty()) sb.appendLine("Faces: ${faces.size}")
                            sb.toString()
                        } else "Could not capture screen for analysis."
                    } catch (_: Exception) { "Visual analysis failed. Try Camera Quick Action." }
                } else "Enable Accessibility Service for visual analysis."
            }

            // ── TRADING ───────────────────────────────────────────
            Intent.TRADING -> {
                stateMachine.setState(AIState.EXECUTING, "ACCESSING TERMINAL...")
                "Trading Terminal is online. Navigate to the Trading screen."
            }

            // ── MEMORY RECALL ─────────────────────────────────────
            Intent.MEMORY_RECALL -> {
                if (lower.contains("remember")) {
                    val fact = lower.replace("remember that", "").replace("remember", "").trim()
                    memoryRepository.storeMemory(fact)
                    "Memory stored: $fact."
                } else {
                    "I remember: " + memoryRepository.searchContext(input)
                }
            }

            // ── AUTONOMOUS CALL ──────────────────────────────────
            Intent.AUTONOMOUS_CALL -> {
                stateMachine.setState(AIState.EXECUTING, "AUTONOMOUS CALL STARTING...")
                handleAutonomousCall(lower)
            }

            // ── AUTO-ANSWER TOGGLE ───────────────────────────────
            Intent.AUTO_ANSWER_TOGGLE -> {
                val isDisable = lower.contains("stop") || lower.contains("disable") || lower.contains("turn off") || lower.contains("don't")
                if (isDisable) {
                    autonomousCallSkill.setAutoAnswerEnabled(false)
                } else {
                    autonomousCallSkill.setAutoAnswerEnabled(
                        enabled = true,
                        purpose = "Answer calls on behalf of ${lower.substringAfter("behalf of").trim().ifBlank { "the user" }}",
                        onUpdate = { update ->
                            android.util.Log.d("NeuralAgent", "AutoAnswer: $update")
                        },
                        onComplete = { summary ->
                            android.util.Log.d("NeuralAgent", "AutoAnswer complete: ${summary.take(200)}")
                        }
                    )
                }
            }

            // ── ACCEPT INCOMING CALL ─────────────────────────────
            Intent.ACCEPT_CALL -> {
                stateMachine.setState(AIState.EXECUTING, "ANSWERING CALL...")
                // Answer the ringing call and start autonomous conversation
                try {
                    val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as? android.telecom.TelecomManager
                    telecomManager?.acceptRingingCall()
                    delay(2000) // Wait for call to connect

                    // Enable speakerphone
                    val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
                    audioManager.isSpeakerphoneOn = true
                    val maxVol = audioManager.getStreamMaxVolume(android.media.AudioManager.STREAM_MUSIC)
                    audioManager.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, maxVol, 0)

                    // Start autonomous conversation on the active call
                    autonomousCallSkill.startConversationOnActiveCall(
                        callerName = "Incoming Caller",
                        purpose = "Answer the call and assist the caller on behalf of the user",
                        onUpdate = { update ->
                            android.util.Log.d("NeuralAgent", "AcceptCall: $update")
                        },
                        onComplete = { summary ->
                            android.util.Log.d("NeuralAgent", "AcceptCall complete: ${summary.take(200)}")
                        }
                    )
                } catch (e: Exception) {
                    "❌ Failed to answer the call: ${e.message}"
                }
            }

            // ── SYSTEM CONTROL ────────────────────────────────────
            Intent.SYSTEM_CONTROL -> {
                stateMachine.setState(AIState.EXECUTING, "SYSTEM ACTION...")
                handleSystemControl(lower)
            }
        }
    }

    // ==========================================
    // HELPER FUNCTIONS
    // ==========================================

    private fun extractAppName(input: String): String {
        val pattern = Regex(".*(open|launch|start|run)\\s+(.+)")
        val match = pattern.find(input)
        return if (match != null) {
            match.groupValues[2].replace(Regex("\\s+(app|application|for me|please|bro|dude|man)$"), "").trim()
        } else {
            input.replace(Regex("(hey|hi|hello|bro|dude|neural|please|can you|could you|open|launch|start|run|the|a|an)"), "").trim()
        }
    }

    private fun cleanTapTarget(input: String): String {
        val fillerWords = listOf("section", "tab", "page", "button", "icon", "menu", "bar", "area", "panel", "option", "link", "the", "a", "an", "on", "in")
        var target = input
            .replace("tap on", "").replace("click on", "").replace("press on", "")
            .replace("go to", "").replace("navigate to", "")
            .replace("tap", "").replace("click", "").replace("press", "")
            .trim()
        for (filler in fillerWords) {
            target = target.replace(Regex("\\b$filler\\b"), "").trim()
        }
        target = target.replace(Regex("\\s+"), " ").trim()
        return target.replaceFirstChar { it.uppercase() }
    }

    private fun extractTextToType(input: String): String {
        val quoted = Regex("[\"'](.+?)[\"']").find(input)
        if (quoted != null) return quoted.groupValues[1]

        val typeMatch = Regex("type\\s+(.+?)(?:\\s+(?:into|in|on)\\s+|$)").find(input)
        if (typeMatch != null) return typeMatch.groupValues[1].trim()

        val sendMatch = Regex("(?:send|write)\\s+(?:message|text|sms)?\\s*(.+?)(?:\\s+to\\s+|$)").find(input)
        if (sendMatch != null) return sendMatch.groupValues[1].trim()

        val searchMatch = Regex("search\\s+(?:for\\s+)?(.+)").find(input)
        if (searchMatch != null) return searchMatch.groupValues[1].trim()

        return input.substringAfter("type ", input).substringAfter("send ", input).trim()
    }

    private fun extractDurationMs(input: String): Long {
        val match = Regex("for\\s+(\\d+)\\s*(minute|minutes|min|mins|second|seconds|sec|secs|hour|hours|hr|hrs)").find(input)
        if (match != null) {
            val amount = match.groupValues[1].toLongOrNull() ?: 1L
            val unit = match.groupValues[2]
            return when {
                unit.startsWith("hour") || unit.startsWith("hr") -> amount * 3600 * 1000L
                unit.startsWith("min") -> amount * 60 * 1000L
                unit.startsWith("sec") -> amount * 1000L
                else -> 0L
            }
        }
        return 0L
    }

    /**
     * Handle autonomous call: extract contact name/number + purpose, then start the AI call.
     */
    private suspend fun handleAutonomousCall(input: String): String {
        // Try to extract a phone number first (e.g. +919405580347)
        val phoneRegex = Regex("""(\+?\d[\d\s\-]{6,14}\d)""")
        val phoneMatch = phoneRegex.find(input)

        // Extract the purpose — everything after "and" / "to" following the contact/number
        val purposeRegex = Regex("""\b(and\s+tell|and\s+ask|and\s+say|and\s+inform|to\s+tell|to\s+ask|to\s+discuss|to\s+say|about)\b(.+)""")
        val purposeMatch = purposeRegex.find(input)
        val purpose = purposeMatch?.groupValues?.getOrNull(2)?.trim()
            ?: "General conversation on behalf of the user"

        if (phoneMatch != null) {
            // Direct phone number provided
            val phoneNumber = phoneMatch.value.replace(Regex("[\\s\\-]"), "")
            stateMachine.setState(AIState.EXECUTING, "CALLING $phoneNumber...")

            return autonomousCallSkill.startAutonomousCall(
                name = phoneNumber,
                purpose = purpose,
                onUpdate = { update ->
                    android.util.Log.d("NeuralAgent", "AutoCall: $update")
                },
                onComplete = { summary ->
                    android.util.Log.d("NeuralAgent", "AutoCall complete: ${summary.take(200)}")
                }
            )
        }

        // No phone number found — try to extract a contact name
        val cleaned = input
            .replace(Regex("\\b(call|ring|dial|phone)\\b"), " ")
            .replace(Regex("\\b(on\\s*(my|your|his|her|their)?\\s*behalf|on\\s*behalf\\s*of\\s*\\w+)\\b"), " ")
            .replace(Regex("\\b(speak\\s*for\\s*me|talk\\s*(to|for|on)\\s*(me|him|her|them)|represent\\s*me|as\\s*me)\\b"), " ")
            .replace(Regex("\\b(and\\s+tell|and\\s+ask|and\\s+say|and\\s+inform|to\\s+tell|to\\s+ask|to\\s+discuss|about)\\b.*"), " ")
            .replace(Regex("\\b(and|then|also|please|can\\s*you|could\\s*you|i\\s*want\\s*you\\s*to|that\\s*you\\s*are|calling)\\b"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        val contactName = cleaned.ifBlank { null }

        if (contactName.isNullOrBlank()) {
            return "❌ I couldn't determine who to call. Please say something like: \"Call John and talk on my behalf about the meeting.\""
        }

        stateMachine.setState(AIState.EXECUTING, "CALLING $contactName...")

        return autonomousCallSkill.startAutonomousCall(
            name = contactName,
            purpose = purpose,
            onUpdate = { update ->
                android.util.Log.d("NeuralAgent", "AutoCall: $update")
            },
            onComplete = { summary ->
                android.util.Log.d("NeuralAgent", "AutoCall complete: ${summary.take(200)}")
            }
        )
    }

    private suspend fun handleSystemControl(input: String): String {
        return when {
            input.contains("location") || input.contains("where am i") || input.contains("gps") -> {
                locationSkill.getLocationString()
            }
            input.contains("call") -> {
                // Extract just the phone number or contact name (stop at "and", "to", etc.)
                val phoneRegex = Regex("""(\+?\d[\d\s\-]{6,14}\d)""")
                val phoneMatch = phoneRegex.find(input)

                if (phoneMatch != null) {
                    val number = phoneMatch.value.replace(Regex("[\\s\\-]"), "")
                    phoneSkill.makeCall(number)
                    "Calling $number."
                } else {
                    // Extract contact name: text after "call" but before "and"/"to"/"about"
                    val target = input
                        .replace(Regex(".*\\bcall\\b\\s*"), "")
                        .replace(Regex("\\s*(and|to|about|on|for)\\b.*"), "")
                        .trim()
                    val contacts = phoneSkill.readContacts(target)
                    if (contacts.isNotEmpty()) {
                        val contact = contacts.first()
                        phoneSkill.makeCall(contact.phoneNumber)
                        "Calling ${contact.name}."
                    } else {
                        phoneSkill.makeCall(target)
                        "Calling $target."
                    }
                }
            }
            input.contains("send") && (input.contains("sms") || input.contains("message") || input.contains("text")) -> {
                "SMS skill ready. Format: 'send sms to [name]: [message]'."
            }
            input.contains("back") -> {
                if (appControlSkill.goBack()) "Pressed Back." else "Back failed."
            }
            input.contains("home") -> {
                if (appControlSkill.goHome()) "Home." else "Home failed."
            }
            else -> "System control: location, call, sms, back, home."
        }
    }
}
