package com.neuralai.agent.core.skills.appcontrol

import android.graphics.Rect

/**
 * Represents a single interactive or readable element on the Android screen.
 */
data class UIElement(
    val text: String?,
    val description: String?,
    val className: String?,
    val bounds: Rect,
    val isClickable: Boolean,
    val resourceId: String?
) {
    override fun toString(): String {
        val label = text ?: description ?: ""
        return "[$className] '$label' bounds=${bounds.toShortString()} clickable=$isClickable id=$resourceId"
    }
}
