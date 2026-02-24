"""
Structural Vision Context Layer.

Thin wrapper around the existing Vision LLM scan.
Returns ONLY structural observations:
    - Support/resistance zones
    - Chart pattern type (double top, ascending triangle, etc.)
    - Structure alignment score (0–1)

Does NOT compute numbers. Does NOT make trade decisions.
Feeds `structure_alignment` into the confidence engine.
"""
import logging
from typing import Dict, Any, Optional


class StructuralVisionEngine:
    """
    Converts raw Vision LLM output into a normalized structural context score.
    This engine does NOT call the LLM itself — it receives already-parsed
    vision data from the API layer and extracts structural context.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("StructuralVisionEngine")
        self._last_analysis: Optional[Dict[str, Any]] = None

    def extract_structure(
        self,
        vision_data: Dict[str, Any],
        current_price: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Extract structural context from Vision LLM output.

        Args:
            vision_data: Parsed JSON from the vision analysis endpoint.
                Expected keys: signals, analysis_summary, chart_y_min, chart_y_max
            current_price: Current live price of the asset

        Returns:
            dict with structure_score (0–1), support/resistance zones,
            pattern_type, and alignment assessment
        """
        signals = vision_data.get("signals", [])
        summary = vision_data.get("analysis_summary", "")
        y_min = vision_data.get("chart_y_min", 0)
        y_max = vision_data.get("chart_y_max", 0)

        # ── Extract support and resistance levels ──────────────
        support_levels = []
        resistance_levels = []

        for sig in signals:
            entry = sig.get("entry_price", 0)
            direction = sig.get("direction", "")
            if entry <= 0:
                continue
            if direction == "LONG":
                support_levels.append(entry)
            elif direction == "SHORT":
                resistance_levels.append(entry)

        # ── Pattern detection from summary text ────────────────
        pattern_type = self._detect_pattern(summary)

        # ── Structure alignment score ──────────────────────────
        # How well does current price align with identified structure?
        structure_score = self._compute_alignment(
            current_price, support_levels, resistance_levels, y_min, y_max
        )

        result = {
            "structure_score": round(structure_score, 4),
            "support_levels": [round(s, 2) for s in sorted(support_levels)],
            "resistance_levels": [round(r, 2) for r in sorted(resistance_levels)],
            "pattern_type": pattern_type,
            "y_range": {"min": y_min, "max": y_max},
            "signal_count": len(signals),
        }

        self._last_analysis = result
        self.logger.debug(f"Structure: score={structure_score:.3f}, pattern={pattern_type}")
        return result

    def _compute_alignment(
        self,
        price: float,
        supports: list,
        resistances: list,
        y_min: float,
        y_max: float,
    ) -> float:
        """
        Compute how well price aligns with identified structure.
        High score = price is near a support (for buys) or resistance (for sells).
        """
        if price <= 0 or (not supports and not resistances):
            return 0.5  # Neutral — no structure identified

        y_range = y_max - y_min if y_max > y_min else price * 0.1

        # Distance to nearest support
        min_support_dist = float('inf')
        for s in supports:
            dist = abs(price - s) / y_range
            min_support_dist = min(min_support_dist, dist)

        # Distance to nearest resistance
        min_resist_dist = float('inf')
        for r in resistances:
            dist = abs(price - r) / y_range
            min_resist_dist = min(min_resist_dist, dist)

        # Closest level distance
        closest = min(min_support_dist, min_resist_dist)

        # Score: closer to structure = higher score
        # Within 5% of range = excellent (1.0), 20%+ = poor (0.2)
        if closest < 0.05:
            return 1.0
        elif closest < 0.10:
            return 0.8
        elif closest < 0.15:
            return 0.6
        elif closest < 0.25:
            return 0.4
        else:
            return 0.2

    def _detect_pattern(self, summary: str) -> str:
        """Extract chart pattern from analysis summary text."""
        summary_lower = summary.lower()

        patterns = {
            "double_top": ["double top", "double-top"],
            "double_bottom": ["double bottom", "double-bottom"],
            "head_shoulders": ["head and shoulders", "h&s"],
            "ascending_triangle": ["ascending triangle"],
            "descending_triangle": ["descending triangle"],
            "symmetrical_triangle": ["symmetrical triangle", "triangle"],
            "bull_flag": ["bull flag", "bullish flag"],
            "bear_flag": ["bear flag", "bearish flag"],
            "wedge": ["wedge", "rising wedge", "falling wedge"],
            "channel": ["channel", "ascending channel", "descending channel"],
            "consolidation": ["consolidation", "range", "sideways"],
            "breakout": ["breakout", "breaking out"],
            "reversal": ["reversal", "reversing"],
        }

        for pattern_name, keywords in patterns.items():
            for keyword in keywords:
                if keyword in summary_lower:
                    return pattern_name

        return "unidentified"

    def get_last_analysis(self) -> Optional[Dict[str, Any]]:
        return self._last_analysis
