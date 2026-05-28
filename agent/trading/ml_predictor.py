"""
ML Price Prediction Engine.

Uses the 15-dimensional feature vector from FeatureEngine to predict:
    1. Next candle direction (UP / DOWN)
    2. Expected magnitude (% move)
    3. Confidence score (0-1)

Model: Gradient Boosting Classifier + Regressor (scikit-learn)
Training: Rolling window of recent candles, auto-retrain every N bars.

Integration:
    - Called from the /api/trading/indicators endpoint
    - Results rendered as prediction markers on the CandlestickChart

No LLM. Fully deterministic (given the same data).
"""

import time
import math
import logging
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from agent.trading.feature_engine import FeatureEngine, FEATURE_NAMES

# ── Try to import scikit-learn ──
try:
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    np = None


class MLPredictor:
    """
    Gradient Boosting price direction predictor.

    Features → {direction, magnitude, confidence, entry, stop, target}

    Usage:
        predictor = MLPredictor()
        prediction = predictor.predict(closes, highs, lows, volumes, opens)
    """

    # ── Tuning ──
    MIN_TRAIN_SAMPLES = 100       # Minimum bars needed to train
    RETRAIN_INTERVAL = 50         # Retrain every N new candles
    LOOKFORWARD = 3               # Predict N candles ahead
    TRAIN_WINDOW = 500            # Max training window size
    MODEL_DIR = Path("data/models")

    def __init__(self) -> None:
        self.logger = logging.getLogger("MLPredictor")
        self.feature_engine = FeatureEngine(window_size=50)

        # Models
        self._clf: Optional[Any] = None     # Direction classifier
        self._reg: Optional[Any] = None     # Magnitude regressor
        self._scaler: Optional[Any] = None  # Feature scaler

        # State tracking
        self._last_train_count = 0
        self._train_accuracy = 0.0
        self._is_trained = False

        # Cache
        self._last_prediction: Optional[Dict] = None
        self._last_predict_time = 0.0

        if not SKLEARN_AVAILABLE:
            self.logger.warning("scikit-learn not installed — ML predictions disabled")

    # ═══════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════

    def predict(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        opens: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a prediction for the NEXT candle(s).

        Returns dict with:
            direction: 'UP' or 'DOWN'
            confidence: 0.0 - 1.0
            magnitude: expected % move
            entry_price: suggested entry
            stop_price: suggested stop loss
            target_price: suggested target
            features_used: feature importance ranking
            model_accuracy: training accuracy
        """
        if not SKLEARN_AVAILABLE:
            return None

        n = len(closes)
        if n < self.MIN_TRAIN_SAMPLES:
            return None

        # Throttle: don't predict more than once per second
        now = time.time()
        if now - self._last_predict_time < 1.0 and self._last_prediction:
            return self._last_prediction

        # ── Auto-retrain if needed ──
        if not self._is_trained or (n - self._last_train_count) >= self.RETRAIN_INTERVAL:
            self._train(closes, highs, lows, volumes, opens)

        if not self._is_trained:
            return None

        # ── Extract features for current bar ──
        features = self.feature_engine.extract_features(
            closes, highs, lows, volumes, opens
        )
        if not features:
            return None

        try:
            X = np.array([features["vector"]])
            X_scaled = self._scaler.transform(X)

            # Direction prediction
            direction_proba = self._clf.predict_proba(X_scaled)[0]
            predicted_class = self._clf.predict(X_scaled)[0]
            direction = "UP" if predicted_class == 1 else "DOWN"

            # Confidence = probability of the predicted class
            confidence = float(max(direction_proba))

            # Magnitude prediction (absolute % move)
            magnitude = float(abs(self._reg.predict(X_scaled)[0]))

            # ── Generate entry/stop/target from prediction ──
            current_price = closes[-1]
            atr = self._estimate_atr(highs, lows, closes)

            if direction == "UP":
                entry_price = current_price
                stop_price = current_price - atr * 1.5
                target_price = current_price + (current_price * magnitude / 100)
                # Ensure target is at least 2x the risk
                risk = entry_price - stop_price
                if risk > 0:
                    target_price = max(target_price, entry_price + risk * 2)
            else:
                entry_price = current_price
                stop_price = current_price + atr * 1.5
                target_price = current_price - (current_price * magnitude / 100)
                risk = stop_price - entry_price
                if risk > 0:
                    target_price = min(target_price, entry_price - risk * 2)

            # ── Feature importance ──
            importances = self._clf.feature_importances_
            top_features = sorted(
                zip(FEATURE_NAMES, importances),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            prediction = {
                "direction": direction,
                "confidence": round(confidence, 3),
                "magnitude": round(magnitude, 4),
                "entry_price": round(entry_price, 2),
                "stop_price": round(stop_price, 2),
                "target_price": round(target_price, 2),
                "model_accuracy": round(self._train_accuracy, 3),
                "top_features": [
                    {"name": name, "importance": round(imp, 3)}
                    for name, imp in top_features
                ],
                "lookforward": self.LOOKFORWARD,
                "trained_on": self._last_train_count,
            }

            self._last_prediction = prediction
            self._last_predict_time = now
            return prediction

        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    # TRAINING
    # ═══════════════════════════════════════════════════════════

    def _train(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        opens: Optional[List[float]] = None,
    ) -> None:
        """Train on a rolling window of historical data."""
        n = len(closes)
        if n < self.MIN_TRAIN_SAMPLES + self.LOOKFORWARD:
            return

        self.logger.info(f"Training ML model on {n} candles...")
        start = time.time()

        try:
            # ── Build training dataset ──
            X_list = []
            y_dir = []   # 1 = UP, 0 = DOWN
            y_mag = []   # magnitude (% change)

            # Use a window for training, leave last LOOKFORWARD for prediction
            train_end = n - self.LOOKFORWARD
            train_start = max(self.feature_engine.window_size, train_end - self.TRAIN_WINDOW)

            for i in range(train_start, train_end):
                # Extract features using data up to index i
                feat = self.feature_engine.extract_features(
                    closes[:i + 1],
                    highs[:i + 1],
                    lows[:i + 1],
                    volumes[:i + 1],
                    opens[:i + 1] if opens else None,
                )
                if feat is None:
                    continue

                # Label: what happened LOOKFORWARD candles later?
                future_idx = min(i + self.LOOKFORWARD, n - 1)
                future_price = closes[future_idx]
                current_price = closes[i]

                if current_price <= 0:
                    continue

                pct_change = (future_price - current_price) / current_price * 100
                direction = 1 if pct_change > 0 else 0

                X_list.append(feat["vector"])
                y_dir.append(direction)
                y_mag.append(abs(pct_change))

            if len(X_list) < self.MIN_TRAIN_SAMPLES:
                self.logger.warning(f"Insufficient training samples: {len(X_list)}")
                return

            X = np.array(X_list)
            y_direction = np.array(y_dir)
            y_magnitude = np.array(y_mag)

            # ── Scale features ──
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # ── Train direction classifier ──
            self._clf = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                min_samples_leaf=10,
                subsample=0.8,
                random_state=42,
            )
            self._clf.fit(X_scaled, y_direction)

            # ── Train magnitude regressor ──
            self._reg = GradientBoostingRegressor(
                n_estimators=80,
                max_depth=3,
                learning_rate=0.1,
                min_samples_leaf=10,
                subsample=0.8,
                random_state=42,
            )
            self._reg.fit(X_scaled, y_magnitude)

            # ── Evaluate on training data ──
            train_preds = self._clf.predict(X_scaled)
            self._train_accuracy = float(np.mean(train_preds == y_direction))
            self._is_trained = True
            self._last_train_count = n

            elapsed = time.time() - start
            self.logger.info(
                f"ML model trained: {len(X_list)} samples, "
                f"accuracy={self._train_accuracy:.1%}, "
                f"time={elapsed:.1f}s"
            )

        except Exception as e:
            self.logger.error(f"Training failed: {e}", exc_info=True)
            self._is_trained = False

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _estimate_atr(
        highs: List[float], lows: List[float], closes: List[float],
        period: int = 14
    ) -> float:
        """Calculate Average True Range for stop/target sizing."""
        if len(highs) < period + 1:
            return abs(highs[-1] - lows[-1]) if highs else 0

        trs = []
        for i in range(-period, 0):
            h = highs[i]
            l = lows[i]
            pc = closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)

        return sum(trs) / len(trs) if trs else 0

    def get_status(self) -> Dict[str, Any]:
        """Return current model status for System Health display."""
        return {
            "available": SKLEARN_AVAILABLE,
            "trained": self._is_trained,
            "accuracy": round(self._train_accuracy, 3) if self._is_trained else 0,
            "trained_on_bars": self._last_train_count,
            "retrain_interval": self.RETRAIN_INTERVAL,
            "lookforward": self.LOOKFORWARD,
        }
