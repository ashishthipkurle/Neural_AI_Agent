"""
LangGraph Tool Wrappers — thin @tool facades over existing skill execute() methods.

Each function delegates to the corresponding *already-initialised* skill
instance obtained from the SkillRouter at graph build time.  This keeps all
battle-tested skill logic untouched.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any, Dict, Optional

from langchain_core.tools import tool

logger = logging.getLogger("graph.tools")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# These module-level holders are populated by ``register_skills()`` at startup
# ---------------------------------------------------------------------------
_skills: Dict[str, Any] = {}
_tool_router: Any = None


def register_skills(skill_router: Any, tool_router: Any) -> None:
    """Called once during LangGraphRuntime init to capture live skill instances."""
    global _skills, _tool_router
    _tool_router = tool_router

    if skill_router:
        # SkillRouter.skills property returns skill_loader.get_all() → Dict[str, BaseSkill]
        if hasattr(skill_router, "skills"):
            for name, instance in skill_router.skills.items():
                _skills[name] = instance
        elif hasattr(skill_router, "skill_loader"):
            for name, instance in skill_router.skill_loader.get_all().items():
                _skills[name] = instance
        logger.info(f"Registered {len(_skills)} skills: {list(_skills.keys())}")


def _run_coroutine_sync(coro):
    """Safely run a coroutine from sync context, even inside a running loop."""
    try:
        loop = asyncio.get_running_loop()
        # Already inside an async context — run in a new thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=120)
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)


def _run_skill(skill_name: str, action: str, params: dict, context: dict | None = None) -> str:
    """Execute a skill action — handles both sync and async execute()."""
    skill = _skills.get(skill_name)
    if not skill:
        return f"Error: skill '{skill_name}' not loaded"

    try:
        result = skill.execute(action, params, context)
        # Handle coroutine if execute is async
        if asyncio.iscoroutine(result):
            result = _run_coroutine_sync(result)
        
        if hasattr(result, "message"):
            # Surface errors from failed skill results
            if hasattr(result, "success") and not result.success and hasattr(result, "error") and result.error:
                return f"Error: {result.error}"
            msg = result.message
            if not msg and result.data:
                msg = str(result.data)
            if not msg and result.success:
                msg = "Action completed successfully (no text output)"
            return msg or str(result)
            
        return str(result)
    except Exception as exc:
        logger.error(f"Skill {skill_name}.{action} failed: {exc}")
        return f"Error: {exc}"


# =========================================================================
# @tool definitions — each wraps one skill's primary action
# =========================================================================

@tool
def browser_tool(action: str, url: str = "", query: str = "", message: str = "") -> str:
    """Browse the web: navigate to URLs, search, read pages, send messages on web apps.
    
    Args:
        action: One of navigate, search, read_page, send_message, chat_on_site.
        url: Target URL for navigation.
        query: Search query or message text.
        message: Message to type/send on a web page.
    """
    params = {"url": url, "query": query, "message": message}
    return _run_skill("browser", action, {k: v for k, v in params.items() if v})


@tool
def desktop_tool(action: str, app_name: str = "", text: str = "", key: str = "") -> str:
    """Control the desktop OS: launch apps, type text, press keys, move/click mouse.
    
    Args:
        action: One of launch_app, type_text, press_key, click, screenshot.
        app_name: Application to launch.
        text: Text to type.
        key: Key to press (e.g. enter, tab, escape).
    """
    params = {"app_name": app_name, "text": text, "key": key}
    return _run_skill("desktop", action, {k: v for k, v in params.items() if v})


@tool
def research_tool(query: str, depth: str = "normal") -> str:
    """Search the web for information and return a research summary.
    
    Args:
        query: Research topic or question.
        depth: Research depth (normal or deep).
    """
    return _run_skill("research", "deep_research", {"query": query, "topic": query, "depth": depth})


@tool
def coding_tool(action: str, code: str = "", language: str = "python", path: str = "") -> str:
    """Write, edit, or execute code.
    
    Args:
        action: One of write_code, edit_code, execute_code, run_command.
        code: The code content or command to run.
        language: Programming language (python, shell, etc.).
        path: File path for read/write operations.
    """
    params = {"code": code, "language": language, "path": path}
    
    # Map actions to skills/coding/skill.py capabilities
    if action in ("write_code", "edit_code"):
        action = "write_file"
        params["content"] = code  # Map 'code' arg to 'content' for write_file
    
    elif action == "execute_code":
        action = "run_command"
        lang = language.lower() if language else "python"
        # If python file exists at path, run it
        if lang == "python" and path and not code:
             params["command"] = f"python \"{path}\""
        # If python code provided, write to temp file and run
        elif lang == "python" and code:
             import tempfile
             tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
             tmp.write(code)
             tmp.close()
             run_path = path or tmp.name
             if path:
                 # Write code to specified path
                 os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                 with open(path, "w", encoding="utf-8") as f:
                     f.write(code)
                 run_path = path
             params["command"] = f"python \"{run_path}\""
        # Shell command
        elif code:
             params["command"] = code
        else:
             return "Error: execute_code requires 'code' or 'path'"

    return _run_skill("coding", action, {k: v for k, v in params.items() if v})


@tool
def memory_tool(action: str, content: str = "", query: str = "") -> str:
    """Store or search the agent's long-term memory.
    
    Args:
        action: One of store, search, recall.
        content: Content to store in memory.
        query: Search query to recall from memory.
    """
    params = {"content": content, "query": query}
    return _run_skill("memory", action, {k: v for k, v in params.items() if v})


@tool
def telegram_tool(action: str, message: str = "", chat_id: str = "") -> str:
    """Send or check Telegram messages.
    
    Args:
        action: One of send_message, check_messages.
        message: Message text to send.
        chat_id: Target chat/group ID.
    """
    params = {"message": message, "chat_id": chat_id}
    return _run_skill("telegram", action, {k: v for k, v in params.items() if v})


@tool
def voice_tool(action: str, text: str = "") -> str:
    """Text-to-speech and voice control.
    
    Args:
        action: One of speak, stop_speaking.
        text: Text to speak aloud.
    """
    return _run_skill("voice", action, {"text": text})


@tool
def vision_tool(action: str, image_data: str = "", question: str = "", path: str = "", text: str = "") -> str:
    """Analyze images or the screen using computer vision.
    
    Args:
        action: One of screenshot, analyze, ocr, detect_elements, find_text, compare, read_popup.
        image_data: Base64-encoded image data (optional — captures screen if empty).
        question: Question to ask about what's on screen (for analyze action).
        path: File path for screenshot output or image input.
        text: Text to search for on screen (for find_text action).
    """
    # Map common LLM aliases to actual skill action names
    action_map = {
        "analyze_screen": "analyze",
        "describe_image": "analyze",
        "detect_objects": "detect_elements",
        "capture_screen": "screenshot",
        "capture": "screenshot",
        "extract_text": "ocr",
        "read_text": "ocr",
    }
    action = action_map.get(action, action)
    
    params = {}
    if image_data:
        params["image_data"] = image_data
    if question:
        params["question"] = question
    if path:
        params["path"] = path
    if text:
        params["text"] = text
    
    return _run_skill("vision", action, params)


@tool
def file_ops_tool(action: str, path: str, content: Any = "") -> str:
    """Read, write, list, or create files and directories on the local filesystem.
    
    Args:
        action: One of read_file, write_file, list_dir, create_dir, delete_path.
        path: File or directory path.
        content: File content for write operations (string or dict/list for JSON).
    """
    import shutil

    # Ensure content is a string
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    elif content and not isinstance(content, str):
        content = str(content)

    # Ensure path is absolute
    if path and not os.path.isabs(path):
        workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(workspace, path)

    # ── list_dir ──
    if action in ("list_dir", "ls"):
        try:
            if not os.path.isdir(path):
                return f"Error: '{path}' is not a directory"
            entries = os.listdir(path)
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as exc:
            return f"Error listing '{path}': {exc}"

    # ── create_dir ──
    if action in ("create_dir", "mkdir", "makedirs"):
        try:
            os.makedirs(path, exist_ok=True)
            return f"Directory created: {path}"
        except Exception as exc:
            return f"Error creating directory '{path}': {exc}"

    # ── write_file ──
    if action in ("write_file", "write", "set"):
        try:
            # Ensure parent directory exists
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            logger.info(f"Wrote {len(content or '')} chars to {path}")
            return f"Successfully wrote to {path}"
        except Exception as exc:
            return f"Error writing '{path}': {exc}"

    # ── read_file ──
    if action in ("read_file", "read", "get"):
        try:
            if not os.path.isfile(path):
                return f"Error: File not found: {path}"
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            return data[:4000] if len(data) > 4000 else data
        except Exception as exc:
            return f"Error reading file: {exc}"

    # ── delete_path ──
    if action in ("delete_path", "delete", "remove"):
        try:
            if os.path.isfile(path):
                os.remove(path)
                return f"Deleted file: {path}"
            elif os.path.isdir(path):
                shutil.rmtree(path)
                return f"Deleted directory: {path}"
            else:
                return f"Error: Path not found: {path}"
        except Exception as exc:
            return f"Error deleting '{path}': {exc}"

    # ── search (find files by name pattern) ──
    if action in ("search", "find", "find_file"):
        try:
            search_term = content or os.path.basename(path) if path else ""
            search_root = path if os.path.isdir(path) else os.path.dirname(path) or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            matches = []
            for root, dirs, files in os.walk(search_root):
                # Skip hidden and common ignore dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git')]
                for name in files + dirs:
                    if search_term.lower() in name.lower():
                        matches.append(os.path.join(root, name))
                if len(matches) >= 20:
                    break
            if matches:
                return "Found:\n" + "\n".join(matches[:20])
            return f"No files matching '{search_term}' found in {search_root}"
        except Exception as exc:
            return f"Error searching: {exc}"

    # ── exists (check if path exists) ──
    if action in ("exists", "check", "stat"):
        if os.path.isfile(path):
            size = os.path.getsize(path)
            return f"FILE exists: {path} ({size} bytes)"
        elif os.path.isdir(path):
            entries = len(os.listdir(path))
            return f"DIRECTORY exists: {path} ({entries} entries)"
        else:
            return f"NOT FOUND: {path}"

    return f"Error: unknown file action '{action}'. Use: read_file, write_file, list_dir, create_dir, delete_path, search, exists"


@tool
def system_tool(action: str, app_name: str = "", expression: str = "") -> str:
    """Launch apps, calculate math, or control OS settings.
    
    Args:
        action: One of launch_app, calculate, system_info.
        app_name: Application name to launch.
        expression: Math expression to evaluate.
    """
    if not _tool_router:
        return "Error: ToolRouter not available"

    handler = _tool_router.tools.get(action)
    if handler:
        try:
            kwargs = {}
            if app_name:
                kwargs["app_name"] = app_name
            if expression:
                kwargs["expression"] = expression
            result = handler(**kwargs) if kwargs else handler()
            if asyncio.iscoroutine(result):
                result = _run_coroutine_sync(result)
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"
    return f"Error: unknown system action '{action}'"


# =========================================================================
# LTM + Knowledge Graph tools — direct access to §5 memory systems
# =========================================================================

@tool
def ltm_tool(action: str, key: str = "", value: Any = "", category: str = "general", query: str = "") -> str:
    """Store or retrieve from Long-Term Memory (versioned, persistent database).

    Args:
        action: One of store, retrieve, search.
        key: Memory key (required for store and retrieve).
        value: Content to store (required for store). Can be a string or JSON object.
        category: Memory category (default: general).
        query: Search keyword (required for search).
    """
    try:
        from agent.memory.ltm import VersionedLTM
        ltm = VersionedLTM()

        if action == "store":
            if not key or not value:
                return "Error: ltm_tool store requires key and value"
            # Auto-serialize dict/list values to JSON string
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            else:
                value = str(value)
            result = ltm.store(key=key, value=value, category=category)
            return json.dumps(result)

        elif action == "retrieve":
            if not key:
                return "Error: ltm_tool retrieve requires key"
            val = ltm.retrieve(key)
            if val is None:
                return f"No LTM entry found for key '{key}'"
            return val

        elif action == "search":
            if not query:
                return "Error: ltm_tool search requires query"
            results = ltm.search(query, category=category if category != "general" else None)
            if not results:
                return f"No LTM entries matching '{query}'"
            return json.dumps(results, indent=2)

        else:
            return f"Error: unknown ltm_tool action '{action}'. Use store, retrieve, or search."
    except Exception as e:
        logger.error(f"ltm_tool.{action} failed: {e}")
        return f"Error: {e}"


@tool
def kg_tool(action: str, entity_id: str = "", entity_type: str = "", name: str = "",
            source: str = "", target: str = "", relation_type: str = "",
            query: str = "") -> str:
    """Add entities and relations to the Knowledge Graph, or query it.

    Args:
        action: One of add_entity, add_relation, get_entity, find_entities, stats.
        entity_id: Entity identifier (for add_entity, get_entity).
        entity_type: Entity type string (for add_entity, find_entities).
        name: Entity display name (for add_entity).
        source: Source entity ID (for add_relation).
        target: Target entity ID (for add_relation).
        relation_type: Relation type string (for add_relation).
        query: Name substring filter (for find_entities).
    """
    try:
        from agent.memory.knowledge_graph import KnowledgeGraph
        import os
        kg_path = os.path.join(WORKSPACE_ROOT, "agent_data", "knowledge_graph.json")
        kg = KnowledgeGraph(path=kg_path)

        if action == "add_entity":
            if not entity_id or not entity_type or not name:
                return "Error: add_entity requires entity_id, entity_type, and name"
            is_new = kg.add_entity(entity_id=entity_id, entity_type=entity_type, name=name)
            return f"Entity '{entity_id}' {'created' if is_new else 'updated'}"

        elif action == "add_relation":
            if not source or not target or not relation_type:
                return "Error: add_relation requires source, target, and relation_type"
            # Check entities exist FIRST to give correct error
            if kg.get_entity(source) is None or kg.get_entity(target) is None:
                missing = []
                if kg.get_entity(source) is None:
                    missing.append(source)
                if kg.get_entity(target) is None:
                    missing.append(target)
                return f"Relation failed: entities not found: {', '.join(missing)}. Create them with add_entity first."
            ok = kg.add_relation(source=source, target=target, relation_type=relation_type)
            if ok:
                return f"Relation added: {source} --[{relation_type}]--> {target}"
            return f"Relation already exists: {source} --[{relation_type}]--> {target} (no change needed, move on)"

        elif action == "get_entity":
            if not entity_id:
                return "Error: get_entity requires entity_id"
            entity = kg.get_entity(entity_id)
            if entity is None:
                return f"Entity '{entity_id}' not found"
            return json.dumps(entity, indent=2, default=str)

        elif action == "find_entities":
            results = kg.find_entities(
                entity_type=entity_type or None,
                name_contains=query or None,
            )
            if not results:
                return "No entities found"
            return json.dumps(results, indent=2, default=str)

        elif action == "stats":
            s = kg.stats()
            return json.dumps(s)

        else:
            return f"Error: unknown kg_tool action '{action}'. Use add_entity, add_relation, get_entity, find_entities, or stats."
    except Exception as e:
        logger.error(f"kg_tool.{action} failed: {e}")
        return f"Error: {e}"


# =========================================================================
# Public list for bind_tools()
# =========================================================================
ALL_TOOLS = [
    browser_tool,
    desktop_tool,
    research_tool,
    coding_tool,
    memory_tool,
    ltm_tool,
    kg_tool,
    telegram_tool,
    voice_tool,
    vision_tool,
    file_ops_tool,
    system_tool,
]
