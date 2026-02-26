package com.neuralai.agent.core

import javax.inject.Inject
import javax.inject.Singleton

enum class Intent {
    CHAT,
    WEB_SEARCH,
    OPEN_APP,
    SYSTEM_CONTROL,
    VISION_ANALYZE,
    TRADING,
    MEMORY_RECALL,
    // Device automation
    TAP,
    TYPE_TEXT,
    SWIPE,
    SCROLL,
    SCREENSHOT,
    READ_SCREEN,
    // App management
    INSTALL_APP,
    UNINSTALL_APP,
    // Notifications & Sensors
    READ_NOTIFICATIONS,
    SENSOR_DATA
}

@Singleton
class IntentParser @Inject constructor() {

    fun parse(input: String): Intent {
        val lower = input.lowercase()
        return when {
            // Device automation — match first (most specific)
            lower.contains("tap on") || lower.contains("click on") || lower.contains("press on") -> Intent.TAP
            lower.contains("type ") && (lower.contains("into") || lower.contains("in the") || lower.contains("message")) -> Intent.TYPE_TEXT
            (lower.contains("send") && (lower.contains("message") || lower.contains("text") || lower.contains("sms")))
                && !lower.contains("call") -> Intent.TYPE_TEXT
            lower.contains("swipe") -> Intent.SWIPE
            lower.contains("scroll") -> Intent.SCROLL
            lower.contains("screenshot") || lower.contains("screen shot") || lower.contains("capture screen") -> Intent.SCREENSHOT
            lower.contains("read screen") || lower.contains("what's on screen") || lower.contains("screen content") -> Intent.READ_SCREEN
            // App management
            lower.contains("install") && !lower.contains("uninstall") -> Intent.INSTALL_APP
            lower.contains("uninstall") || lower.contains("remove app") || lower.contains("delete app") -> Intent.UNINSTALL_APP
            // Notifications
            lower.contains("notification") && (lower.contains("read") || lower.contains("show") || lower.contains("check") || lower.contains("what")) -> Intent.READ_NOTIFICATIONS
            // Sensors
            lower.contains("sensor") || lower.contains("accelerometer") || lower.contains("gyro") || lower.contains("proximity") -> Intent.SENSOR_DATA
            // Existing intents
            lower.contains("search") || lower.contains("look up") -> Intent.WEB_SEARCH
            lower.contains("open") || lower.contains("launch") -> Intent.OPEN_APP
            lower.contains("what do you see") || lower.contains("look at") || lower.contains("analyze") && lower.contains("image") -> Intent.VISION_ANALYZE
            lower.contains("price of") || lower.contains("buy") || lower.contains("sell") -> Intent.TRADING
            lower.contains("remember") || lower.contains("what did i") -> Intent.MEMORY_RECALL
            lower.contains("turn on") || lower.contains("volume") || lower.contains("call") || lower.contains("location") || lower.contains("where am i") -> Intent.SYSTEM_CONTROL
            lower.contains("notify") || lower.contains("notification") -> Intent.SYSTEM_CONTROL
            else -> Intent.CHAT
        }
    }
}
