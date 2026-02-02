from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

# Configure logger
logger = logging.getLogger("CodingIntentClassifier")

class CodingIntentType(Enum):
    """
    Deterministic intent types for the coding agent.
    Classification MUST strictly follow these categories without LLM guessing.
    """
    INLINE_SUGGEST = "inline_suggest"   # Autocomplete at cursor
    EXPLAIN_CODE = "explain_code"       # Explain selected code or file
    REFACTOR_FILE = "refactor_file"     # Modify/Optimize code (returns diff)
    CREATE_FILE = "create_file"         # Generate new file from scratch
    GENERAL_CHAT = "general_chat"       # Fallback for Q&A

@dataclass
class CodingContext:
    """Context information required for deterministic classification."""
    user_input: str
    active_file_path: Optional[str] = None
    file_content: Optional[str] = None
    cursor_line: Optional[int] = None
    cursor_column: Optional[int] = None
    selection: Optional[str] = None
    language_id: Optional[str] = None

@dataclass
class CodingIntent:
    """Structured intent result."""
    intent_type: CodingIntentType
    confidence: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

class CodingIntentClassifier:
    """
    Deterministic intent classifier - NO LLM INVOLVED.
    Uses regex, keyword matching, and editor context to route requests.
    """

    def __init__(self):
        self._setup_keywords()

    def _setup_keywords(self):
        # Triggers for EXPLAIN_CODE
        self.explain_keywords = [
            "explain", "what does", "how does", "why is", "help me understand", 
            "analyze this", "walkthrough", "describe"
        ]
        
        # Triggers for REFACTOR_FILE
        self.refactor_keywords = [
            "refactor", "optimize", "improve", "fix", "clean up", "format", 
            "rewrite", "modify", "update", "change", "convert", "simplify"
        ]
        
        # Triggers for CREATE_FILE
        self.create_keywords = [
            "create file", "new file", "generate file", "make a file", 
            "write a script", "scaffold", "setup project",
            "create a", "generate a", "make a new" # Broader matching
        ]

    def classify(self, context: CodingContext) -> CodingIntent:
        """
        Classifies the user intent based on input and context.
        Strictly deterministic priority:
        1. Inline Suggestion (Auto-trigger conditions)
        2. Create File (Explicit keywords)
        3. Refactor (Explicit keywords)
        4. Explain (Explicit keywords)
        5. General Chat (Fallback)
        """
        user_input_lower = context.user_input.strip().lower()

        # 1. INLINE SUGGESTION LOGIC
        # If input is empty or very short AND cursor is active in a file
        # This usually happens when the user just types code and waits
        if not user_input_lower and context.active_file_path and context.cursor_line is not None:
            return CodingIntent(
                intent_type=CodingIntentType.INLINE_SUGGEST,
                confidence=1.0,
                reasoning="Empty input with active cursor context implies autocomplete interaction.",
                parameters={
                    "file_path": context.active_file_path,
                    "line": context.cursor_line,
                    "column": context.cursor_column
                }
            )

        # 2. CREATE FILE LOGIC
        if any(k in user_input_lower for k in self.create_keywords):
            return CodingIntent(
                intent_type=CodingIntentType.CREATE_FILE,
                confidence=1.0,
                reasoning="Explicit file creation keyword detected.",
                parameters={"prompt": context.user_input}
            )

        # 3. REFACTOR / MODIFY LOGIC
        if any(k in user_input_lower for k in self.refactor_keywords):
            # Requires an active file or selection to refactor
            if context.active_file_path:
                return CodingIntent(
                    intent_type=CodingIntentType.REFACTOR_FILE,
                    confidence=1.0,
                    reasoning="Refactor/Modify keyword detected with active file context.",
                    parameters={
                        "file_path": context.active_file_path,
                        "selection": context.selection,
                        "instructions": context.user_input
                    }
                )
            else:
                 # If no file is open, we can't refactor, so fallback to chat but maybe warn
                 pass

        # 4. EXPLAIN LOGIC
        if any(k in user_input_lower for k in self.explain_keywords):
            return CodingIntent(
                intent_type=CodingIntentType.EXPLAIN_CODE,
                confidence=1.0,
                reasoning="Explanation keyword detected.",
                parameters={
                    "file_path": context.active_file_path,
                    "selection": context.selection,
                    "question": context.user_input
                }
            )

        # 5. GENERAL CHAT (Fallback)
        # If user types something that doesn't match above, treat as specific question
        return CodingIntent(
            intent_type=CodingIntentType.GENERAL_CHAT,
            confidence=0.5,
            reasoning="No specific coding keywords matched; defaulting to general chat.",
            parameters={"message": context.user_input}
        )
