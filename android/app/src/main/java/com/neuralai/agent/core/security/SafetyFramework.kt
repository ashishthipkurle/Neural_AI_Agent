package com.neuralai.agent.core.security

import javax.inject.Inject
import javax.inject.Singleton

/**
 * Blocks dangerous commands before they ever reach skill execution.
 */
@Singleton
class SafetyFramework @Inject constructor() {

    private val blockedPatterns = listOf(
        "factory reset",
        "wipe data",
        "format storage",
        "delete all",
        "rm -rf",
        "brick",
        "root device",
        "install unknown",
        "disable security"
    )

    private val sensitivePatterns = listOf(
        "call", "sms", "send message", "text",
        "delete", "remove", "uninstall",
        "payment", "transfer", "money",
        "password", "credential"
    )

    data class SafetyResult(
        val isAllowed: Boolean,
        val requiresConsent: Boolean,
        val reason: String
    )

    fun evaluate(input: String): SafetyResult {
        val lower = input.lowercase()

        // Hard block
        for (pattern in blockedPatterns) {
            if (lower.contains(pattern)) {
                return SafetyResult(
                    isAllowed = false,
                    requiresConsent = false,
                    reason = "Blocked: '$pattern' is a prohibited action."
                )
            }
        }

        // Consent required
        for (pattern in sensitivePatterns) {
            if (lower.contains(pattern)) {
                return SafetyResult(
                    isAllowed = true,
                    requiresConsent = true,
                    reason = "This action ('$pattern') requires your explicit confirmation."
                )
            }
        }

        // Safe
        return SafetyResult(
            isAllowed = true,
            requiresConsent = false,
            reason = "OK"
        )
    }
}
