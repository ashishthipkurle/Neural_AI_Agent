import os

input_files = [
    r"d:\All Projects\My AI Agent\android_commands_1.txt",
    r"d:\All Projects\My AI Agent\android_commands_2.txt",
    r"d:\All Projects\My AI Agent\android_commands_3.txt",
    r"d:\All Projects\My AI Agent\android_commands_4.txt",
    r"d:\All Projects\My AI Agent\android_commands_5.txt"
]

commands = []
current_category = "UNKNOWN"

for fpath in input_files:
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith('## '):
                    current_category = line.replace('## ', '').strip()
                elif line.startswith('- "') and '"' in line[3:]:
                    cmd = line[3:].split('"')[0]
                    commands.append((current_category, cmd))

def map_to_intent(category, cmd):
    cat_lower = category.lower()
    cmd_lower = cmd.lower()
    
    # ── HIGHEST PRIORITY: INTENT KEYWORDS IN COMMAND ──
    if cmd_lower.startswith("turn on") or cmd_lower.startswith("turn off") or cmd_lower.startswith("toggle") or cmd_lower.startswith("enable") or cmd_lower.startswith("disable"):
        if "flashlight" in cmd_lower or "torch" in cmd_lower or "wifi" in cmd_lower or "wi-fi" in cmd_lower or "bluetooth" in cmd_lower or "airplane" in cmd_lower or "hotspot" in cmd_lower or "nfc" in cmd_lower or "vpn" in cmd_lower or "do not disturb" in cmd_lower or "battery saver" in cmd_lower or "low power" in cmd_lower: return "Intent.TOGGLE_SETTING"
        if "light" in cmd_lower or "lamp" in cmd_lower or "tv" in cmd_lower or "heater" in cmd_lower or "ac" in cmd_lower or "fan" in cmd_lower: return "Intent.SYSTEM_CONTROL"
    
    if cmd_lower.startswith("open ") or cmd_lower.startswith("launch ") or cmd_lower.startswith("start "):
        if "camera" in cmd_lower or "record" in cmd_lower: return "Intent.TAKE_PHOTO"
        if "stopwatch" in cmd_lower or "timer" in cmd_lower or "workout" in cmd_lower: return "Intent.ALARM_TIMER"
        return "Intent.OPEN_APP"
        
    if cmd_lower.startswith("close ") or cmd_lower.startswith("force close ") or cmd_lower.startswith("force stop ") or cmd_lower.startswith("exit "): return "Intent.CLOSE_APP"
    if cmd_lower.startswith("call ") or cmd_lower.startswith("dial ") or cmd_lower.startswith("facetime "): return "Intent.SYSTEM_CONTROL"
    if "volume" in cmd_lower or "mute" in cmd_lower or "silent" in cmd_lower or "loud" in cmd_lower: return "Intent.VOLUME_CONTROL"
    if "bright" in cmd_lower or "dim " in cmd_lower: return "Intent.BRIGHTNESS"
    if "screenshot" in cmd_lower or "record screen" in cmd_lower or "capture screen" in cmd_lower: return "Intent.SCREENSHOT"
    if cmd_lower.startswith("play ") or cmd_lower.startswith("pause") or cmd_lower.startswith("resume") or cmd_lower.startswith("stop the music"): return "Intent.MEDIA_CONTROL"
    if "next song" in cmd_lower or "previous song" in cmd_lower or "skip" in cmd_lower or "rewind" in cmd_lower or "fast forward" in cmd_lower: return "Intent.MEDIA_CONTROL"
    if "take a photo" in cmd_lower or "take a picture" in cmd_lower or "take a selfie" in cmd_lower or "record a video" in cmd_lower: return "Intent.TAKE_PHOTO"
    if cmd_lower.startswith("search ") or "google " in cmd_lower: return "Intent.WEB_SEARCH"
    if "send a text" in cmd_lower or cmd_lower.startswith("text ") or cmd_lower.startswith("message ") or cmd_lower.startswith("reply"): return "Intent.TYPE_TEXT"
    if cmd_lower.startswith("write ") or cmd_lower.startswith("compose "): return "Intent.TYPE_TEXT"
    if "alarm" in cmd_lower or "timer" in cmd_lower or "wake me up" in cmd_lower or "snooze" in cmd_lower: return "Intent.ALARM_TIMER"
    if cmd_lower.startswith("remind "): return "Intent.ALARM_TIMER"
    if cmd_lower.startswith("share"): return "Intent.SHARE"
    if cmd_lower.startswith("scroll "): return "Intent.SCROLL"
    if cmd_lower.startswith("swipe "): return "Intent.SWIPE"
    if "go back" in cmd_lower: return "Intent.GO_BACK"
    if "go home" in cmd_lower: return "Intent.GO_HOME"
    
    # ── CATEGORY FALLBACKS ──
    if "flashlight" in cat_lower: return "Intent.TOGGLE_SETTING"
    if "screen & display" in cat_lower: 
        if "screenshot" in cmd_lower or "record" in cmd_lower: return "Intent.SCREENSHOT"
        if "brightness" in cmd_lower or "dim" in cmd_lower: return "Intent.BRIGHTNESS"
        return "Intent.SYSTEM_CONTROL"
    if "volume & sound" in cat_lower: return "Intent.VOLUME_CONTROL"
    if "battery & power" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "connectivity" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "alarms" in cat_lower or "timers" in cat_lower or "reminders" in cat_lower: return "Intent.ALARM_TIMER"
    if "clock & date" in cat_lower: return "Intent.CHAT"
    if "calendar & scheduling" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "email" in cat_lower:
        if "read" in cmd_lower or "show" in cmd_lower: return "Intent.READ_NOTIFICATIONS"
        return "Intent.TYPE_TEXT"
    if "messaging & sms" in cat_lower: 
        if "read" in cmd_lower or "show" in cmd_lower: return "Intent.READ_NOTIFICATIONS"
        return "Intent.TYPE_TEXT"
    if "phone calls" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "web browsing" in cat_lower or "search & information" in cat_lower: return "Intent.WEB_SEARCH"
    if "maps & navigation" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "music" in cat_lower or "podcasts" in cat_lower or "video" in cat_lower: return "Intent.MEDIA_CONTROL"
    if "files" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "notes" in cat_lower: return "Intent.TYPE_TEXT"
    if "calculations" in cat_lower: return "Intent.CHAT"
    if "shopping" in cat_lower: return "Intent.WEB_SEARCH"
    if "finance" in cat_lower: return "Intent.CHAT"
    if "smart home" in cat_lower: return "Intent.CHAT"
    if "weather" in cat_lower: return "Intent.CHAT"
    if "camera" in cat_lower: return "Intent.TAKE_PHOTO"
    if "health" in cat_lower: return "Intent.CHAT"
    if "contacts" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "social media" in cat_lower: return "Intent.TYPE_TEXT"
    if "security" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "apps" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "education" in cat_lower or "work" in cat_lower or "creation" in cat_lower or "travel" in cat_lower or "food" in cat_lower or "wellness" in cat_lower or "gaming" in cat_lower or "language" in cat_lower: return "Intent.CHAT"
    if "emergency" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "printing" in cat_lower: return "Intent.SYSTEM_CONTROL"
    if "automation" in cat_lower: return "Intent.SYSTEM_CONTROL"
    
    return "Intent.CHAT"

kt_lines = []
kt_lines.append("package com.neuralai.agent.core")
kt_lines.append("")
kt_lines.append("/**")
kt_lines.append(" * Ultra-Complete Voice Command Bible for Android Agent")
kt_lines.append(" * Autogenerated mapping of literal phrases to intents.")
kt_lines.append(" */")
kt_lines.append("object AndroidCommandRegistry {")
kt_lines.append("    val COMMANDS: Map<String, Intent> = mapOf(")

seen = set()
for cat, cmd in commands:
    cmd_lower = cmd.lower()
    if cmd_lower in seen:
        continue
    seen.add(cmd_lower)
    
    intent = map_to_intent(cat, cmd)
    escaped_cmd = cmd_lower.replace('"', '\\"')
    kt_lines.append(f'        "{escaped_cmd}" to {intent},')

kt_lines.append("    )")
kt_lines.append("}")

kt_code = "\n".join(kt_lines)

out_path = r"d:\All Projects\My AI Agent\android\app\src\main\java\com\neuralai\agent\core\AndroidCommandRegistry.kt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(kt_code)

print(f"Generated {out_path} with {len(seen)} commands.")
