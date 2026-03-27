package com.neuralai.agent.core.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Text-to-Speech engine with support for in-call audio.
 */
@Singleton
class TTSEngine @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val TAG = "TTSEngine"
        private const val TTS_TIMEOUT_MS = 30000L // 30 second safety timeout

        private val _isSpeakingFlow = MutableStateFlow(false)
        val isSpeakingFlow: StateFlow<Boolean> = _isSpeakingFlow.asStateFlow()
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private var tts: TextToSpeech? = null
    private var isInitialized = false

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                isInitialized = true
                val result = tts?.setLanguage(Locale.US)

                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    Log.w(TAG, "TTS Language not supported")
                } else {
                    tts?.setPitch(1.0f)
                    tts?.setSpeechRate(0.9f)
                }
                Log.d(TAG, "TTS initialized successfully")
            } else {
                Log.e(TAG, "TTS Initialization failed with status: $status")
            }
        }
    }

    /**
     * Normal speak — fire and forget. Uses default audio stream.
     */
    fun speak(text: String) {
        if (!isInitialized) return
        val cleanText = cleanMarkdown(text)
        _isSpeakingFlow.value = true
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(uttId: String?) {
                _isSpeakingFlow.value = true
            }
            override fun onDone(uttId: String?) {
                _isSpeakingFlow.value = false
            }
            override fun onError(uttId: String?) {
                _isSpeakingFlow.value = false
            }
        })
        tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, "response_${System.currentTimeMillis()}")
    }

    /**
     * Speak and wait for TTS to complete before returning.
     */
    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    suspend fun speakAndWaitForCompletion(text: String, duringCall: Boolean = false): Boolean {
        if (!isInitialized) {
            Log.w(TAG, "TTS not initialized, cannot speak")
            return false
        }

        val cleanText = cleanMarkdown(text)
        if (cleanText.isBlank()) return true

        Log.d(TAG, "Speaking (duringCall=$duringCall): ${cleanText.take(100)}...")

        // During a call, max out STREAM_MUSIC volume so the mic picks it up
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        var previousVolume = -1
        if (duringCall) {
            try {
                previousVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, 0)
                Log.d(TAG, "STREAM_MUSIC volume maxed ($previousVolume -> $maxVolume)")
            } catch (e: Exception) {
                Log.w(TAG, "Failed to set volume: ${e.message}")
            }
        }

        val result = withTimeoutOrNull(TTS_TIMEOUT_MS) {
            suspendCancellableCoroutine { cont ->
                val utteranceId = "await_${System.currentTimeMillis()}"

                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(uttId: String?) {
                        Log.d(TAG, "TTS utterance started: $uttId")
                        _isSpeakingFlow.value = true
                    }

                    override fun onDone(uttId: String?) {
                        Log.d(TAG, "TTS utterance completed: $uttId")
                        _isSpeakingFlow.value = false
                        if (uttId == utteranceId && cont.isActive) {
                            cont.resume(true, onCancellation = null)
                        }
                    }

                    @Deprecated("Deprecated in API")
                    override fun onError(uttId: String?) {
                        Log.e(TAG, "TTS utterance error: $uttId")
                        _isSpeakingFlow.value = false
                        if (uttId == utteranceId && cont.isActive) {
                            cont.resume(false, onCancellation = null)
                        }
                    }
                })

                // Use STREAM_MUSIC — plays through the speaker
                // Speakerphone mic picks it up and transmits to the other party
                val params = Bundle().apply {
                    putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_MUSIC)
                }

                tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, params, utteranceId)

                cont.invokeOnCancellation {
                    Log.d(TAG, "TTS cancelled")
                    tts?.stop()
                }
            }
        } ?: false

        // Restore volume after TTS completes
        if (duringCall && previousVolume >= 0) {
            try {
                // Keep volume high during the call — don't restore
                // audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, previousVolume, 0)
            } catch (_: Exception) {}
        }

        Log.d(TAG, "TTS speakAndWait result: $result")
        return result
    }

    fun stopSpeaking() {
        if (tts?.isSpeaking == true) {
            tts?.stop()
            _isSpeakingFlow.value = false
        }
    }

    fun isSpeaking(): Boolean = tts?.isSpeaking == true

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
    }

    private fun cleanMarkdown(text: String): String {
        return text.replace(Regex("\\*\\*(.*?)\\*\\*"), "$1")
            .replace(Regex("\\*(.*?)\\*"), "$1")
            .replace("###", "")
            .replace("##", "")
            .replace("#", "")
    }
}
