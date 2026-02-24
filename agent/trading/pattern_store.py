"""
Historical Pattern Database.

Stores feature vectors + forward outcomes for the sliding window approach.

For each window:
    - pattern_id
    - feature_vector (15-dim normalized)
    - forward outcomes over prediction_horizon:
        - future_return
        - max_drawdown
        - max_runup
        - r_multiple
        - regime_label

In-memory with optional disk persistence (JSON lines).
No LLM. Deterministic. Millions of patterns supported.
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class PatternStore:
    """
    In-memory pattern database indexed by timeframe.
    Stores feature vectors + forward outcomes for similarity search.
    """

    def __init__(
        self,
        prediction_horizon: int = 10,
        persist_path: Optional[str] = None,
    ) -> None:
        self.logger = logging.getLogger("PatternStore")
        self.prediction_horizon = prediction_horizon

        # Store: {timeframe: [pattern_dict, ...]}
        self._patterns: Dict[str, List[Dict[str, Any]]] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        self._next_id = 0

    # ── Pattern Computation ────────────────────────────────────

    def compute_forward_outcomes(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        anchor_index: int,
        entry_price: float,
        stop_distance: float = 0.0,
    ) -> Optional[Dict[str, float]]:
        """
        Compute forward outcomes from anchor_index over prediction_horizon.

        Args:
            closes, highs, lows: Full price series
            anchor_index: Index of the pattern end (closed candle)
            entry_price: Price at pattern time
            stop_distance: ATR-based stop distance for R calculation

        Returns:
            dict with future_return, max_drawdown, max_runup, r_multiple
        """
        start = anchor_index + 1
        end = min(start + self.prediction_horizon, len(closes))

        if end <= start or entry_price <= 0:
            return None

        future_closes = closes[start:end]
        future_highs = highs[start:end]
        future_lows = lows[start:end]

        if not future_closes:
            return None

        # Future return
        final_price = future_closes[-1]
        future_return = (final_price - entry_price) / entry_price

        # Max drawdown (worst trough from entry)
        max_dd = 0.0
        for low in future_lows:
            dd = (entry_price - low) / entry_price
            max_dd = max(max_dd, dd)

        # Max runup (best peak from entry)
        max_ru = 0.0
        for high in future_highs:
            ru = (high - entry_price) / entry_price
            max_ru = max(max_ru, ru)

        # R multiple (reward / risk)
        r_multiple = 0.0
        if stop_distance > 0:
            r_multiple = (final_price - entry_price) / stop_distance

        return {
            "future_return": round(future_return, 6),
            "max_drawdown": round(max_dd, 6),
            "max_runup": round(max_ru, 6),
            "r_multiple": round(r_multiple, 4),
        }

    # ── Storage ────────────────────────────────────────────────

    def add_pattern(
        self,
        timeframe: str,
        instrument_id: int,
        candle_index: int,
        feature_vector: List[float],
        future_return: float,
        max_drawdown: float,
        max_runup: float,
        r_multiple: float,
        regime_label: str,
        timestamp: int = 0,
    ) -> str:
        """
        Store a pattern with its feature vector and forward outcomes.
        Returns the assigned pattern_id.
        """
        self._next_id += 1
        pattern_id = f"P_{timeframe}_{instrument_id}_{self._next_id}"

        pattern = {
            "pattern_id": pattern_id,
            "instrument_id": instrument_id,
            "timeframe": timeframe,
            "candle_index": candle_index,
            "timestamp": timestamp,
            "feature_vector": feature_vector,
            "future_return": future_return,
            "max_drawdown": max_drawdown,
            "max_runup": max_runup,
            "r_multiple": r_multiple,
            "regime_label": regime_label,
        }

        if timeframe not in self._patterns:
            self._patterns[timeframe] = []
        self._patterns[timeframe].append(pattern)

        return pattern_id

    def add_patterns_bulk(
        self,
        timeframe: str,
        instrument_id: int,
        feature_vectors: List[List[float]],
        outcomes: List[Dict[str, float]],
        regime_labels: List[str],
        candle_indices: Optional[List[int]] = None,
    ) -> int:
        """Bulk add patterns. Returns count added."""
        count = 0
        for i in range(len(feature_vectors)):
            if i >= len(outcomes):
                break
            idx = candle_indices[i] if candle_indices and i < len(candle_indices) else i
            self.add_pattern(
                timeframe=timeframe,
                instrument_id=instrument_id,
                candle_index=idx,
                feature_vector=feature_vectors[i],
                future_return=outcomes[i].get("future_return", 0),
                max_drawdown=outcomes[i].get("max_drawdown", 0),
                max_runup=outcomes[i].get("max_runup", 0),
                r_multiple=outcomes[i].get("r_multiple", 0),
                regime_label=regime_labels[i] if i < len(regime_labels) else "UNKNOWN",
            )
            count += 1

        self.logger.info(f"Bulk added {count} patterns for {timeframe}")
        return count

    # ── Retrieval ──────────────────────────────────────────────

    def get_patterns_by_timeframe(self, timeframe: str) -> List[Dict[str, Any]]:
        return self._patterns.get(timeframe, [])

    def get_vectors_by_timeframe(self, timeframe: str) -> Tuple[List[List[float]], List[str]]:
        """
        Get all feature vectors and pattern IDs for a timeframe.
        Used for building FAISS index.
        """
        patterns = self._patterns.get(timeframe, [])
        vectors = [p["feature_vector"] for p in patterns]
        ids = [p["pattern_id"] for p in patterns]
        return vectors, ids

    def get_pattern_by_id(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a single pattern by ID."""
        for tf_patterns in self._patterns.values():
            for p in tf_patterns:
                if p["pattern_id"] == pattern_id:
                    return p
        return None

    def get_outcomes_for_ids(self, pattern_ids: List[str]) -> List[Dict[str, Any]]:
        """Get forward outcomes for a list of pattern IDs. For probability engine."""
        # Build ID lookup
        id_set = set(pattern_ids)
        results = []
        for tf_patterns in self._patterns.values():
            for p in tf_patterns:
                if p["pattern_id"] in id_set:
                    results.append({
                        "pattern_id": p["pattern_id"],
                        "future_return": p["future_return"],
                        "max_drawdown": p["max_drawdown"],
                        "max_runup": p["max_runup"],
                        "r_multiple": p["r_multiple"],
                        "regime_label": p["regime_label"],
                    })
        return results

    # ── Persistence ────────────────────────────────────────────

    def save_to_disk(self, path: Optional[str] = None) -> int:
        """Save all patterns to JSON lines file."""
        target = Path(path) if path else self._persist_path
        if not target:
            return 0

        target.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(target, "w", encoding="utf-8") as f:
            for tf, patterns in self._patterns.items():
                for p in patterns:
                    f.write(json.dumps(p) + "\n")
                    count += 1

        self.logger.info(f"Saved {count} patterns to {target}")
        return count

    def load_from_disk(self, path: Optional[str] = None) -> int:
        """Load patterns from JSON lines file."""
        target = Path(path) if path else self._persist_path
        if not target or not target.exists():
            return 0

        count = 0
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                p = json.loads(line)
                tf = p.get("timeframe", "unknown")
                if tf not in self._patterns:
                    self._patterns[tf] = []
                self._patterns[tf].append(p)
                count += 1
                self._next_id = max(self._next_id, count)

        self.logger.info(f"Loaded {count} patterns from {target}")
        return count

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        by_tf = {tf: len(pats) for tf, pats in self._patterns.items()}
        total = sum(by_tf.values())
        return {
            "total_patterns": total,
            "by_timeframe": by_tf,
            "prediction_horizon": self.prediction_horizon,
        }
