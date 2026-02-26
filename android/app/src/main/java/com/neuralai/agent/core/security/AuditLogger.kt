package com.neuralai.agent.core.security

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Logs all sensitive agent actions to a local audit file for security review.
 */
@Singleton
class AuditLogger @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)

    private val logFile: File by lazy {
        File(context.filesDir, "audit_log.txt").also {
            if (!it.exists()) it.createNewFile()
        }
    }

    fun log(action: String, input: String, result: String) {
        val timestamp = dateFormat.format(Date())
        val entry = "[$timestamp] ACTION=$action | INPUT=$input | RESULT=$result\n"
        logFile.appendText(entry)
    }

    fun getRecentLogs(count: Int = 20): List<String> {
        if (!logFile.exists()) return emptyList()
        return logFile.readLines().takeLast(count)
    }

    fun clearLogs() {
        if (logFile.exists()) {
            logFile.writeText("")
        }
    }
}
