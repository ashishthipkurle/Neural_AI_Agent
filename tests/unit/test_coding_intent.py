import pytest
from agent.core.coding_intent import CodingIntentClassifier, CodingContext, CodingIntentType

class TestCodingIntentClassifier:
    
    def setup_method(self):
        self.classifier = CodingIntentClassifier()

    def test_inline_suggest_when_cursor_active_no_input(self):
        """
        Verify that empty input with an active cursor triggers INLINE_SUGGEST.
        This simulates the user typing code and stopping to wait for ghost text.
        """
        context = CodingContext(
            user_input="",
            active_file_path="/path/to/script.py",
            file_content="def hello():\n    pass",
            cursor_line=1,
            cursor_column=4
        )
        intent = self.classifier.classify(context)
        
        assert intent.intent_type == CodingIntentType.INLINE_SUGGEST
        assert intent.confidence == 1.0
        assert intent.parameters["line"] == 1

    def test_explain_keywords(self):
        """Verify keywords like 'explain', 'why' trigger EXPLAIN_CODE."""
        inputs = [
            "explain this function",
            "why is this here?",
            "what does this code do",
            "help me understand this logic"
        ]
        
        for text in inputs:
            context = CodingContext(
                user_input=text,
                active_file_path="/path/to/code.js",
                selection="const x = 1;"
            )
            intent = self.classifier.classify(context)
            assert intent.intent_type == CodingIntentType.EXPLAIN_CODE, f"Failed for input: {text}"

    def test_refactor_keywords(self):
        """Verify keywords like 'refactor', 'optimize' trigger REFACTOR_FILE."""
        inputs = [
            "refactor this class",
            "optimize for performance",
            "fix the bug in this function",
            "improve readability",
            "change var to let"
        ]
        
        for text in inputs:
            context = CodingContext(
                user_input=text,
                active_file_path="/path/to/code.ts",
                selection="function bad() {}"
            )
            intent = self.classifier.classify(context)
            assert intent.intent_type == CodingIntentType.REFACTOR_FILE, f"Failed for input: {text}"
            assert intent.parameters["file_path"] == "/path/to/code.ts"

    def test_create_file_keywords(self):
        """Verify keywords like 'create file', 'new file' trigger CREATE_FILE."""
        inputs = [
            "create a new python script",
            "new file called utils.py",
            "generate a react component",
            "scaffold a new project"
        ]
        
        for text in inputs:
            context = CodingContext(
                user_input=text,
                active_file_path=None # Can create file without active file
            )
            intent = self.classifier.classify(context)
            assert intent.intent_type == CodingIntentType.CREATE_FILE, f"Failed for input: {text}"

    def test_general_chat_fallback(self):
        """Verify random inputs fallback to GENERAL_CHAT."""
        inputs = [
            "hello there",
            "what is the weather",
            "who are you"
        ]
        
        for text in inputs:
            context = CodingContext(user_input=text)
            intent = self.classifier.classify(context)
            assert intent.intent_type == CodingIntentType.GENERAL_CHAT

    def test_refactor_requires_active_file(self):
        """Verify that refactor requests without an active file fallback to GENERAL_CHAT (or appropriate handling)."""
        # In current logic, if no file is open, it falls through to general chat or explain depending on overlap
        # But specifically 'refactor' implies changing something.
        # Implemented logic: if active_file_path is None, it skips refactor block.
        
        context = CodingContext(
            user_input="refactor this",
            active_file_path=None
        )
        intent = self.classifier.classify(context)
        
        # Should probably fall back to general chat or we might want to prompt user
        assert intent.intent_type == CodingIntentType.GENERAL_CHAT

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
