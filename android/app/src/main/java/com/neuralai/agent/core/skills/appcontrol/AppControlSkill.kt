package com.neuralai.agent.core.skills.appcontrol

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.neuralai.agent.services.AccessibilityControlService
import com.neuralai.agent.services.WakeWordService
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.delay
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AppControlSkill @Inject constructor(
    @ApplicationContext private val context: Context
) {
    // Map of common app names to package names.
    private val appMap = mapOf(
        "whatsapp" to "com.whatsapp",
        "chrome" to "com.android.chrome",
        "instagram" to "com.instagram.android",
        "youtube" to "com.google.android.youtube",
        "camera" to "com.android.camera2",
        "settings" to "com.android.settings",
        "phone" to "com.android.dialer",
        "messages" to "com.google.android.apps.messaging",
        "gmail" to "com.google.android.gm",
        "maps" to "com.google.android.apps.maps",
        "play store" to "com.android.vending",
        "spotify" to "com.spotify.music"
    )

    private val accessibilityService: AccessibilityControlService?
        get() = AccessibilityControlService.instance.value

    var lastLaunchedApp: String? = null
        private set

    fun isServiceActive(): Boolean {
        return accessibilityService != null
    }

    /**
     * Launches an application by common name or exact package name.
     * Priority: 1) Known appMap  2) Search installed apps by label  3) Play Store search
     */
    fun launchApp(appName: String): Boolean {
        val lower = appName.lowercase().trim()
        
        // 1. Try known package from our map
        val knownPackage = appMap[lower]
        if (knownPackage != null) {
            val intent = context.packageManager.getLaunchIntentForPackage(knownPackage)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                // Route through our visible foreground service to bypass Android 10+ background restrictions
                val wakeService = WakeWordService.instance.value
                val accService = accessibilityService
                when {
                    wakeService != null -> wakeService.startActivity(intent)
                    accService != null -> accService.startActivity(intent)
                    else -> context.startActivity(intent)
                }
                lastLaunchedApp = lower
                return true
            }
        }
        
        // 2. Search all installed apps by display name (label)
        val pm = context.packageManager
        val installedApps = pm.getInstalledApplications(0)
        for (app in installedApps) {
            val label = pm.getApplicationLabel(app).toString().lowercase()
            if (label.contains(lower) || lower.contains(label)) {
                val intent = pm.getLaunchIntentForPackage(app.packageName)
                if (intent != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    val wakeService = WakeWordService.instance.value
                    val accService = accessibilityService
                    when {
                        wakeService != null -> wakeService.startActivity(intent)
                        accService != null -> accService.startActivity(intent)
                        else -> context.startActivity(intent)
                    }
                    lastLaunchedApp = lower
                    return true
                }
            }
        }
        
        // 3. Last resort: return false — don't silently redirect to Play Store
        return false
    }

    /**
     * Redirect user to Accessibility Settings
     */
    fun openAccessibilitySettings() {
        try {
            val intent = Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val wakeService = WakeWordService.instance.value
            val accService = accessibilityService
            when {
                wakeService != null -> wakeService.startActivity(intent)
                accService != null -> accService.startActivity(intent)
                else -> context.startActivity(intent)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    /**
     * Reads all interactable elements currently visible on the screen.
     */
    fun readScreen(): String {
        val service = accessibilityService ?: return "Error: Accessibility Service not active."
        val elements = service.getScreenContent()
        if (elements.isEmpty()) return "Screen is empty or cannot be read."
        
        return elements.joinToString("\n") { it.toString() }
    }

    /**
     * Taps an element matching the exact or partial text.
     */
    fun tapOnScreen(text: String): Boolean {
        val service = accessibilityService ?: return false
        return service.tapElement(text)
    }

    /**
     * Taps at absolute screen coordinates.
     */
    fun tapAt(x: Float, y: Float): Boolean {
        val service = accessibilityService ?: return false
        return service.tapCoordinates(x, y)
    }

    /**
     * Types text into the currently focused input field.
     */
    fun typeInto(text: String): Boolean {
        val service = accessibilityService ?: return false
        return service.typeText(text)
    }

    /**
     * Swipes up (scrolls down the page).
     */
    fun swipeUp(): Boolean {
        val service = accessibilityService ?: return false
        return service.scrollDown() // semantic inverse matches user intention usually
    }

    /**
     * Swipes down (scrolls up the page).
     */
    fun swipeDown(): Boolean {
        val service = accessibilityService ?: return false
        return service.scrollUp()
    }

    fun goBack(): Boolean {
        return accessibilityService?.pressBack() ?: false
    }

    fun goHome(): Boolean {
        return accessibilityService?.pressHome() ?: false
    }
    
    fun openNotifications(): Boolean {
        return accessibilityService?.openNotifications() ?: false
    }

    /**
     * Opens the Play Store to install an app by name.
     */
    fun installApp(appName: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("market://search?q=$appName"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val wakeService = WakeWordService.instance.value
            val accService = accessibilityService
            when {
                wakeService != null -> wakeService.startActivity(intent)
                accService != null -> accService.startActivity(intent)
                else -> context.startActivity(intent)
            }
            true
        } catch (e: Exception) {
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/search?q=$appName"))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                val wakeService = WakeWordService.instance.value
                val accService = accessibilityService
                when {
                    wakeService != null -> wakeService.startActivity(intent)
                    accService != null -> accService.startActivity(intent)
                    else -> context.startActivity(intent)
                }
                true
            } catch (_: Exception) { false }
        }
    }

    /**
     * Uninstalls an app by package name or display name.
     */
    fun uninstallApp(appName: String): Boolean {
        val lower = appName.lowercase().trim()

        // Find package name
        val packageName = appMap[lower] ?: run {
            val pm = context.packageManager
            pm.getInstalledApplications(0).firstOrNull {
                pm.getApplicationLabel(it).toString().lowercase().contains(lower)
            }?.packageName
        }

        if (packageName != null) {
            return try {
                val intent = Intent(Intent.ACTION_DELETE, Uri.parse("package:$packageName"))
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                val wakeService = WakeWordService.instance.value
                val accService = accessibilityService
                when {
                    wakeService != null -> wakeService.startActivity(intent)
                    accService != null -> accService.startActivity(intent)
                    else -> context.startActivity(intent)
                }
                true
            } catch (_: Exception) { false }
        }
        return false
    }

    /**
     * Takes a screenshot via the AccessibilityService API.
     */
    fun takeScreenshot(callback: ((android.graphics.Bitmap?) -> Unit)? = null) {
        val service = accessibilityService
        if (service != null) {
            service.captureScreen(callback)
        } else {
            callback?.invoke(null)
        }
    }

    /**
     * Finds an editable text field and types into it.
     */
    fun findAndType(hint: String?, text: String): Boolean {
        val service = accessibilityService ?: return false
        return service.findEditableAndType(hint, text)
    }

    /**
     * Custom swipe gesture at specific coordinates.
     */
    fun swipeGesture(startX: Float, startY: Float, endX: Float, endY: Float): Boolean {
        val service = accessibilityService ?: return false
        return service.swipe(startX, startY, endX, endY)
    }

    /**
     * Force-stops an application by package name or display name.
     */
    fun closeApp(appName: String): Boolean {
        val lower = appName.lowercase().trim()
        val packageName = appMap[lower] ?: run {
            val pm = context.packageManager
            pm.getInstalledApplications(0).firstOrNull {
                pm.getApplicationLabel(it).toString().lowercase().contains(lower)
            }?.packageName
        }
        if (packageName != null) {
            try {
                val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                am.killBackgroundProcesses(packageName)
                return true
            } catch (_: Exception) { }
        }
        // Fallback: press Back + Home to leave the app
        goBack()
        goHome()
        return true
    }

    /**
     * Long-presses an element matching the text.
     */
    fun longPressOnScreen(text: String): Boolean {
        val service = accessibilityService ?: return false
        return service.longClickElement(text)
    }
}
