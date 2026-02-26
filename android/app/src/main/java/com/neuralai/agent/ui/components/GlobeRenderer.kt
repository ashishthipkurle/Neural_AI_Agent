package com.neuralai.agent.ui.components

import android.content.Context
import android.opengl.GLES30
import android.opengl.GLSurfaceView
import android.os.SystemClock
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.acos
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

data class AudioData(val audio: Float, val bass: Float, val mid: Float, val high: Float)

class GlobeRenderer(private val context: Context) : GLSurfaceView.Renderer {

    private var program = 0
    private var uTime = 0
    private var uAudio = 0
    private var uBass = 0
    private var uMid = 0
    private var uHigh = 0
    private var uColor = 0
    private var uRotationY = 0
    private var uAspect = 0

    private var startTime = SystemClock.uptimeMillis()
    @Volatile var state = "idle"
    @Volatile var muted = false

    // External audio level (0..1) fed from microphone/voice engine
    @Volatile var audioLevel = 0f

    // Smoothed audio values (PC-style interpolation: a, b, m, h)
    private var smoothA = 0f  // overall
    private var smoothB = 0f  // bass
    private var smoothM = 0f  // mid
    private var smoothH = 0f  // high

    private var rotationAngle = 0f
    private var aspectRatio = 1f

    private lateinit var vertexBuffer: FloatBuffer
    private lateinit var phaseBuffer: FloatBuffer
    // Reduced from 12000 → 5000 for cleaner look on mobile
    private val particleCount = 5000
    private val radius = 1.5f

    private val vertexShader = """
        #version 300 es
        precision mediump float;
        
        in vec3 aPosition;
        in float aPhase;
        
        uniform float uTime;
        uniform float uAudio;
        uniform float uBass;
        uniform float uMid;
        uniform float uRotationY;
        uniform float uAspect;
        
        out float vPulse;
        out float vDepth;
        
        void main() {
            float pulse = sin(uTime * 0.8 + aPhase) * 0.5 + 0.5;
            vPulse = pulse;
            
            // Audio-reactive deformation (gentle)
            float audioOffset = uBass * 0.15 + uMid * 0.1;
            vec3 displaced = aPosition * (1.0 + audioOffset * sin(aPhase + uTime * 0.8));
            
            // Y-axis rotation
            float cosR = cos(uRotationY);
            float sinR = sin(uRotationY);
            mat3 rotY = mat3(
                cosR,  0.0, sinR,
                 0.0,  1.0,  0.0,
                -sinR, 0.0, cosR
            );
            
            // Slight X tilt
            float tiltX = 0.15;
            float cosT = cos(tiltX);
            float sinT = sin(tiltX);
            mat3 rotX = mat3(
                1.0,  0.0,  0.0,
                0.0, cosT, -sinT,
                0.0, sinT,  cosT
            );
            
            vec3 rotated = rotX * rotY * displaced;
            
            float fov = 5.5;
            float z = rotated.z + fov;
            float scale = fov / z;
            
            vDepth = (rotated.z + 1.5) / 3.0;
            
            vec2 projected = rotated.xy * scale;
            projected.x /= uAspect;
            
            gl_Position = vec4(projected * 0.5, 0.0, 1.0);
            
            // Gentle particle size variation
            float baseSize = 3.5;
            gl_PointSize = baseSize * scale * (1.0 + pulse * 0.3) * (1.0 + uAudio * 0.5);
        }
    """.trimIndent()

    private val fragmentShader = """
        #version 300 es
        precision mediump float;
        
        uniform vec3 uColor;
        uniform float uAudio;
        
        in float vPulse;
        in float vDepth;
        
        out vec4 fragColor;
        
        void main() {
            float d = length(gl_PointCoord - vec2(0.5));
            float alpha = smoothstep(0.5, 0.02, d);
            
            // Depth-based fading
            float depthAlpha = clamp(vDepth * 0.85 + 0.15, 0.1, 1.0);
            alpha *= depthAlpha;
            
            // Glow on audio
            vec3 bright = vec3(0.5, 1.0, 1.0);
            vec3 color = mix(uColor, bright, uAudio * 0.7);
            color *= 0.6 + vPulse * 0.4;
            
            // Bloom effect — brighter center
            float bloom = smoothstep(0.4, 0.0, d) * 0.3;
            color += bloom;
            
            fragColor = vec4(color, alpha);
        }
    """.trimIndent()

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES30.glClearColor(0.0f, 0.0f, 0.0f, 0.0f)
        GLES30.glEnable(GLES30.GL_BLEND)
        GLES30.glBlendFunc(GLES30.GL_SRC_ALPHA, GLES30.GL_ONE)

        val vertices = FloatArray(particleCount * 3)
        val phases = FloatArray(particleCount)
        for (i in 0 until particleCount) {
            val u = Random.nextFloat()
            val v = Random.nextFloat()
            val theta = 2f * Math.PI.toFloat() * u
            val phi = acos(2f * v - 1f)

            vertices[i * 3] = radius * sin(phi) * cos(theta)
            vertices[i * 3 + 1] = radius * cos(phi)
            vertices[i * 3 + 2] = radius * sin(phi) * sin(theta)
            phases[i] = Random.nextFloat() * Math.PI.toFloat() * 2f
        }

