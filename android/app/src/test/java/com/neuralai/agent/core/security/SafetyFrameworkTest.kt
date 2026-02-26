package com.neuralai.agent.core.security

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class SafetyFrameworkTest {

    private lateinit var safetyFramework: SafetyFramework

    @Before
    fun setup() {
        safetyFramework = SafetyFramework()
    }

    @Test
    fun `test hard blocked commands are rejected`() {
        val dangerousInputs = listOf(
            "factory reset my phone",
            "wipe data completely",
            "format storage now",
            "delete all contacts",
            "execute rm -rf /",
            "brick this device",
            "root device please",
            "install unknown apk",
            "disable security checks"
        )

        for (input in dangerousInputs) {
            val result = safetyFramework.evaluate(input)
            assertFalse("Input '$input' should be blocked", result.isAllowed)
            assertFalse("Input '$input' should not ask for consent, just block", result.requiresConsent)
            assertTrue("Reason should state it is blocked", result.reason.contains("Blocked"))
        }
    }

    @Test
    fun `test sensitive commands require consent`() {
        val sensitiveInputs = listOf(
            "call mom",
            "send a sms to 555-1234",
            "delete that photo",
            "uninstall facebook",
            "make a payment of 50 bucks",
            "transfer money to bob",
            "show my password"
        )

        for (input in sensitiveInputs) {
            val result = safetyFramework.evaluate(input)
            assertTrue("Input '$input' should be theoretically allowed", result.isAllowed)
            assertTrue("Input '$input' MUST require consent", result.requiresConsent)
            assertTrue("Reason should mention confirmation", result.reason.contains("explicit confirmation"))
        }
    }

    @Test
    fun `test benign commands are allowed without consent`() {
        val benignInputs = listOf(
            "what is the weather like",
            "open youtube",
            "who is the president",
            "turn on the flashlight",
            "take a picture",
            "read my screen"
        )

        for (input in benignInputs) {
            val result = safetyFramework.evaluate(input)
            assertTrue("Input '$input' should be allowed", result.isAllowed)
            assertFalse("Input '$input' should not require consent", result.requiresConsent)
            assertEquals("OK", result.reason)
        }
    }
}
