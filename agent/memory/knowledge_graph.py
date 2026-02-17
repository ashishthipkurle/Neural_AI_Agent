"""
Knowledge Graph — §5 of Production Autonomous Agent Spec.

Structured JSON graph with entity-relation enforcement.
Separate store from STM and LTM.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("memory.kg")


class KnowledgeGraph:
    """Entity-relation graph stored as structured JSON — §5.

    Rules:
    - Entities must have type + name.
    - Relations must reference existing entities.
    - Updates require entity extraction pipeline (caller responsibility).
    - Persisted to disk after mutations.
    """

    def __init__(self, path: str = "agent_data/knowledge_graph.json"):
        self.path = path
        self._lock = threading.Lock()
        self._entities: Dict[str, Dict[str, Any]] = {}  # id → {type, name, attrs}
        self._relations: List[Dict[str, Any]] = []       # [{source, target, type, attrs}]
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self._entities = data.get("entities", {})
                self._relations = data.get("relations", [])
                logger.info(f"KG loaded: {len(self._entities)} entities, {len(self._relations)} relations")
            except Exception as e:
                logger.warning(f"KG load failed: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({
                "entities": self._entities,
                "relations": self._relations,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2, default=str)

    # ── Entity Operations ──

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: Dict[str, Any] = None,
    ) -> bool:
        """Add or update an entity. Returns True if new, False if updated."""
        with self._lock:
            is_new = entity_id not in self._entities
            self._entities[entity_id] = {
                "type": entity_type,
                "name": name,
                "attributes": attributes or {},
                "created_at": datetime.now(timezone.utc).isoformat() if is_new else self._entities.get(entity_id, {}).get("created_at", ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save()
            return is_new

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._entities.get(entity_id)

    def find_entities(self, entity_type: str = None, name_contains: str = None) -> List[Dict[str, Any]]:
        with self._lock:
            results = []
            for eid, data in self._entities.items():
                if entity_type and data.get("type") != entity_type:
                    continue
                if name_contains and name_contains.lower() not in data.get("name", "").lower():
                    continue
                results.append({"id": eid, **data})
            return results

    def remove_entity(self, entity_id: str) -> bool:
        with self._lock:
            if entity_id in self._entities:
                del self._entities[entity_id]
                # Remove orphaned relations
                self._relations = [
                    r for r in self._relations
                    if r["source"] != entity_id and r["target"] != entity_id
                ]
                self._save()
                return True
            return False

    # ── Relation Operations ──

    def add_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        attributes: Dict[str, Any] = None,
    ) -> bool:
        """Add a relation. Both entities must exist.

        Returns True if added, False if entities not found.
        """
        with self._lock:
            if source not in self._entities or target not in self._entities:
                logger.warning(f"Relation rejected: entity not found ({source} → {target})")
                return False

            # Check for duplicate
            for r in self._relations:
                if r["source"] == source and r["target"] == target and r["type"] == relation_type:
                    return False  # Already exists

            self._relations.append({
                "source": source,
                "target": target,
                "type": relation_type,
                "attributes": attributes or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            self._save()
            return True

    def get_relations(
        self,
        entity_id: str,
        direction: str = "both",
        relation_type: str = None,
    ) -> List[Dict[str, Any]]:
        """Get relations for an entity.

        Args:
            direction: "outgoing", "incoming", or "both"
        """
        with self._lock:
            results = []
            for r in self._relations:
                if relation_type and r["type"] != relation_type:
                    continue
                if direction in ("outgoing", "both") and r["source"] == entity_id:
                    results.append(r)
                elif direction in ("incoming", "both") and r["target"] == entity_id:
                    results.append(r)
            return results

    # ── Query ──

    def get_subgraph(self, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get entity + connected entities up to N hops."""
        visited: Set[str] = set()
        entities = {}
        relations = []

        queue = [(entity_id, 0)]
        while queue:
            eid, d = queue.pop(0)
            if eid in visited or d > depth:
                continue
            visited.add(eid)

            entity = self._entities.get(eid)
            if entity:
                entities[eid] = entity

            for r in self._relations:
                if r["source"] == eid:
                    relations.append(r)
                    if r["target"] not in visited:
                        queue.append((r["target"], d + 1))
                elif r["target"] == eid:
                    relations.append(r)
                    if r["source"] not in visited:
                        queue.append((r["source"], d + 1))

        return {"entities": entities, "relations": relations}

    # ── Stats ──

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "entities": len(self._entities),
                "relations": len(self._relations),
            }

    def get_kg_id(self) -> str:
        return f"kg_{os.path.basename(self.path)}"
