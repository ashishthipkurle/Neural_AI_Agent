package com.neuralai.agent.core.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TTSEngine @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private var tts: TextToSpeech? = null
    private var isInitialized = false

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                isInitialized = true
                val result = tts?.setLanguage(Locale.US)
                
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    println("TTS Language not supported")
                } else {
                    tts?.setPitch(1.0f)
                    tts?.setSpeechRate(0.9f) // Slightly slower for clarity
                }
            } else {
                println("TTS Initialization failed")
            }
        }
    }

    fun speak(text: String) {
        if (!isInitialized) return
        
        // Remove markdown formatting like **bold** or *italic* before speaking
        val cleanText = text.replace(Regex("\\*\\*(.*?)\\*\\*"), "$1")
            .replace(Regex("\\*(.*?)\\*"), "$1")
            .replace("###", "")
            .replace("##", "")
            .replace("#", "")
            
        tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, "response_${System.currentTimeMillis()}")
    }

    fun stopSpeaking() {
        if (tts?.isSpeaking == true) {
            tts?.stop()
        }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
    }
}
