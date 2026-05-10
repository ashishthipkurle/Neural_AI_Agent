"""
Trading Chat Copilot.

Chat may:
    - Explain bias (per-timeframe + fused)
    - Explain confidence (factor breakdown)
    - Explain regime (current + history)
    - Explain sizing (Kelly + vol adjust)
    - Explain risk mode (triggers)
    - Provide screener results

Chat MUST reference deterministic numeric outputs.
Never fabricate numbers. Read from engine state only.
"""
import logging
from typing import Dict, Any, Optional


class TradingChatAgent:
    """
    Analytical copilot that references engine state.
    All responses are grounded in deterministic engine outputs.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("TradingChatAgent")
        self._engine_state: Dict[str, Any] = {}

    def update_state(
        self,
        regime: Optional[Dict[str, Any]] = None,
        bias: Optional[Dict[str, Any]] = None,
        fusion: Optional[Dict[str, Any]] = None,
        confidence: Optional[Dict[str, Any]] = None,
        sizing: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        lifecycle: Optional[Dict[str, Any]] = None,
        screener: Optional[list] = None,
        structure: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the copilot's view of current engine state."""
        if regime:
            self._engine_state["regime"] = regime
        if bias:
            self._engine_state["bias"] = bias
        if fusion:
            self._engine_state["fusion"] = fusion
        if confidence:
            self._engine_state["confidence"] = confidence
        if sizing:
            self._engine_state["sizing"] = sizing
        if risk:
            self._engine_state["risk"] = risk
        if lifecycle:
            self._engine_state["lifecycle"] = lifecycle
        if screener:
            self._engine_state["screener"] = screener
        if structure:
            self._engine_state["structure"] = structure

    def handle_query(self, query: str) -> Dict[str, Any]:
        """
        Process a user query and return a grounded response using the AI LLM.

        Args:
            query: Natural language question about current market state

        Returns:
            dict with response text, referenced data, and source engine
        """
        try:
            import openai
            
            # Gather current deterministic engine state
            state_summary_dict = self._full_summary()
            state_summary = state_summary_dict.get("response", "No engine state available yet.")
            
            # Setup the LLM via Ollama using standard OpenAI client
            client = openai.OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"
            )
            
            # Construct the prompt
            system_prompt = (
                "You are Neural, Ashish's personal trading copilot.\n"
                "You're knowledgeable, friendly, and talk like a sharp trader friend.\n"
                "Use the engine data below to answer — don't make up numbers.\n"
                "Keep it conversational. If there's no data, just say so naturally.\n"
                "If greeted, greet back warmly.\n\n"
                f"=== CURRENT ENGINE STATE ===\n{state_summary}\n============================"
            )
            
            # Generate response
            response = client.chat.completions.create(
                model="qwen3-coder:480b-cloud",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.3
            )
            
            return {
                "response": response.choices[0].message.content,
                "source": "Ollama LLM",
                "data": self._engine_state
            }
            
        except Exception as e:
            self.logger.error(f"LLM Chat Error (OpenAI client): {e}", exc_info=True)
            
            # Fallback to the old router if the LLM fails or is unavailable
            query_lower = query.lower().strip()
            if any(k in query_lower for k in ["bias", "direction", "bullish", "bearish"]):
                return self._explain_bias()
            elif any(k in query_lower for k in ["confidence", "score", "quality"]):
                return self._explain_confidence()
            elif any(k in query_lower for k in ["regime", "market type", "market mode"]):
                return self._explain_regime()
            elif any(k in query_lower for k in ["size", "position", "kelly", "allocation"]):
                return self._explain_sizing()
            elif any(k in query_lower for k in ["risk", "drawdown", "halt", "mode"]):
                return self._explain_risk()
            elif any(k in query_lower for k in ["screen", "scan", "top", "best", "rank"]):
                return self._explain_screener()
            elif any(k in query_lower for k in ["signal", "trade", "active", "lifecycle"]):
                return self._explain_signals()
            elif any(k in query_lower for k in ["structure", "support", "resistance", "pattern"]):
                return self._explain_structure()
            elif any(k in query_lower for k in ["summary", "overview", "status", "everything"]):
                return self._full_summary()
            else:
                return {
                    "response": (
                        "I can explain: bias, confidence, regime, sizing, risk mode, "
                        "screener results, active signals, or structure. What would you like to know?"
                    ),
                    "source": "ROUTER_FALLBACK",
                    "data": {},
                }

    def _explain_bias(self) -> Dict[str, Any]:
        bias = self._engine_state.get("bias", {})
        fusion = self._engine_state.get("fusion", {})

        if not fusion:
            return {"response": "No bias data available yet. Waiting for analysis.", "source": "bias_engine", "data": {}}

        response = (
            f"**Directional Bias**: {fusion.get('fusion_label', 'N/A')} "
            f"(score: {fusion.get('fusion_score', 0):.2f})\n\n"
            f"• HTF (1h/4h) average: {fusion.get('htf_score', 0):.2f}\n"
            f"• LTF (1m/5m/15m) average: {fusion.get('ltf_score', 0):.2f}\n"
            f"• HTF override active: {'Yes' if fusion.get('override_active') else 'No'}\n"
        )
        breakdown = fusion.get("timeframe_breakdown", {})
        if breakdown:
            response += "\nPer-timeframe:\n"
            for tf, score in breakdown.items():
                response += f"  {tf}: {score:+.2f}\n"

        return {"response": response, "source": "mtf_fusion_engine", "data": fusion}

    def _explain_confidence(self) -> Dict[str, Any]:
        conf = self._engine_state.get("confidence", {})
        if not conf:
            return {"response": "No confidence data available yet.", "source": "confidence_engine", "data": {}}

        factors = conf.get("factors", {})
        response = (
            f"**Confidence Score**: {conf.get('confidence_score', 0):.3f} "
            f"(Action: {conf.get('action', 'N/A')})\n\n"
            f"Factor Breakdown:\n"
        )
        for name, value in factors.items():
            response += f"  • {name}: {value:.3f}\n"
        response += f"\nRegime adjustment: {conf.get('regime', 'N/A')}"

        return {"response": response, "source": "confidence_engine", "data": conf}

    def _explain_regime(self) -> Dict[str, Any]:
        regime = self._engine_state.get("regime", {})
        if not regime:
            return {"response": "No regime data available yet.", "source": "regime_engine", "data": {}}

        response = (
            f"**Market Regime**: {regime.get('current_regime', 'N/A')}\n\n"
            f"• Regime stable: {'Yes' if regime.get('is_stable') else 'No'}\n"
            f"• Risk multiplier: {regime.get('risk_multiplier', 1.0):.2f}\n"
        )
        return {"response": response, "source": "regime_engine", "data": regime}

    def _explain_sizing(self) -> Dict[str, Any]:
        sizing = self._engine_state.get("sizing", {})
        if not sizing:
            return {"response": "No sizing data available yet.", "source": "sizing_engine", "data": {}}

        response = (
            f"**Position Sizing**: {sizing.get('status', 'N/A')}\n\n"
            f"• Size: {sizing.get('position_size_pct', 0):.4%} of portfolio\n"
            f"• Kelly raw: {sizing.get('kelly_raw', 0):.4f}\n"
            f"• Kelly fractional: {sizing.get('kelly_fractional', 0):.4f}\n"
            f"• Vol adjustment: {sizing.get('vol_adjust', 1):.3f}\n"
            f"• Regime multiplier: {sizing.get('regime_multiplier', 1):.3f}\n"
        )
        return {"response": response, "source": "sizing_engine", "data": sizing}

    def _explain_risk(self) -> Dict[str, Any]:
        risk = self._engine_state.get("risk", {})
        if not risk:
            return {"response": "No risk data available yet.", "source": "risk_engine", "data": {}}

        response = (
            f"**Risk Mode**: {risk.get('mode', 'N/A')}\n\n"
            f"• R multiplier: {risk.get('r_multiplier', 1.0):.2f}\n"
            f"• Signals allowed: {'Yes' if risk.get('signals_allowed') else 'NO — HALTED'}\n"
        )
        if risk.get("halted_reason"):
            response += f"• Halt reason: {risk['halted_reason']}\n"

        return {"response": response, "source": "risk_engine", "data": risk}

    def _explain_screener(self) -> Dict[str, Any]:
        screener = self._engine_state.get("screener", [])
        if not screener:
            return {"response": "No screener data available yet.", "source": "screener_engine", "data": {}}

        response = "**Market Screener — Top Assets**:\n\n"
        for i, asset in enumerate(screener, 1):
            response += (
                f"{i}. **{asset.get('asset', '?')}** — "
                f"Score: {asset.get('total_score', 0):.3f}\n"
            )
        return {"response": response, "source": "screener_engine", "data": screener}

    def _explain_signals(self) -> Dict[str, Any]:
        lifecycle = self._engine_state.get("lifecycle", {})
        if not lifecycle:
            return {"response": "No active signals.", "source": "lifecycle_engine", "data": {}}

        response = (
            f"**Signal Status**:\n"
            f"• Active: {lifecycle.get('active_count', 0)}\n"
            f"• Completed: {lifecycle.get('completed_count', 0)}\n"
        )
        return {"response": response, "source": "lifecycle_engine", "data": lifecycle}

    def _explain_structure(self) -> Dict[str, Any]:
        structure = self._engine_state.get("structure", {})
        if not structure:
            return {"response": "No structural analysis available yet.", "source": "structural_vision_engine", "data": {}}

        response = (
            f"**Chart Structure**:\n"
            f"• Pattern: {structure.get('pattern_type', 'unidentified')}\n"
            f"• Structure score: {structure.get('structure_score', 0):.3f}\n"
            f"• Supports: {structure.get('support_levels', [])}\n"
            f"• Resistances: {structure.get('resistance_levels', [])}\n"
        )
        return {"response": response, "source": "structural_vision_engine", "data": structure}

    def _full_summary(self) -> Dict[str, Any]:
        parts = []
        for handler in [
            self._explain_regime,
            self._explain_bias,
            self._explain_confidence,
            self._explain_risk,
            self._explain_signals,
        ]:
            result = handler()
            if result["data"]:
                parts.append(result["response"])

        if not parts:
            return {"response": "No engine data available yet. Waiting for first analysis.", "source": "summary", "data": {}}

        return {
            "response": "\n---\n".join(parts),
            "source": "summary",
            "data": self._engine_state,
        }
