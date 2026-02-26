package com.neuralai.agent.services

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.neuralai.agent.core.skills.appcontrol.UIElement
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class AccessibilityControlService : AccessibilityService() {

    companion object {
        private val _instance = MutableStateFlow<AccessibilityControlService?>(null)
        val instance: StateFlow<AccessibilityControlService?> = _instance.asStateFlow()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        _instance.value = this
    }

    override fun onUnbind(intent: Intent?): Boolean {
        _instance.value = null
        return super.onUnbind(intent)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // We generally don't need to process every event actively if we just poll the screen on demand,
        // but we could track window state changes here if needed.
    }

    override fun onInterrupt() {
        // Required, nothing to do here usually
    }

    // ==========================================
    // SCREEN READING capabilities
    // ==========================================

    fun getScreenContent(): List<UIElement> {
        val root = rootInActiveWindow ?: return emptyList()
        val elements = mutableListOf<UIElement>()
        traverseTree(root, elements)
        return elements.filter { it.text != null || it.description != null || it.isClickable }
    }

    private fun traverseTree(node: AccessibilityNodeInfo, elements: MutableList<UIElement>) {
        if (node.text != null || node.contentDescription != null || node.isClickable) {
            val bounds = Rect()
            node.getBoundsInScreen(bounds)
            elements.add(
                UIElement(
                    text = node.text?.toString(),
                    description = node.contentDescription?.toString(),
                    className = node.className?.toString(),
                    bounds = bounds,
                    isClickable = node.isClickable,
                    resourceId = node.viewIdResourceName
                )
            )
        }

        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { child ->
                traverseTree(child, elements)
            }
        }
    }

    private fun findNodeByText(root: AccessibilityNodeInfo, targetText: String, ignoreCase: Boolean = true): AccessibilityNodeInfo? {
        val textStr = root.text?.toString() ?: ""
        val descStr = root.contentDescription?.toString() ?: ""
        
        if (textStr.equals(targetText, ignoreCase) || descStr.equals(targetText, ignoreCase)) {
            return root
        }

        for (i in 0 until root.childCount) {
            root.getChild(i)?.let { child ->
                val found = findNodeByText(child, targetText, ignoreCase)
                if (found != null) return found
            }
        }
        return null
    }

    // ==========================================
    // GESTURE & ACTION capabilities
    // ==========================================

    fun tapElement(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val node = findNodeByText(root, text)
        
        // Find the node, but if it's not clickable itself, search upwards for a clickable parent
        var targetNode = node
        while (targetNode != null && !targetNode.isClickable) {
            targetNode = targetNode.parent
        }
        
        return targetNode?.performAction(AccessibilityNodeInfo.ACTION_CLICK) ?: false
    }

    fun tapCoordinates(x: Float, y: Float): Boolean {
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    fun swipe(startX: Float, startY: Float, endX: Float, endY: Float, duration: Long = 300): Boolean {
        val path = Path().apply {
            moveTo(startX, startY)
            lineTo(endX, endY)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    fun typeText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        
        return focused?.let {
            val args = Bundle().apply { 
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) 
            }
            it.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        } ?: false
    }

    fun scrollDown(): Boolean {
        val root = rootInActiveWindow ?: return false
        val scrollable = findScrollableNode(root)
        return scrollable?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD) ?: false
    }

    fun scrollUp(): Boolean {
        val root = rootInActiveWindow ?: return false
        val scrollable = findScrollableNode(root)
        return scrollable?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) ?: false
    }

    private fun findScrollableNode(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (root.isScrollable) return root
        for (i in 0 until root.childCount) {
            root.getChild(i)?.let { child ->
                val found = findScrollableNode(child)
                if (found != null) return found
            }
        }
        return null
    }

    // ==========================================
    // FIND & TYPE into specific fields
    // ==========================================

    /**
     * Finds an editable text field (EditText) and types text into it.
     * Searches by hint text, content description, or nearby labels.
     */
    fun findEditableAndType(hint: String?, text: String): Boolean {
        val root = rootInActiveWindow ?: return false

        // Strategy 1: Find any focused editable
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        if (focused != null && focused.isEditable) {
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            }
            return focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        }

        // Strategy 2: Find editable by scanning tree
        val editable = findEditableNode(root, hint)
        if (editable != null) {
            editable.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            }
            return editable.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        }

        return false
    }

    private fun findEditableNode(root: AccessibilityNodeInfo, hint: String?): AccessibilityNodeInfo? {
        if (root.isEditable) {
            if (hint == null) return root
            val nodeText = root.text?.toString()?.lowercase() ?: ""
            val nodeHint = root.hintText?.toString()?.lowercase() ?: ""
            val nodeDesc = root.contentDescription?.toString()?.lowercase() ?: ""
            val lowerHint = hint.lowercase()
            if (nodeText.contains(lowerHint) || nodeHint.contains(lowerHint) || nodeDesc.contains(lowerHint)) {
                return root
            }
        }
        for (i in 0 until root.childCount) {
            root.getChild(i)?.let { child ->
                val found = findEditableNode(child, hint)
                if (found != null) return found
            }
        }
        // If no specific match found and hint is null, return first editable
        if (hint != null) return findEditableNode(root, null)
        return null
    }

    // ==========================================
    // SCREENSHOT CAPTURE
    // ==========================================

    /**
     * Takes a screenshot using the AccessibilityService API (Android 11+).
     * The result is delivered asynchronously via callback.
     */
    @Volatile
    var lastScreenshot: android.graphics.Bitmap? = null
        private set

    fun captureScreen(callback: ((android.graphics.Bitmap?) -> Unit)? = null) {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            takeScreenshot(
                android.view.Display.DEFAULT_DISPLAY,
                mainExecutor,
                object : TakeScreenshotCallback {
                    override fun onSuccess(screenshot: ScreenshotResult) {
                        val hwBitmap = android.graphics.Bitmap.wrapHardwareBuffer(
                            screenshot.hardwareBuffer,
                            screenshot.colorSpace
                        )
                        val swBitmap = hwBitmap?.copy(android.graphics.Bitmap.Config.ARGB_8888, false)
                        hwBitmap?.recycle()
                        screenshot.hardwareBuffer.close()
                        lastScreenshot = swBitmap
                        callback?.invoke(swBitmap)
                    }

                    override fun onFailure(errorCode: Int) {
                        lastScreenshot = null
                        callback?.invoke(null)
                    }
                }
            )
        } else {
            callback?.invoke(null)
        }
    }

    // ==========================================
    // GLOBAL ACTIONS
    // ==========================================

    fun pressBack() = performGlobalAction(GLOBAL_ACTION_BACK)
    fun pressHome() = performGlobalAction(GLOBAL_ACTION_HOME)
    fun pressRecents() = performGlobalAction(GLOBAL_ACTION_RECENTS)
    fun openNotifications() = performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
    fun takeScreenshotGlobal() = performGlobalAction(GLOBAL_ACTION_TAKE_SCREENSHOT)
}
