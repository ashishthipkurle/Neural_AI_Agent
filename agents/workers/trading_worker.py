"""
INDRA OS — Trading Agent Worker

Wraps the existing trading infrastructure as a BaseAgent.
Handles stock analysis, order placement, portfolio management,
and market alerts. Adds confirmation safety for real trades.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.Trading")

_STRONG_SIGNALS = [
    "buy", "sell", "trade", "stock", "share", "portfolio",
    "market", "nifty", "sensex", "reliance", "tata", "infosys",
    "price of", "stop loss", "position", "holdings", "watchlist",
    "place order", "cancel order", "check balance",
    "backtest", "strategy", "signal", "indicator",
    "profit", "loss", "returns",
]

_MEDIUM_SIGNALS = [
    "invest", "trading", "broker", "upstox", "zerodha",
    "candlestick", "chart", "analysis", "bullish", "bearish",
    "support", "resistance", "volume", "ema", "rsi", "macd",
]


class TradingWorker(BaseAgent):
    """
    Trading agent — market analysis, order management, portfolio tracking.
    Wraps existing trading infrastructure with safety confirmations.
    """

    def __init__(self, llm_func=None, speak_func=None):
        super().__init__(
            name="trading",
            description="Stock trading — buy/sell orders, portfolio management, market analysis, alerts",
            capabilities=[
                "buy_stock", "sell_stock", "check_portfolio",
                "analyze_market", "set_alert", "backtest_strategy",
                "get_price", "market_overview", "watchlist",
            ],
        )
        self._llm = llm_func
        self._speak = speak_func
        self._chat_agent = None
        self._broker = None
        self._order_manager = None

    async def initialize(self) -> bool:
        """Load trading subsystems."""
        try:
            from agent.trading.trading_chat_agent import TradingChatAgent
            self._chat_agent = TradingChatAgent

            # Try loading broker adapter
            try:
                from agent.trading.broker_adapter import BrokerAdapter
                self._broker = BrokerAdapter
                logger.info("Broker adapter loaded")
            except Exception as e:
                logger.warning(f"Broker adapter unavailable: {e}")

            try:
                from agent.trading.order_manager import OrderManager
                self._order_manager = OrderManager
            except Exception as e:
                logger.warning(f"Order manager unavailable: {e}")

            self.status = self.status.IDLE
            logger.info("Trading agent initialized")
            return True

        except ImportError as e:
            logger.warning(f"Trading imports partial: {e}")
            self.status = self.status.IDLE
            return True  # Still functional for LLM-based analysis

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()
        if any(s in lower for s in _STRONG_SIGNALS):
            return 0.93
        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.7
        return 0.05

    async def execute(self, task: Task) -> TaskResult:
        """Handle a trading task."""
        steps_taken = []

        try:
            # Classify trading intent
            intent = self._classify_trading_intent(task.description)
            steps_taken.append(f"Intent: {intent}")

            await self.publish_progress(0.2, f"Processing: {intent}", 0, 3)

            if intent == "order":
                return await self._handle_order(task, steps_taken)
            elif intent == "analysis":
                return await self._handle_analysis(task, steps_taken)
            elif intent == "portfolio":
                return await self._handle_portfolio(task, steps_taken)
            else:
                return await self._handle_general_trading(task, steps_taken)

        except Exception as e:
            logger.error(f"Trading agent error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Trading task failed",
                error=str(e),
                steps_taken=steps_taken,
            )

    def _classify_trading_intent(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["buy", "sell", "place order", "cancel order"]):
            return "order"
        if any(w in lower for w in ["portfolio", "holdings", "position", "balance"]):
            return "portfolio"
        if any(w in lower for w in ["analyze", "analysis", "chart", "price", "signal"]):
            return "analysis"
        return "general"

    async def _handle_order(self, task: Task, steps_taken: list) -> TaskResult:
        """Handle buy/sell orders with safety confirmation."""
        await self.publish_progress(0.3, "Parsing order details...", 1, 3)

        # Parse order from natural language using LLM
        order = await self._parse_order(task.description)
        steps_taken.append(f"Parsed order: {order}")

        if not order:
            return TaskResult(
                task_id=task.id, success=False,
                output="I couldn't understand the order details, sir.",
                error="Failed to parse order",
                steps_taken=steps_taken,
            )

        # SAFETY: Always confirm before executing
        confirm_msg = (
            f"Sir, I'm about to {order.get('action', 'trade')} "
            f"{order.get('quantity', '?')} shares of {order.get('symbol', '?')} "
            f"at {order.get('price_type', 'market')} price. "
            f"Shall I proceed?"
        )

        if self._speak:
            self._speak(confirm_msg)

        steps_taken.append(f"Awaiting confirmation: {confirm_msg}")

        # For now, return the confirmation request
        # Real execution would wait for user approval via message bus
        return TaskResult(
            task_id=task.id, success=True,
            output=confirm_msg,
            steps_taken=steps_taken,
        )

    async def _handle_analysis(self, task: Task, steps_taken: list) -> TaskResult:
        """Market analysis using LLM."""
        await self.publish_progress(0.5, "Analyzing...", 1, 2)

        if self._llm:
            prompt = (
                f"You are a professional stock market analyst for the Indian market (NSE/BSE). "
                f"Analyze this request: {task.description}\n\n"
                f"Provide a concise but insightful analysis with actionable points."
            )
            response = await self._llm(prompt)

            if self._speak:
                self._speak(response[:300])

            return TaskResult(
                task_id=task.id, success=True,
                output=response,
                steps_taken=steps_taken + ["Generated market analysis"],
            )

        return TaskResult(
            task_id=task.id, success=False,
            output="Analysis unavailable — no LLM", error="No LLM",
            steps_taken=steps_taken,
        )

    async def _handle_portfolio(self, task: Task, steps_taken: list) -> TaskResult:
        """Portfolio/holdings query."""
        if self._llm:
            response = await self._llm(
                f"The user asked about their portfolio: {task.description}\n"
                "Since we don't have live portfolio data connected yet, "
                "explain what information you'd need and suggest next steps."
            )
            if self._speak:
                self._speak(response[:200])
            return TaskResult(
                task_id=task.id, success=True,
                output=response, steps_taken=steps_taken,
            )
        return TaskResult(
            task_id=task.id, success=False,
            output="Portfolio data unavailable", error="No broker connection",
            steps_taken=steps_taken,
        )

    async def _handle_general_trading(self, task: Task, steps_taken: list) -> TaskResult:
        """General trading questions."""
        if self._llm:
            response = await self._llm(
                f"You are a trading expert. Answer: {task.description}"
            )
            if self._speak:
                self._speak(response[:300])
            return TaskResult(
                task_id=task.id, success=True,
                output=response, steps_taken=steps_taken,
            )
        return TaskResult(
            task_id=task.id, success=False,
            output="No LLM available", error="No LLM",
            steps_taken=steps_taken,
        )

    async def _parse_order(self, text: str) -> Optional[dict]:
        """Parse natural language into structured order."""
        if not self._llm:
            return None
        try:
            prompt = (
                f"Parse this trading order into JSON: \"{text}\"\n\n"
                'Return: {"action": "buy|sell", "symbol": "RELIANCE", '
                '"quantity": 10, "price_type": "market|limit", "price": null}'
            )
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            return json.loads(response)
        except Exception:
            return None
