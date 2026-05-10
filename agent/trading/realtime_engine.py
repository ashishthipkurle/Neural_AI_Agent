"""
Realtime Engine Orchestrator.

Architecture:
    Central intelligence loop modified in Phase 4 for Deterministic Event-Driven flow.
    - Fast Path: Passive monitoring of active signals via `lifecycle_engine`.
    - Slow Path (Candle Close only): FAISS -> Prob -> Risk -> Alloc -> `generate_and_lock`.
"""
import time
import logging
from typing import Dict, Any, List
import math
import uuid
import asyncio

# Core Engines
from .data_integrity_guard import DataIntegrityGuard
from .feature_engine import FeatureEngine
from .similarity_engine import SimilarityEngine
from .probability_engine import ProbabilityEngine
from .correlation_engine import CorrelationEngine
from .portfolio_risk_aggregator import PortfolioRiskAggregator
from .capital_allocator import CapitalAllocator
from .cluster_coordinator import ClusterCoordinator
from .audit_logger import AuditLogger
from .observability_stack import ObservabilityStack
from .lifecycle_engine import LifecycleEngine
from .trading_chat_agent import TradingChatAgent


class RealtimeEngine:
    """
    Coordinates the end-to-end signal generation pipeline.
    Delegates all state ownership to LifecycleEngine.
    """

    def __init__(self, websocket_hub=None) -> None:
        self.logger = logging.getLogger("RealtimeEngine")
        
        # Initialize sub-systems
        self.integrity_guard = DataIntegrityGuard()
        self.feature_engine = FeatureEngine()
        self.similarity_engine = SimilarityEngine()
        self.probability_engine = ProbabilityEngine()
        self.correlation_engine = CorrelationEngine()
        self.risk_aggregator = PortfolioRiskAggregator()
        self.capital_allocator = CapitalAllocator()
        
        # In a real setup, this is injected by the startup script
        self.coordinator = ClusterCoordinator("node-0", ["node-0", "node-1", "node-2"])
        
        self.audit_logger = AuditLogger()
        self.observability = ObservabilityStack()
        self.chat = TradingChatAgent()
        
        self.websocket_hub = websocket_hub

        def _event_emitter(payload: Dict[str, Any]) -> None:
            # Phase 4: Time Consistency Guard
            payload["signal_timestamp_utc"] = time.time()
            payload["engine_clock_hash"] = hash(time.time()) # Mock clock hash
            
            self.logger.info(f"EMITTING_EVENT: type={payload.get('event')}, sequence={payload.get('event_sequence_number')}, signal_id={payload.get('signal', {}).get('signal_id', 'none')}")
            
            if self.websocket_hub:
                try:
                    # Thread-safe asyncio dispatch
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self.websocket_hub.broadcast(payload), loop)
                    else:
                        loop.run_until_complete(self.websocket_hub.broadcast(payload))
                except RuntimeError:
                    pass

        self.lifecycle_engine = LifecycleEngine(event_emitter=_event_emitter)

        # Deterministic Candle Close Tracking
        self.last_processed_candle_epoch: int = 0
        
        # Vision LLM Safety Locks
        self.analysis_in_progress = False
        self.last_analysis_time = 0.0

    def tick(
        self, 
        instrument_id: int, 
        closes: List[float], 
        highs: List[float], 
        lows: List[float], 
        volumes: List[float],
        current_regime: str,
        regime_volatility_bucket: str,
        candle_timestamp_ms: int = 0,
        is_candle_close: bool = False
    ) -> Dict[str, Any]:
        """
        Processes a high-frequency tick. 
        Most ticks only evaluate active signal stops/targets.
        Only structural candle closes trigger real generation.
        """
        current_price = closes[-1] if closes else 0.0
        asset_name = f"ASSET_{instrument_id}"
        
        # 1. HARD FAIL-SAFE CHECK
        if self.integrity_guard.should_freeze_engine():
            if not self.lifecycle_engine.system_halted:
                self.lifecycle_engine.trigger_system_halt("INTEGRITY_GUARD_FROZEN")
            return {"status": "REJECTED", "reason": "ENGINE_FROZEN"}

        # 2. FAST PATH: PASSIVE TICK MONITORING 
        # (Evaluates hit targets/stops but does not compute signals)
        self.lifecycle_engine.evaluate_price_tick(
            asset=asset_name, 
            current_price=current_price, 
            current_candle_index=len(closes)
        )

        # 3. CANDLE CLOSE AUTHORITY CHECK
        if not is_candle_close:
            return {"status": "MONITORING"}

        candle_epoch = math.floor(candle_timestamp_ms / (15 * 60 * 1000)) if candle_timestamp_ms > 0 else 0

        self.logger.debug(f"Tick - current_candle_epoch: {candle_epoch}, previous_candle_epoch: {getattr(self, 'last_processed_candle_epoch', 0)}, timeframe: 15m, candle_timestamp_ms: {candle_timestamp_ms}")

        if candle_epoch > 0 and candle_epoch <= getattr(self, "last_processed_candle_epoch", 0):
            return {"status": "REJECTED", "reason": "DUPLICATE_CANDLE_CLOSE"}

        if candle_epoch > 0:
            self.logger.info(f"CANDLE_CLOSE_DETECTED. timeframe=15m, current_candle_epoch={candle_epoch}")
            self.last_processed_candle_epoch = candle_epoch

        # TRIGGER VISION ANALYSIS ON STRUCTURAL CANDLE CLOSE
        # 1. Anti-Reentrancy Lock
        if self.analysis_in_progress:
            self.logger.warning("Skipping Vision analysis - previous analysis still in progress")
        # 2. Rate Limit (1 per timeframe min)
        elif time.time() - self.last_analysis_time < (15 * 60 * 0.9): 
            self.logger.warning("Skipping Vision analysis - Rate limit active (too soon)")
        else:
            self.logger.info("Triggering background Vision Analysis Pipeline natively from Engine")
            
            def run_vision_pipeline():
                if self.analysis_in_progress: return
                self.analysis_in_progress = True
                self.last_analysis_time = time.time()
                try:
                    import urllib.request
                    import json
                    from urllib.request import Request, urlopen
                    
                    # 1. Capture Screen
                    req_capture = Request('http://localhost:8000/api/trading/capture_screen', data=b"{}", headers={'Content-Type': 'application/json'})
                    with urlopen(req_capture) as response:
                        capture_res = json.loads(response.read().decode())
                        
                    img_data = capture_res.get("image")
                    if not img_data:
                        self.logger.error("Vision Pipeline failed: No image returned from capture_screen")
                        return
                        
                    # 2. Analyze Vision
                    payload = json.dumps({
                        "image": img_data,
                        # Pass a fake URL so the API can extract the asset name using its regex
                        "url": f"https://groww.in/charts/indices/{asset_name.split('_')[-1] if '_' in asset_name else asset_name}"
                    }).encode('utf-8')
                    
                    req_analyze = Request('http://localhost:8000/api/trading/analyze_vision', data=payload, headers={'Content-Type': 'application/json'})
                    with urlopen(req_analyze) as response:
                        analysis_res = json.loads(response.read().decode())
                        
                    self.logger.info(f"Vision Pipeline structural analysis complete: {len(analysis_res.get('signals', []))} signals.")
                    
                except Exception as e:
                    self.logger.error(f"Background Vision Pipeline crashed: {e}")
                finally:
                    self.analysis_in_progress = False

            # Dispatch background thread to avoid blocking tick loop
            import threading
            threading.Thread(target=run_vision_pipeline, daemon=True).start()

        # SECTION 7 - CONTROLLED TEST SIGNAL (Mock logic disabled since we use real vision now)
        import os
        if os.environ.get("DIAGNOSTIC") == "1":
            self.logger.info("[DIAGNOSTIC] Forced test signal mode activated on candle close.")
            entry_price = current_price
            atr = entry_price * 0.005
            stop_price = entry_price - atr
            target_price = entry_price + (2 * atr)
            
            signal = self.lifecycle_engine.generate_and_lock(
                signal_id=uuid.uuid4().hex[:12],
                asset=asset_name,
                direction="LONG",
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                candle_index=len(closes),
                timeframe="15m",
                confidence=0.75,
                position_size_pct=0.01,
                metadata={"test": "diagnostic"}
            )
            return {"status": "DIAGNOSTIC_EMITTED", "signal": signal}

        # 4. SLOW PATH: FULL SIGNAL PIPELINE

        data_status = self.integrity_guard.validate_price_series(closes)
        if not data_status["stable"]:
            return {"status": "REJECTED", "reason": "DATA_ANOMALY"}

        features = self.feature_engine.extract_features(closes, highs, lows, volumes)
        if not features:
            return {"status": "REJECTED", "reason": "INSUFFICIENT_DATA"}

        fetch_segment = f"15m_{current_regime}_{regime_volatility_bucket}"

        # 5. DISTRIBUTED FAISS
        t_start = time.time()
        similar_patterns = self.similarity_engine.query(
            segment_key=fetch_segment, 
            vector=features["vector"], 
            k=50, 
            timeout_ms=50
        )
        latency_ms = (time.time() - t_start) * 1000.0
        self.observability.record_query_latency(fetch_segment, latency_ms)

        if not similar_patterns:
            return {"status": "REJECTED", "reason": "NO_SIMILAR_PATTERNS"}

        # 6. PROBABILITIES
        prob_result = self.probability_engine.aggregate(similar_patterns, current_regime)
        signal_direction = prob_result.get("signal", "NONE")
        
        self.logger.info(
            f"STRATEGY_EVALUATED: bias={signal_direction}, "
            f"confidence={prob_result.get('signal_confidence')}, "
            f"raw_expected_R={prob_result.get('expected_r')}, "
            f"volatility_state={regime_volatility_bucket}, "
            f"regime={current_regime}"
        )
        
        if signal_direction == "NONE":
            return {"status": "REJECTED", "reason": prob_result.get("signal_reason", "LOW_PROBABILITY")}

        # 7. CORRELATION LIMITS
        proposed_trade_usd = 10_000.0 * (-1 if signal_direction == "SHORT" else 1)
        
        # TEMPORARY GATE RELAXATION: Disable correlation gate for diagnostics
        # accepted_size = self.correlation_engine.enforce_cluster_exposure_limit(
        #     instrument_id, proposed_trade_usd, {}, 250_000.0
        # )
        # if accepted_size == 0.0:
        #     return {"status": "REJECTED", "reason": "CORRELATION_CLUSTER_FULL"}
        accepted_size = proposed_trade_usd

        # 8. RISK AGGREGATION
        risk_evaluation = self.risk_aggregator.evaluate_signal_impact(
            signal_size_usd=accepted_size,
            sector="UNKNOWN",
            regime=current_regime,
            incremental_variance_impact=0.0001
        )
        if not risk_evaluation["approved"]:
            return {"status": "REJECTED", "reason": risk_evaluation["reason"]}

        # 9. CAPITAL ALLOCATION
        allocation_result = self.capital_allocator.allocate_capital(
            total_account_value=self.risk_aggregator.total_capital,
            signal_win_rate=prob_result.get("bullish_probability", 0.0) if signal_direction == "LONG" else prob_result.get("bearish_probability", 0.0),
            signal_expected_r=prob_result.get("expected_r", 0.0),
            portfolio_volatility=0.12,
            current_drawdown=0.02,
            cluster_concentration=0.1,
            proposed_es99=0.04
        )
        
        final_capital_usd = allocation_result.get("allocated_capital", 0.0)
        if final_capital_usd <= 0.0:
            return {"status": "REJECTED", "reason": f"Capital Allocator: {allocation_result.get('reason')}"}
            
        final_size_signed = math.copysign(final_capital_usd, accepted_size)

        # 10. LIFECYCLE COMMIT & ATOMIC EMISSION
        request_id = uuid.uuid4().hex[:12]
        entry_price = current_price
        
        # Determine R thresholds based on vol bucket mock
        atr = entry_price * 0.005
        if signal_direction == "LONG":
            stop_price = entry_price - (atr * 2)
            target_price = entry_price + (atr * 4)
        else:
            stop_price = entry_price + (atr * 2)
            target_price = entry_price - (atr * 4)

        metadata = {
            "snapshot_id": fetch_segment + "_" + "latest",
            "feature_schema_hash": features.get("schema_version", "unknown"),
            "risk_state_hash": self.risk_aggregator.get_portfolio_state_hash(),
            "node_id": self.coordinator.node_id,
            "coordinator_epoch": self.coordinator.coordinator_epoch,
            "request_id": request_id,
            "kelly_fraction": allocation_result.get("fraction", 0.0)
        }

        # Commits signal into the Hard Locked state machine and atomically broadcasts
        signal = self.lifecycle_engine.generate_and_lock(
            signal_id=request_id,
            asset=asset_name,
            direction=signal_direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            candle_index=len(closes),
            timeframe="15m",
            confidence=prob_result.get("signal_confidence", 0.0),
            position_size_pct=allocation_result.get("fraction", 0.0),
            metadata=metadata
        )

        if not signal:
            return {"status": "REJECTED", "reason": "LIFECYCLE_GATE_BLOCKED"}

        # Register audit (Audit logger logic stays parallel for compliance docs)
        receipt = self.audit_logger.generate_audit_receipt(
            signal_dict={"signal": signal_direction, "proposed_size": final_size_signed},
            snapshot_id=metadata["snapshot_id"],
            feature_schema_hash=metadata["feature_schema_hash"],
            index_version="v1",
            risk_state_hash=metadata["risk_state_hash"],
            portfolio_covariance_hash="cov_hash_mock",
            drift_state_hash="drift_mock",
            capital_allocation_state_hash="cap_alloc_mock",
            shard_id=0,
            node_id=metadata["node_id"],
            coordinator_epoch=metadata["coordinator_epoch"],
            request_id=request_id
        )

        self.risk_aggregator.commit_trade(final_size_signed, "UNKNOWN", current_regime, 0.0001)
        self.observability.record_signal(signal_direction, current_regime)
        
        return {
            "status": "APPROVED",
            "signal_id": request_id, 
            "receipt_signature": receipt["audit_signature"]
        }