        vertexBuffer = ByteBuffer.allocateDirect(vertices.size * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer()
        vertexBuffer.put(vertices).position(0)

        phaseBuffer = ByteBuffer.allocateDirect(phases.size * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer()
        phaseBuffer.put(phases).position(0)

        program = createProgram(vertexShader, fragmentShader)

        uTime = GLES30.glGetUniformLocation(program, "uTime")
        uAudio = GLES30.glGetUniformLocation(program, "uAudio")
        uBass = GLES30.glGetUniformLocation(program, "uBass")
        uMid = GLES30.glGetUniformLocation(program, "uMid")
        uHigh = GLES30.glGetUniformLocation(program, "uHigh")
        uColor = GLES30.glGetUniformLocation(program, "uColor")
        uRotationY = GLES30.glGetUniformLocation(program, "uRotationY")
        uAspect = GLES30.glGetUniformLocation(program, "uAspect")
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        GLES30.glViewport(0, 0, width, height)
        aspectRatio = if (height > 0) width.toFloat() / height else 1f
    }

    override fun onDrawFrame(gl: GL10?) {
        GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT or GLES30.GL_DEPTH_BUFFER_BIT)
        GLES30.glUseProgram(program)

        val elapsed = (SystemClock.uptimeMillis() - startTime) / 1000f
        GLES30.glUniform1f(uTime, elapsed)

        // Rotation speed based on state
        val rotationSpeed = when (state) {
            "thinking" -> 0.003f
            "executing" -> 0.004f
            "listening" -> 0.0015f
            else -> 0.0007f
        }
        rotationAngle += rotationSpeed
        GLES30.glUniform1f(uRotationY, rotationAngle)
        GLES30.glUniform1f(uAspect, aspectRatio)

        // Use real audio level when listening, otherwise simulate
        // PC-style smoothed interpolation based on mic RMS 
        val audioData = if ((state == "listening" || state == "speaking") && audioLevel > 0.01f) {
            val level = audioLevel.coerceIn(0f, 1f)
            val targetA = level                     // overall = full level
            val targetB = level * 0.8f              // bass dominates voice
            val targetM = level * 0.5f              // mid present
            val targetH = level * 0.3f              // high = sibilants

            // Lerp toward target each frame for fluid motion
            smoothA += (targetA - smoothA) * 0.15f
            smoothB += (targetB - smoothB) * 0.20f
            smoothM += (targetM - smoothM) * 0.18f
            smoothH += (targetH - smoothH) * 0.12f

            AudioData(smoothA, smoothB, smoothM, smoothH)
        } else {
            val sim = simulateAudio(elapsed)
            // Decay back down smoothly when not speaking
            smoothA += (sim.audio - smoothA) * 0.08f
            smoothB += (sim.bass - smoothB) * 0.10f
            smoothM += (sim.mid - smoothM) * 0.10f
            smoothH += (sim.high - smoothH) * 0.08f
            AudioData(smoothA, smoothB, smoothM, smoothH)
        }

        GLES30.glUniform1f(uAudio, audioData.audio)
        GLES30.glUniform1f(uBass, audioData.bass)
        GLES30.glUniform1f(uMid, audioData.mid)
        GLES30.glUniform1f(uHigh, audioData.high)

        val color = when (state) {
            "thinking" -> floatArrayOf(0.66f, 0.33f, 0.97f)
            "listening" -> floatArrayOf(0f, 1f, 0.53f)
            "speaking" -> floatArrayOf(0f, 0.78f, 0.83f)
            "executing" -> floatArrayOf(1f, 1f, 1f)
            "error" -> floatArrayOf(1f, 0.2f, 0.2f)
            else -> floatArrayOf(0f, 0.78f, 0.83f)
        }
        GLES30.glUniform3fv(uColor, 1, color, 0)

        val posHandle = GLES30.glGetAttribLocation(program, "aPosition")
        GLES30.glEnableVertexAttribArray(posHandle)
        GLES30.glVertexAttribPointer(posHandle, 3, GLES30.GL_FLOAT, false, 0, vertexBuffer)

        val phaseHandle = GLES30.glGetAttribLocation(program, "aPhase")
        GLES30.glEnableVertexAttribArray(phaseHandle)
        GLES30.glVertexAttribPointer(phaseHandle, 1, GLES30.GL_FLOAT, false, 0, phaseBuffer)

        GLES30.glDrawArrays(GLES30.GL_POINTS, 0, particleCount)
    }

    private fun simulateAudio(t: Float): AudioData {
        if (muted) return AudioData(0f, 0f, 0f, 0f)
        return when (state) {
            "thinking" -> AudioData(0.35f, 0.25f, 0.1f, 0f)
            "executing" -> AudioData(0.4f, 0.3f, 0.1f, 0f)
            else -> AudioData(0f, 0f, 0f, 0f)
        }
    }

    private fun createProgram(vs: String, fs: String): Int {
        val v = loadShader(GLES30.GL_VERTEX_SHADER, vs)
        val f = loadShader(GLES30.GL_FRAGMENT_SHADER, fs)
        val p = GLES30.glCreateProgram()
        GLES30.glAttachShader(p, v)
        GLES30.glAttachShader(p, f)
        GLES30.glLinkProgram(p)
        return p
    }

    private fun loadShader(type: Int, source: String): Int {
        val s = GLES30.glCreateShader(type)
        GLES30.glShaderSource(s, source)
        GLES30.glCompileShader(s)
        return s
    }
}
