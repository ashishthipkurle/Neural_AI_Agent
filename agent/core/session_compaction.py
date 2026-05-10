import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("core.session_compaction")

@dataclass
class CompactionConfig:
    preserve_recent_messages: int = 4
    max_estimated_tokens: int = 10_000

@dataclass
class CompactionResult:
    compacted_messages: List[Dict[str, Any]]
    summary: str
    tokens_saved: int

class SessionCompactor:
    """Claw-parity conversation compaction — §compact.rs"""
    
    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate tokens for a list of messages. Roughly len // 4."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4 + 1
            elif isinstance(content, list):
                for block in content:
                    text = block.get("text", "")
                    if text:
                        total += len(text) // 4 + 1
        return total

    def should_compact(self, messages: List[Dict[str, Any]], config: CompactionConfig) -> bool:
        if len(messages) <= config.preserve_recent_messages:
            return False
            
        return self.estimate_tokens(messages) > config.max_estimated_tokens

    def compact(self, messages: List[Dict[str, Any]], config: CompactionConfig) -> CompactionResult:
        if not self.should_compact(messages, config):
            return CompactionResult(messages, "", 0)
            
        preserve_count = config.preserve_recent_messages
        to_compact = messages[:-preserve_count]
        preserved = messages[-preserve_count:]
        
        original_tokens = self.estimate_tokens(messages)
        
        summary = self._summarize_messages(to_compact)
        infer_work = self._infer_pending_work(messages)
        key_files = self._collect_key_files(to_compact)
        
        full_summary = f"<compaction_summary>\n{summary}\n"
        if key_files:
            full_summary += f"Key Files Evaluated:\n" + "\n".join(f"- {f}" for f in key_files) + "\n"
        if infer_work:
            full_summary += f"Inferred Pending Work:\n" + "\n".join(f"- {w}" for w in infer_work) + "\n"
        full_summary += "</compaction_summary>"
        
        # We usually merge previous summaries if they exist in the to_compact array.
        # But for this simple implementation, we assume to_compact has the raw messages.
        
        summary_msg = {
            "role": "system",
            "content": full_summary
        }
        
        compacted_messages = [summary_msg] + preserved
        new_tokens = self.estimate_tokens(compacted_messages)
        
        return CompactionResult(
            compacted_messages=compacted_messages,
            summary=full_summary,
            tokens_saved=max(0, original_tokens - new_tokens)
        )

    def _summarize_messages(self, messages: List[Dict[str, Any]]) -> str:
        tools_used = set()
        user_intents = []
        
        for msg in messages:
            content = msg.get("content", "")
            if msg.get("role") == "user":
                if isinstance(content, str):
                    user_intents.append(content[:100] + "..." if len(content) > 100 else content)
            elif msg.get("role") == "assistant" and "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    tools_used.add(tc["function"]["name"])
                    
        summary = "Previous interaction summary:\n"
        if user_intents:
            summary += f"User asked for: {user_intents[-1]}\n"
        if tools_used:
            summary += f"Tools utilized: {', '.join(tools_used)}\n"
            
        return summary

    def _infer_pending_work(self, messages: List[Dict[str, Any]]) -> List[str]:
        pending = []
        for msg in messages[-5:]:
            content = msg.get("content", "")
            if isinstance(content, str):
                if re.search(r'\b(todo|next|pending|remaining)\b', content, re.IGNORECASE):
                    # very simplistic extraction
                    sentences = content.split('.')
                    for s in sentences:
                        if re.search(r'\b(todo|next|pending|remaining)\b', s, re.IGNORECASE):
                            pending.append(s.strip())
        return pending

    def _collect_key_files(self, messages: List[Dict[str, Any]]) -> List[str]:
        files = set()
        pattern = re.compile(r'([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)')
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                matches = pattern.findall(content)
                for m in matches:
                    if '/' in m or '\\' in m:
                        files.add(m)
        return list(files)[:10]  # Cap at 10 files

    def _merge_summaries(self, existing: Optional[str], new: str) -> str:
        if not existing:
            return new
        return f"{existing}\n\n[UPDATE]\n{new}"
