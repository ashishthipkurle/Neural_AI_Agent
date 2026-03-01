package com.neuralai.agent.core.skills.phone

import android.content.Context
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.provider.ContactsContract
import android.provider.CallLog
import android.telephony.SmsManager
import com.neuralai.agent.services.AccessibilityControlService
import com.neuralai.agent.services.WakeWordService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

data class ContactInfo(
    val name: String,
    val phoneNumber: String
)

data class CallLogEntry(
    val number: String,
    val type: String,
    val date: Long,
    val duration: Long
)

@Singleton
class PhoneSkill @Inject constructor(
    @ApplicationContext private val context: Context
) {

    /**
     * Send an SMS to a given phone number.
     */
    fun sendSMS(number: String, message: String): Boolean {
        return try {
            val smsManager = SmsManager.getDefault()
            smsManager.sendTextMessage(number, null, message, null, null)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Initiate a phone call. routes through Foreground Service to bypass Android 10 restrictions.
     */
    fun makeCall(number: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            val wakeService = WakeWordService.instance.value
            val accService = AccessibilityControlService.instance.value
            when {
                wakeService != null -> wakeService.startActivity(intent)
                accService != null -> accService.startActivity(intent)
                else -> context.startActivity(intent)
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Open WhatsApp directly to a specific contact with an optional pre-filled message.
     */
    fun openWhatsAppChat(phoneNumber: String, message: String): Boolean {
        val cleanNumber = phoneNumber.replace("+", "").replace(Regex("\\s+"), "")
        return try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                // Use direct whatsapp:// scheme to bypass browser redirect, which makes the timing predictable
                data = Uri.parse("whatsapp://send?phone=$cleanNumber&text=${Uri.encode(message)}")
                setPackage("com.whatsapp")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
            val wakeService = WakeWordService.instance.value
            val accService = AccessibilityControlService.instance.value
            when {
                wakeService != null -> wakeService.startActivity(intent)
                accService != null -> accService.startActivity(intent)
                else -> context.startActivity(intent)
            }
            
            // Wait for WhatsApp to open and load the chat, then click Send
            CoroutineScope(Dispatchers.IO).launch {
                delay(1500) // Give WhatsApp time to open (much faster now with direct scheme)
                
                // Retry tapping "Send" up to 3 times
                for (i in 0 until 3) {
                    val tapped = accService?.tapElement("Send") == true
                    if (tapped) break
                    delay(1000)
                }
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Search contacts by name query.
     */
    fun readContacts(query: String): List<ContactInfo> {
        val contacts = mutableListOf<ContactInfo>()
        val cursor: Cursor? = context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
            ),
            "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?",
            arrayOf("%$query%"),
            null
        )

        cursor?.use {
            val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numberIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (it.moveToNext()) {
                contacts.add(
                    ContactInfo(
                        name = it.getString(nameIdx) ?: "",
                        phoneNumber = it.getString(numberIdx) ?: ""
                    )
                )
            }
        }
        return contacts
    }

    /**
     * Get the most recent call log entries.
     */
    fun getRecentCalls(limit: Int = 10): List<CallLogEntry> {
        val calls = mutableListOf<CallLogEntry>()
        val cursor: Cursor? = context.contentResolver.query(
            CallLog.Calls.CONTENT_URI,
            arrayOf(
                CallLog.Calls.NUMBER,
                CallLog.Calls.TYPE,
                CallLog.Calls.DATE,
                CallLog.Calls.DURATION
            ),
            null, null,
            "${CallLog.Calls.DATE} DESC"
        )

        cursor?.use {
            val numberIdx = it.getColumnIndex(CallLog.Calls.NUMBER)
            val typeIdx = it.getColumnIndex(CallLog.Calls.TYPE)
            val dateIdx = it.getColumnIndex(CallLog.Calls.DATE)
            val durationIdx = it.getColumnIndex(CallLog.Calls.DURATION)
            
            var count = 0
            while (it.moveToNext() && count < limit) {
                val typeInt = it.getInt(typeIdx)
                val typeStr = when (typeInt) {
                    CallLog.Calls.INCOMING_TYPE -> "Incoming"
                    CallLog.Calls.OUTGOING_TYPE -> "Outgoing"
                    CallLog.Calls.MISSED_TYPE -> "Missed"
                    else -> "Unknown"
                }
                calls.add(
                    CallLogEntry(
                        number = it.getString(numberIdx) ?: "",
                        type = typeStr,
                        date = it.getLong(dateIdx),
                        duration = it.getLong(durationIdx)
                    )
                )
                count++
            }
        }
        return calls
    }
}
