package com.neuralai.agent.core.skills.phone

import android.content.Context
import android.media.AudioManager
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyManager
import android.util.Log
import com.neuralai.agent.core.llm.OllamaClient
import com.neuralai.agent.core.voice.TTSEngine
import com.neuralai.agent.core.voice.VoiceEngine
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import kotlinx.coroutines.suspendCancellableCoroutine
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Autonomous Call Skill — Speakerphone-based AI calling system.
 *
 * How it works (speakerphone relay):
 * 1. Dial the contact via the native Phone app dialer
 * 2. Wait for the call to be answered (OFFHOOK state)
 * 3. Enable speakerphone so the device speaker + mic are active
 * 4. Play TTS through STREAM_MUSIC (the device speaker) at max volume
 * 5. The phone's mic picks up the TTS audio and transmits to the caller
 * 6. Use STT to listen for the caller's response through the mic
 * 7. Generate AI response via LLM, then speak it via TTS
 * 8. Repeat until the call ends or goodbye is detected
 * 9. Return full transcript + LLM summary
 */
@Singleton
class AutonomousCallSkill @Inject constructor(
    @ApplicationContext private val context: Context,
    private val phoneSkill: PhoneSkill,
    private val voiceEngine: VoiceEngine,
    private val ttsEngine: TTSEngine,
    private val ollamaClient: OllamaClient
) {
    companion object {
        private const val TAG = "AutonomousCallSkill"
        private const val MAX_SILENCE_RETRIES = 3
        private const val POST_TTS_PAUSE_MS = 1000L
        private const val STT_TIMEOUT_MS = 12000L
    }

    data class ConversationTurn(
        val speaker: String,    // "Contact" or "Agent"
        val text: String,
        val timestamp: Long = System.currentTimeMillis()
    )

    // Conversation state
    private val transcript = mutableListOf<ConversationTurn>()
    @Volatile private var isCallActive = false
    @Volatile private var isCallConnected = false
    private var callJob: Job? = null

    // Hold references to prevent GC
    @Suppress("DEPRECATION")
    private var callStateListener: PhoneStateListener? = null
    @Suppress("DEPRECATION")
    private var incomingCallListener: PhoneStateListener? = null

    // Auto-answer state
    @Volatile private var autoAnswerEnabled = false
    private var autoAnswerPurpose: String = "Answer calls on behalf of the user"
    private var onAutoAnswerUpdate: ((String) -> Unit)? = null
    private var onAutoAnswerComplete: ((String) -> Unit)? = null

    /**
     * Enable/disable auto-answer for incoming calls.
     */
    fun setAutoAnswerEnabled(
        enabled: Boolean,
        purpose: String = "Answer calls on behalf of the user",
        onUpdate: ((String) -> Unit)? = null,
        onComplete: ((String) -> Unit)? = null
    ): String {
        autoAnswerEnabled = enabled
        autoAnswerPurpose = purpose
        onAutoAnswerUpdate = onUpdate
        onAutoAnswerComplete = onComplete

        if (enabled) {
            registerIncomingCallListener()
            Log.d(TAG, "Auto-answer ENABLED: $purpose")
            return "✅ Auto-answer is now ON. I'll pick up incoming calls and talk on your behalf."
        } else {
            unregisterIncomingCallListener()
            Log.d(TAG, "Auto-answer DISABLED")
            return "🔴 Auto-answer is now OFF. Incoming calls will ring normally."
        }
    }

    fun isAutoAnswerEnabled(): Boolean = autoAnswerEnabled

    /**
     * Start an autonomous OUTGOING call.
     */
    suspend fun startAutonomousCall(
        name: String,
        purpose: String,
        onUpdate: (String) -> Unit = {},
        onComplete: (String) -> Unit = {}
    ): String {
        transcript.clear()
        isCallActive = true
        isCallConnected = false

        // ── Step 1: Resolve the contact or use direct phone number ──
        val isPhoneNumber = name.matches(Regex("""^\+?\d[\d\s\-]{6,14}\d$"""))
        val displayName: String
        val phoneNumber: String

        if (isPhoneNumber) {
            displayName = name
            phoneNumber = name
            onUpdate("📞 Dialing $name directly...")
        } else {
            val contacts = phoneSkill.readContacts(name)
            if (contacts.isEmpty()) {
                return "❌ Could not find a contact named \"$name\". Please check the name and try again."
            }
            val contact = contacts.first()
            displayName = contact.name
            phoneNumber = contact.phoneNumber
            onUpdate("📞 Found ${contact.name} (${contact.phoneNumber}). Dialing...")
        }

        // ── Step 2: Register call state listener BEFORE dialing ──
        registerCallStateListener()

        // ── Step 3: Dial via native phone app ──
        val callStarted = phoneSkill.makeCall(phoneNumber)
        if (!callStarted) {
            return "❌ Failed to initiate the call to $displayName."
        }

        Log.d(TAG, "Call initiated to $displayName ($phoneNumber). Waiting for connection...")

        // ── Step 4: Wait for call to be ANSWERED (OFFHOOK state) ──
        val connected = waitForCallConnected(timeoutMs = 45000L)
        if (!connected || !isCallActive) {
            Log.d(TAG, "Call was not answered or ended early")
            return "📵 Call to $displayName was not answered."
        }

        Log.d(TAG, "Call connected! Enabling speakerphone...")
        onUpdate("📞 $displayName answered! Enabling speakerphone...")

        // ── Step 5: Enable speakerphone ──
        delay(1000L) // Small delay for audio path to stabilize
        enableSpeakerphone()
        delay(1500L) // Wait for speakerphone to fully activate
        onUpdate("🔊 Speakerphone ON. Agent is now talking to $displayName...")

        // ── Step 6: Run the conversation loop ──
        val result = runConversationLoop(displayName, purpose, onUpdate)

        // ── Step 7: Generate summary ──
        onUpdate("📝 Call ended. Generating summary...")
        disableSpeakerphone()
        val summary = generateSummary(displayName, purpose)
        onComplete(summary)

        return summary
    }

    /**
     * Wait for the call state to become OFFHOOK (connected).
     * Uses both listener AND direct polling as fallback.
     */
    @Suppress("DEPRECATION")
    private suspend fun waitForCallConnected(timeoutMs: Long): Boolean {
        val startTime = System.currentTimeMillis()
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        while (!isCallConnected && isCallActive && (System.currentTimeMillis() - startTime) < timeoutMs) {
            // Fallback: directly poll TelephonyManager
            try {
                if (tm.callState == TelephonyManager.CALL_STATE_OFFHOOK) {
                    Log.d(TAG, "OFFHOOK detected via direct polling")
                    isCallConnected = true
                    break
                }
            } catch (e: Exception) {
                Log.w(TAG, "callState poll failed: ${e.message}")
            }
            delay(500L)
        }
        Log.d(TAG, "waitForCallConnected result: connected=$isCallConnected, active=$isCallActive")
        return isCallConnected && isCallActive
    }

    /**
     * Start a conversation on an already-active call (for incoming calls).
     * Skips dialing — assumes the call is already connected with speakerphone ON.
     */
    suspend fun startConversationOnActiveCall(
        callerName: String,
        purpose: String,
        onUpdate: (String) -> Unit = {},
        onComplete: (String) -> Unit = {}
    ): String {
        transcript.clear()
        isCallActive = true
        isCallConnected = true

        registerCallStateListener()

        Log.d(TAG, "Starting conversation on active call with $callerName")
        onUpdate("\uD83E\uDD16 Agent is now talking to $callerName...")

        // Run the conversation loop
        runConversationLoop(callerName, purpose, onUpdate)

        // Generate summary
        disableSpeakerphone()
        val summary = generateSummary(callerName, purpose)
        onComplete(summary)

        return summary
    }

    /**
     * Handle an incoming call — auto-answer and start conversation.
     */
    private suspend fun handleIncomingCall(incomingNumber: String?) {
        val displayName = if (!incomingNumber.isNullOrBlank()) {
            // Try to look up contact name
            try {
                val contacts = phoneSkill.readContacts(incomingNumber)
                if (contacts.isNotEmpty()) contacts.first().name else incomingNumber
            } catch (_: Exception) { incomingNumber }
        } else {
            "Unknown caller"
        }

        transcript.clear()
        isCallActive = true
        isCallConnected = false

        Log.d(TAG, "Auto-answering call from: $displayName ($incomingNumber)")
        onAutoAnswerUpdate?.invoke("📱 Incoming call from $displayName — auto-answering...")

        // Small delay before answering
        delay(1500L)

        // Auto-answer the call
        val answered = answerIncomingCall()
        if (!answered) {
            Log.e(TAG, "Failed to auto-answer")
            onAutoAnswerUpdate?.invoke("❌ Failed to auto-answer the call.")
            return
        }

        isCallConnected = true
        registerCallStateListener()

        // Wait for audio path to stabilize
        delay(2000L)
        enableSpeakerphone()
        delay(1500L)

        onAutoAnswerUpdate?.invoke("🔊 Call answered. Speakerphone ON. Talking to $displayName...")

        // Run conversation loop
        runConversationLoop(displayName, autoAnswerPurpose) { update ->
            onAutoAnswerUpdate?.invoke(update)
        }

        // Generate summary
        disableSpeakerphone()
        val summary = generateSummary(displayName, autoAnswerPurpose)
        onAutoAnswerComplete?.invoke(summary)
        Log.d(TAG, "Auto-answer call completed")
    }

    /**
     * Auto-answer an incoming call.
     */
    @Suppress("MissingPermission")
    private fun answerIncomingCall(): Boolean {
        return try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
                telecomManager?.acceptRingingCall()
                Log.d(TAG, "Call answered via TelecomManager.acceptRingingCall()")
                true
            } else {
                // For older devices, simulate headset button press
                val intent = android.content.Intent(android.content.Intent.ACTION_MEDIA_BUTTON)
                val downEvent = android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_HEADSETHOOK)
                intent.putExtra(android.content.Intent.EXTRA_KEY_EVENT, downEvent)
                context.sendOrderedBroadcast(intent, "android.permission.CALL_PRIVILEGED")

                val upEvent = android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_HEADSETHOOK)
                intent.putExtra(android.content.Intent.EXTRA_KEY_EVENT, upEvent)
                context.sendOrderedBroadcast(intent, "android.permission.CALL_PRIVILEGED")

                Log.d(TAG, "Call answered via headset hook broadcast")
                true
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to auto-answer: ${e.message}", e)
            false
        }
    }

    /**
     * Main conversation loop: Speak opening → Listen → Respond → Repeat.
     */
    private suspend fun runConversationLoop(
        contactDisplayName: String,
        purpose: String,
        onUpdate: (String) -> Unit
    ): String {
        var silenceCount = 0
        var turnCount = 0

        // ── OPENING: Generate and speak introduction ──
        Log.d(TAG, "Generating opening line...")
        val openingLine = ollamaClient.chat(
            model = "qwen2.5:0.5b",
            systemPrompt = buildSystemPrompt(contactDisplayName, purpose),
            userMessage = "The call just connected. Say your opening greeting and state the purpose of the call. Keep it natural and brief (1-2 sentences max)."
        )
        Log.d(TAG, "Opening line: $openingLine")
        transcript.add(ConversationTurn("Agent", openingLine))
        onUpdate("🤖 Agent: $openingLine")

        // Speak opening through speaker — mic relays to other party
        val ttsResult = ttsEngine.speakAndWaitForCompletion(openingLine, duringCall = true)
        Log.d(TAG, "Opening TTS result: $ttsResult")
        delay(POST_TTS_PAUSE_MS)
        turnCount++

        // ── CONVERSATION LOOP ──
        while (isCallActive && turnCount < 30) {
            Log.d(TAG, "Listening for response... (turn $turnCount)")

            // Listen for the other person's response
            val heardText = withTimeoutOrNull(STT_TIMEOUT_MS) {
                listenForSpeech()
            }

            if (!isCallActive) {
                Log.d(TAG, "Call ended during listen")
                break
            }

            if (heardText.isNullOrBlank()) {
                silenceCount++
                Log.d(TAG, "No speech detected ($silenceCount/$MAX_SILENCE_RETRIES)")
                if (silenceCount >= MAX_SILENCE_RETRIES) {
                    val closingLine = "I haven't heard a response. I'll end the call now. Thank you for your time. Goodbye!"
                    transcript.add(ConversationTurn("Agent", closingLine))
                    onUpdate("🤖 Agent: $closingLine")
                    ttsEngine.speakAndWaitForCompletion(closingLine, duringCall = true)
                    break
                }
                continue
            }

            // We heard something!
            silenceCount = 0
            transcript.add(ConversationTurn("Contact", heardText))
            onUpdate("👤 $contactDisplayName: $heardText")
            Log.d(TAG, "Heard from contact: $heardText")

            // Check if the contact said goodbye
            if (isGoodbye(heardText)) {
                val farewellLine = "Thank you for your time! Goodbye, have a great day!"
                transcript.add(ConversationTurn("Agent", farewellLine))
                onUpdate("🤖 Agent: $farewellLine")
                ttsEngine.speakAndWaitForCompletion(farewellLine, duringCall = true)
                break
            }

            // Generate AI response
            Log.d(TAG, "Generating AI response...")
            val conversationContext = buildConversationContext()
            val response = ollamaClient.chat(
                model = "qwen2.5:0.5b",
                systemPrompt = buildSystemPrompt(contactDisplayName, purpose),
                userMessage = "Conversation so far:\n$conversationContext\n\nThe contact just said: \"$heardText\"\n\nRespond naturally and concisely (1-3 sentences). Stay focused on the purpose of the call."
            )

            transcript.add(ConversationTurn("Agent", response))
            onUpdate("🤖 Agent: $response")
            Log.d(TAG, "AI response: $response")

            // Speak through speaker
            ttsEngine.speakAndWaitForCompletion(response, duringCall = true)
            delay(POST_TTS_PAUSE_MS)
            turnCount++
        }

        return "Call completed with $turnCount exchanges."
    }

    private fun buildSystemPrompt(contactDisplayName: String, purpose: String): String {
        return """You are an AI assistant making a phone call on behalf of your user.
You are speaking TO: $contactDisplayName
Purpose of this call: $purpose

RULES:
- You are representing your user. Speak as if you are their assistant.
- Be polite, professional, and concise.
- Keep responses SHORT (1-3 sentences max) — this is a phone call, not an essay.
- Stay focused on the call's purpose.
- If the contact asks who you are, say you're an AI assistant calling on behalf of your user.
- If the conversation goal is achieved, politely wrap up the call.
- Never make up information — if you don't know, say you'll have your user follow up.
- Sound natural and conversational, not robotic."""
    }

    private fun buildConversationContext(): String {
        return transcript.joinToString("\n") { "${it.speaker}: ${it.text}" }
    }

    /**
     * Listen for speech using Android SpeechRecognizer.
     */
    private suspend fun listenForSpeech(): String? = suspendCancellableCoroutine { cont ->
        voiceEngine.startListening(object : VoiceEngine.VoiceListener {
            override fun onPartialResult(text: String) {
                // Wait for final result
            }
            override fun onFinalResult(text: String) {
                if (cont.isActive) cont.resume(text.ifBlank { null }, onCancellation = null)
            }
            override fun onError(errorMsg: String) {
                Log.w(TAG, "STT error: $errorMsg")
                if (cont.isActive) cont.resume(null, onCancellation = null)
            }
        })
    }

    /**
     * Enable speakerphone and set audio mode to NORMAL.
     * 
     * IMPORTANT: We use MODE_NORMAL (not MODE_IN_COMMUNICATION) because:
     * - MODE_IN_COMMUNICATION is for VoIP, not telephony
     * - MODE_NORMAL allows TTS to play through STREAM_MUSIC normally
     * - The speakerphone ensures the mic picks up the speaker output
     */
    @Suppress("DEPRECATION")
    private fun enableSpeakerphone() {
        try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.isSpeakerphoneOn = true
            // Max out the music stream volume for TTS
            val maxMusic = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, maxMusic, 0)
            // Also max voice call volume
            val maxCall = am.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
            am.setStreamVolume(AudioManager.STREAM_VOICE_CALL, maxCall, 0)
            Log.d(TAG, "Speakerphone ON, volumes maxed (music=$maxMusic, call=$maxCall)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to enable speakerphone: ${e.message}")
        }
    }

    @Suppress("DEPRECATION")
    private fun disableSpeakerphone() {
        try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.isSpeakerphoneOn = false
            am.mode = AudioManager.MODE_NORMAL
            Log.d(TAG, "Speakerphone OFF, audio mode NORMAL")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to disable speakerphone: ${e.message}")
        }
    }

    /**
     * Monitor call state for outgoing calls. Detects OFFHOOK (answered) and IDLE (ended).
     */
    @Suppress("DEPRECATION")
    private fun registerCallStateListener() {
        try {
            val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            callStateListener = object : PhoneStateListener() {
                override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                    when (state) {
                        TelephonyManager.CALL_STATE_OFFHOOK -> {
                            Log.d(TAG, ">>> Call CONNECTED (OFFHOOK)")
                            isCallConnected = true
                        }
                        TelephonyManager.CALL_STATE_IDLE -> {
                            Log.d(TAG, ">>> Call ENDED (IDLE)")
                            isCallActive = false
                            isCallConnected = false
                        }
                        TelephonyManager.CALL_STATE_RINGING -> {
                            Log.d(TAG, ">>> Phone RINGING")
                        }
                    }
                }
            }
            tm.listen(callStateListener, PhoneStateListener.LISTEN_CALL_STATE)
            Log.d(TAG, "Call state listener registered")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to register call state listener: ${e.message}")
        }
    }

    /**
     * Monitor incoming calls and auto-answer when enabled.
     * Holds a strong reference to prevent GC.
     */
    @Suppress("DEPRECATION")
    private fun registerIncomingCallListener() {
        unregisterIncomingCallListener()
        try {
            val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            incomingCallListener = object : PhoneStateListener() {
                override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                    if (state == TelephonyManager.CALL_STATE_RINGING && autoAnswerEnabled) {
                        Log.d(TAG, ">>> Incoming call from $phoneNumber — AUTO-ANSWERING")
                        CoroutineScope(Dispatchers.Main + SupervisorJob()).launch {
                            delay(2000L) // Let it ring for 2 seconds so the system registers
                            handleIncomingCall(phoneNumber)
                        }
                    }
                }
            }
            tm.listen(incomingCallListener, PhoneStateListener.LISTEN_CALL_STATE)
            Log.d(TAG, "Incoming call listener registered")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to register incoming call listener: ${e.message}")
        }
    }

    @Suppress("DEPRECATION")
    private fun unregisterIncomingCallListener() {
        try {
            if (incomingCallListener != null) {
                val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                tm.listen(incomingCallListener, PhoneStateListener.LISTEN_NONE)
                incomingCallListener = null
                Log.d(TAG, "Incoming call listener unregistered")
            }
        } catch (_: Exception) {}
    }

    private fun isGoodbye(text: String): Boolean {
        val lower = text.lowercase()
        return listOf(
            "goodbye", "good bye", "bye", "bye bye",
            "talk to you later", "see you later",
            "have a good day", "have a nice day",
            "take care", "gotta go", "got to go",
            "i have to go", "i need to go",
            "thanks bye", "thank you bye",
            "ok bye", "okay bye", "alright bye"
        ).any { lower.contains(it) }
    }

    private suspend fun generateSummary(contactDisplayName: String, purpose: String): String {
        if (transcript.isEmpty()) {
            return "📵 No conversation took place."
        }

        val conversationText = buildConversationContext()
        val summary = ollamaClient.chat(
            model = "qwen2.5:0.5b",
            systemPrompt = "You are a conversation summarizer. Provide a clear, concise summary of a phone call.",
            userMessage = """Summarize this phone call:
Contact: $contactDisplayName
Purpose: $purpose
Transcript:
$conversationText

Provide:
1. A 2-3 sentence summary
2. Key outcomes or action items
3. Overall tone of conversation"""
        )

        return """📞 **Call Summary — $contactDisplayName**
---
$summary

---
**Full Transcript** (${transcript.size} exchanges):
${transcript.joinToString("\n") { "  ${it.speaker}: ${it.text}" }}"""
    }

    fun stopCall(): String {
        isCallActive = false
        isCallConnected = false
        callJob?.cancel()
        disableSpeakerphone()
        return if (transcript.isEmpty()) {
            "Call stopped. No conversation was recorded."
        } else {
            "Call stopped.\n\n${transcript.joinToString("\n") { "${it.speaker}: ${it.text}" }}"
        }
    }
}
