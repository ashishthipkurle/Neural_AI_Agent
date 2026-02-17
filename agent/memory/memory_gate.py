"""
Memory Gate — §5 of Production Autonomous Agent Spec.

Cross-layer validation. Prevents:
- STM overwriting LTM
- LTM writes without validation
- KG updates without entity extraction
- Memory drift and corruption
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("memory.gate")


class MemoryGate:
    """Enforces cross-layer memory safety — §5.

    Rules:
    1. STM is read-only from LTM/KG perspective (cannot write to them).
    2. LTM writes require validation function.
    3. KG writes require entity_type and name.
    4. Prevents memory drift by checking content before write.
    """

    def __init__(self, stm, ltm, kg):
        from agent.memory.stm import ShortTermWorkingMemory
        from agent.memory.ltm import VersionedLTM
        from agent.memory.knowledge_graph import KnowledgeGraph

        self.stm: ShortTermWorkingMemory = stm
        self.ltm: VersionedLTM = ltm
        self.kg: KnowledgeGraph = kg

    def write_stm(self, role: str, content: str) -> None:
        """Write to STM. Always allowed."""
        self.stm.add_message(role, content)

    def write_ltm(
        self,
        key: str,
        value: str,
        category: str = "general",
        source: str = "system",
    ) -> Dict[str, Any]:
        """Write to LTM with validation.

        - Source must be identified.
        - Value must not be empty.
        - Validation rejects duplicate content.
        """
        if not value or not value.strip():
            return {"success": False, "reason": "empty_value"}

        if source == "stm":
            logger.warning("BLOCKED: STM cannot directly write to LTM")
            return {"success": False, "reason": "stm_cannot_write_ltm"}

        def _validator(old: str, new: str) -> bool:
            # Reject if new value is subset of old (no new info)
            if new.strip() in old:
                return False
            # Reject if too short (likely garbage)
            if len(new.strip()) < 10:
                return False
            return True

        result = self.ltm.store(key, value, category, validation_fn=_validator)
        return result

    def write_kg(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: Dict[str, Any] = None,
        source: str = "system",
    ) -> bool:
        """Write entity to KG with validation.

        - Must have type and name.
        - Source must be identified.
        """
        if not entity_type or not name:
            logger.warning("BLOCKED: KG entity must have type and name")
            return False

        if source == "stm":
            logger.warning("BLOCKED: STM cannot directly write to KG")
            return False

        return self.kg.add_entity(entity_id, entity_type, name, attributes)

    def add_relation(
        self,
        source_entity: str,
        target_entity: str,
        relation_type: str,
        attributes: Dict[str, Any] = None,
    ) -> bool:
        """Add KG relation. Both entities must already exist."""
        return self.kg.add_relation(source_entity, target_entity, relation_type, attributes)

    def promote_stm_to_ltm(self, key: str, category: str = "learned") -> Dict[str, Any]:
        """Explicitly promote STM content to LTM.

        This is the ONLY sanctioned way for STM content to reach LTM.
        Goes through full validation.
        """
        observations = self.stm.get_observations()
        if not observations:
            return {"success": False, "reason": "no_observations_to_promote"}

        combined = "\n".join(o["text"] for o in observations)
        return self.write_ltm(key, combined, category, source="promotion")

    def get_memory_refs(self) -> Dict[str, Any]:
        """Get reference IDs for state tracking."""
        return {
            "stm_id": self.stm.get_stm_id(),
            "ltm_id": self.ltm.get_ltm_id(),
            "kg_id": self.kg.get_kg_id(),
        }
