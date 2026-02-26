package com.neuralai.agent.core.skills.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SensorSkill @Inject constructor(
    @ApplicationContext private val context: Context
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

    // Latest readings
    @Volatile var accelerometer: FloatArray = floatArrayOf(0f, 0f, 0f)
    @Volatile var gyroscope: FloatArray = floatArrayOf(0f, 0f, 0f)
    @Volatile var proximity: Float = -1f
    @Volatile var light: Float = -1f

    private var registered = false

    fun startListening() {
        if (registered) return
        registered = true

        sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        sensorManager.getDefaultSensor(Sensor.TYPE_PROXIMITY)?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT)?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
    }

    fun stopListening() {
        sensorManager.unregisterListener(this)
        registered = false
    }

    override fun onSensorChanged(event: SensorEvent?) {
        event ?: return
        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> accelerometer = event.values.copyOf()
            Sensor.TYPE_GYROSCOPE -> gyroscope = event.values.copyOf()
            Sensor.TYPE_PROXIMITY -> proximity = event.values[0]
            Sensor.TYPE_LIGHT -> light = event.values[0]
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    /**
     * Returns a formatted summary of all sensor readings.
     */
    fun getSensorData(): String {
        startListening() // Ensure we're listening

        val sb = StringBuilder("📡 Sensor Readings:\n")
        sb.appendLine("• Accelerometer: x=${f(accelerometer[0])}, y=${f(accelerometer[1])}, z=${f(accelerometer[2])} m/s²")
        sb.appendLine("• Gyroscope: x=${f(gyroscope[0])}, y=${f(gyroscope[1])}, z=${f(gyroscope[2])} rad/s")

        if (proximity >= 0) sb.appendLine("• Proximity: ${f(proximity)} cm")
        if (light >= 0) sb.appendLine("• Light: ${f(light)} lux")

        // Device orientation info
        val isFlat = kotlin.math.abs(accelerometer[2]) > 8f
        val isFaceDown = accelerometer[2] < -8f
        val isPortrait = kotlin.math.abs(accelerometer[1]) > kotlin.math.abs(accelerometer[0])
        sb.appendLine("• Orientation: ${if (isFlat) if (isFaceDown) "Face Down" else "Flat" else if (isPortrait) "Portrait" else "Landscape"}")

        return sb.toString()
    }

    private fun f(v: Float) = String.format("%.2f", v)
}
