"""Quick verification of all 6 fixes."""
import sys
sys.path.insert(0, ".")

# Test 1: Import everything
from agent.graph.nodes.coder import coder_node, _extract_bash_prefix, _parse_json_tool_calls
from agent.graph.tools import CODER_TOOLS
from agent.graph.nodes.coder_prompts import CODER_PROMPT_COMPACT, CODER_PROMPT

print(f"[OK] Tools count: {len(CODER_TOOLS)}")

# Test 2: Compact prompt is shorter
print(f"[OK] Full prompt: {len(CODER_PROMPT)} chars")
print(f"[OK] Compact prompt: {len(CODER_PROMPT_COMPACT)} chars")
assert len(CODER_PROMPT_COMPACT) < len(CODER_PROMPT), "Compact should be shorter!"

# Test 3: Bash prefix extraction (no LLM needed)
assert _extract_bash_prefix("git status") == "git status"
assert _extract_bash_prefix("git diff HEAD~1") == "git diff"
assert _extract_bash_prefix("ls -la") == "ls"
assert _extract_bash_prefix("npm run lint") == "npm run lint"
assert _extract_bash_prefix("python -m pytest") == "python -m pytest"
print("[OK] Bash prefix extraction works")

# Test 4: Tool call parsing (expanded)
test1 = _parse_json_tool_calls('<tool_call>{"name": "read", "arguments": {"file_path": "test.py"}}</tool_call>')
assert len(test1) == 1 and test1[0]["name"] == "read", f"XML tag test failed: {test1}"
print("[OK] XML tool_call parsing works")

test2 = _parse_json_tool_calls('```json\n{"name": "bash", "args": {"command": "ls"}}\n```')
assert len(test2) == 1 and test2[0]["name"] == "bash", f"Markdown test failed: {test2}"
print("[OK] Markdown JSON parsing works")

test3 = _parse_json_tool_calls('I will read the file: {"name": "read", "args": {"file_path": "/tmp/x.py"}}')
assert len(test3) == 1 and test3[0]["name"] == "read", f"Bare JSON test failed: {test3}"
print("[OK] Bare JSON parsing works")

# Test 5: LLM provider config
from agent.core.llm_provider import get_llm
llm = get_llm({"llm": {"model_name": "test", "ollama_url": "http://localhost:11434"}})
assert llm.num_predict == 16384, f"num_predict={llm.num_predict}, expected 16384"
print("[OK] num_predict = 16384")

print("\n=== ALL 6 FIXES VERIFIED ===")
