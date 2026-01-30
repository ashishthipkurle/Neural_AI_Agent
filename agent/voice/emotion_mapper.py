
class EmotionMapper:
    """
    Maps intents and system states to emotional tags for TTS.
    """
    
    EMOTION_MAP = {
        "greeting": "happy",
        "welcome": "warm",
        "confirmation": "calm",
        "success": "happy",
        "error": "concerned",
        "warning": "serious",
        "alert": "urgent",
        "thinking": "neutral",
        "neutral": "neutral"
    }

    @staticmethod
    def get_emotion(intent_name: str, text: str) -> str:
        """
        Determine emotion based on intent name or keywords in text.
        """
        intent = intent_name.lower()
        
        # Check explicit intent mapping
        if intent in EmotionMapper.EMOTION_MAP:
            return EmotionMapper.EMOTION_MAP[intent]
            
        # Check text keywords if intent is generic (like 'chat')
        text_lower = text.lower()
        if "sorry" in text_lower or "apologize" in text_lower or "error" in text_lower:
            return "concerned"
        if "great" in text_lower or "congratulations" in text_lower:
            return "happy"
        if "warning" in text_lower or "careful" in text_lower:
            return "serious"
            
        return "neutral"
