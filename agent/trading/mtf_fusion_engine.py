"""
Multi-Timeframe Bias Fusion Engine.

Fuses bias scores from multiple timeframes with strict hierarchy:
    HTF (1h, 4h) weight = 0.60
    LTF (1m, 5m, 15m) weight = 0.40

Thresholds:
    >= +2.5 → STRONG_BULLISH
    <= -2.5 → STRONG_BEARISH
    else    → MIXED / TRANSITION

HARD RULE: Lower timeframe NEVER overrides strong higher timeframe bias.

No LLM. Fully deterministic.
"""
import logging
from typing import Dict, Any, Optional


class MTFFusionEngine:
    """
    Multi-timeframe bias fusion with higher-timeframe priority enforcement.
    """

    # Timeframe classification
    HTF_TIMEFRAMES = ["1h", "4h"]      # Higher timeframes — trend direction
    LTF_TIMEFRAMES = ["1m", "5m", "15m"]  # Lower timeframes — entry timing

    # Fixed weights per specification
    HTF_WEIGHT = 0.60
    LTF_WEIGHT = 0.40

    # Fusion output thresholds
    STRONG_BULLISH_THRESHOLD = 2.5
    STRONG_BEARISH_THRESHOLD = -2.5

    # HTF override threshold — if HTF score exceeds this, LTF cannot override
    HTF_OVERRIDE_THRESHOLD = 2.0

    def __init__(self) -> None:
        self.logger = logging.getLogger("MTFFusionEngine")
        self._last_fusion: Optional[Dict[str, Any]] = None

    def fuse(self, timeframe_biases: Dict[str, float]) -> Dict[str, Any]:
        """
        Fuse per-timeframe bias scores into a single directional signal.

        Args:
            timeframe_biases: Dict mapping timeframe string to bias score.
                Example: {"1m": 1.2, "5m": 0.8, "15m": 0.3, "1h": -1.5, "4h": -2.1}

        Returns:
            dict with fusion_score, fusion_label, htf_score, ltf_score,
            override_active flag, per-timeframe breakdown
        """
        # ── Separate HTF and LTF ───────────────────────────────
        htf_scores = []
        ltf_scores = []

        for tf, score in timeframe_biases.items():
            if tf in self.HTF_TIMEFRAMES:
                htf_scores.append(score)
            elif tf in self.LTF_TIMEFRAMES:
                ltf_scores.append(score)
            else:
                self.logger.warning(f"Unknown timeframe '{tf}' — ignoring")

        # ── Compute group averages ─────────────────────────────
        htf_avg = sum(htf_scores) / len(htf_scores) if htf_scores else 0.0
        ltf_avg = sum(ltf_scores) / len(ltf_scores) if ltf_scores else 0.0

        # ── HTF Override Rule ──────────────────────────────────
        # If HTF has strong conviction, LTF is clamped to not oppose it
        override_active = False
        effective_ltf = ltf_avg

        if abs(htf_avg) >= self.HTF_OVERRIDE_THRESHOLD:
            # HTF has strong directional conviction
            if htf_avg > 0 and ltf_avg < 0:
                # HTF bullish, LTF bearish → LTF clamped to 0 (neutral, not opposing)
                effective_ltf = 0.0
                override_active = True
                self.logger.debug(
                    f"HTF override: HTF={htf_avg:.2f} bullish, LTF={ltf_avg:.2f} bearish → LTF clamped to 0"
                )
            elif htf_avg < 0 and ltf_avg > 0:
                # HTF bearish, LTF bullish → LTF clamped to 0
                effective_ltf = 0.0
                override_active = True
                self.logger.debug(
                    f"HTF override: HTF={htf_avg:.2f} bearish, LTF={ltf_avg:.2f} bullish → LTF clamped to 0"
                )

        # ── Weighted Fusion ────────────────────────────────────
        fusion_score = (
            self.HTF_WEIGHT * htf_avg +
            self.LTF_WEIGHT * effective_ltf
        )

        # Clamp to ±3.0
        fusion_score = max(-3.0, min(3.0, fusion_score))

        # ── Label Classification ───────────────────────────────
        if fusion_score >= self.STRONG_BULLISH_THRESHOLD:
            label = "STRONG_BULLISH"
        elif fusion_score >= 0.75:
            label = "BULLISH"
        elif fusion_score > -0.75:
            label = "MIXED"
        elif fusion_score > self.STRONG_BEARISH_THRESHOLD:
            label = "BEARISH"
        else:
            label = "STRONG_BEARISH"

        result = {
            "fusion_score": round(fusion_score, 3),
            "fusion_label": label,
            "htf_score": round(htf_avg, 3),
            "ltf_score": round(ltf_avg, 3),
            "effective_ltf": round(effective_ltf, 3),
            "override_active": override_active,
            "timeframe_breakdown": {
                tf: round(score, 3) for tf, score in timeframe_biases.items()
            },
        }

        self._last_fusion = result
        self.logger.debug(
            f"Fusion: {fusion_score:.3f} ({label}) | "
            f"HTF={htf_avg:.2f} LTF={ltf_avg:.2f} | override={override_active}"
        )
        return result

    def get_last_fusion(self) -> Optional[Dict[str, Any]]:
        """Return the last computed fusion result."""
        return self._last_fusion
