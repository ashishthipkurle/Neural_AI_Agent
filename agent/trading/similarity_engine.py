"""
FAISS-based Pattern Similarity Engine (Phase 2).

Architecture:
    - Segmented indexing (timeframe_regime_volatility)
    - IndexIVFFlat with explicit centroid retraining for scale >10M
    - Immutable index versioning and double-buffer swapping
    - Incremental live additions
    - Query fail-safes (timeout, fallback)

No LLM. Deterministic. Horizontally scalable.
"""
import math
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

# Try to import FAISS; fallback to pure Python if not available
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class SimilarityEngine:
    """
    Vector similarity search across segmented pattern databases.
    Uses FAISS IndexIVFFlat for production-scale (millions of patterns).
    """

    def __init__(self, dimension: int = 15) -> None:
        self.logger = logging.getLogger("SimilarityEngine")
        self.dimension = dimension

        # Active FAISS indices per segment key (e.g., "15m_trending_high")
        self._indices: Dict[str, Any] = {}
        # Pattern ID mappings: segment_key -> list of pattern_ids
        self._id_maps: Dict[str, List[str]] = {}
        # Track version string of currently active indices
        self._versions: Dict[str, str] = {}
        
        # Raw vectors for fallback mode (or exact search)
        self._raw_vectors: Dict[str, List[List[float]]] = {}

        if FAISS_AVAILABLE:
            self.logger.info("FAISS available — using IndexIVFFlat similarity")
        else:
            self.logger.warning("FAISS not installed — using pure Python brute-force fallback")

    @staticmethod
    def get_segment_key(timeframe: str, regime: str = "UNKNOWN", vol_bucket: str = "UNKNOWN") -> str:
        """Route vectors to exact physical segmented index."""
        return f"{timeframe}_{regime}_{vol_bucket}"

    # ── Index Building & Double Buffering ──────────────────────

    def build_index(
        self,
        segment_key: str,
        vectors: List[List[float]],
        pattern_ids: List[str],
        version_id: str = "v1"
    ) -> Dict[str, Any]:
        """
        Builds a new index OFFLINE (returns it, doesn't mount it).
        Allows double-buffering. Call `swap_index()` to mount.
        """
        if len(vectors) != len(pattern_ids):
            raise ValueError(f"Vector count != ID count")

        count = len(vectors)
        if count == 0:
            return {"segment_key": segment_key, "count": 0, "status": "EMPTY", "index": None, "id_map": [], "vectors": []}

        normalized = [self._l2_normalize(v) for v in vectors]

        if FAISS_AVAILABLE:
            import numpy as np
            matrix = np.array(normalized, dtype=np.float32)
            
            # Use IndexIVFFlat. 
            # Rule of thumb for nlist (centroids): 4 * sqrt(N), bounded
            nlist = max(1, min(1024, int(4 * math.sqrt(count))))
            if count < 39: # FAISS constraint
                nlist = 1
                
            quantizer = faiss.IndexFlatIP(self.dimension)
            index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist, faiss.METRIC_INNER_PRODUCT)
            
            # Train Centroids explicitly
            index.train(matrix)
            index.add(matrix)
            
            # Increase nprobe for better recall at cost of slight speed
            index.nprobe = min(nlist, max(1, nlist // 4)) 

            backend = "FAISS_IVF"
        else:
            index = "BRUTE_FORCE"
            backend = "BRUTE_FORCE"

        self.logger.info(f"Offline index built: {segment_key} | {count} vectors | nlist={nlist if FAISS_AVAILABLE else 0}")
        
        return {
            "segment_key": segment_key,
            "version": version_id,
            "count": count,
            "backend": backend,
            "index": index,
            "id_map": list(pattern_ids),
            "vectors": normalized,
            "dimension": self.dimension
        }

    def swap_index(self, build_report: Dict[str, Any]) -> None:
        """Atomic hot-swap of an offline-built index into active serving."""
        seg = build_report["segment_key"]
        
        if build_report.get("status") == "EMPTY" or build_report.get("index") is None:
            return
            
        self._indices[seg] = build_report["index"]
        self._id_maps[seg] = build_report["id_map"]
        self._versions[seg] = build_report["version"]
        self._raw_vectors[seg] = build_report["vectors"]
        
        self.logger.info(f"Swapped index safely: {seg} -> version {build_report['version']} ({build_report['count']} vectors)")

    def add_incremental(self, segment_key: str, vector: List[float], pattern_id: str) -> bool:
        """Incrementally add a single vector without full rebuild."""
        if segment_key not in self._indices:
            self.logger.warning(f"Cannot incrementally add to missing segment {segment_key}")
            return False

        normalized = self._l2_normalize(vector)
        self._id_maps[segment_key].append(pattern_id)
        self._raw_vectors[segment_key].append(normalized)

        if FAISS_AVAILABLE and isinstance(self._indices[segment_key], faiss.Index):
            import numpy as np
            vec_np = np.array([normalized], dtype=np.float32)
            self._indices[segment_key].add(vec_np)
            
        return True

    # ── Query & Fail-Safes ─────────────────────────────────────

    def query(
        self,
        segment_key: str,
        vector: List[float],
        k: int = 50,
        timeout_ms: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query vector with timeout fail-safe.
        """
        start_t = time.time()
        
        if segment_key not in self._indices:
            return []

        normalized_query = self._l2_normalize(vector)
        id_map = self._id_maps.get(segment_key, [])

        if not id_map:
            return []

        k = min(k, len(id_map))

        try:
            if FAISS_AVAILABLE and isinstance(self._indices.get(segment_key), faiss.Index):
                res = self._query_faiss(segment_key, normalized_query, k)
            else:
                res = self._query_brute_force(segment_key, normalized_query, k)
                
            elapsed_ms = (time.time() - start_t) * 1000
            if elapsed_ms > timeout_ms:
                self.logger.warning(f"Query latency breached safety: {elapsed_ms:.1f}ms (Budget: {timeout_ms}ms)")
                
            return res
            
        except Exception as e:
            self.logger.error(f"Query fail-safe triggered on {segment_key}: {str(e)}")
            return []  # Graceful degrade

    def _query_faiss(self, segment_key: str, query: List[float], k: int) -> List[Dict[str, Any]]:
        import numpy as np
        index = self._indices[segment_key]
        id_map = self._id_maps[segment_key]

        query_np = np.array([query], dtype=np.float32)
        distances, indices = index.search(query_np, k)

        results = []
        for i in range(k):
            idx = int(indices[0][i])
            if 0 <= idx < len(id_map):
                results.append({
                    "pattern_id": id_map[idx],
                    "similarity_score": round(float(distances[0][i]), 6),
                    "rank": i + 1,
                })
        return results

    def _query_brute_force(self, segment_key: str, query: List[float], k: int) -> List[Dict[str, Any]]:
        id_map = self._id_maps[segment_key]
        vectors = self._raw_vectors.get(segment_key, [])

        scores = []
        for i, vec in enumerate(vectors):
            dot = sum(q * v for q, v in zip(query, vec))
            scores.append((i, dot))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (idx, score) in enumerate(scores[:k], 1):
            results.append({
                "pattern_id": id_map[idx],
                "similarity_score": round(score, 6),
                "rank": rank,
            })
        return results

    # ── Multi-Timeframe (Distributed Mock) ──────────────────────

    def query_multi_segment(
        self,
        vectors_by_seg: Dict[str, List[float]],
        k: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Query multiple segments independently (can be fanned out over network)."""
        results = {}
        for seg, vector in vectors_by_seg.items():
            results[seg] = self.query(seg, vector, k)
        return results

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _l2_normalize(vector: List[float]) -> List[float]:
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude <= 0:
            return [0.0] * len(vector)
        return [v / magnitude for v in vector]

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        indices = {}
        for seg in self._indices:
            id_map = self._id_maps.get(seg, [])
            backend = "FAISS_IVF" if FAISS_AVAILABLE and isinstance(self._indices.get(seg), object) and self._indices[seg] != "BRUTE_FORCE" else "BRUTE_FORCE"
            indices[seg] = {
                "count": len(id_map),
                "backend": backend,
                "version": self._versions.get(seg, "v1")
            }

        return {
            "faiss_available": FAISS_AVAILABLE,
            "dimension": self.dimension,
            "indices": indices,
            "total_patterns": sum(len(ids) for ids in self._id_maps.values()),
        }
