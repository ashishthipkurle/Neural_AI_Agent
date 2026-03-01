package test

fun splitCompoundCommand(input: String): List<String> {
    val actionKeywords = listOf("open", "launch", "start", "send", "call", "search", "turn", "play", "close", "set", "text", "message", "tap", "type", "swipe", "scroll", "take", "install", "uninstall")
    val lower = input.lowercase()
    val andIndex = lower.indexOf(" and ")
    if (andIndex > 0) {
        val afterAnd = lower.substring(andIndex + 5).trimStart()
        val startsWithAction = actionKeywords.any { afterAnd.startsWith(it) }
        if (startsWithAction) {
            val first = input.substring(0, andIndex).trim()
            val second = input.substring(andIndex + 5).trim()
            return listOf(first) + splitCompoundCommand(second)
        }
    }
    return listOf(input)
}

fun parse(input: String): String {
    val lower = input.lowercase()
    return when {
        lower.contains("tap on") || lower.contains("click on") || lower.contains("press on") -> "TAP"
        lower.contains("type ") && (lower.contains("into") || lower.contains("in the") || lower.contains("message")) -> "TYPE_TEXT"
        (lower.contains("send") && (lower.contains("message") || lower.contains("text") || lower.contains("sms")))
            && !lower.contains("call") -> "TYPE_TEXT"
        lower.contains("swipe") -> "SWIPE"
        lower.contains("scroll") -> "SCROLL"
        lower.contains("screenshot") || lower.contains("screen shot") || lower.contains("capture screen") -> "SCREENSHOT"
        lower.contains("read screen") || lower.contains("what's on screen") || lower.contains("screen content") -> "READ_SCREEN"
        lower.contains("install") && !lower.contains("uninstall") -> "INSTALL_APP"
        lower.contains("uninstall") || lower.contains("remove app") || lower.contains("delete app") -> "UNINSTALL_APP"
        lower.contains("notification") && (lower.contains("read") || lower.contains("show") || lower.contains("check") || lower.contains("what")) -> "READ_NOTIFICATIONS"
        lower.contains("sensor") || lower.contains("accelerometer") || lower.contains("gyro") || lower.contains("proximity") -> "SENSOR_DATA"
        lower.contains("search") || lower.contains("look up") -> "WEB_SEARCH"
        lower.contains("open") || lower.contains("launch") -> "OPEN_APP"
        lower.contains("what do you see") || lower.contains("look at") || lower.contains("analyze") && lower.contains("image") -> "VISION_ANALYZE"
        lower.contains("price of") || lower.contains("buy") || lower.contains("sell") -> "TRADING"
        lower.contains("remember") || lower.contains("what did i") -> "MEMORY_RECALL"
        lower.contains("turn on") || lower.contains("volume") || lower.contains("call") || lower.contains("location") || lower.contains("where am i") -> "SYSTEM_CONTROL"
        lower.contains("notify") || lower.contains("notification") -> "SYSTEM_CONTROL"
        else -> "CHAT"
    }
}

fun main() {
    val cmd1 = "open instagram go to the reels section and start scrolling"
    val sub1 = splitCompoundCommand(cmd1)
    println("Original: $cmd1")
    sub1.forEach { println(" - Sub: $it -> ${parse(it)}") }

    val cmd2 = "open whatsapp and send hii to ashish"
    val sub2 = splitCompoundCommand(cmd2)
    println("\nOriginal: $cmd2")
    sub2.forEach { println(" - Sub: $it -> ${parse(it)}") }
    
    val cmd3 = "open chrome and tap search"
    val sub3 = splitCompoundCommand(cmd3)
    println("\nOriginal: $cmd3")
    sub3.forEach { println(" - Sub: $it -> ${parse(it)}") }
}
