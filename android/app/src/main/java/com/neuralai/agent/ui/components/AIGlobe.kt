package com.neuralai.agent.ui.components

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import com.neuralai.agent.core.AIState

/**
 * Compose wrapper around the OpenGL ES 3.0 particle globe.
 * Passes AI state and real-time audio level to the renderer.
 */
@Composable
fun AIGlobe(
    aiState: AIState,
    audioRms: Float = 0f,
    modifier: Modifier = Modifier
) {
    val stateString = when (aiState) {
        AIState.IDLE -> "idle"
        AIState.THINKING -> "thinking"
        AIState.LISTENING -> "listening"
        AIState.SPEAKING -> "speaking"
        AIState.EXECUTING -> "executing"
        AIState.ERROR -> "error"
    }

    AndroidView(
        modifier = modifier,
        factory = { context ->
            GlobeGLSurfaceView(context).apply {
                setState(stateString)
                setMuted(false)
                setAudioLevel(audioRms)
            }
        },
        update = { view ->
            view.setState(stateString)
            view.setAudioLevel(audioRms)
        }
    )
}
