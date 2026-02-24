"""
Slippage & Execution Simulation Model.

Simulates realistic order fill conditions:
    slippage = spread + volatility_factor × ATR
    effective_entry = entry ± slippage (depending on direction)

Recalculates R-multiple using effective prices.
Displays worst-case fill simulation.

No LLM. Fully deterministic.
"""
import logging
from typing import Dict, Any


class SlippageEngine:
    """
    Execution cost simulator for realistic signal evaluation.
    """

    def __init__(
        self,
        default_spread_pct: float = 0.001,    # 0.1% default spread
        volatility_factor: float = 0.5,         # Weight of ATR in slippage calc
    ) -> None:
        self.logger = logging.getLogger("SlippageEngine")
        self.default_spread_pct = default_spread_pct
        self.volatility_factor = volatility_factor

    def simulate_slippage(
        self,
        entry_price: float,
        stop_price: float,
        target_price: float,
        atr: float,
        direction: str = "LONG",
        spread_pct: float = None,
    ) -> Dict[str, Any]:
        """
        Simulate execution slippage and recalculate effective R-multiple.

        Args:
            entry_price: Intended entry price
            stop_price: Stop loss price
            target_price: Take profit target price
            atr: Current Average True Range
            direction: "LONG" or "SHORT"
            spread_pct: Override default spread percentage

        Returns:
            dict with effective prices, slippage amount, original R, effective R,
            worst-case scenario, and fill quality assessment
        """
        if entry_price <= 0 or atr < 0:
            return self._empty_result("INVALID_INPUTS")

        spread = (spread_pct or self.default_spread_pct) * entry_price
        vol_slippage = self.volatility_factor * atr
        total_slippage = spread + vol_slippage

        # ── Direction-aware effective prices ───────────────────
        if direction == "LONG":
            effective_entry = entry_price + total_slippage
            effective_stop = stop_price - total_slippage  # Worse fill on stop
            effective_target = target_price - total_slippage  # Worse fill on exit
        else:  # SHORT
            effective_entry = entry_price - total_slippage
            effective_stop = stop_price + total_slippage
            effective_target = target_price + total_slippage

        # ── R-multiple calculations ────────────────────────────
        # Original R (ideal fills)
        original_risk = abs(entry_price - stop_price)
        original_reward = abs(target_price - entry_price)
        original_r = original_reward / original_risk if original_risk > 0 else 0.0

        # Effective R (with slippage)
        effective_risk = abs(effective_entry - effective_stop)
        effective_reward = abs(effective_target - effective_entry)
        effective_r = effective_reward / effective_risk if effective_risk > 0 else 0.0

        # ── Worst-case scenario (2x slippage) ──────────────────
        worst_slippage = total_slippage * 2.0
        if direction == "LONG":
            worst_entry = entry_price + worst_slippage
            worst_stop = stop_price - worst_slippage
            worst_target = target_price - worst_slippage
        else:
            worst_entry = entry_price - worst_slippage
            worst_stop = stop_price + worst_slippage
            worst_target = target_price + worst_slippage

        worst_risk = abs(worst_entry - worst_stop)
        worst_reward = abs(worst_target - worst_entry)
        worst_r = worst_reward / worst_risk if worst_risk > 0 else 0.0

        # ── Fill quality assessment ────────────────────────────
        if effective_r >= original_r * 0.85:
            fill_quality = "GOOD"
        elif effective_r >= original_r * 0.65:
            fill_quality = "ACCEPTABLE"
        elif effective_r > 0:
            fill_quality = "POOR"
        else:
            fill_quality = "UNVIABLE"

        # R degradation warning
        r_degradation = 1.0 - (effective_r / original_r) if original_r > 0 else 1.0

        result = {
            "original": {
                "entry": round(entry_price, 6),
                "stop": round(stop_price, 6),
                "target": round(target_price, 6),
                "r_multiple": round(original_r, 4),
            },
            "effective": {
                "entry": round(effective_entry, 6),
                "stop": round(effective_stop, 6),
                "target": round(effective_target, 6),
                "r_multiple": round(effective_r, 4),
            },
            "worst_case": {
                "entry": round(worst_entry, 6),
                "stop": round(worst_stop, 6),
                "target": round(worst_target, 6),
                "r_multiple": round(worst_r, 4),
            },
            "slippage": {
                "spread": round(spread, 6),
                "vol_component": round(vol_slippage, 6),
                "total": round(total_slippage, 6),
                "pct_of_entry": round(total_slippage / entry_price * 100, 4),
            },
            "fill_quality": fill_quality,
            "r_degradation_pct": round(r_degradation * 100, 2),
            "status": "SIMULATED",
        }

        self.logger.debug(
            f"Slippage: {total_slippage:.4f} ({fill_quality}) | "
            f"R: {original_r:.2f} → {effective_r:.2f} ({r_degradation:.1%} degradation)"
        )

        return result

    def _empty_result(self, status: str) -> Dict[str, Any]:
        return {
            "original": {"entry": 0, "stop": 0, "target": 0, "r_multiple": 0},
            "effective": {"entry": 0, "stop": 0, "target": 0, "r_multiple": 0},
            "worst_case": {"entry": 0, "stop": 0, "target": 0, "r_multiple": 0},
            "slippage": {"spread": 0, "vol_component": 0, "total": 0, "pct_of_entry": 0},
            "fill_quality": "UNVIABLE",
            "r_degradation_pct": 100.0,
            "status": status,
        }
