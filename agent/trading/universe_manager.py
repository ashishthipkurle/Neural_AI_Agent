"""
Global Market Universe Manager.

Maintains a registry of all tradable instruments across:
    - Equities (all global exchanges)
    - Indices
    - Futures
    - Options
    - Forex
    - Crypto
    - Commodities

Filters by:
    - Liquidity score
    - Average daily volume
    - Volatility (30d)
    - Market cap
    - Asset type
    - Exchange
    - Sector
    - Active status

No LLM. Deterministic. Horizontally scalable.
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from agent.trading.db_schema import Instrument, AssetType


class UniverseManager:
    """
    In-memory instrument universe with multi-dimensional filtering.
    Can be backed by instruments table in TimescaleDB when deployed.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("UniverseManager")
        self._instruments: Dict[str, Instrument] = {}  # key = "SYMBOL:EXCHANGE"
        self._next_id = 1

    # ── Registration ───────────────────────────────────────────

    def add_instrument(
        self,
        symbol: str,
        exchange: str,
        asset_type: str,
        sector: str = "",
        liquidity_score: float = 0.0,
        avg_daily_volume: float = 0.0,
        market_cap: float = 0.0,
        volatility_30d: float = 0.0,
        active: bool = True,
    ) -> Instrument:
        """Register a new instrument in the universe."""
        key = f"{symbol}:{exchange}"

        inst = Instrument(
            instrument_id=self._next_id,
            symbol=symbol,
            exchange=exchange,
            asset_type=asset_type,
            sector=sector,
            liquidity_score=liquidity_score,
            avg_daily_volume=avg_daily_volume,
            market_cap=market_cap,
            volatility_30d=volatility_30d,
            active=active,
        )
        self._instruments[key] = inst
        self._next_id += 1

        self.logger.debug(f"Registered: {key} ({asset_type})")
        return inst

    def bulk_add(self, instruments: List[Dict[str, Any]]) -> int:
        """Bulk register instruments from list of dicts."""
        count = 0
        for data in instruments:
            try:
                self.add_instrument(**data)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to add instrument: {e}")
        self.logger.info(f"Bulk registered {count}/{len(instruments)} instruments")
        return count

    # ── Updates ────────────────────────────────────────────────

    def update_liquidity(self, symbol: str, exchange: str, score: float) -> bool:
        key = f"{symbol}:{exchange}"
        inst = self._instruments.get(key)
        if inst:
            inst.liquidity_score = score
            return True
        return False

    def update_volume(self, symbol: str, exchange: str, volume: float) -> bool:
        key = f"{symbol}:{exchange}"
        inst = self._instruments.get(key)
        if inst:
            inst.avg_daily_volume = volume
            return True
        return False

    def update_volatility(self, symbol: str, exchange: str, vol: float) -> bool:
        key = f"{symbol}:{exchange}"
        inst = self._instruments.get(key)
        if inst:
            inst.volatility_30d = vol
            return True
        return False

    def deactivate(self, symbol: str, exchange: str) -> bool:
        key = f"{symbol}:{exchange}"
        inst = self._instruments.get(key)
        if inst:
            inst.active = False
            return True
        return False

    # ── Queries ────────────────────────────────────────────────

    def get_instrument(self, symbol: str, exchange: str) -> Optional[Instrument]:
        return self._instruments.get(f"{symbol}:{exchange}")

    def get_universe(self, active_only: bool = True) -> List[Instrument]:
        """Get all instruments, optionally filtered to active only."""
        if active_only:
            return [i for i in self._instruments.values() if i.active]
        return list(self._instruments.values())

    def filter_by(
        self,
        asset_type: Optional[str] = None,
        exchange: Optional[str] = None,
        sector: Optional[str] = None,
        min_liquidity: float = 0.0,
        min_volume: float = 0.0,
        min_market_cap: float = 0.0,
        max_volatility: Optional[float] = None,
        min_volatility: Optional[float] = None,
        active_only: bool = True,
    ) -> List[Instrument]:
        """
        Multi-dimensional filter over the universe.

        All filters are AND-combined.
        Returns sorted by liquidity_score descending.
        """
        result = []
        for inst in self._instruments.values():
            if active_only and not inst.active:
                continue
            if asset_type and inst.asset_type != asset_type:
                continue
            if exchange and inst.exchange != exchange:
                continue
            if sector and inst.sector != sector:
                continue
            if inst.liquidity_score < min_liquidity:
                continue
            if inst.avg_daily_volume < min_volume:
                continue
            if inst.market_cap < min_market_cap:
                continue
            if max_volatility is not None and inst.volatility_30d > max_volatility:
                continue
            if min_volatility is not None and inst.volatility_30d < min_volatility:
                continue
            result.append(inst)

        result.sort(key=lambda x: x.liquidity_score, reverse=True)
        return result

    def get_by_type(self, asset_type: str) -> List[Instrument]:
        """Shortcut: get all instruments of a specific asset type."""
        return self.filter_by(asset_type=asset_type)

    def get_by_exchange(self, exchange: str) -> List[Instrument]:
        """Shortcut: get all instruments on a specific exchange."""
        return self.filter_by(exchange=exchange)

    def get_top_liquid(self, n: int = 50, asset_type: Optional[str] = None) -> List[Instrument]:
        """Get top N most liquid instruments."""
        filtered = self.filter_by(asset_type=asset_type)
        return filtered[:n]

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        all_inst = list(self._instruments.values())
        active = [i for i in all_inst if i.active]

        by_type: Dict[str, int] = {}
        by_exchange: Dict[str, int] = {}
        for i in active:
            by_type[i.asset_type] = by_type.get(i.asset_type, 0) + 1
            by_exchange[i.exchange] = by_exchange.get(i.exchange, 0) + 1

        return {
            "total_instruments": len(all_inst),
            "active_instruments": len(active),
            "by_asset_type": by_type,
            "by_exchange": by_exchange,
        }
