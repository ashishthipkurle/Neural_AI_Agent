"""
Distributed Shard Router for FAISS Similarity Engine.

Architecture:
    - Routes pattern updates/queries to specific shards via hashing.
    - Master aggregator merges `K`-nearest results from multiple shards.
    - Interfaces with `cluster_coordinator.py` to route around dead nodes.
"""
import logging
import hashlib
from typing import Dict, List, Any, Optional
from .cluster_coordinator import ClusterCoordinator

class ShardRouter:
    """
    Manages distribution of FAISS queries and index builds across physical shards.
    Ensures that instrument vectors live on deterministic nodes unless failover occurs.
    """

    def __init__(self, coordinator: ClusterCoordinator, num_shards: int = 4) -> None:
        self.logger = logging.getLogger("ShardRouter")
        self.coordinator = coordinator
        self.num_shards = num_shards
        
        # Logical Shard Map: Shard_ID -> Node_ID (from coordinator)
        self._shard_map: Dict[int, str] = {}
        
    def rebuild_topology(self) -> None:
        """Map active nodes from coordinator to logical shards."""
        active_nodes = self.coordinator.get_healthy_nodes()
        if not active_nodes:
            self.logger.critical("No active FAISS nodes available in cluster!")
            self._shard_map.clear()
            return
            
        # Simplistic consistent hashing mapping
        active_nodes.sort()
        for i in range(self.num_shards):
            # Map shard to node (round robin wrap)
            self._shard_map[i] = active_nodes[i % len(active_nodes)]
            
        self.logger.info(f"Topology rebuilt. {self.num_shards} shards mapped across {len(active_nodes)} nodes.")

    def get_shard_for_instrument(self, instrument_id: int) -> int:
        """
        Hash-based routing: Deterministically maps an instrument to a shard number.
        """
        # SHA-256 for uniform distribution
        hash_str = hashlib.sha256(str(instrument_id).encode()).hexdigest()
        shard_id = int(hash_str, 16) % self.num_shards
        return shard_id

    def get_node_for_instrument(self, instrument_id: int) -> Optional[str]:
        """Returns the physical active Node ID responsible for this instrument."""
        shard_id = self.get_shard_for_instrument(instrument_id)
        
        node_id = self._shard_map.get(shard_id)
        if practically_dead(node_id):
            self.rebuild_topology()
            node_id = self._shard_map.get(shard_id)
            
        return node_id
        
    def aggregate_top_k(self, shard_results: List[List[Dict[str, Any]]], k: int = 50) -> List[Dict[str, Any]]:
        """
        Master Aggregator: Merges `K`-nearest results from multiple distributed shards.
        shard_results: List of result lists returned by individual nodes.
        Returns single merged list of K top results.
        """
        flattened = [item for sublist in shard_results for item in sublist]
        
        # Sort by similarity descending
        flattened.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        
        # Deduplicate by pattern_id
        seen = set()
        unique = []
        for res in flattened:
            pid = res["pattern_id"]
            if pid not in seen:
                seen.add(pid)
                unique.append(res)
                if len(unique) >= k:
                    break
                    
        return unique

    def get_routing_table(self) -> Dict[str, Any]:
        """View logical topology."""
        return {
            "num_shards": self.num_shards,
            "shard_to_node_map": self._shard_map,
            "active_nodes_count": len(set(self._shard_map.values()))
        }

# Local helper to check if a node ID is actually dead
def practically_dead(node_id: Optional[str]) -> bool:
    if not node_id:
        return True
    return False
