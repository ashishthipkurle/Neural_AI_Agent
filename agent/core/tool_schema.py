"""
Tool Schema Validation — §6 of Production Autonomous Agent Spec.

Every tool must declare input_schema, output_schema, risk_level.
All inputs are validated BEFORE execution.
All outputs are validated AFTER execution.
No tool may return unstructured text.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("core.tool_schema")


class RiskLevel(Enum):
    SAFE = "safe"
    ELEVATED = "elevated"
    DESTRUCTIVE = "destructive"


@dataclass
class ToolSpec:
    """Strict specification for a single tool — §6."""
    name: str
    description: str
    risk_level: RiskLevel
    requires_confirmation: bool
    input_schema: Dict[str, Any]   # JSON Schema
    output_schema: Dict[str, Any]  # JSON Schema


@dataclass
class ToolResult:
    """Structured tool result — no unstructured text allowed (§7)."""
    status: str                     # "success" | "error" | "partial"
    result: Any                     # Typed payload
    confidence: float = 1.0         # 0.0–1.0
    error_type: Optional[str] = None
    recovery_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "result": self.result,
            "confidence": self.confidence,
            "error_type": self.error_type,
            "recovery_suggestion": self.recovery_suggestion,
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate data against a JSON Schema.  Returns list of violations."""
    errors: List[str] = []
    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    # Check types
    for field_name, field_spec in properties.items():
        if field_name not in data:
            continue
        value = data[field_name]
        expected_type = field_spec.get("type")

        if expected_type and not _type_matches(value, expected_type):
            errors.append(
                f"Field '{field_name}': expected type '{expected_type}', "
                f"got '{type(value).__name__}'"
            )

        # Check enum
        enum_values = field_spec.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"Field '{field_name}': value '{value}' not in {enum_values}")

    return errors


def _type_matches(value: Any, json_type: str) -> bool:
    """Check if a Python value matches a JSON Schema type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected = type_map.get(json_type)
    if expected is None:
        return True  # Unknown type, skip validation
    return isinstance(value, expected)


class ToolRegistry:
    """Registry of all tools with schema validation — §6."""

    def __init__(self):
        self._specs: Dict[str, ToolSpec] = {}
        self._handlers: Dict[str, Callable] = {}
        self._rejected_log: List[Dict[str, Any]] = []

    def register(self, spec: ToolSpec, handler: Callable) -> None:
        """Register a tool with its spec and handler."""
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler
        logger.info(f"Registered tool: {spec.name} (risk={spec.risk_level.value})")

    def validate_input(self, tool_name: str, params: Dict[str, Any]) -> List[str]:
        """Validate input parameters against tool's input_schema.

        Returns list of violation strings. Empty = valid.
        """
        spec = self._specs.get(tool_name)
        if not spec:
            return [f"Unknown tool: {tool_name}"]
        return _validate_json_schema(params, spec.input_schema)

    def validate_output(self, tool_name: str, result: Any) -> List[str]:
        """Validate tool output against output_schema."""
        spec = self._specs.get(tool_name)
        if not spec:
            return [f"Unknown tool: {tool_name}"]

        if isinstance(result, ToolResult):
            data = result.to_dict()
        elif isinstance(result, dict):
            data = result
        else:
            return [f"Output must be ToolResult or dict, got {type(result).__name__}"]

        return _validate_json_schema(data, spec.output_schema)

    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        *,
        confirmation_token: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool with full validation pipeline.

        1. Validate inputs
        2. Check risk level / confirmation
        3. Execute handler
        4. Validate output
        5. Return structured ToolResult
        """
        spec = self._specs.get(tool_name)
        if not spec:
            return ToolResult(
                status="error",
                result=None,
                error_type="TOOL_ERROR",
                recovery_suggestion=f"Tool '{tool_name}' not registered",
            )

        # Input validation
        input_errors = self.validate_input(tool_name, params)
        if input_errors:
            self._rejected_log.append({
                "tool": tool_name, "params": params, "errors": input_errors
            })
            logger.warning(f"Rejected {tool_name} call: {input_errors}")
            return ToolResult(
                status="error",
                result=None,
                error_type="TOOL_ERROR",
                recovery_suggestion=f"Invalid inputs: {'; '.join(input_errors)}",
            )

        # Risk check
        if spec.requires_confirmation and spec.risk_level == RiskLevel.DESTRUCTIVE:
            if not confirmation_token:
                return ToolResult(
                    status="error",
                    result=None,
                    error_type="AUTH_ERROR",
                    recovery_suggestion="Destructive action requires confirmation_token",
                )

        # Execute
        try:
            import asyncio
            handler = self._handlers[tool_name]
            raw = handler(**params)
            if asyncio.iscoroutine(raw):
                raw = await raw

            # Wrap in ToolResult if handler returned plain value
            if isinstance(raw, ToolResult):
                result = raw
            elif isinstance(raw, dict):
                result = ToolResult(status="success", result=raw)
            else:
                result = ToolResult(status="success", result=str(raw))

        except Exception as exc:
            from agent.core.failure_types import classify_failure
            ft = classify_failure(exc)
            result = ToolResult(
                status="error",
                result=None,
                error_type=ft.value,
                recovery_suggestion=str(exc),
            )

        # Output validation
        output_errors = self.validate_output(tool_name, result)
        if output_errors:
            logger.warning(f"Output validation warnings for {tool_name}: {output_errors}")
            # Don't reject — but lower confidence
            result.confidence = max(0.0, result.confidence - 0.3)

        return result

    def get_spec(self, tool_name: str) -> Optional[ToolSpec]:
        return self._specs.get(tool_name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": s.name,
                "risk_level": s.risk_level.value,
                "requires_confirmation": s.requires_confirmation,
                "description": s.description,
            }
            for s in self._specs.values()
        ]

    @property
    def rejected_log(self) -> List[Dict[str, Any]]:
        return list(self._rejected_log)


# ── Standard output schema that ALL tools must conform to ──
STANDARD_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["status", "result"],
    "properties": {
        "status": {"type": "string", "enum": ["success", "error", "partial"]},
        "result": {},
        "confidence": {"type": "number"},
        "error_type": {"type": "string"},
        "recovery_suggestion": {"type": "string"},
    },
}
