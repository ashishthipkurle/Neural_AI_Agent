package com.neuralai.agent.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
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
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Always-on background service that listens for the wake word "Hey Neural".
 * Uses Android SpeechRecognizer in a continuous restart loop.
 *
 * Flow:
 * 1. Service starts as foreground with persistent notification
 * 2. SpeechRecognizer listens continuously
 * 3. On detecting "hey neural" or "neural", broadcasts wake intent
 * 4. On timeout/error, automatically restarts listening (after 500ms delay)
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

        // Stable state for whether the 24/7 service is fully running
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

        // Broadcast action when speech command is detected
        const val ACTION_WAKE_DETECTED = "com.neuralai.agent.WAKE_DETECTED"
        const val EXTRA_COMMAND_TEXT = "command_text"

        var activeWakeTimeMs: Long = 0
        const val WAKE_WINDOW_MS = 20000L // 20 seconds

        fun extendWakeWindow() {
            activeWakeTimeMs = System.currentTimeMillis()
        }
    }

    private var recognizer: SpeechRecognizer? = null
    private val handler = Handler(Looper.getMainLooper())
    private var isRunning = false

    override fun onCreate() {
        super.onCreate()
        _instance.value = this
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("Listening 24/7 for commands..."))
        isRunning = true
        _isServiceRunning.value = true
        handler.post { startContinuousListening() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // The actual listening and service state management is now handled in onCreate
        // This method just ensures the service stays running if killed by the system
        return START_STICKY
    }

    override fun onDestroy() {
        isRunning = false
        _isServiceRunning.value = false
        _instance.value = null
        _isListening.value = false
        handler.removeCallbacksAndMessages(null)
        recognizer?.destroy()
        recognizer = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startContinuousListening() {
        if (!isRunning) return
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "Speech recognition not available")
            scheduleRestart(1000)
            return
        }

        try {
            recognizer?.destroy()
            recognizer = SpeechRecognizer.createSpeechRecognizer(this)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create recognizer: ${e.message}")
            scheduleRestart()
            return
        }

        val listenIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            // Snappier silence timeouts so it stops listening shortly after the user stops speaking
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1000L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1000L)
        }

        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                _isListening.value = true
                Log.d(TAG, "Listening for wake word...")
            }

            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {
                // Keep the value between 0.1 and 1.0 to ensure the globe keeps flowing
                val normalized = ((rmsdB + 2f) / 14f).coerceIn(0.1f, 1f)
                _audioRms.value = normalized
            }
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() { 
                _isListening.value = false 
                // Let the audio level decay naturally or stay at a minimum base level
                _audioRms.value = 0.1f
            }

            override fun onError(error: Int) {
                _isListening.value = false
                _partialSpeech.value = ""
                // Drop to a lower baseline on error but don't snap to 0
                _audioRms.value = 0.05f
                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                        // Normal: just no one spoke. Restart quickly.
                        scheduleRestart(200)
                    }
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> {
                        scheduleRestart(1000)
                    }
                    else -> {
                        Log.w(TAG, "Recognition error: $error, restarting...")
                        scheduleRestart(500)
                    }
                }
            }

            override fun onResults(results: Bundle?) {
                _isListening.value = false
                _audioRms.value = 0.1f
                _partialSpeech.value = ""
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull()?.trim() ?: ""
                Log.d(TAG, "Heard: $text")
                if (text.isNotBlank()) {
                    handleRecognizedText(text)
                }
                scheduleRestart(300)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull() ?: ""
                _partialSpeech.value = text
                
                // Keep the wake window open as long as they are actively speaking!
                val now = System.currentTimeMillis()
                if ((now - activeWakeTimeMs) < WAKE_WINDOW_MS) {
                    activeWakeTimeMs = now
                }
            }

            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        try {
            val audioManager = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
            val currentVolume = audioManager.getStreamVolume(android.media.AudioManager.STREAM_MUSIC)
            // Mute the stream to hide the system "beep"
            audioManager.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, 0, 0)
            
            recognizer?.startListening(listenIntent)
            
            // Restore volume shortly after the beep usually plays
            handler.postDelayed({
                audioManager.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, currentVolume, 0)
            }, 300)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start listening: ${e.message}")
            scheduleRestart()
        }
    }

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
                activeWakeTimeMs = now // Reset the window
                
                for (wakeWord in WAKE_WORDS) {
                    if (command.contains(wakeWord)) {
                        val afterWake = command.substringAfter(wakeWord).trim()
                        command = if (afterWake.isNotBlank()) afterWake else ""
                        break
                    }
                }
            } else {
                Log.i(TAG, "🎤 Command accepted within wake window: $lowerText")
                activeWakeTimeMs = now // Extend window as long as they keep interacting
            }

            _wakeCommand.tryEmit(command)

            // Broadcast to the app
            val wakeIntent = Intent(ACTION_WAKE_DETECTED).apply {
                putExtra(EXTRA_COMMAND_TEXT, command)
                setPackage(packageName)
            }
            sendBroadcast(wakeIntent)

            updateNotification(if (command.isNotBlank()) "Processed command: \"$command\"" else "Wake word detected!")

            // After a brief pause, reset notification
            handler.postDelayed({
                updateNotification("Listening 24/7 for commands...")
            }, 3000)
        } else {
            Log.d(TAG, "Ignored speech outside wake window: $lowerText")
        }
    }

    private fun scheduleRestart(delayMs: Long = 500) {
        handler.postDelayed({
            if (isRunning) startContinuousListening()
        }, delayMs)
    }

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Wake Word Listener",
                NotificationManager.IMPORTANCE_LOW
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
