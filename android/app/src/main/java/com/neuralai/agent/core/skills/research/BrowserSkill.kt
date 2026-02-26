package com.neuralai.agent.core.skills.research

import android.content.Context
import android.content.Intent
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class BrowserSkill @Inject constructor(
    @ApplicationContext private val context: Context
) {
    /**
     * Launch a URL in the user's default browser or Chrome natively.
     */
    fun openUrl(url: String): Boolean {
        return try {
            val parsedUrl = if (!url.startsWith("http://") && !url.startsWith("https://")) {
                "https://$url"
            } else {
                url
            }
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(parsedUrl)).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }
}
