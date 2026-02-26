package com.neuralai.agent.core

import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class IntentParserTest {

    private lateinit var intentParser: IntentParser

    @Before
    fun setup() {
        intentParser = IntentParser()
    }

    @Test
    fun `test WEB_SEARCH intent`() {
        assertEquals(Intent.WEB_SEARCH, intentParser.parse("search for the latest news"))
        assertEquals(Intent.WEB_SEARCH, intentParser.parse("look up the height of mount everest"))
    }

    @Test
    fun `test OPEN_APP intent`() {
        assertEquals(Intent.OPEN_APP, intentParser.parse("open spotify"))
        assertEquals(Intent.OPEN_APP, intentParser.parse("launch the calculator please"))
    }

    @Test
    fun `test VISION_ANALYZE intent`() {
        assertEquals(Intent.VISION_ANALYZE, intentParser.parse("what do you see on my screen"))
        assertEquals(Intent.VISION_ANALYZE, intentParser.parse("look at this picture"))
    }

    @Test
    fun `test TRADING intent`() {
        assertEquals(Intent.TRADING, intentParser.parse("what is the price of bitcoin"))
        assertEquals(Intent.TRADING, intentParser.parse("should i buy tesla stock"))
        assertEquals(Intent.TRADING, intentParser.parse("sell all my shares"))
    }

    @Test
    fun `test MEMORY_RECALL intent`() {
        assertEquals(Intent.MEMORY_RECALL, intentParser.parse("remember that my favorite color is blue"))
        assertEquals(Intent.MEMORY_RECALL, intentParser.parse("what did i tell you yesterday"))
    }

    @Test
    fun `test SYSTEM_CONTROL intent`() {
        assertEquals(Intent.SYSTEM_CONTROL, intentParser.parse("turn on bluetooth"))
        assertEquals(Intent.SYSTEM_CONTROL, intentParser.parse("increase the volume"))
    }

    @Test
    fun `test CHAT intent fallback`() {
        // Anything that doesn't match the specific keywords should fall back to CHAT
        assertEquals(Intent.CHAT, intentParser.parse("hello there!"))
        assertEquals(Intent.CHAT, intentParser.parse("tell me a joke"))
        assertEquals(Intent.CHAT, intentParser.parse("how are you doing today?"))
    }

    @Test
    fun `test case insensitivity`() {
        assertEquals(Intent.WEB_SEARCH, intentParser.parse("SEARCH for cats"))
        assertEquals(Intent.OPEN_APP, intentParser.parse("OpEn settings"))
        assertEquals(Intent.TRADING, intentParser.parse("What is the PRICE OF AAPL"))
    }
}
