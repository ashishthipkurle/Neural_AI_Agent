package com.neuralai.agent.services

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class NotificationData(
    val packageName: String,
    val title: String,
    val text: String,
    val timestamp: Long,
    val appName: String = ""
)

class NeuralNotificationListener : NotificationListenerService() {

    companion object {
        private val _recentNotifications = MutableStateFlow<List<NotificationData>>(emptyList())
        val recentNotifications: StateFlow<List<NotificationData>> = _recentNotifications.asStateFlow()

        private val _isConnected = MutableStateFlow(false)
        val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

        private const val MAX_NOTIFICATIONS = 30

        fun getFormattedNotifications(): String {
            val notifs = _recentNotifications.value
            if (notifs.isEmpty()) return "No recent notifications."
            return notifs.takeLast(15).joinToString("\n") { n ->
                "• [${n.appName.ifEmpty { n.packageName }}] ${n.title}: ${n.text}"
            }
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        _isConnected.value = true
        // Load existing active notifications
        try {
            val active = activeNotifications ?: emptyArray()
            val existing = active.mapNotNull { parseNotification(it) }
            _recentNotifications.value = existing.takeLast(MAX_NOTIFICATIONS)
        } catch (_: Exception) { }
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        _isConnected.value = false
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        sbn ?: return
        val data = parseNotification(sbn) ?: return
        val current = _recentNotifications.value.toMutableList()
        current.add(data)
        if (current.size > MAX_NOTIFICATIONS) {
            _recentNotifications.value = current.takeLast(MAX_NOTIFICATIONS)
        } else {
            _recentNotifications.value = current
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        // Keep in history — don't remove
    }

    private fun parseNotification(sbn: StatusBarNotification): NotificationData? {
        val extras = sbn.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        if (title.isEmpty() && text.isEmpty()) return null

        val appName = try {
            val pm = applicationContext.packageManager
            pm.getApplicationLabel(pm.getApplicationInfo(sbn.packageName, 0)).toString()
        } catch (_: Exception) { "" }

        return NotificationData(
            packageName = sbn.packageName,
            title = title,
            text = text,
            timestamp = sbn.postTime,
            appName = appName
        )
    }
}
