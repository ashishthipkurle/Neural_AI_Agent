package com.neuralai.agent.core

import javax.inject.Inject
import javax.inject.Singleton

enum class Intent {
    CHAT,
    WEB_SEARCH,
    OPEN_APP,
    CLOSE_APP,
    SYSTEM_CONTROL,
    VISION_ANALYZE,
    TRADING,
    MEMORY_RECALL,
    // Device automation
    TAP,
    LONG_PRESS,
    TYPE_TEXT,
    SWIPE,
    SCROLL,
    SCREENSHOT,
    READ_SCREEN,
    // App management
    INSTALL_APP,
    UNINSTALL_APP,
    // Navigation
    GO_BACK,
    GO_HOME,
    // Media & Volume
    MEDIA_CONTROL,
    VOLUME_CONTROL,
    BRIGHTNESS,
    // Device toggles
    TOGGLE_SETTING,
    // Alarms
    ALARM_TIMER,
    // Camera
    TAKE_PHOTO,
    // Notifications & Sensors
    READ_NOTIFICATIONS,
    SENSOR_DATA,
    // Share
    SHARE
}

@Singleton
class IntentParser @Inject constructor() {

    fun parse(input: String): Intent {
        val lower = input.lowercase().trim()

        return when {
            // ── Navigation shortcuts (highest priority) ──────────────
            lower.matches(Regex("^(go\\s*back|back|previous|previous\\s*page)$")) -> Intent.GO_BACK
            lower.matches(Regex("^(go\\s*home|home|home\\s*screen|main\\s*screen)$")) -> Intent.GO_HOME

            // ── Device automation gestures ────────────────────────────
            lower.matches(Regex(".*\\b(long\\s*press|long\\s*click|hold|press\\s*and\\s*hold)\\b.*")) -> Intent.LONG_PRESS
            lower.matches(Regex(".*\\b(tap|taps|tapping|click|clicks|clicking|press|presses|pressing)\\b.*"))
                && !lower.matches(Regex(".*\\b(long)\\b.*")) -> Intent.TAP
            lower.matches(Regex(".*\\b(type|types|typing|write|writes|writing|enter)\\b.*")) -> Intent.TYPE_TEXT
            lower.matches(Regex(".*\\b(send|sending)\\b.*")) && !lower.matches(Regex(".*\\b(call|calling)\\b.*")) -> Intent.TYPE_TEXT
            lower.matches(Regex(".*\\b(swipe|swipes|swiping)\\b.*")) -> Intent.SWIPE
            lower.matches(Regex(".*\\b(scroll|scrolls|scrolling)\\b.*")) -> Intent.SCROLL
            lower.matches(Regex(".*\\b(screen\\s*shot|capture\\s*screen|take\\s*screenshot)\\b.*")) -> Intent.SCREENSHOT
            lower.matches(Regex(".*\\b(read\\s*screen|what's\\s*on\\s*screen|screen\\s*content)\\b.*")) -> Intent.READ_SCREEN

            // ── Camera ────────────────────────────────────────────────
            lower.matches(Regex(".*\\b(take\\s*(a\\s*)?(photo|picture|selfie|pic)|record\\s*video|open\\s*camera)\\b.*")) -> Intent.TAKE_PHOTO

            // ── Share ─────────────────────────────────────────────────
            lower.matches(Regex(".*\\b(share)\\b.*")) -> Intent.SHARE

            // ── App management ────────────────────────────────────────
            lower.matches(Regex(".*\\b(close|exit|quit|kill|force\\s*stop)\\b.*")) -> Intent.CLOSE_APP
            lower.matches(Regex(".*\\b(install|download)\\b.*")) && !lower.matches(Regex(".*\\b(uninstall|remove|delete)\\b.*")) -> Intent.INSTALL_APP
            lower.matches(Regex(".*\\b(uninstall|remove|delete)\\b.*")) && lower.contains("app") -> Intent.UNINSTALL_APP

            // ── Alarms & Timers ───────────────────────────────────────
            lower.matches(Regex(".*\\b(set\\s*alarm|set\\s*timer|alarm|timer|wake\\s*me\\s*up|countdown|set\\s*reminder)\\b.*")) -> Intent.ALARM_TIMER

            // ── Media controls ────────────────────────────────────────
            lower.matches(Regex(".*\\b(play\\s*music|pause\\s*music|stop\\s*music|next\\s*song|previous\\s*song|skip\\s*song|resume\\s*music)\\b.*")) -> Intent.MEDIA_CONTROL
            lower.matches(Regex("^(play|pause|resume|stop|skip|next|previous)$")) -> Intent.MEDIA_CONTROL

            // ── Volume ────────────────────────────────────────────────
            lower.matches(Regex(".*\\b(volume\\s*(up|down|max|mute|unmute|loud|silent)|set\\s*volume|mute|unmute)\\b.*")) -> Intent.VOLUME_CONTROL

            // ── Brightness ────────────────────────────────────────────
            lower.matches(Regex(".*\\b(brightness\\s*(up|down|max|min|low|high)|set\\s*brightness|max\\s*brightness|min\\s*brightness)\\b.*")) -> Intent.BRIGHTNESS

            // ── Toggle settings (wifi, bluetooth, flashlight, etc.) ──
            lower.matches(Regex(".*\\b(turn\\s*(on|off)|enable|disable|toggle)\\b.*\\b(wifi|wi-fi|bluetooth|flashlight|torch|airplane\\s*mode|flight\\s*mode|mobile\\s*data|cellular\\s*data|data|hotspot|dark\\s*mode|night\\s*mode|do\\s*not\\s*disturb|dnd|auto\\s*rotate|rotation|nfc|gps|location)\\b.*")) -> Intent.TOGGLE_SETTING
            lower.matches(Regex(".*\\b(wifi|bluetooth|flashlight|torch|airplane|hotspot|dark\\s*mode|dnd)\\b.*\\b(on|off|enable|disable)\\b.*")) -> Intent.TOGGLE_SETTING

            // ── Notifications & Sensors ───────────────────────────────
            lower.matches(Regex(".*\\b(notification|notifications)\\b.*")) && lower.matches(Regex(".*\\b(read|show|check|what)\\b.*")) -> Intent.READ_NOTIFICATIONS
            lower.matches(Regex(".*\\b(sensor|sensors|accelerometer|gyro|proximity)\\b.*")) -> Intent.SENSOR_DATA

            // ── Existing intents ──────────────────────────────────────
            lower.matches(Regex(".*\\b(search|look\\s*up)\\b.*")) && !lower.matches(Regex(".*\\b(tap|click)\\b.*")) -> Intent.WEB_SEARCH
            lower.matches(Regex(".*\\b(analyze|look\\s*at|what\\s*do\\s*you\\s*see)\\b.*")) && lower.contains("image") -> Intent.VISION_ANALYZE
            lower.matches(Regex(".*\\b(price\\s*of|buy|sell|trading)\\b.*")) -> Intent.TRADING
            lower.matches(Regex(".*\\b(remember|what\\s*did\\s*i)\\b.*")) -> Intent.MEMORY_RECALL
            lower.matches(Regex(".*\\b(call|calling)\\b.*")) -> Intent.SYSTEM_CONTROL
            lower.matches(Regex(".*\\b(location|where\\s*am\\s*i|gps)\\b.*")) -> Intent.SYSTEM_CONTROL
            lower.matches(Regex(".*\\b(notify|notification)\\b.*")) -> Intent.SYSTEM_CONTROL

            // ── "go to" as TAP (after all more specific "go" patterns) ──
            lower.matches(Regex(".*\\b(go\\s*to|navigate\\s*to)\\b.*")) -> Intent.TAP

            // ── Open App is LOWEST priority ───────────────────────────
            lower.matches(Regex(".*\\b(open|launch|start|run)\\b.*")) -> Intent.OPEN_APP

            else -> Intent.CHAT
        }
    }
}
