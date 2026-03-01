package com.neuralai.agent.core.skills.device

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.wifi.WifiManager
import android.os.Build
import android.provider.AlarmClock
import android.provider.Settings
import android.hardware.camera2.CameraManager
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import com.neuralai.agent.services.WakeWordService
import com.neuralai.agent.services.AccessibilityControlService
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DeviceControlSkill @Inject constructor(
    @ApplicationContext private val context: Context
) {

    // ==========================================
    // WIFI
    // ==========================================
    
    fun setWifi(enable: Boolean): String {
        return try {
            val intent = Intent(Settings.ACTION_WIFI_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            launchIntent(intent)
            "Opening WiFi settings. Please toggle WiFi ${if (enable) "on" else "off"}."
        } catch (e: Exception) {
            "Could not open WiFi settings: ${e.message}"
        }
    }

    // ==========================================
    // BLUETOOTH
    // ==========================================

    fun setBluetooth(enable: Boolean): String {
        return try {
            val intent = Intent(Settings.ACTION_BLUETOOTH_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            launchIntent(intent)
            "Opening Bluetooth settings. Please toggle Bluetooth ${if (enable) "on" else "off"}."
        } catch (e: Exception) {
            "Could not open Bluetooth settings: ${e.message}"
        }
    }

    // ==========================================
    // FLASHLIGHT / TORCH
    // ==========================================

    fun setFlashlight(enable: Boolean): String {
        return try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraId = cameraManager.cameraIdList[0]
            cameraManager.setTorchMode(cameraId, enable)
            "Flashlight turned ${if (enable) "on" else "off"}."
        } catch (e: Exception) {
            "Could not control flashlight: ${e.message}"
        }
    }

    // ==========================================
    // VOLUME
    // ==========================================

    fun setVolume(action: String): String {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val currentVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        
        return when {
            action.contains("up") || action.contains("increase") || action.contains("loud") -> {
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
                "Volume increased."
            }
            action.contains("down") || action.contains("decrease") || action.contains("lower") -> {
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
                "Volume decreased."
            }
            action.contains("max") || action.contains("full") -> {
                audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, AudioManager.FLAG_SHOW_UI)
                "Volume set to maximum."
            }
            action.contains("mute") || action.contains("silent") -> {
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI)
                "Volume muted."
            }
            action.contains("unmute") -> {
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, AudioManager.FLAG_SHOW_UI)
                "Volume unmuted."
            }
            else -> {
                // Try to extract a percentage: "set volume to 50"
                val pctMatch = Regex("(\\d+)").find(action)
                if (pctMatch != null) {
                    val pct = pctMatch.groupValues[1].toIntOrNull() ?: 50
                    val targetVol = (maxVolume * pct / 100).coerceIn(0, maxVolume)
                    audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, targetVol, AudioManager.FLAG_SHOW_UI)
                    "Volume set to $pct%."
                } else {
                    audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
                    "Volume increased."
                }
            }
        }
    }

    // ==========================================
    // BRIGHTNESS
    // ==========================================

    fun setBrightness(action: String): String {
        return try {
            if (!Settings.System.canWrite(context)) {
                val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                launchIntent(intent)
                return "Please grant 'Modify system settings' permission first."
            }
            
            val currentBrightness = Settings.System.getInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, 128)
            
            when {
                action.contains("up") || action.contains("increase") || action.contains("high") -> {
                    val newVal = (currentBrightness + 50).coerceAtMost(255)
                    Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, newVal)
                    "Brightness increased."
                }
                action.contains("down") || action.contains("decrease") || action.contains("low") || action.contains("dim") -> {
                    val newVal = (currentBrightness - 50).coerceAtLeast(10)
                    Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, newVal)
                    "Brightness decreased."
                }
                action.contains("max") || action.contains("full") -> {
                    Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, 255)
                    "Brightness set to maximum."
                }
                action.contains("min") -> {
                    Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, 10)
                    "Brightness set to minimum."
                }
                else -> {
                    val pctMatch = Regex("(\\d+)").find(action)
                    if (pctMatch != null) {
                        val pct = pctMatch.groupValues[1].toIntOrNull() ?: 50
                        val targetVal = (255 * pct / 100).coerceIn(10, 255)
                        Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, targetVal)
                        "Brightness set to $pct%."
                    } else {
                        "Please specify brightness level (up, down, max, min, or a percentage)."
                    }
                }
            }
        } catch (e: Exception) {
            "Could not change brightness: ${e.message}"
        }
    }

    // ==========================================
    // MEDIA CONTROLS
    // ==========================================

    fun mediaControl(action: String): String {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        
        return when {
            action.contains("play") || action.contains("resume") -> {
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PLAY)
                )
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PLAY)
                )
                "Playing media."
            }
            action.contains("pause") || action.contains("stop") -> {
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE)
                )
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE)
                )
                "Media paused."
            }
            action.contains("next") || action.contains("skip") -> {
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_NEXT)
                )
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_NEXT)
                )
                "Skipped to next track."
            }
            action.contains("previous") || action.contains("prev") -> {
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS)
                )
                audioManager.dispatchMediaKeyEvent(
                    android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS)
                )
                "Playing previous track."
            }
            else -> "Media control: specify play, pause, next, or previous."
        }
    }

    // ==========================================
    // ALARM & TIMER
    // ==========================================

    fun setAlarm(input: String): String {
        val lower = input.lowercase()
        
        // Timer: "set timer for 5 minutes"
        val timerMatch = Regex("timer\\s+(?:for\\s+)?(\\d+)\\s*(minute|minutes|min|mins|second|seconds|sec|secs|hour|hours|hr|hrs)").find(lower)
        if (timerMatch != null) {
            val amount = timerMatch.groupValues[1].toIntOrNull() ?: 1
            val unit = timerMatch.groupValues[2]
            val seconds = when {
                unit.startsWith("hour") || unit.startsWith("hr") -> amount * 3600
                unit.startsWith("min") -> amount * 60
                unit.startsWith("sec") -> amount
                else -> amount * 60
            }
            return try {
                val intent = Intent(AlarmClock.ACTION_SET_TIMER).apply {
                    putExtra(AlarmClock.EXTRA_LENGTH, seconds)
                    putExtra(AlarmClock.EXTRA_MESSAGE, "Neural Agent Timer")
                    putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                launchIntent(intent)
                "Timer set for $amount ${unit}."
            } catch (e: Exception) {
                "Could not set timer: ${e.message}"
            }
        }
        
        // Alarm: "set alarm for 7 am" or "set alarm for 7:30" or "wake me up at 6:30 am"
        val alarmMatch = Regex("(?:alarm|wake\\s*(?:me\\s*)?up)\\s+(?:for|at)\\s+(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?").find(lower)
        if (alarmMatch != null) {
            var hour = alarmMatch.groupValues[1].toIntOrNull() ?: 7
            val minute = alarmMatch.groupValues[2].toIntOrNull() ?: 0
            val amPm = alarmMatch.groupValues[3]
            
            if (amPm == "pm" && hour < 12) hour += 12
            if (amPm == "am" && hour == 12) hour = 0
            
            return try {
                val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                    putExtra(AlarmClock.EXTRA_HOUR, hour)
                    putExtra(AlarmClock.EXTRA_MINUTES, minute)
                    putExtra(AlarmClock.EXTRA_MESSAGE, "Neural Agent Alarm")
                    putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                launchIntent(intent)
                val formattedHour = if (hour > 12) hour - 12 else if (hour == 0) 12 else hour
                val amPmStr = if (hour >= 12) "PM" else "AM"
                "Alarm set for $formattedHour:${String.format("%02d", minute)} $amPmStr."
            } catch (e: Exception) {
                "Could not set alarm: ${e.message}"
            }
        }
        
        return "Please specify a time. E.g. 'set alarm for 7 am' or 'set timer for 5 minutes'."
    }

    // ==========================================
    // TOGGLE SETTINGS
    // ==========================================

    fun toggleSetting(input: String): String {
        val lower = input.lowercase()
        val turnOn = lower.contains("on") || lower.contains("enable")
        
        return when {
            lower.contains("wifi") || lower.contains("wi-fi") -> setWifi(turnOn)
            lower.contains("bluetooth") -> setBluetooth(turnOn)
            lower.contains("flashlight") || lower.contains("torch") -> setFlashlight(turnOn)
            lower.contains("airplane") || lower.contains("flight mode") -> {
                try {
                    val intent = Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Airplane Mode settings."
                } catch (e: Exception) {
                    "Could not open Airplane Mode settings."
                }
            }
            lower.contains("mobile data") || lower.contains("cellular") || (lower.contains("data") && !lower.contains("sensor")) -> {
                try {
                    val intent = Intent(Settings.ACTION_DATA_ROAMING_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Mobile Data settings."
                } catch (e: Exception) {
                    "Could not open Data settings."
                }
            }
            lower.contains("hotspot") || lower.contains("tethering") -> {
                try {
                    val intent = Intent(Settings.ACTION_WIRELESS_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Hotspot settings."
                } catch (e: Exception) {
                    "Could not open Hotspot settings."
                }
            }
            lower.contains("dark mode") || lower.contains("night mode") -> {
                try {
                    val intent = Intent(Settings.ACTION_DISPLAY_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Display settings for Dark Mode."
                } catch (e: Exception) {
                    "Could not open Display settings."
                }
            }
            lower.contains("do not disturb") || lower.contains("dnd") -> {
                try {
                    val intent = Intent(Settings.ACTION_ZEN_MODE_PRIORITY_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Do Not Disturb settings."
                } catch (e: Exception) {
                    "Could not open DND settings."
                }
            }
            lower.contains("auto rotate") || lower.contains("rotation") -> {
                try {
                    if (Settings.System.canWrite(context)) {
                        val current = Settings.System.getInt(context.contentResolver, Settings.System.ACCELEROMETER_ROTATION, 0)
                        Settings.System.putInt(context.contentResolver, Settings.System.ACCELEROMETER_ROTATION, if (current == 1) 0 else 1)
                        "Auto-rotate ${if (current == 1) "disabled" else "enabled"}."
                    } else {
                        val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        launchIntent(intent)
                        "Please grant 'Modify system settings' permission first."
                    }
                } catch (e: Exception) {
                    "Could not toggle auto-rotate."
                }
            }
            lower.contains("nfc") -> {
                try {
                    val intent = Intent(Settings.ACTION_NFC_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening NFC settings."
                } catch (e: Exception) {
                    "Could not open NFC settings."
                }
            }
            lower.contains("location") || lower.contains("gps") -> {
                try {
                    val intent = Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    launchIntent(intent)
                    "Opening Location settings."
                } catch (e: Exception) {
                    "Could not open Location settings."
                }
            }
            else -> "Unrecognized setting. Available: wifi, bluetooth, flashlight, airplane mode, mobile data, hotspot, dark mode, dnd, auto rotate, nfc, location."
        }
    }

    // ==========================================
    // CAMERA
    // ==========================================

    fun openCamera(mode: String): String {
        return try {
            val intent = if (mode.contains("video")) {
                Intent(android.provider.MediaStore.ACTION_VIDEO_CAPTURE)
            } else if (mode.contains("selfie") || mode.contains("front")) {
                Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE).apply {
                    putExtra("android.intent.extras.CAMERA_FACING", 1) // Front camera
                }
            } else {
                Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE)
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            launchIntent(intent)
            when {
                mode.contains("video") -> "Opening camera for video recording."
                mode.contains("selfie") -> "Opening front camera for selfie."
                else -> "Opening camera."
            }
        } catch (e: Exception) {
            "Could not open camera: ${e.message}"
        }
    }

    // ==========================================
    // SHARE
    // ==========================================

    fun shareText(text: String): String {
        return try {
            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, text)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            val chooser = Intent.createChooser(shareIntent, "Share via").apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            launchIntent(chooser)
            "Opening share dialog."
        } catch (e: Exception) {
            "Could not share: ${e.message}"
        }
    }

    // ==========================================
    // UTILITY
    // ==========================================

    private fun launchIntent(intent: Intent) {
        val wakeService = WakeWordService.instance.value
        val accService = AccessibilityControlService.instance.value
        when {
            wakeService != null -> wakeService.startActivity(intent)
            accService != null -> accService.startActivity(intent)
            else -> context.startActivity(intent)
        }
    }
}
