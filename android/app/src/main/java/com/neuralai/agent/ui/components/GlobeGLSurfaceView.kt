package com.neuralai.agent.ui.components

import android.content.Context
import android.graphics.PixelFormat
import android.opengl.GLSurfaceView

/**
 * GLSurfaceView wrapper for the AI Globe.
 * Uses setZOrderOnTop(true) to enable per-pixel alpha transparency
 * so the globe particles float over the background without a black box.
 */
class GlobeGLSurfaceView(context: Context) : GLSurfaceView(context) {

    val renderer: GlobeRenderer

    init {
        setEGLContextClientVersion(3)
        // 8-bit RGBA for transparency
        setEGLConfigChooser(8, 8, 8, 8, 16, 0)
        holder.setFormat(PixelFormat.TRANSLUCENT)
        // Required for transparent background - places GL surface above the window
        setZOrderOnTop(true)
        
        renderer = GlobeRenderer(context)
        setRenderer(renderer)
        renderMode = RENDERMODE_CONTINUOUSLY
    }

    fun setState(state: String) {
        renderer.state = state
    }

    fun setMuted(muted: Boolean) {
        renderer.muted = muted
    }

    fun setAudioLevel(level: Float) {
        renderer.audioLevel = level
    }
}
