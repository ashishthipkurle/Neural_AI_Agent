package com.neuralai.agent.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.app.NotificationCompat
import com.neuralai.agent.MainActivity
import com.neuralai.agent.R
import com.neuralai.agent.core.voice.TTSEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Always-on background service that listens for the wake word "Hey Neural".
 *
 * KEY DESIGN: To prevent the "mic connect/disconnect" sound that Android
 * plays when SpeechRecognizer starts/stops:
 *
 * 1. We acquire AUDIO FOCUS and set MODE_IN_COMMUNICATION at service start.
 *    This tells Android we're in a "phone call"-like state, suppressing
 *    all system recognition beeps/dings.
 * 2. We create the SpeechRecognizer ONCE and reuse it across restart cycles.
 *    Only recreate it after consecutive fatal errors.
 * 3. _isListening stays TRUE for the service lifetime — no UI flickering.
 * 4. Audio focus and mode are released only when the service is stopped.
 */
class WakeWordService : Service() {

    companion object {
        const val TAG = "WakeWordService"
        const val CHANNEL_ID = "wake_word_channel"
        const val NOTIFICATION_ID = 2

        private val WAKE_WORDS = listOf(
            "hey neural", "neural", "new role", "new rule", "neutral",
            "near all", "hii bro", "hey bro", "hi bro",
            "hey newton", "hey annual", "hey new right", "he knew that", "henry",
            "hey noodle", "he noodle"
        )

        private val _isListening = MutableStateFlow(false)
        val isListening: StateFlow<Boolean> = _isListening.asStateFlow()

        private val _isServiceRunning = MutableStateFlow(false)
        val isServiceRunning: StateFlow<Boolean> = _isServiceRunning.asStateFlow()

        private val _instance = MutableStateFlow<WakeWordService?>(null)
        val instance: StateFlow<WakeWordService?> = _instance.asStateFlow()

        private val _wakeCommand = MutableSharedFlow<String>(extraBufferCapacity = 1)
        val wakeCommand: SharedFlow<String> = _wakeCommand.asSharedFlow()

        private val _audioRms = MutableStateFlow(0f)
        val audioRms: StateFlow<Float> = _audioRms.asStateFlow()

        private val _partialSpeech = MutableStateFlow("")
        val partialSpeech: StateFlow<String> = _partialSpeech.asStateFlow()

        const val ACTION_WAKE_DETECTED = "com.neuralai.agent.WAKE_DETECTED"
        const val EXTRA_COMMAND_TEXT = "command_text"

        var activeWakeTimeMs: Long = 0
        const val WAKE_WINDOW_MS = 20000L

        fun extendWakeWindow() {
            activeWakeTimeMs = System.currentTimeMillis()
        }
    }

    private var recognizer: SpeechRecognizer? = null
    private val handler = Handler(Looper.getMainLooper())
    private var isRunning = false
    private var consecutiveErrors = 0
    private val MAX_ERRORS_BEFORE_RECREATE = 5

    // Audio focus management — held for the entire service lifetime
    private var audioManager: AudioManager? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var previousAudioMode: Int = AudioManager.MODE_NORMAL

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var ttsObservationJob: Job? = null
    private var isPausedByTts = false

    // Stream volume muting — saves & restores volumes around startListening beep
    private var savedMusicVol = -1
    private var savedSystemVol = -1
    private var savedNotifVol = -1
    private var savedRingVol = -1
    private var isMuted = false
    private val unmuteRunnable = Runnable { restoreStreamVolumes() }

    override fun onCreate() {
        super.onCreate()
        _instance.value = this
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("Listening 24/7 for commands..."))
        isRunning = true
        _isServiceRunning.value = true
        _isListening.value = true

        // Acquire audio focus and set communication mode BEFORE starting recognition
        acquireAudioFocusAndMode()

        observeTtsState()

