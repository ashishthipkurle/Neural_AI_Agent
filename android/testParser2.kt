package test

fun splitCompound(input: String): List<String> {
    val actionKeywords = listOf("open", "launch", "start", "send", "call", "search", "turn", "play", "close", "set", "text", "message", "tap", "type", "swipe", "scroll", "take", "install", "uninstall", "click", "go to")
    val lower = input.lowercase()
    
    val delimiters = listOf(" and ", " then ", ", ", " go to ")
    
    var earliestDelim: String? = null
    var earliestIndex = Int.MAX_VALUE
    
    for (delim in delimiters) {
        val delimIndex = lower.indexOf(delim)
        // Ensure the delimiter isn't at the very beginning (0) and is the earliest found
        if (delimIndex in 1 until earliestIndex) {
            var afterDelim = lower.substring(delimIndex + delim.length).trimStart()
            if (delim == " go to ") {
                afterDelim = "go to $afterDelim"
            }
            
            // Check if what follows the delimiter looks like a fresh action
            val startsWithAction = actionKeywords.any { afterDelim.startsWith(it) } || delim == " go to "
            
            if (startsWithAction) {
                earliestIndex = delimIndex
                earliestDelim = delim
            }
        }
    }
    
    if (earliestDelim != null) {
        val first = input.substring(0, earliestIndex).trim()
        val second = input.substring(earliestIndex + earliestDelim.length).trim()
        val secondToParse = if (earliestDelim == " go to ") "go to $second" else second
        return listOf(first) + splitCompound(secondToParse)
    }
    
    return listOf(input)
}

fun extractDurationMs(input: String): Long {
    // We want to catch "for 1 min", "for 1min", "for 1 seconds", "for 30sec" etc.
    // The optional space is \\s*
    val durationMatch = Regex("for\\s+(\\d+)\\s*(minute|minutes|second|seconds|min|mins|sec|secs)").find(input)
    if (durationMatch != null) {
        val amount = durationMatch.groupValues[1].toLongOrNull() ?: 1L
        val unit = durationMatch.groupValues[2]
        return when {
            unit.startsWith("min") -> amount * 60 * 1000L
            unit.startsWith("sec") -> amount * 1000L
            else -> 0L
        }
    }
    return 0L
}

fun main() {
    val prompts = listOf(
        "open youtube and start scrolling for 1min",
        "open instagram go to reels section and start scrolling",
        "turn on location then open maps and type neural ai in search",
        "open whatsapp and send hii to ashish",
        "message anuj on whatsapp say i am busy then close app",
        "scroll down for 30secs and take screenshot"
    )
    
    for (prompt in prompts) {
        println("\nPrompt: \"$prompt\"")
        val splits = splitCompound(prompt)
        splits.forEach {
            println(" -> Command: '$it' (Duration MS: ${extractDurationMs(it)})")
        }
        println("--------------------------------------------------")
    }
}
