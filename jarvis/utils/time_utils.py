"""
INDRA Time Utilities -- Current time, greeting period, IST handling.
"""

from datetime import datetime, timezone, timedelta

# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def get_time_string() -> str:
    """
    Formatted time string for the system prompt and greetings.
    Example: "09:14 PM, Tuesday 14 May 2026"
    """
    t = now_ist()
    return t.strftime("%I:%M %p, %A %d %B %Y")


def get_greeting_period() -> str:
    """
    Returns 'morning', 'afternoon', or 'evening' based on IST hour.
    Morning: 5 AM – 11:59 AM
    Afternoon: 12 PM – 4:59 PM
    Evening: 5 PM – 4:59 AM
    """
    hour = now_ist().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    else:
        return "evening"


def get_formatted_greeting() -> str:
    """
    Returns the time portion of the INDRA greeting.
    Example: "Good evening, Ashish. It's 9:14 PM."
    """
    from config import USER_NAME
    period = get_greeting_period()
    t = now_ist()
    time_str = t.strftime("%I:%M %p").lstrip("0")
    return f"Good {period}, {USER_NAME}. It's {time_str}."