        handler.post { initRecognizerAndStart() }
    }

    private fun observeTtsState() {
        ttsObservationJob?.cancel()
        ttsObservationJob = serviceScope.launch {
            TTSEngine.isSpeakingFlow.collect { isSpeaking ->
                if (isSpeaking) {
                    Log.d(TAG, "TTS speaking detected, pausing mic...")
                    isPausedByTts = true
                    stopRecognitionTemporarily()
                } else if (isPausedByTts) {
                    Log.d(TAG, "TTS finished, resuming mic in 500ms...")
                    delay(500)
                    isPausedByTts = false
                    if (isRunning) startListeningOnExistingRecognizer()
                }
            }
        }
    }

    private fun stopRecognitionTemporarily() {
        try {
            recognizer?.stopListening()
            recognizer?.cancel()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping recognition for TTS: ${e.message}")
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        isRunning = false
        _isServiceRunning.value = false
        _instance.value = null
        _isListening.value = false
        _audioRms.value = 0f

        // Restore any muted volumes before destroying
        restoreStreamVolumes()
        handler.removeCallbacksAndMessages(null)
        recognizer?.destroy()
        recognizer = null

        // Release audio focus and restore mode
        releaseAudioFocusAndMode()

        serviceScope.launch {
            ttsObservationJob?.cancel()
            _instance.value = null
        }

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // =========================================================================
    // AUDIO FOCUS — suppresses system sounds during mic acquire/release
    // =========================================================================

    private fun acquireAudioFocusAndMode() {
        try {
            audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

            // Save the previous audio mode so we can restore it later
            previousAudioMode = audioManager?.mode ?: AudioManager.MODE_NORMAL

            // Set MODE_IN_COMMUNICATION — this is the key trick.
            // In this mode, Android treats the app like a VoIP call and suppresses
            // all system recognition beeps, mic connection sounds, etc.
            audioManager?.mode = AudioManager.MODE_IN_COMMUNICATION

            // Request audio focus to prevent other apps from interrupting
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build()
                    )
                    .setAcceptsDelayedFocusGain(true)
                    .setOnAudioFocusChangeListener { /* ignore focus changes */ }
                    .build()
                audioFocusRequest = focusRequest
                audioManager?.requestAudioFocus(focusRequest)
            } else {
                @Suppress("DEPRECATION")
                audioManager?.requestAudioFocus(
                    { /* ignore */ },
                    AudioManager.STREAM_VOICE_CALL,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
                )
            }
            Log.d(TAG, "Audio focus acquired, mode set to IN_COMMUNICATION")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to acquire audio focus: ${e.message}")
        }
    }

    private fun releaseAudioFocusAndMode() {
        try {
            // Restore previous audio mode
            audioManager?.mode = previousAudioMode

            // Abandon audio focus
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                audioFocusRequest?.let { audioManager?.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioManager?.abandonAudioFocus { /* ignore */ }
            }
            audioFocusRequest = null
            audioManager = null
            Log.d(TAG, "Audio focus released, mode restored")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to release audio focus: ${e.message}")
        }
    }

    // =========================================================================
    // RECOGNIZER — created once, reused across restart cycles
    // =========================================================================

    /**
     * Creates the SpeechRecognizer ONCE and starts listening.
     * Only called at service start or after too many consecutive errors.
     */
    private fun initRecognizerAndStart() {
        if (!isRunning) return
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "Speech recognition not available")
            handler.postDelayed({ initRecognizerAndStart() }, 2000)
            return
        }

        try {
            recognizer?.destroy()
            recognizer = SpeechRecognizer.createSpeechRecognizer(this)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create recognizer: ${e.message}")
            handler.postDelayed({ initRecognizerAndStart() }, 2000)
            return
        }

        recognizer?.setRecognitionListener(createRecognitionListener())
        consecutiveErrors = 0
        startListeningOnExistingRecognizer()
    }

    /**
     * Restarts listening on the EXISTING recognizer — NO destroy/recreate.
     * Mutes all audio streams BEFORE calling startListening to kill the beep,
     * then restores them once onReadyForSpeech fires (or after a safety timeout).
     */
    private fun startListeningOnExistingRecognizer() {
        if (!isRunning || isPausedByTts) return

        val rec = recognizer
        if (rec == null) {
            Log.w(TAG, "Recognizer is null, reinitializing...")
            initRecognizerAndStart()
            return
        }

        val listenIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            // Longer timeouts = fewer restarts
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 3000L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1500L)
        }

        try {
            // MUTE all streams before startListening to swallow the beep
            muteStreamVolumes()
            rec.startListening(listenIntent)
            // Safety: restore volumes after 500ms even if onReadyForSpeech doesn't fire
            handler.removeCallbacks(unmuteRunnable)
            handler.postDelayed(unmuteRunnable, 500)
        } catch (e: Exception) {
            restoreStreamVolumes()
            Log.e(TAG, "Failed to start listening: ${e.message}")
            handler.postDelayed({ initRecognizerAndStart() }, 1000)
        }
    }

    // =========================================================================
    // STREAM MUTING — kills the SpeechRecognizer beep at the audio level
    // =========================================================================

    private fun muteStreamVolumes() {
        val am = audioManager ?: return
        try {
            if (!isMuted) {
                savedMusicVol = am.getStreamVolume(AudioManager.STREAM_MUSIC)
                savedSystemVol = am.getStreamVolume(AudioManager.STREAM_SYSTEM)
                savedNotifVol = am.getStreamVolume(AudioManager.STREAM_NOTIFICATION)
                savedRingVol = am.getStreamVolume(AudioManager.STREAM_RING)
            }
            am.setStreamVolume(AudioManager.STREAM_MUSIC, 0, 0)
            am.setStreamVolume(AudioManager.STREAM_SYSTEM, 0, 0)
            am.setStreamVolume(AudioManager.STREAM_NOTIFICATION, 0, 0)
            am.setStreamVolume(AudioManager.STREAM_RING, 0, 0)
            isMuted = true
        } catch (e: Exception) {
            Log.w(TAG, "Failed to mute streams: ${e.message}")
        }
    }

    private fun restoreStreamVolumes() {
        val am = audioManager ?: return
        if (!isMuted) return
        try {
            if (savedMusicVol >= 0) am.setStreamVolume(AudioManager.STREAM_MUSIC, savedMusicVol, 0)
            if (savedSystemVol >= 0) am.setStreamVolume(AudioManager.STREAM_SYSTEM, savedSystemVol, 0)
            if (savedNotifVol >= 0) am.setStreamVolume(AudioManager.STREAM_NOTIFICATION, savedNotifVol, 0)
            if (savedRingVol >= 0) am.setStreamVolume(AudioManager.STREAM_RING, savedRingVol, 0)
            isMuted = false
        } catch (e: Exception) {
            Log.w(TAG, "Failed to restore streams: ${e.message}")
        }
    }

    private fun createRecognitionListener(): RecognitionListener {
        return object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                consecutiveErrors = 0
                // Beep window has passed — restore volumes now
                handler.removeCallbacks(unmuteRunnable)
                restoreStreamVolumes()
                Log.d(TAG, "Listening for wake word...")
            }

            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {
                val normalized = ((rmsdB + 2f) / 14f).coerceIn(0.1f, 1f)
                _audioRms.value = normalized
            }
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {
                _audioRms.value = 0.1f
                // Do NOT set _isListening = false — mic stays "on"
            }

            override fun onError(error: Int) {
                _partialSpeech.value = ""
                _audioRms.value = 0.1f
                consecutiveErrors++

                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                        if (consecutiveErrors >= MAX_ERRORS_BEFORE_RECREATE) {
                            Log.w(TAG, "Too many timeouts ($consecutiveErrors), recreating recognizer")
                            consecutiveErrors = 0
                            handler.postDelayed({ initRecognizerAndStart() }, 500)
                        } else {
                            scheduleRestartOnSameRecognizer(200)
                        }
                    }
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> {
                        scheduleRestartOnSameRecognizer(1500)
                    }
                    SpeechRecognizer.ERROR_CLIENT -> {
                        Log.w(TAG, "Client error, recreating recognizer")
                        handler.postDelayed({ initRecognizerAndStart() }, 500)
                    }
                    else -> {
                        Log.w(TAG, "Recognition error: $error")
                        if (consecutiveErrors >= MAX_ERRORS_BEFORE_RECREATE) {
                            consecutiveErrors = 0
                            handler.postDelayed({ initRecognizerAndStart() }, 1000)
                        } else {
                            scheduleRestartOnSameRecognizer(500)
                        }
                    }
                }
            }

            override fun onResults(results: Bundle?) {
                _audioRms.value = 0.1f
                _partialSpeech.value = ""
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull()?.trim() ?: ""
                Log.d(TAG, "Heard: $text")
                if (text.isNotBlank()) {
                    handleRecognizedText(text)
                }
                if (isPausedByTts) return
                scheduleRestartOnSameRecognizer(300)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull() ?: ""
                _partialSpeech.value = text
                val now = System.currentTimeMillis()
                if ((now - activeWakeTimeMs) < WAKE_WINDOW_MS) {
                    activeWakeTimeMs = now
                }
            }

            override fun onEvent(eventType: Int, params: Bundle?) {}
        }
    }

    private fun scheduleRestartOnSameRecognizer(delayMs: Long) {
        handler.postDelayed({
            if (isRunning && !isPausedByTts) startListeningOnExistingRecognizer()
        }, delayMs)
    }

    // =========================================================================
    // WAKE WORD HANDLING
    // =========================================================================

    private fun containsWakeWord(text: String): Boolean {
        val lowerText = text.lowercase()
        return WAKE_WORDS.any { lowerText.contains(it) }
    }

    private fun handleRecognizedText(text: String) {
        val lowerText = text.lowercase()
        val hasWakeWord = containsWakeWord(lowerText)
        val now = System.currentTimeMillis()
        val isWithinWindow = (now - activeWakeTimeMs) < WAKE_WINDOW_MS

        if (hasWakeWord || isWithinWindow) {
            var command = lowerText

            if (hasWakeWord) {
                Log.i(TAG, "🎤 Wake word detected! Text: $lowerText")
                activeWakeTimeMs = now

                for (wakeWord in WAKE_WORDS) {
                    if (command.contains(wakeWord)) {
                        val afterWake = command.substringAfter(wakeWord).trim()
                        command = if (afterWake.isNotBlank()) afterWake else ""
                        break
                    }
                }
            } else {
                Log.i(TAG, "🎤 Command within wake window: $lowerText")
                activeWakeTimeMs = now
            }

            _wakeCommand.tryEmit(command)

            val wakeIntent = Intent(ACTION_WAKE_DETECTED).apply {
                putExtra(EXTRA_COMMAND_TEXT, command)
                setPackage(packageName)
            }
            sendBroadcast(wakeIntent)

            updateNotification(
                if (command.isNotBlank()) "Processed: \"$command\"" else "Wake word detected!"
            )
            handler.postDelayed({
                updateNotification("Listening 24/7 for commands...")
            }, 3000)
        } else {
            Log.d(TAG, "Ignored (outside wake window): $lowerText")
        }
    }

    // =========================================================================
    // NOTIFICATION
    // =========================================================================

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "Wake Word Listener", NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Neural Agent always-on wake word detection"
                setShowBadge(false)
            }
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Neural Agent")
            .setContentText(text)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }
}
