"""
Database Schema Definitions.

ORM-agnostic dataclass schemas + raw SQL generation for:
    - instruments (global market universe)
    - candles (OHLCV time series)
    - pattern_features (sliding window feature vectors)
    - pattern_outcomes (forward outcomes per pattern)

Designed for TimescaleDB/ClickHouse at scale.
Pure Python — no heavy ORM dependency.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


# ══════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════

class AssetType(Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"


class Timeframe(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


# ══════════════════════════════════════════════════════════════
# INSTRUMENTS TABLE
# ══════════════════════════════════════════════════════════════

@dataclass
class Instrument:
    """Single tradable instrument in the global universe."""
    symbol: str
    exchange: str
    asset_type: str             # AssetType.value
    sector: str = ""
    liquidity_score: float = 0.0
    avg_daily_volume: float = 0.0
    market_cap: float = 0.0
    volatility_30d: float = 0.0
    active: bool = True
    instrument_id: int = 0      # Auto-assigned

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
# CANDLES TABLE
# ══════════════════════════════════════════════════════════════

@dataclass
class Candle:
    """Single OHLCV candle."""
    instrument_id: int
    timeframe: str
    timestamp: int              # Unix epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body_ratio(self) -> float:
        """Body size relative to total range."""
        total = self.high - self.low
        if total <= 0:
            return 0.0
        return abs(self.close - self.open) / total

    @property
    def upper_wick_ratio(self) -> float:
        total = self.high - self.low
        if total <= 0:
            return 0.0
        top = max(self.open, self.close)
        return (self.high - top) / total

    @property
    def lower_wick_ratio(self) -> float:
        total = self.high - self.low
        if total <= 0:
            return 0.0
        bottom = min(self.open, self.close)
        return (bottom - self.low) / total


# ══════════════════════════════════════════════════════════════
# PATTERN FEATURES TABLE
# ══════════════════════════════════════════════════════════════

@dataclass
class PatternFeature:
    """Feature vector extracted from a sliding window of candles."""
    pattern_id: str
    instrument_id: int
    timeframe: str
    window_end_timestamp: int
    candle_index: int           # Position in candle series
    regime_bucket: str = "UNKNOWN"
    volatility_bucket: str = "UNKNOWN"

    # 15-dimensional normalized feature vector
    feature_vector: List[float] = field(default_factory=list)

    # Feature labels (for auditability)
    feature_names: List[str] = field(default_factory=lambda: [
        "ema20_slope", "ema50_slope", "ema200_alignment", "adx",
        "rsi", "rsi_slope", "macd_delta",
        "atr_percentile", "bband_width_pct", "vol_compression",
        "volume_spike", "obv_slope",
        "vwap_distance", "body_ratio", "wick_ratio",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
# PATTERN OUTCOMES TABLE
# ══════════════════════════════════════════════════════════════

@dataclass
class PatternOutcome:
    """Forward outcomes computed for a pattern's prediction horizon."""
    pattern_id: int             # Matches BIGSERIAL from pattern_features
    future_return: float        # % return over horizon
    max_drawdown: float         # Worst peak-to-trough over horizon
    max_runup: float            # Best trough-to-peak over horizon
    r_multiple: float           # Reward/risk ratio achieved


# ══════════════════════════════════════════════════════════════
# SQL GENERATION
# ══════════════════════════════════════════════════════════════

SQL_SCHEMA = """
-- Instruments table (global universe)
CREATE TABLE IF NOT EXISTS instruments (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    asset_type VARCHAR(20) NOT NULL,
    sector VARCHAR(50) DEFAULT '',
    liquidity_score DOUBLE PRECISION DEFAULT 0.0,
    avg_daily_volume DOUBLE PRECISION DEFAULT 0.0,
    market_cap DOUBLE PRECISION DEFAULT 0.0,
    volatility_30d DOUBLE PRECISION DEFAULT 0.0,
    active BOOLEAN DEFAULT TRUE,
    UNIQUE (symbol, exchange)
);

CREATE INDEX idx_instruments_type ON instruments (asset_type);
CREATE INDEX idx_instruments_liquidity ON instruments (liquidity_score DESC);
CREATE INDEX idx_instruments_active ON instruments (active);

-- Candles table (OHLCV time series — partition ready)
CREATE TABLE IF NOT EXISTS candles (
    instrument_id BIGINT NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION DEFAULT 0.0,
    PRIMARY KEY (instrument_id, timeframe, timestamp)
);

CREATE INDEX idx_candles_lookup ON candles (instrument_id, timeframe, timestamp DESC);

-- Pattern features table (sliding window vectors)
CREATE TABLE IF NOT EXISTS pattern_features (
    pattern_id BIGSERIAL PRIMARY KEY,
    instrument_id BIGINT NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    regime_bucket VARCHAR(20) NOT NULL,
    volatility_bucket VARCHAR(20) NOT NULL,
    feature_vector VECTOR(15) NOT NULL
);

CREATE INDEX idx_patterns_tf_regime_vol ON pattern_features (timeframe, regime_bucket, volatility_bucket);

-- Pattern outcomes table (forward-looking results)
CREATE TABLE IF NOT EXISTS pattern_outcomes (
    pattern_id BIGINT PRIMARY KEY,
    future_return DOUBLE PRECISION NOT NULL,
    max_drawdown DOUBLE PRECISION NOT NULL,
    max_runup DOUBLE PRECISION NOT NULL,
    r_multiple DOUBLE PRECISION NOT NULL
);
"""

def get_schema_sql() -> str:
    """Return full SQL schema for database setup."""
    return SQL_SCHEMA
