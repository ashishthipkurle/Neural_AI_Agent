import logging
import math

class MathTools:
    def __init__(self):
        self.logger = logging.getLogger("MathTools")

    def calculate(self, expression: str) -> str:
        """
        Evaluates a mathematical expression safely.
        Uses a restricted environment for eval().
        """
        allowed_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("__")
        }
        # clean input
        expression = expression.replace('^', '**')
        
        try:
            # Dangerous: eval is generally bad, but with restricted globals it's safer.
            # In production, use AST parsing or libraries like numexpr.
            # For this phase, we use restricted eval.
            result = eval(expression, {"__builtins__": None}, allowed_names)
            return f"Result: {result}"
        except Exception as e:
            return f"Error calculating: {e}"
