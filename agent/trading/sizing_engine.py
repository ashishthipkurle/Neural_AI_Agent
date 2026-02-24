"""
Portfolio Position Sizing Engine — Fractional Kelly + Volatility Adjusted.

Formula:
    f* = (b*p - q) / b
    position_size = f* × 0.25 (quarter-Kelly)
    vol_adjust = target_volatility / asset_volatility
    final_size = position_size × vol_adjust

Capped at portfolio max risk per trade.

No LLM. Fully deterministic.
"""
import logging
from typing import Dict, Any


class SizingEngine:
    """
    Institutional position sizing with fractional Kelly and volatility adjustment.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        max_position_pct: float = 0.10,
        target_volatility: float = 0.15,
        max_portfolio_risk_pct: float = 0.02,
    ) -> None:
        """
        Args:
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter-Kelly)
            max_position_pct: Maximum position size as % of portfolio (0.10 = 10%)
            target_volatility: Target annualized portfolio volatility (0.15 = 15%)
            max_portfolio_risk_pct: Max risk per trade as % of portfolio (0.02 = 2%)
        """
        self.logger = logging.getLogger("SizingEngine")
        self.kelly_fraction = kelly_fraction
        self.max_position_pct = max_position_pct
        self.target_volatility = target_volatility
        self.max_portfolio_risk_pct = max_portfolio_risk_pct

    def calculate_size(
        self,
        win_probability: float,
        reward_risk_ratio: float,
        asset_volatility: float,
        portfolio_value: float,
        confidence_action: str = "ALLOW",
        regime_multiplier: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate position size using Fractional Kelly + Volatility Adjustment.

        Args:
            win_probability: Estimated probability of winning (0–1), derived from confidence
            reward_risk_ratio: Target/Stop ratio (e.g., 2.0 means 2:1 R:R)
            asset_volatility: Asset's annualized volatility (e.g., 0.30 = 30%)
            portfolio_value: Total portfolio value in currency units
            confidence_action: "ALLOW", "REDUCE", or "BLOCK" from confidence engine
            regime_multiplier: Scaling factor from regime engine (0–1)

        Returns:
            dict with position_size_pct, position_size_units, kelly_raw, vol_adjust, etc.
        """
        # ── Guard: Blocked signals get zero size ───────────────
        if confidence_action == "BLOCK":
            return self._build_result(
                0.0, 0.0, 0.0, 0.0, portfolio_value, "BLOCKED_BY_CONFIDENCE"
            )

        if win_probability <= 0 or reward_risk_ratio <= 0:
            return self._build_result(
                0.0, 0.0, 0.0, 0.0, portfolio_value, "INVALID_INPUTS"
            )

        # ── Step 1: Raw Kelly Criterion ────────────────────────
        # f* = (b*p - q) / b
        b = reward_risk_ratio
        p = min(max(win_probability, 0.0), 1.0)
        q = 1.0 - p

        kelly_raw = (b * p - q) / b

        if kelly_raw <= 0:
            return self._build_result(
                0.0, kelly_raw, 0.0, 0.0, portfolio_value, "NEGATIVE_EDGE"
            )

        # ── Step 2: Apply Fractional Kelly ─────────────────────
        position_kelly = kelly_raw * self.kelly_fraction

        # ── Step 3: Volatility Adjustment ──────────────────────
        if asset_volatility > 0:
            vol_adjust = self.target_volatility / asset_volatility
        else:
            vol_adjust = 1.0

        position_vol_adjusted = position_kelly * vol_adjust

        # ── Step 4: Regime Adjustment ──────────────────────────
        position_regime = position_vol_adjusted * regime_multiplier

        # ── Step 5: Confidence Reduction ───────────────────────
        if confidence_action == "REDUCE":
            position_regime *= 0.5  # Half size for low confidence

        # ── Step 6: Cap at maximum limits ──────────────────────
        final_pct = min(position_regime, self.max_position_pct)
        final_pct = min(final_pct, self.max_portfolio_risk_pct * b)  # Risk-adjusted cap
        final_pct = max(final_pct, 0.0)

        return self._build_result(
            final_pct, kelly_raw, vol_adjust, regime_multiplier,
            portfolio_value, "SIZED"
        )

    def _build_result(
        self, size_pct: float, kelly_raw: float, vol_adjust: float,
        regime_mult: float, portfolio_value: float, status: str
    ) -> Dict[str, Any]:
        """Construct the sizing result dict."""
        size_units = size_pct * portfolio_value

        self.logger.debug(
            f"Sizing: {size_pct:.4%} of {portfolio_value:.0f} = {size_units:.2f} | "
            f"kelly_raw={kelly_raw:.4f} vol_adj={vol_adjust:.3f} | {status}"
        )

        return {
            "position_size_pct": round(size_pct, 6),
            "position_size_units": round(size_units, 2),
            "kelly_raw": round(kelly_raw, 6),
            "kelly_fractional": round(kelly_raw * self.kelly_fraction, 6),
            "vol_adjust": round(vol_adjust, 4),
            "regime_multiplier": round(regime_mult, 4),
            "max_position_pct": self.max_position_pct,
            "max_risk_pct": self.max_portfolio_risk_pct,
            "status": status,
        }
