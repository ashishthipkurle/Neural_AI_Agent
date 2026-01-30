"""
Tool Schema - Structured tool/function calling for LLMs.

This module defines the schema for tool calling and provides
utilities for generating tool prompts and parsing tool calls.
"""
import logging
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class ParameterType(Enum):
    """Supported parameter types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolSchema:
    """
    Schema definition for a callable tool.
    
    Follows OpenAI function calling format for compatibility.
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    requires_confirmation: bool = False
    is_destructive: bool = False
    category: str = "general"
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type.value,
                "description": param.description
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def to_prompt_string(self) -> str:
        """Convert to human-readable prompt format."""
        params_str = ", ".join(
            f"{p.name}: {p.type.value}" + (" (optional)" if not p.required else "")
            for p in self.parameters
        )
        return f"- {self.name}({params_str}): {self.description}"


@dataclass
class ToolCall:
    """Represents a parsed tool call from LLM output."""
    tool_name: str
    arguments: Dict[str, Any]
    reasoning: str = ""
    confidence: float = 1.0


class ToolRegistry:
    """
    Registry for available tools.
    
    Manages tool schemas and provides utilities for:
    - Tool registration
    - Schema generation
    - Tool prompt generation
    - Tool call parsing
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ToolRegistry")
        self._tools: Dict[str, ToolSchema] = {}
        self._handlers: Dict[str, Callable] = {}
        
        # Register default tools
        self._register_default_tools()
        
        self.logger.info("ToolRegistry initialized.")
    
    def _register_default_tools(self) -> None:
        """Register default tool schemas."""
        # Chat tool
        self.register(ToolSchema(
            name="chat_tool",
            description="Respond to the user conversationally",
            parameters=[
                ToolParameter("message", ParameterType.STRING, "The response message")
            ],
            category="communication"
        ))
        
        # File operations
        self.register(ToolSchema(
            name="read_file",
            description="Read contents of a file",
            parameters=[
                ToolParameter("path", ParameterType.STRING, "Path to the file")
            ],
            category="files"
        ))
        
        self.register(ToolSchema(
            name="write_file",
            description="Write content to a file",
            parameters=[
                ToolParameter("path", ParameterType.STRING, "Path to the file"),
                ToolParameter("content", ParameterType.STRING, "Content to write")
            ],
            requires_confirmation=True,
            is_destructive=True,
            category="files"
        ))
        
        # App control
        self.register(ToolSchema(
            name="launch_app",
            description="Launch an application",
            parameters=[
                ToolParameter("app_name", ParameterType.STRING, "Name of the application"),
                ToolParameter("extra_args", ParameterType.STRING, "Extra arguments", required=False)
            ],
            category="system"
        ))
        
        # Browser
        self.register(ToolSchema(
            name="browser_navigate",
            description="Navigate browser to a URL",
            parameters=[
                ToolParameter("url", ParameterType.STRING, "URL to navigate to")
            ],
            category="browser"
        ))
        
        # Code execution
        self.register(ToolSchema(
            name="execute_code",
            description="Execute code in a sandboxed environment",
            parameters=[
                ToolParameter("language", ParameterType.STRING, "Programming language"),
                ToolParameter("code", ParameterType.STRING, "Code to execute")
            ],
            requires_confirmation=True,
            is_destructive=True,
            category="development"
        ))
        
        # Memory
        self.register(ToolSchema(
            name="store_memory",
            description="Store information in long-term memory",
            parameters=[
                ToolParameter("text", ParameterType.STRING, "Information to remember"),
                ToolParameter("tags", ParameterType.ARRAY, "Tags for categorization", required=False)
            ],
            category="memory"
        ))
        
        self.register(ToolSchema(
            name="search_memory",
            description="Search stored memories",
            parameters=[
                ToolParameter("query", ParameterType.STRING, "Search query")
            ],
            category="memory"
        ))
        
        # Vision
        self.register(ToolSchema(
            name="capture_screen",
            description="Capture a screenshot of the current screen",
            parameters=[],
            category="vision"
        ))
        
        # Security
        self.register(ToolSchema(
            name="lock_agent",
            description="Lock the agent requiring face/PIN to unlock",
            parameters=[],
            requires_confirmation=True,
            category="security"
        ))

        # Market Analysis
        self.register(ToolSchema(
            name="analyze_chart",
            description="Analyze a stock/index chart screenshot for technical trend assessment",
            parameters=[
                ToolParameter("path", ParameterType.STRING, "Path to the chart image")
            ],
            category="analysis"
        ))

        self.register(ToolSchema(
            name="analyze_screen_chart",
            description="Capture screen and analyze any visible chart for technical trend assessment",
            parameters=[],
            category="analysis"
        ))
    
    def register(self, schema: ToolSchema, handler: Optional[Callable] = None) -> None:
        """
        Register a tool schema.
        
        Args:
            schema: Tool schema definition.
            handler: Optional callable handler for the tool.
        """
        self._tools[schema.name] = schema
        if handler:
            self._handlers[schema.name] = handler
        self.logger.debug(f"Registered tool: {schema.name}")
    
    def get(self, tool_name: str) -> Optional[ToolSchema]:
        """Get a tool schema by name."""
        return self._tools.get(tool_name)
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolSchema]:
        """
        List all registered tools.
        
        Args:
            category: Optional category filter.
        
        Returns:
            List of tool schemas.
        """
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools
    
    def get_categories(self) -> List[str]:
        """Get list of unique tool categories."""
        return list(set(t.category for t in self._tools.values()))
    
    def generate_prompt(self, include_categories: Optional[List[str]] = None) -> str:
        """
        Generate a tool prompt for LLM.
        
        Args:
            include_categories: Optional list of categories to include.
        
        Returns:
            Formatted tool prompt string.
        """
        lines = ["Available tools:"]
        
        tools = self.list_tools()
        if include_categories:
            tools = [t for t in tools if t.category in include_categories]
        
        # Group by category
        by_category: Dict[str, List[ToolSchema]] = {}
        for tool in tools:
            by_category.setdefault(tool.category, []).append(tool)
        
        for category, cat_tools in sorted(by_category.items()):
            lines.append(f"\n[{category.upper()}]")
            for tool in cat_tools:
                lines.append(tool.to_prompt_string())
        
        lines.append("\nTo use a tool, respond with JSON:")
        lines.append('{"actions": [{"action": "tool_name", "parameters": {...}}]}')
        
        return "\n".join(lines)
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI function calling format."""
        return [
            {"type": "function", "function": tool.to_openai_schema()}
            for tool in self._tools.values()
        ]
    
    def parse_tool_call(self, llm_output: str) -> List[ToolCall]:
        """
        Parse tool calls from LLM output.
        
        Args:
            llm_output: Raw LLM output string.
        
        Returns:
            List of parsed ToolCalls.
        """
        calls = []
        
        try:
            # Try to extract JSON from output
            output_clean = llm_output.strip()
            
            # Handle markdown code blocks
            if "```json" in output_clean:
                start = output_clean.index("```json") + 7
                end = output_clean.index("```", start)
                output_clean = output_clean[start:end].strip()
            elif "```" in output_clean:
                start = output_clean.index("```") + 3
                end = output_clean.index("```", start)
                output_clean = output_clean[start:end].strip()
            
            data = json.loads(output_clean)
            
            actions = data.get("actions", [])
            for action in actions:
                call = ToolCall(
                    tool_name=action.get("action", ""),
                    arguments=action.get("parameters", {}),
                    reasoning=action.get("reasoning", "")
                )
                calls.append(call)
                
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse tool call JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing tool calls: {e}")
        
        return calls
